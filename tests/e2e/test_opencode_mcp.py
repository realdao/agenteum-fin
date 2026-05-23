"""E2E test: verify opencode can connect to Agenteum Fin and invoke MCP tools."""

from __future__ import annotations

import json
import os
import signal
import socket
import subprocess
import time
from pathlib import Path
from typing import Any

import pytest

SERVER_PORT = 8766
SERVER_START_TIMEOUT = 15.0
OPENCODE_TIMEOUT = 120.0
PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _find_uv() -> str:
    import shutil

    uv = shutil.which("uv")
    if uv is None:
        pytest.skip("uv not found in PATH")
    return uv


def _find_opencode() -> str:
    import shutil

    opencode = shutil.which("opencode")
    if opencode is None:
        pytest.skip("opencode not found in PATH")
    return opencode


def _port_is_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        return sock.connect_ex(("127.0.0.1", port)) != 0


def _wait_for_server(proc: subprocess.Popen, timeout: float = SERVER_START_TIMEOUT) -> None:
    start = time.time()
    while time.time() - start < timeout:
        if proc.poll() is not None:
            stdout = proc.stdout.read() if proc.stdout else ""
            stderr = proc.stderr.read() if proc.stderr else ""
            raise RuntimeError(
                f"Server exited early (code={proc.returncode}).\n"
                f"stdout: {stdout}\nstderr: {stderr}"
            )
        if not _port_is_free(SERVER_PORT):
            return
        time.sleep(0.2)
    raise RuntimeError(f"Agenteum Fin did not open port {SERVER_PORT} in time.")


def _run_opencode(cmd_args: list[str], timeout: float = OPENCODE_TIMEOUT) -> tuple[str, str, int]:
    result = subprocess.run(
        [_find_opencode(), "--pure", *cmd_args],
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=str(PROJECT_ROOT),
    )
    return result.stdout, result.stderr, result.returncode


def _parse_opencode_json_events(raw: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for line in raw.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return events


def _find_tool_use_event(
    events: list[dict[str, Any]],
    tool_name_substring: str,
) -> dict[str, Any] | None:
    for event in events:
        if event.get("type") != "tool_use":
            continue
        part = event.get("part", {})
        tool = part.get("tool", "")
        if tool_name_substring in tool:
            return event
    return None


def _terminate_process_tree(proc: subprocess.Popen) -> None:
    if proc.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
            capture_output=True,
            text=True,
        )
        try:
            proc.wait(timeout=5.0)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
        return

    proc.send_signal(signal.SIGTERM)
    try:
        proc.wait(timeout=5.0)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()


@pytest.fixture(scope="module")
def server() -> subprocess.Popen:
    if not _port_is_free(SERVER_PORT):
        pytest.skip(f"port {SERVER_PORT} is already in use")

    uv = _find_uv()
    proc = subprocess.Popen(
        [uv, "run", "agenteum-fin"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=str(PROJECT_ROOT),
        env={
            **dict(os.environ),
            "AGENTEUM_HOST": "127.0.0.1",
            "AGENTEUM_PORT": str(SERVER_PORT),
            "AGENTEUM_ALLOW_REMOTE": "false",
        },
    )
    try:
        _wait_for_server(proc)
        yield proc
    finally:
        _terminate_process_tree(proc)


def test_mcp_list_shows_agenteum_fin_when_user_configured(server: subprocess.Popen) -> None:
    stdout, stderr, rc = _run_opencode(["mcp", "list"])
    combined = stdout + stderr

    assert rc == 0, f"opencode mcp list exited with {rc}. Output:\n{combined}"
    if "agenteum-fin" not in combined:
        pytest.skip(
            "opencode is not configured with agenteum-fin MCP; "
            "user config is not modified by tests"
        )
    assert "connected" in combined.lower(), f"agenteum-fin not connected. Output:\n{combined}"


def test_stock_profile_tool_is_called_via_agenteum_fin(server: subprocess.Popen) -> None:
    stdout, stderr, rc = _run_opencode(["mcp", "list"])
    combined = stdout + stderr
    assert rc == 0, f"opencode mcp list exited with {rc}. Output:\n{combined}"
    if "agenteum-fin" not in combined:
        pytest.skip(
            "opencode is not configured with agenteum-fin MCP; "
            "user config is not modified by tests"
        )

    prompt = "请通过 agenteum-fin 查询 600519 的 stock_profile，只需要调用工具并返回结果摘要"
    stdout, stderr, rc = _run_opencode(
        ["run", "--format", "json", "--dangerously-skip-permissions", prompt]
    )
    assert rc == 0, f"opencode run exited with {rc}. stdout:\n{stdout}\nstderr:\n{stderr}"

    events = _parse_opencode_json_events(stdout)
    assert events, f"No JSON events parsed from stdout. stdout:\n{stdout}\nstderr:\n{stderr}"

    tool_event = _find_tool_use_event(events, "stock_profile")
    assert tool_event is not None, (
        "No stock_profile tool_use event found. Events:\n"
        + json.dumps(events, indent=2, ensure_ascii=False)
    )

    tool_input = tool_event.get("part", {}).get("state", {}).get("input", {})
    assert tool_input.get("symbol") in {"600519", "SH600519", "600519.SH"}

"""E2E test: verify Claude Code can connect to Agenteum Fin and invoke MCP tools."""

from __future__ import annotations

import json
import os
import shutil
import signal
import socket
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any

import pytest

SERVER_PORT = 8766
SERVER_START_TIMEOUT = 15.0
CLAUDE_TIMEOUT = 180.0
PROJECT_ROOT = Path(__file__).resolve().parents[2]
E2E_TMP_ROOT = PROJECT_ROOT / ".tmp-claude-code-e2e"


def _find_uv() -> str:
    import shutil

    uv = shutil.which("uv")
    if uv is None:
        pytest.skip("uv not found in PATH")
    return uv


def _find_claude() -> str:
    import shutil

    claude = shutil.which("claude")
    if claude is None:
        pytest.skip("claude not found in PATH")
    return claude


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


def _write_mcp_config(path: Path) -> Path:
    config = {
        "mcpServers": {
            "agenteum-fin": {
                "type": "http",
                "url": f"http://127.0.0.1:{SERVER_PORT}/mcp/full",
            }
        }
    }
    path.write_text(json.dumps(config), encoding="utf-8")
    return path


def _run_claude(
    prompt: str,
    *,
    mcp_config: Path,
    env: dict[str, str] | None = None,
    timeout: float = CLAUDE_TIMEOUT,
) -> tuple[str, str, int]:
    result = subprocess.run(
        [
            _find_claude(),
            "--bare",
            "--mcp-config",
            str(mcp_config),
            "--strict-mcp-config",
            "--permission-mode",
            "bypassPermissions",
            "--output-format",
            "stream-json",
            "--verbose",
            "-p",
            prompt,
        ],
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=str(PROJECT_ROOT),
        env=env,
    )
    return result.stdout, result.stderr, result.returncode


def _parse_claude_json_events(raw: str) -> list[dict[str, Any]]:
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
        if event.get("type") != "assistant":
            continue
        message = event.get("message", {})
        for item in message.get("content", []):
            if item.get("type") != "tool_use":
                continue
            name = item.get("name", "")
            if tool_name_substring in name:
                return item
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


def _write_fake_opencli(directory: Path) -> Path:
    script = directory / "fake_opencli.py"
    script.write_text(
        "\n".join(
            [
                "import json",
                "import os",
                "import sys",
                "from pathlib import Path",
                "log_dir = Path(os.environ['AGENTEUM_FIN_FAKE_OPENCLI_LOG_DIR'])",
                "log_dir.mkdir(parents=True, exist_ok=True)",
                "path = log_dir / f'{os.getpid()}.json'",
                "path.write_text(json.dumps(sys.argv[1:], ensure_ascii=False), encoding='utf-8')",
                "print('[]')",
            ]
        ),
        encoding="utf-8",
    )
    script.chmod(0o755)
    return script


@pytest.fixture
def claude_tmp_path() -> Path:
    path = E2E_TMP_ROOT / uuid.uuid4().hex
    path.mkdir(parents=True)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


@pytest.fixture(scope="module")
def claude_e2e_dir() -> Path:
    path = E2E_TMP_ROOT / uuid.uuid4().hex
    path.mkdir(parents=True)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


@pytest.fixture(scope="module")
def server(claude_e2e_dir: Path) -> subprocess.Popen:
    if not _port_is_free(SERVER_PORT):
        pytest.skip(f"port {SERVER_PORT} is already in use")

    uv = _find_uv()
    fake_opencli = _write_fake_opencli(claude_e2e_dir)
    log_dir = claude_e2e_dir / "opencli-calls"
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
            "AGENTEUM_FIN_FAKE_OPENCLI_LOG_DIR": str(log_dir),
            "AGENTEUM_FIN_OPENCLI_COMMAND": f"python {fake_opencli}",
        },
    )
    try:
        _wait_for_server(proc)
        yield proc
    finally:
        _terminate_process_tree(proc)


def test_stock_profile_tool_is_called_via_claude_code(
    server: subprocess.Popen,
    claude_tmp_path: Path,
) -> None:
    mcp_config = _write_mcp_config(claude_tmp_path / "mcp.json")
    prompt = "请通过 agenteum-fin 查询 600519 的 stock_profile，只需要调用工具并返回结果摘要"

    stdout, stderr, rc = _run_claude(prompt, mcp_config=mcp_config)

    assert rc == 0, f"claude exited with {rc}. stdout:\n{stdout}\nstderr:\n{stderr}"
    events = _parse_claude_json_events(stdout)
    assert events, f"No JSON events parsed from stdout. stdout:\n{stdout}\nstderr:\n{stderr}"

    tool_event = _find_tool_use_event(events, "stock_profile")
    assert tool_event is not None, (
        "No stock_profile tool_use event found. Events:\n"
        + json.dumps(events, indent=2, ensure_ascii=False)
    )

    tool_input = tool_event.get("input", {})
    assert tool_input.get("symbol") in {"600519", "SH600519", "600519.SH"}


def test_stock_news_hk_xueqiu_symbol_is_called_via_claude_code(
    server: subprocess.Popen,
    claude_tmp_path: Path,
    claude_e2e_dir: Path,
) -> None:
    mcp_config = _write_mcp_config(claude_tmp_path / "mcp.json")
    log_dir = claude_e2e_dir / "opencli-calls"
    shutil.rmtree(log_dir, ignore_errors=True)

    prompt = "请通过 agenteum-fin 查询 00700 的 stock_news，time_range 用 d，只需要调用工具"
    stdout, stderr, rc = _run_claude(prompt, mcp_config=mcp_config)

    assert rc == 0, f"claude exited with {rc}. stdout:\n{stdout}\nstderr:\n{stderr}"

    events = _parse_claude_json_events(stdout)
    assert events, f"No JSON events parsed from stdout. stdout:\n{stdout}\nstderr:\n{stderr}"

    tool_event = _find_tool_use_event(events, "stock_news")
    assert tool_event is not None, (
        "No stock_news tool_use event found. Events:\n"
        + json.dumps(events, indent=2, ensure_ascii=False)
    )

    tool_input = tool_event.get("input", {})
    assert tool_input.get("symbol") in {"00700", "HK00700", "00700.HK"}
    assert tool_input.get("time_range") == "d"

    assert log_dir.exists(), "fake opencli was not called"
    calls = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in log_dir.glob("*.json")
    ]
    assert ["xueqiu", "comments", "00700", "-f", "json"] in calls

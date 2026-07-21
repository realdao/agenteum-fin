from __future__ import annotations

from importlib.resources import files

RESOURCE_URIS = {
    "agenteum-fin://tools/stock-tools-guide": "stock-tools-guide.md",
    "agenteum-fin://tools/iwencai-query-guide": "iwencai-query-guide.md",
    "agenteum-fin://providers/capabilities": "providers-capabilities.md",
}


def load_resource_text(filename: str) -> str:
    return files("src.resources").joinpath(filename).read_text(encoding="utf-8")


def resource_text_by_uri(uri: str) -> str:
    return load_resource_text(RESOURCE_URIS[uri])

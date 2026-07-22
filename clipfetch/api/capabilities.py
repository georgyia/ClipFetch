"""Optional-dependency capability matrix for the API.

Reports which optional ClipFetch features are usable in this environment, so the UI can adapt
without hiding *why* something is unavailable. Detection uses :func:`importlib.util.find_spec` and
never imports the heavy modules themselves.
"""

from __future__ import annotations

from importlib.util import find_spec
from typing import Any

# Capability name -> the import that its optional extra provides.
_CAPABILITIES = {
    "semantic_search": "fastembed",
    "transcription": "faster_whisper",
    "duplicate_analysis": "av",
    "cookie_import": "cryptography",
}


def _is_available(module: str) -> bool:
    try:
        return find_spec(module) is not None
    except (ImportError, ValueError):
        return False


def capability_matrix() -> dict[str, dict[str, Any]]:
    """Return ``{capability: {"available": bool, "reason"?: str}}`` for each optional feature."""
    matrix: dict[str, dict[str, Any]] = {}
    for name, module in _CAPABILITIES.items():
        available = _is_available(module)
        entry: dict[str, Any] = {"available": available}
        if not available:
            entry["reason"] = "dependency_missing"
        matrix[name] = entry
    return matrix

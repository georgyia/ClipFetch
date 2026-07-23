"""Sandboxed directory browser for the onboarding "add a library" flow.

The browser can't read server-side paths, so onboarding needs a way to navigate the machine and pick
a library folder. This exposes **only directory names**, sandboxed to the user's home directory:
never file contents, never a path outside home, and traversal (``..``, absolute escapes, symlinks
out) is rejected. It is a deliberate, bounded exception to the "no filesystem paths to the client"
rule — the whole point is to let the single, local user choose their own folder over loopback.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


class FsError(ValueError):
    """A rejected or invalid browse request, safe to show the user."""


def _root() -> Path:
    """The sandbox boundary. Overridden in tests."""
    return Path.home().resolve()


def _within_root(target: Path, root: Path) -> bool:
    return target == root or root in target.parents


def browse(path: str | None) -> dict[str, Any]:
    """List the immediate subdirectories of ``path`` (default: home), within the home sandbox.

    Returns the current directory, its parent (``None`` at the sandbox root), and directory entries
    each flagged with whether it already looks like a ClipFetch library.
    """
    root = _root()
    target = Path(path).resolve() if path else root
    if not _within_root(target, root):
        raise FsError("That location is outside the allowed area.")
    if not target.is_dir():
        raise FsError("That path is not a directory.")

    entries = []
    try:
        for child in sorted(target.iterdir(), key=lambda p: p.name.lower()):
            if child.name.startswith(".") or not child.is_dir():
                continue  # directories only; skip dotfolders and all files
            entries.append(
                {
                    "name": child.name,
                    "path": str(child),
                    "is_library": (child / ".clipfetch" / "catalog.sqlite3").is_file(),
                }
            )
    except PermissionError:
        entries = []

    at_root = target == root
    return {
        "cwd": str(target),
        "parent": None if at_root else str(target.parent),
        "at_root": at_root,
        "entries": entries,
    }

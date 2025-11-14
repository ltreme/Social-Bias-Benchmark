"""Utilities for analysis scripts and notebooks."""

from __future__ import annotations

import sys
from pathlib import Path


def _discover_project_root(start: Path) -> Path | None:
    """Find repo root by locating a directory that contains 'apps'.

    When the package is installed in site-packages, searching only relative to
    the package path will fail. This helper also tries from the current working
    directory to support notebooks/scripts executed from the repo.
    """
    # 1) Walk up from the package path
    for candidate in start.parents:
        if (candidate / "apps").is_dir():
            return candidate
    # 2) Walk up from CWD (e.g., notebooks launched from repo)
    cwd = Path.cwd()
    for candidate in (cwd, *cwd.parents):
        if (candidate / "apps").is_dir():
            return candidate
    return None


_PACKAGE_ROOT = Path(__file__).resolve().parent
_PROJECT_ROOT = _discover_project_root(_PACKAGE_ROOT) or Path.cwd()

if _PROJECT_ROOT != _PACKAGE_ROOT:
    _SRC_ROOTS = [
        _PROJECT_ROOT / "apps" / "backend" / "src",
    ]
    for _path in _SRC_ROOTS:
        if _path.exists():
            _str_path = str(_path)
            if _str_path not in sys.path:
                sys.path.append(_str_path)


def get_project_root() -> Path:
    """Return repository root for relative paths."""
    return _PROJECT_ROOT

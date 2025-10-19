"""Utilities for analysis scripts and notebooks."""
from __future__ import annotations

import sys
from pathlib import Path


def _discover_project_root(start: Path) -> Path | None:
    for candidate in start.parents:
        if (candidate / "apps").is_dir():
            return candidate
    return None


_PACKAGE_ROOT = Path(__file__).resolve().parent
_PROJECT_ROOT = _discover_project_root(_PACKAGE_ROOT) or _PACKAGE_ROOT

if _PROJECT_ROOT != _PACKAGE_ROOT:
    _SRC_ROOTS = [
        _PROJECT_ROOT / "apps" / "shared" / "src",
        _PROJECT_ROOT / "apps" / "benchmark" / "src",
        _PROJECT_ROOT / "apps" / "persona_generator" / "src",
    ]
    for _path in _SRC_ROOTS:
        if _path.exists():
            _str_path = str(_path)
            if _str_path not in sys.path:
                sys.path.append(_str_path)


def get_project_root() -> Path:
    """Return repository root for relative paths."""
    return _PROJECT_ROOT

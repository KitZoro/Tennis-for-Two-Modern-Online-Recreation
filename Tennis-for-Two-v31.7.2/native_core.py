"""Optional native helper layer for Tennis for Two.

The game remains fully playable in pure Python.  When the bundled C helper is
available and passes its startup self-test, deterministic helper operations can
use it.  If anything is missing or mismatched, Python is used automatically.
"""
from __future__ import annotations

import ctypes
import os
from pathlib import Path

CORE_ABI_VERSION = 1
_ROOT = Path(__file__).resolve().parent
_ENGINE = _ROOT / "engine"


def _python_shot_error(frame: int, side: int, score1: int, score2: int, power: int) -> float:
    if power <= 100:
        return 0.0
    error_range = (power - 100) * 0.125
    seed = (
        int(frame) * 1103515245
        + int(side) * 12345
        + int(score1) * 97
        + int(score2) * 193
    ) & 0x7FFFFFFF
    normalized = ((seed % 2001) / 1000.0) - 1.0
    return normalized * error_range


def _candidate_paths() -> list[Path]:
    if os.name == "nt":
        return [_ENGINE / "tennis_core.dll"]
    if os.uname().sysname == "Darwin":
        return [_ENGINE / "libtennis_core.dylib"]
    return [_ENGINE / "libtennis_core.so"]


_lib = None
_status = "pure-python fallback"
for _path in _candidate_paths():
    if not _path.exists():
        continue
    try:
        candidate = ctypes.CDLL(str(_path))
        candidate.tft_core_version.argtypes = []
        candidate.tft_core_version.restype = ctypes.c_int
        candidate.tft_deterministic_shot_error.argtypes = [
            ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int
        ]
        candidate.tft_deterministic_shot_error.restype = ctypes.c_double
        if candidate.tft_core_version() != CORE_ABI_VERSION:
            _status = f"native ABI mismatch ({candidate.tft_core_version()} != {CORE_ABI_VERSION})"
            continue

        # Cross-check the native helper against the canonical Python formula.
        tests = [
            (0, 1, 0, 0, 100),
            (1, 1, 0, 0, 110),
            (431, 2, 3, 2, 125),
            (9999, 1, 9, 10, 150),
        ]
        if any(abs(candidate.tft_deterministic_shot_error(*t) - _python_shot_error(*t)) > 1e-12 for t in tests):
            _status = "native self-test failed; using Python"
            continue
        _lib = candidate
        _status = f"native C core v{CORE_ABI_VERSION}"
        break
    except (OSError, AttributeError, ValueError) as exc:
        _status = f"native unavailable ({exc}); using Python"


def status() -> str:
    return _status


def using_native() -> bool:
    return _lib is not None


def deterministic_shot_error(frame: int, side: int, score1: int, score2: int, power: int) -> float:
    if _lib is not None:
        return float(_lib.tft_deterministic_shot_error(frame, side, score1, score2, power))
    return _python_shot_error(frame, side, score1, score2, power)

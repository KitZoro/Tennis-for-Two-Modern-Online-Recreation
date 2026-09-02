# Tennis for Two v31.4 — Hybrid Python + C + Shell

This build deliberately uses three languages, with one responsibility each.

## Python — the editable game
Python/Pygame remains responsible for gameplay orchestration, Story Mode,
Edwin/Kit drawing, UI, audio, saves, networking, and rollback logic.  This is
the layer that should stay easy to edit.

## C — the deterministic helper core
`engine/tennis_core.c` is a small native helper rather than a rewrite.  It
currently implements deterministic shot-error math and an input-packing helper.
Python loads it through `ctypes` only after an ABI check and a self-test against
the canonical Python implementation.  If the library is absent or fails the
self-test, the game automatically falls back to pure Python.

That makes the C layer safe to expand gradually instead of putting the whole
game at risk in one rewrite.

## Shell — Linux build, launch, diagnostics
- `run_linux.sh` builds the C helper when needed, reports which core is active,
  then launches the game.
- `build_native.sh` builds only the optional C helper.
- `diagnose_linux.sh` checks Python, Pygame, the compiler, C loading, and Python
  syntax.

## Networking compatibility
The rollback simulation fingerprint now covers `game.py`, `rollback.py`,
`native_core.py`, and the C source/header.  Gameplay-source changes therefore
cannot silently connect as if they were the same simulation build.

## Why this approach
The project does **not** become easier merely by having more languages.  It
becomes easier when language boundaries are stable.  This version keeps story
and presentation flexible in Python, infrastructure in shell, and creates a
small verified C boundary that can later absorb genuinely performance-sensitive
simulation work.

## Windows compatibility (v31.4.1)

Windows now has `build_native_windows.bat`, a robust `run_windows.bat`, and
`diagnose_windows.bat`. The launcher detects `py`, `python`, or `python3`,
checks/installs Python dependencies, and builds `engine/tennis_core.dll` with
GCC, Clang, or MSVC when available. No compiler is required to play because
`native_core.py` retains the deterministic Python fallback.

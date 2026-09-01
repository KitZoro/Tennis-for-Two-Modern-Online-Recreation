#!/usr/bin/env bash
set -u
cd "$(dirname "$0")"

echo "=== Tennis for Two v31.4 diagnostics ==="
printf "Python: "; python3 --version 2>&1 || true
printf "Compiler: "; if command -v cc >/dev/null 2>&1; then cc --version | head -1; else echo "not installed (optional)"; fi
printf "Pygame: "; python3 - <<'PY'
try:
 import pygame; print(pygame.version.ver)
except Exception as exc: print("ERROR:", exc)
PY
./build_native.sh || true
python3 - <<'PY'
import native_core
print("Native helper:", native_core.status())
PY
python3 -m py_compile main.py game.py rollback.py network.py story.py ui.py native_core.py && echo "Python syntax: OK"
echo "========================================"

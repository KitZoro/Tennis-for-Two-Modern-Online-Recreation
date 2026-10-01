#!/usr/bin/env bash
set -u
cd "$(dirname "$0")"

SRC="engine/tennis_core.c"
OUT="engine/libtennis_core.so"

if ! command -v cc >/dev/null 2>&1; then
  echo "[TFT] No C compiler found. The game will use the pure-Python fallback."
  exit 0
fi

echo "[TFT] Building optional native C core..."
if cc -O2 -std=c11 -fPIC -shared -Wall -Wextra -Wpedantic "$SRC" -o "$OUT"; then
  echo "[TFT] Native core built: $OUT"
else
  echo "[TFT] Native build failed. The game can still run with the Python fallback."
  rm -f "$OUT"
  exit 0
fi

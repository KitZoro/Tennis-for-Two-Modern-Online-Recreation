#!/usr/bin/env bash
set -u
cd "$(dirname "$0")"

echo "Starting Tennis for Two v31.4 Hybrid"

# Build the optional C helper when possible.  This never blocks the Python game.
if [ ! -f engine/libtennis_core.so ] || [ engine/tennis_core.c -nt engine/libtennis_core.so ]; then
  ./build_native.sh || true
fi

python3 - <<'PY'
try:
    import native_core
    print("[TFT] Core:", native_core.status())
except Exception as exc:
    print("[TFT] Native-core status check failed; continuing in Python:", exc)
PY

exec python3 main.py

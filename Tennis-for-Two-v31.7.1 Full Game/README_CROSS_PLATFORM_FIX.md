# v31.4.2 Cross-platform compatibility fix

This patch fixes false online incompatibility errors between Windows and Linux.

## Root cause
The simulation fingerprint used Python `ast.dump()`. The AST representation can differ between Python interpreter versions, even when the source files are identical. A Linux player on Python 3.12 and a Windows player on another Python release could therefore be rejected with `Incompatible gameplay build: deterministic simulation differs`.

## Fix
The compatibility fingerprint now hashes normalized gameplay source bytes. CRLF/LF line endings and UTF-8 BOMs are normalized, making the result stable across Windows, Linux, and Python versions. `config.py` is now included because gameplay constants affect deterministic simulation.

Both players should use this exact v31.4.2 folder/ZIP for online testing.

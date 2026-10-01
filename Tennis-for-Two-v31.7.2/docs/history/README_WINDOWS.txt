TENNIS FOR TWO v31.5 - WINDOWS NOTES

Normal Windows launch:
    Double-click run_windows.bat

The launcher will:
1. Find Python 3 using py, python, or python3.
2. Verify Python is new enough.
3. Install pygame and cryptography if they are missing.
4. Try to build engine\tennis_core.dll if GCC, Clang, or MSVC is available.
5. If no C compiler/DLL is available, safely use the Python deterministic fallback.
6. Start main.py.

You do NOT need a C compiler just to play the source build.
The C core is optional.

For troubleshooting, double-click:
    diagnose_windows.bat

This is still a SOURCE build. A future packaged Windows .exe can remove the
need for players to install Python at all.

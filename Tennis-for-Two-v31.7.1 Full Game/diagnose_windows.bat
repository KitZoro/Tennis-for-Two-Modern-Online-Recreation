@echo off
setlocal EnableExtensions
cd /d "%~dp0"
echo =============================================
echo Tennis for Two - Windows Diagnostics
echo =============================================

set "PYEXE="
where py >nul 2>nul && set "PYEXE=py -3"
if not defined PYEXE where python >nul 2>nul && set "PYEXE=python"
if not defined PYEXE where python3 >nul 2>nul && set "PYEXE=python3"

if not defined PYEXE (
    echo [FAIL] Python 3 not found.
    goto :end
)

echo [OK] Python command: %PYEXE%
%PYEXE% --version
%PYEXE% -c "import sys; print('[INFO] executable:', sys.executable); print('[INFO] platform:', sys.platform); print('[INFO] bits:', 64 if sys.maxsize ^> 2**32 else 32)"

%PYEXE% -c "import pygame; print('[OK] pygame', pygame.version.ver)" 2>nul || echo [FAIL] pygame missing
%PYEXE% -c "import cryptography; print('[OK] cryptography', cryptography.__version__)" 2>nul || echo [FAIL] cryptography missing
%PYEXE% -c "import native_core; print('[OK] native_core:', native_core.status())" 2>nul || echo [FAIL] native_core import failed
%PYEXE% -c "import rollback; print('[OK] Simulation fingerprint:', rollback.SIMULATION_FINGERPRINT)"

if exist "engine\tennis_core.dll" (
    echo [OK] engine\tennis_core.dll exists
) else (
    echo [INFO] No Windows DLL. Python fallback will be used.
)

where gcc >nul 2>nul && echo [OK] GCC found || echo [INFO] GCC not found
where clang >nul 2>nul && echo [OK] Clang found || echo [INFO] Clang not found
where cl >nul 2>nul && echo [OK] MSVC cl found || echo [INFO] MSVC cl not found

%PYEXE% -m py_compile main.py game.py rollback.py network.py story.py ui.py native_core.py
if errorlevel 1 (echo [FAIL] Python syntax check) else echo [OK] Python syntax check

:end
echo =============================================
pause

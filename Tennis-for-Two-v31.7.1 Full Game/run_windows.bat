@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Tennis for Two v31.4.1

echo Starting Tennis for Two v31.4.1 - Windows Compatible

set "PYEXE="
where py >nul 2>nul
if %errorlevel%==0 set "PYEXE=py -3"
if defined PYEXE goto :python_found

where python >nul 2>nul
if %errorlevel%==0 set "PYEXE=python"
if defined PYEXE goto :python_found

where python3 >nul 2>nul
if %errorlevel%==0 set "PYEXE=python3"
if defined PYEXE goto :python_found

echo.
echo [TFT] Python 3 was not found.
echo Install Python 3.12 or newer from python.org, enable "Add Python to PATH",
echo then run this file again.
pause
exit /b 1

:python_found
echo [TFT] Python: %PYEXE%

%PYEXE% -c "import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)"
if errorlevel 1 (
    echo [TFT] Python 3.10 or newer is required.
    pause
    exit /b 1
)

%PYEXE% -c "import pygame, cryptography" >nul 2>nul
if errorlevel 1 (
    echo [TFT] Installing missing Python requirements...
    %PYEXE% -m pip install --user -r requirements.txt
    if errorlevel 1 (
        echo.
        echo [TFT] Dependency installation failed.
        echo Try: %PYEXE% -m pip install --user -r requirements.txt
        pause
        exit /b 1
    )
)

if not exist "engine\tennis_core.dll" call build_native_windows.bat

%PYEXE% -c "import native_core; print('[TFT] Core:', native_core.status())"
if errorlevel 1 echo [TFT] Native-core check failed; continuing with Python fallback.

echo.
%PYEXE% main.py
set "GAME_EXIT=%errorlevel%"

if not "%GAME_EXIT%"=="0" (
    echo.
    echo [TFT] Game exited with code %GAME_EXIT%.
    echo Run diagnose_windows.bat for a system check.
    pause
)
exit /b %GAME_EXIT%

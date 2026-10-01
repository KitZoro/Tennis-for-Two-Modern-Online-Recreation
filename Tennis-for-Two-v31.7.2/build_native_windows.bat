@echo off
setlocal
cd /d "%~dp0"

set "SRC=engine\tennis_core.c"
set "OUT=engine\tennis_core.dll"

where gcc >nul 2>nul
if %errorlevel%==0 (
    echo [TFT] Building optional native C core with GCC...
    gcc -O2 -std=c11 -shared -Wall -Wextra "%SRC%" -o "%OUT%"
    if exist "%OUT%" (
        echo [TFT] Native Windows core built: %OUT%
        exit /b 0
    )
)

where clang >nul 2>nul
if %errorlevel%==0 (
    echo [TFT] Building optional native C core with Clang...
    clang -O2 -std=c11 -shared "%SRC%" -o "%OUT%"
    if exist "%OUT%" (
        echo [TFT] Native Windows core built: %OUT%
        exit /b 0
    )
)

where cl >nul 2>nul
if %errorlevel%==0 (
    echo [TFT] Building optional native C core with MSVC...
    cl /nologo /O2 /LD "%SRC%" /link /OUT:"%OUT%"
    if exist "%OUT%" (
        echo [TFT] Native Windows core built: %OUT%
        del /q tennis_core.obj tennis_core.lib tennis_core.exp 2>nul
        exit /b 0
    )
)

echo [TFT] No supported C compiler found. That is OK.
echo [TFT] The game will use the deterministic Python fallback.
exit /b 0

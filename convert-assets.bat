@echo off
setlocal
cd /d "%~dp0"

set /p "ASSET_NAME=Asset name: "
if "%ASSET_NAME%"=="" (
    echo ERROR: Asset name is required.
    pause
    exit /b 1
)

call :find_python
if errorlevel 1 exit /b 1

%PYTHON% tools\convert_assets.py --name "%ASSET_NAME%"
if errorlevel 1 (
    echo.
    echo SharpBit conversion failed.
    pause
    exit /b 1
)

echo.
echo SharpBit conversion complete.
pause
exit /b 0

:find_python
where py >nul 2>nul
if not errorlevel 1 (
    set "PYTHON=py -3"
    exit /b 0
)
where python >nul 2>nul
if not errorlevel 1 (
    set "PYTHON=python"
    exit /b 0
)
echo ERROR: Python was not found.
pause
exit /b 1

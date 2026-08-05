@echo off
setlocal
cd /d "%~dp0"

python tools\convert_assets.py
if errorlevel 1 (
    echo.
    echo SharpBit conversion failed.
    exit /b 1
)

echo.
echo SharpBit conversion complete.

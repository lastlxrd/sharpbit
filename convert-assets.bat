@echo off
setlocal
cd /d "%~dp0"
python tools\convert_assets.py
if errorlevel 1 (
    echo.
    echo Conversion failed.
    exit /b 1
)
echo.
echo Conversion complete.

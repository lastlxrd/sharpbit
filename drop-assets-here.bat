@echo off
setlocal
cd /d "%~dp0"

if "%~1"=="" (
    echo Drag and drop one or more files or folders onto this file.
    echo.
    echo Supported:
    echo   PNG, JPG, JPEG, BMP, WebP, GIF
    echo   MP4, MOV, AVI, MKV, WEBM
    echo.
    echo Results:
    echo   output\generated
    echo   output\preview
    pause
    exit /b 1
)

set "ARGS="
:collect
if "%~1"=="" goto run
set "ARGS=%ARGS% "%~f1""
shift
goto collect

:run
python tools\convert_assets.py %ARGS%
if errorlevel 1 (
    echo.
    echo SharpBit conversion failed.
    pause
    exit /b 1
)

echo.
echo SharpBit conversion complete.
echo Results:
echo   output\generated
echo   output\preview
pause

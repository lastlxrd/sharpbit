@echo off
setlocal
cd /d "%~dp0"

if "%~1"=="" (
    echo Drag images, GIFs, videos, or folders onto this file.
    pause
    exit /b 1
)

set /p "ASSET_NAME=Asset name: "
if "%ASSET_NAME%"=="" (
    echo ERROR: Asset name is required.
    pause
    exit /b 1
)

where py >nul 2>nul
if not errorlevel 1 (
    set "PYTHON=py -3"
    goto python_found
)
where python >nul 2>nul
if not errorlevel 1 (
    set "PYTHON=python"
    goto python_found
)
echo ERROR: Python was not found.
pause
exit /b 1

:python_found
set "ARGS="
:collect
if "%~1"=="" goto run
set "ARGS=%ARGS% "%~f1""
shift
goto collect

:run
%PYTHON% tools\convert_assets.py --name "%ASSET_NAME%" %ARGS%
if errorlevel 1 (
    echo.
    echo SharpBit conversion failed.
    pause
    exit /b 1
)

echo.
echo SharpBit conversion complete.
pause

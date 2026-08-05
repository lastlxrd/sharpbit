@echo off
setlocal
cd /d "%~dp0"

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
echo Install Python 3 and enable "Add Python to PATH".
pause
exit /b 1

:python_found
%PYTHON% -m pip install --upgrade pip
%PYTHON% -m pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo Installation failed.
    pause
    exit /b 1
)

echo.
echo SharpBit dependencies installed successfully.
pause

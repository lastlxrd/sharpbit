@echo off
setlocal
cd /d "%~dp0"

echo SharpBit GUI launcher

echo Checking Python...
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

echo.
echo ERROR: Python was not found.
echo Install Python 3 and enable "Add Python to PATH".
echo.
pause
exit /b 1

:python_found
echo Checking dependencies...
%PYTHON% -c "import tkinter; import PIL; import imageio" >nul 2>nul
if errorlevel 1 (
    echo Required packages are missing. Installing them now...
    %PYTHON% -m pip install -r requirements.txt
    if errorlevel 1 goto install_failed
)

%PYTHON% -c "import tkinter" >nul 2>nul
if errorlevel 1 (
    echo.
    echo ERROR: This Python installation has no Tkinter support.
    echo Install the official Python build from python.org and try again.
    echo.
    pause
    exit /b 1
)

echo Starting GUI...
%PYTHON% gui.py
if errorlevel 1 goto gui_failed
exit /b 0

:install_failed
echo.
echo ERROR: Could not install SharpBit dependencies.
echo Try running install.bat manually.
echo.
pause
exit /b 1

:gui_failed
echo.
echo ERROR: SharpBit GUI stopped with an error.
echo The error message is shown above.
echo.
pause
exit /b 1

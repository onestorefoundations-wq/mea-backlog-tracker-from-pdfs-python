@echo off
setlocal
echo ===================================================
echo  KTU Grade Card Extractor - Windows Launcher
echo ===================================================

:: 1. Check if Python is installed
python --version >nul 2>&1
if %errorlevel%==0 (
    echo Python is already installed.
    goto :havepython
)

echo Python was not found on this system.
echo.

:: 2. Try installing via winget (Windows 10/11)
where winget >nul 2>&1
if %errorlevel%==0 (
    echo Attempting to install Python via winget...
    winget install -e --id Python.Python.3.12 --accept-source-agreements --accept-package-agreements
    echo.
    echo Python installed. Please CLOSE this window and run runs.bat again
    echo so the new PATH takes effect.
    pause
    exit /b
) else (
    echo winget is not available on this system.
    echo Please install Python 3 manually from:
    echo     https://www.python.org/downloads/
    echo IMPORTANT: tick "Add Python to PATH" during installation.
    echo Then run runs.bat again.
    pause
    exit /b
)

:havepython
:: 3. Create virtual environment if missing
if not exist env (
    echo Creating virtual environment...
    python -m venv env
) else (
    echo Virtual environment already exists.
)

:: 4. Activate and install requirements
echo Activating virtual environment...
call env\Scripts\activate

echo Upgrading pip and installing requirements...
python -m pip install --upgrade pip
pip install -r requirements.txt

:: 5. Run the app
echo Running the application...
python scraper.py

echo ===================================================
echo  Process finished.
echo ===================================================
pause

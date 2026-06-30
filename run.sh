#!/usr/bin/env bash
# ===================================================
#  KTU Grade Card Extractor - Linux/macOS Launcher
# ===================================================
set -e
cd "$(dirname "$0")"

echo "==================================================="
echo " KTU Grade Card Extractor - Launcher"
echo "==================================================="

# 1. Check for python3
if command -v python3 >/dev/null 2>&1; then
    echo "Python 3 is already installed."
else
    echo "Python 3 not found. Attempting to install..."
    if command -v apt-get >/dev/null 2>&1; then
        sudo apt-get update
        sudo apt-get install -y python3 python3-venv python3-pip python3-tk
    elif command -v dnf >/dev/null 2>&1; then
        sudo dnf install -y python3 python3-pip python3-tkinter
    elif command -v pacman >/dev/null 2>&1; then
        sudo pacman -Sy --noconfirm python python-pip tk
    elif command -v brew >/dev/null 2>&1; then
        brew install python python-tk
    else
        echo "Could not detect a supported package manager."
        echo "Please install Python 3 (with tkinter) manually, then re-run this script."
        exit 1
    fi
fi

# 2. Ensure tkinter is available (it is required for the GUI)
if ! python3 -c "import tkinter" >/dev/null 2>&1; then
    echo "tkinter is missing. Trying to install it..."
    if command -v apt-get >/dev/null 2>&1; then
        sudo apt-get install -y python3-tk
    elif command -v dnf >/dev/null 2>&1; then
        sudo dnf install -y python3-tkinter
    fi
fi

# 3. Create virtual environment if missing
if [ ! -d env ]; then
    echo "Creating virtual environment..."
    python3 -m venv env
else
    echo "Virtual environment already exists."
fi

# 4. Activate and install requirements
echo "Activating virtual environment..."
source env/bin/activate

echo "Upgrading pip and installing requirements..."
python -m pip install --upgrade pip
pip install -r requirements.txt

# 5. Run the app
echo "Running the application..."
python scraper.py

echo "==================================================="
echo " Process finished."
echo "==================================================="

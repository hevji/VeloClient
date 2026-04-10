@echo off
echo This script will install the required Python packages for this project.
timeout /t 5 /nobreak >nul
echo Installing requirements...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
echo Requirements installed successfully.
pause
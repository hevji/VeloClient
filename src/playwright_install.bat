@echo off
echo This script will install a chromium browser for Playwright. this is needed for the client to work.
timeout /t 1 /nobreak >nul
echo After this, you can run the client with "python launcher.py". you dont have to install chromium again after this.
timeout /t 5 /nobreak >nul
echo Installing Playwright Chromium...
playwright install chromium
echo Playwright Chromium installed successfully.
pause
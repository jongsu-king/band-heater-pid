@echo off
rem Build HeaterLog.exe on a Windows PC (cannot be built on a Mac).
rem Needs uv: https://docs.astral.sh/uv/  and the Microsoft Edge WebView2 runtime (already on Windows 10/11).
rem NOT TESTED: this script was written on macOS. The Mac app was built and tested; this one was not.
rem Run it from this folder (the one that contains heater_app.py).
cd /d "%~dp0"
uv run --with pyinstaller --with "pywebview>=5" --with "pyserial>=3.5" pyinstaller --noconfirm --clean --distpath dist packaging\heater_app.spec
if errorlevel 1 (echo BUILD FAILED & pause & exit /b 1)
echo Built: dist\HeaterLog.exe
pause

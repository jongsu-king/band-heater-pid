@echo off
rem Builds the Windows program folder and its installer on a Windows PC (it cannot be built on a Mac).
rem   dist\HeaterLog\HeaterLog.exe                                the program (folder build)
rem   dist\Band-Heater-Logger-<version>-windows-x64-setup.exe     the installer
rem Needs uv (https://docs.astral.sh/uv/). Optional: g++ (MinGW-w64) for the virtual board used by practice mode,
rem and Inno Setup 6 (https://jrsoftware.org/isinfo.php) for the installer.
rem GitHub Actions runs this same file (.github/workflows/windows-installer.yml) and then test-installs the result.
setlocal
cd /d "%~dp0"

where g++ >nul 2>nul
if errorlevel 1 goto nosim
g++ -std=c++17 -w -static -x c++ -I tools\sim\mock -I band_heater_pid tools\sim\sim.cpp -o tools\sim\sim_bin.exe
if errorlevel 1 goto fail
goto build
:nosim
echo g++ not found: building without the virtual board, so practice mode will not be available.

:build
uv run --with pyinstaller --with "pywebview>=5" --with "pyserial>=3.5" pyinstaller --noconfirm --clean --workpath "%TEMP%\heaterlog_pyi" --distpath dist packaging\heater_app.spec
if errorlevel 1 goto fail
echo Built: dist\HeaterLog\HeaterLog.exe

set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" set "ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" goto noiscc
"%ISCC%" packaging\windows\installer.iss
if errorlevel 1 goto fail
goto done
:noiscc
echo Inno Setup 6 not found: the installer was not built. Install it and run this file again.

:done
if not defined CI pause
exit /b 0

:fail
echo BUILD FAILED
if not defined CI pause
exit /b 1

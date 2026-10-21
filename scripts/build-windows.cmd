@echo off
setlocal
cd /d "%~dp0.."
set "PYTRTT_BUILD_ROOT=%LOCALAPPDATA%\PyTRTT\build-cache"
set "PYTRTT_BUILD_CLEAN="
if /I "%~1"=="--clean" set "PYTRTT_BUILD_CLEAN=--clean"

python -c "import PyInstaller, PIL" >nul 2>nul
if errorlevel 1 (
  echo Installing Windows packaging dependencies...
  python -m pip install "pyinstaller>=6" "pillow>=11"
  if errorlevel 1 exit /b 1
)

python -c "import PySide6" >nul 2>nul
if errorlevel 1 (
  echo PySide6 is missing. Installing the GUI runtime...
  python -m pip install "pyside6>=6.10.1,<6.11"
  if errorlevel 1 exit /b 1
)

python scripts\generate_windows_version.py
if errorlevel 1 exit /b 1
set /p PYTRTT_VERSION=<packaging\version.txt

if not exist "%PYTRTT_BUILD_ROOT%\work" mkdir "%PYTRTT_BUILD_ROOT%\work"
if not exist "%PYTRTT_BUILD_ROOT%\dist" mkdir "%PYTRTT_BUILD_ROOT%\dist"

echo Building PyTRTT %PYTRTT_VERSION% in %PYTRTT_BUILD_ROOT%...
python -m PyInstaller --noconfirm %PYTRTT_BUILD_CLEAN% ^
  --workpath "%PYTRTT_BUILD_ROOT%\work" ^
  --distpath "%PYTRTT_BUILD_ROOT%\dist" ^
  packaging\pytrtt.spec
if errorlevel 1 exit /b 1

if not exist "dist" mkdir "dist"
if exist "dist\PyTRTT.exe" (
  powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\archive-windows-exe.ps1 -TargetPath "%CD%\dist\PyTRTT.exe"
  if errorlevel 1 exit /b 1
)
copy /Y "%PYTRTT_BUILD_ROOT%\dist\PyTRTT.exe" "dist\PyTRTT.exe" >nul
if errorlevel 1 exit /b 1
echo Standalone executable: %CD%\dist\PyTRTT.exe

echo Running packaged GUI smoke test...
"dist\PyTRTT.exe" --smoke-test
if errorlevel 1 exit /b 1

where ISCC.exe >nul 2>nul
if not errorlevel 1 (
  ISCC.exe /DAppVersion=%PYTRTT_VERSION% packaging\PyTRTT.iss
  if errorlevel 1 exit /b 1
  exit /b 0
)

if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" (
  "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" /DAppVersion=%PYTRTT_VERSION% packaging\PyTRTT.iss
  if errorlevel 1 exit /b 1
  exit /b 0
)

echo PyTRTT.exe was built, but Inno Setup 6 was not found. 1>&2
echo Install Inno Setup or add ISCC.exe to PATH to create the installer. 1>&2
exit /b 2

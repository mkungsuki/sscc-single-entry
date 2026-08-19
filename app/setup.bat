@echo off
chcp 65001 >nul
title SSCC Stroke - Setup
cd /d %~dp0

echo.
echo  ============================================
echo    SSCC Stroke - First-time setup
echo  ============================================
echo.

call :find_python
if defined PY goto :got_python

echo  [1/4] Python not found - installing automatically (2-3 minutes)...
winget --version >nul 2>&1
if errorlevel 1 goto :manual_python
winget install -e --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements --override "/quiet InstallAllUsers=0 PrependPath=1 Include_launcher=1"
call :find_python
if defined PY goto :got_python
goto :manual_python

:got_python
echo  [1/4] Python found: %PY%
echo.
echo  [2/4] Installing libraries (first time 1-3 minutes, needs internet)...
%PY% -m pip install --disable-pip-version-check -r requirements.txt
if errorlevel 1 goto :pip_fail
%PY% -c "import flask, playwright, openpyxl" >nul 2>&1
if errorlevel 1 goto :pip_fail
echo  [2/4] Libraries OK
echo.
echo  [3/4] Creating desktop shortcut "SSCC Stroke"...
powershell -NoProfile -NonInteractive -Command "$s=(New-Object -ComObject WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Desktop')+'\SSCC Stroke.lnk');$s.TargetPath='%~dp0start.bat';$s.WorkingDirectory='%~dp0';$s.Save()" >nul 2>&1
echo.
echo  [4/4] Setup complete - starting the program...
echo.
echo  Next time, open the program from the "SSCC Stroke" shortcut on the desktop.
timeout /t 3 /nobreak >nul 2>&1
start "" "%~dp0start.bat"
exit /b 0

:manual_python
echo.
echo  Could not install Python automatically - opening the download page.
echo  Install it yourself: tick "Add python.exe to PATH" before clicking Install.
echo  Then double-click setup.bat again.
start "" https://www.python.org/downloads/
pause
exit /b 1

:pip_fail
echo.
echo  Library install failed - usually no internet connection.
echo  Connect to the internet and double-click setup.bat again.
echo  Offline machines: see README.md for the offline install method.
pause
exit /b 1

rem ---- find Python 3.10+: PATH, then py launcher, then standard install folders ----
:find_python
set "PY="
call :try_py python
if defined PY exit /b 0
call :try_launcher
if defined PY exit /b 0
for /d %%D in ("%LocalAppData%\Programs\Python\Python3*") do call :try_py "%%D\python.exe"
if defined PY exit /b 0
for /d %%D in ("%ProgramFiles%\Python3*") do call :try_py "%%D\python.exe"
exit /b 0

:try_py
if defined PY exit /b 0
%* -c "import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)" >nul 2>&1 || exit /b 0
set "PY=%*"
exit /b 0

:try_launcher
py -3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)" >nul 2>&1 || exit /b 0
set "PY=py -3"
exit /b 0

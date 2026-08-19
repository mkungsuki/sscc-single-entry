@echo off
chcp 65001 >nul
title SSCC Stroke - Update

rem Two-stage: this file gets replaced during update, so copy self to TEMP and run from there.
rem Pass APPDIR via env var (argument with quotes breaks inside start's cmd /c).
rem NOTE: this file is ASCII-only on purpose. Thai text in .bat files renders as garbage
rem on old consoles and trips cmd's UTF-8 line parser. Thai messages live in the web UI.
if /i "%~1" neq "GO" (
  copy /y "%~f0" "%TEMP%\sscc_update_run.bat" >nul
  set "SSCC_APPDIR=%~dp0"
  start "SSCC Update" "%TEMP%\sscc_update_run.bat" GO
  exit /b 0
)

set "APPDIR=%SSCC_APPDIR%"
if not defined APPDIR (
  echo Please double-click update.bat inside the program folder, not the TEMP copy.
  pause
  exit /b 1
)
set "REPO_ZIP=https://github.com/mkungsuki/sscc-single-entry/archive/refs/heads/main.zip"
if defined SSCC_UPDATE_ZIP set "REPO_ZIP=%SSCC_UPDATE_ZIP%"
set "WORK=%TEMP%\sscc_update_work"

echo.
echo  ============================================
echo    SSCC Stroke - Update from GitHub
echo  ============================================
echo.

echo  [1/5] Closing running program (if any)...
for /f "tokens=5" %%P in ('netstat -ano ^| findstr /r /c:":8547 .*LISTENING"') do taskkill /pid %%P /f >nul 2>&1

echo  [2/5] Downloading latest version...
if exist "%WORK%" rd /s /q "%WORK%"
mkdir "%WORK%"
powershell -NoProfile -NonInteractive -Command "$ProgressPreference='SilentlyContinue'; [Net.ServicePointManager]::SecurityProtocol='Tls12'; Invoke-WebRequest -Uri '%REPO_ZIP%' -OutFile '%WORK%\src.zip'"
if errorlevel 1 goto :dl_fail
powershell -NoProfile -NonInteractive -Command "$ProgressPreference='SilentlyContinue'; Expand-Archive -Force '%WORK%\src.zip' '%WORK%'"
if errorlevel 1 goto :dl_fail

set "SRC="
for /d %%D in ("%WORK%\*") do if exist "%%D\app\server.py" set "SRC=%%D\app"
if not defined SRC goto :dl_fail

echo  [3/5] Checking downloaded files...
rem Never install broken files: every .bat must be non-empty and the core files must exist.
rem (2026-08-18: a bad conversion step once zeroed every .bat and this check did not exist.)
for %%F in ("%SRC%\*.bat") do if %%~zF LSS 200 goto :bad_src
if not exist "%SRC%\start.bat" goto :bad_src
if not exist "%SRC%\update.bat" goto :bad_src
if not exist "%SRC%\templates\form.html" goto :bad_src
echo         OK

echo  [4/5] Installing (database / Excel / settings / hospital fields are NOT touched)...
robocopy "%SRC%" "%APPDIR%." /e /xd data output __pycache__ mock tools /xf config.json custom_fields.json >nul
if errorlevel 8 goto :copy_fail
for %%F in ("%APPDIR%start.bat" "%APPDIR%update.bat") do if %%~zF LSS 200 goto :copy_fail

echo  [5/5] Installing any new libraries...
call :find_python
if defined PY %PY% -m pip install --disable-pip-version-check -q -r "%APPDIR%requirements.txt"

echo.
echo  Update complete - starting the program...
timeout /t 2 /nobreak >nul 2>&1
start "" "%APPDIR%start.bat"
exit /b 0

:dl_fail
echo.
echo  Download failed - check the internet connection, then double-click update.bat again.
pause
exit /b 1

:bad_src
echo.
echo  Downloaded files look incomplete - nothing was changed. Try again later.
pause
exit /b 1

:copy_fail
echo.
echo  Install failed - close any open program/folder windows and try again.
echo  If start.bat no longer opens, extract start.bat/update.bat/setup.bat from the deploy zip.
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

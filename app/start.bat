@echo off
chcp 65001 >nul
title SSCC Stroke
cd /d %~dp0

rem Already running (e.g. double-clicked twice): just open the web page.
netstat -ano 2>nul | findstr /r /c:":8547 .*LISTENING" >nul
if not errorlevel 1 (
  start "" http://127.0.0.1:8547/
  exit /b 0
)

call :find_python
if not defined PY goto :need_setup
%PY% -c "import flask, playwright, openpyxl" >nul 2>&1
if errorlevel 1 goto :need_setup

start "" http://127.0.0.1:8547/
%PY% server.py
pause
exit /b 0

:need_setup
echo  Not installed yet - double-click setup.bat once, then open again.
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

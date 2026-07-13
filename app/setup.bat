@echo off
chcp 65001 >nul
title SSCC Stroke - ติดตั้งครั้งแรก
cd /d %~dp0

echo.
echo  ============================================
echo    SSCC Stroke - ติดตั้งอัตโนมัติ
echo  ============================================
echo.

call :find_python
if defined PY goto :got_python

echo  [1/4] ไม่พบ Python ในเครื่อง - กำลังติดตั้งให้อัตโนมัติ ใช้เวลา 2-3 นาที...
winget --version >nul 2>&1
if errorlevel 1 goto :manual_python
winget install -e --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements --override "/quiet InstallAllUsers=0 PrependPath=1 Include_launcher=1"
call :find_python
if defined PY goto :got_python
goto :manual_python

:got_python
echo  [1/4] พบ Python แล้ว: %PY%
echo.
echo  [2/4] กำลังติดตั้งไลบรารี - ครั้งแรกใช้เวลา 1-3 นาที ต้องต่ออินเทอร์เน็ต...
%PY% -m pip install --disable-pip-version-check -r requirements.txt
if errorlevel 1 goto :pip_fail
%PY% -c "import flask, playwright, openpyxl" >nul 2>&1
if errorlevel 1 goto :pip_fail
echo  [2/4] ไลบรารีครบแล้ว
echo.
echo  [3/4] สร้างทางลัด "SSCC Stroke" บนหน้าจอ...
powershell -NoProfile -Command "$s=(New-Object -ComObject WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Desktop')+'\SSCC Stroke.lnk');$s.TargetPath='%~dp0start.bat';$s.WorkingDirectory='%~dp0';$s.Save()" >nul 2>&1
echo.
echo  [4/4] ติดตั้งเสร็จแล้ว - กำลังเปิดโปรแกรม...
echo.
echo  ครั้งต่อไปเปิดโปรแกรมจากทางลัด "SSCC Stroke" บนหน้าจอได้เลย
timeout /t 3 /nobreak >nul 2>&1
start "" "%~dp0start.bat"
exit /b 0

:manual_python
echo.
echo  ติดตั้ง Python อัตโนมัติไม่ได้ - กำลังเปิดหน้าดาวน์โหลดให้
echo  ติดตั้งเองโดยติ๊ก "Add python.exe to PATH" ก่อนกด Install
echo  เสร็จแล้วกลับมาดับเบิลคลิก setup.bat นี้อีกครั้ง
start "" https://www.python.org/downloads/
pause
exit /b 1

:pip_fail
echo.
echo  ติดตั้งไลบรารีไม่สำเร็จ - ส่วนใหญ่เพราะเครื่องไม่ได้ต่ออินเทอร์เน็ต
echo  ต่อเน็ตแล้วดับเบิลคลิก setup.bat อีกครั้ง
echo  เครื่องที่ไม่มีเน็ตเลย: อ่านวิธีติดตั้งแบบ offline ใน README.md
pause
exit /b 1

rem ---- หา Python 3.10+ ในเครื่อง: PATH -> py launcher -> โฟลเดอร์ติดตั้งมาตรฐาน ----
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

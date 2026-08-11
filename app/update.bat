@echo off
chcp 65001 >nul
title SSCC Stroke - อัปเดตโปรแกรม

rem สองจังหวะ: ไฟล์นี้จะถูกอัปเดตทับด้วย เลยก๊อปตัวเองไปรันจาก TEMP ก่อน
rem ส่งที่อยู่โฟลเดอร์ผ่าน env var — ส่งเป็น argument ที่มี quote สองชุดแล้ว cmd ตัด quote เพี้ยน (เจอจริง)
if /i "%~1" neq "GO" (
  copy /y "%~f0" "%TEMP%\sscc_update_run.bat" >nul
  set "SSCC_APPDIR=%~dp0"
  start "SSCC Update" "%TEMP%\sscc_update_run.bat" GO
  exit /b 0
)

set "APPDIR=%SSCC_APPDIR%"
if not defined APPDIR (
  echo กรุณาดับเบิลคลิก update.bat ในโฟลเดอร์โปรแกรม ไม่ใช่ไฟล์สำเนาใน TEMP
  pause
  exit /b 1
)
set "REPO_ZIP=https://github.com/mkungsuki/sscc-single-entry/archive/refs/heads/main.zip"
if defined SSCC_UPDATE_ZIP set "REPO_ZIP=%SSCC_UPDATE_ZIP%"
set "WORK=%TEMP%\sscc_update_work"

echo.
echo  ============================================
echo    SSCC Stroke - อัปเดตโปรแกรมจาก GitHub
echo  ============================================
echo.

echo  [1/4] ปิดโปรแกรมที่เปิดค้างอยู่ (ถ้ามี)...
for /f "tokens=5" %%P in ('netstat -ano ^| findstr /r /c:":8547 .*LISTENING"') do taskkill /pid %%P /f >nul 2>&1

echo  [2/4] ดาวน์โหลดเวอร์ชันล่าสุด...
if exist "%WORK%" rd /s /q "%WORK%"
mkdir "%WORK%"
powershell -NoProfile -NonInteractive -Command "$ProgressPreference='SilentlyContinue'; [Net.ServicePointManager]::SecurityProtocol='Tls12'; Invoke-WebRequest -Uri '%REPO_ZIP%' -OutFile '%WORK%\src.zip'"
if errorlevel 1 goto :dl_fail
powershell -NoProfile -NonInteractive -Command "$ProgressPreference='SilentlyContinue'; Expand-Archive -Force '%WORK%\src.zip' '%WORK%'"
if errorlevel 1 goto :dl_fail

set "SRC="
for /d %%D in ("%WORK%\*") do if exist "%%D\app\server.py" set "SRC=%%D\app"
if not defined SRC goto :dl_fail

rem ไฟล์ .bat ใน zip ของ GitHub อาจเป็น LF — ต้องแปลงเป็น CRLF ก่อน ไม่งั้น cmd อ่านภาษาไทยเพี้ยน
powershell -NoProfile -NonInteractive -Command "Get-ChildItem -Path '%SRC%' -Filter *.bat | ForEach-Object { [IO.File]::WriteAllLines($_.FullName, [IO.File]::ReadAllLines($_.FullName), (New-Object Text.UTF8Encoding($false))) }"

echo  [3/4] ติดตั้งไฟล์ใหม่ (ฐานข้อมูล / ไฟล์ Excel / การตั้งค่า / ฟิลด์ รพ. ไม่ถูกแตะ)...
robocopy "%SRC%" "%APPDIR%." /e /xd data output __pycache__ mock tools /xf config.json custom_fields.json >nul
if errorlevel 8 goto :copy_fail

echo  [4/4] ติดตั้งไลบรารีที่อาจเพิ่มใหม่...
call :find_python
if defined PY %PY% -m pip install --disable-pip-version-check -q -r "%APPDIR%requirements.txt"

echo.
echo  อัปเดตเสร็จแล้ว - กำลังเปิดโปรแกรม...
timeout /t 2 /nobreak >nul 2>&1
start "" "%APPDIR%start.bat"
exit /b 0

:dl_fail
echo.
echo  ดาวน์โหลดไม่สำเร็จ - เช็คว่าเครื่องต่ออินเทอร์เน็ตอยู่ แล้วดับเบิลคลิก update.bat ใหม่
pause
exit /b 1

:copy_fail
echo.
echo  ติดตั้งไฟล์ไม่สำเร็จ - ปิดหน้าต่างโปรแกรม/โฟลเดอร์ที่เปิดค้าง แล้วลองใหม่
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

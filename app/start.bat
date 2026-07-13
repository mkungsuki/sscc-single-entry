@echo off
chcp 65001 >nul
title SSCC Stroke - กรอกครั้งเดียว
cd /d %~dp0
start "" http://127.0.0.1:8547/
python server.py
pause

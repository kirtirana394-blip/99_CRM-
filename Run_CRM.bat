@echo off
title Yayath Spaces CRM
echo Starting Yayath Spaces CRM...
cd /d "%~dp0"
start http://127.0.0.1:5000
python app.py
pause

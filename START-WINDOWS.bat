@echo off
title Sur Music - by Mousa International Software House
cd /d "%~dp0"

where py >nul 2>nul
if not errorlevel 1 goto usepy
where python >nul 2>nul
if not errorlevel 1 goto usepython

echo.
echo Python is not installed.
echo 1. Download it from https://www.python.org/downloads/
echo 2. During installation, tick "Add python.exe to PATH".
echo 3. Then double-click this file again.
echo.
goto end

:usepy
py -3 run_local.py
goto end

:usepython
python run_local.py

:end
pause

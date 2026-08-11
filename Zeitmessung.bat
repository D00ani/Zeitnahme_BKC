@echo off
setlocal
chcp 65001 >nul
title Zeitmessung

cd /d "%~dp0"

rem pythonw startet ohne schwarzes Konsolenfenster.
where pythonw >nul 2>&1
if %errorlevel%==0 (
    start "" pythonw Zeitmessung.pyw
    exit /b 0
)

where python >nul 2>&1
if %errorlevel%==0 (
    python Zeitmessung.pyw
    exit /b 0
)

echo Python wurde nicht gefunden.
echo.
echo Bitte Python von python.org installieren und dabei den Haken bei
echo "Add Python to PATH" setzen.
echo.
pause

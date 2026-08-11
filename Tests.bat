@echo off
setlocal
chcp 65001 >nul
title Zeitmessung - Tests

cd /d "%~dp0"

echo ============================================================
echo   Testlauf
echo ============================================================
echo.

python -m unittest discover -s tests -t .

echo.
pause

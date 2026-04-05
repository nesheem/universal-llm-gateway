@echo off
title Universal LLM Gateway v1.0
color 0B
echo.
echo ================================================================
echo    UNIVERSAL LLM GATEWAY v1.0
echo    100 Input Slots  ^|  1 Output Key  ^|  All Providers
echo ================================================================
echo.
python --version 2>nul
if %errorlevel% neq 0 (echo ERROR: Python not found && pause && exit /b 1)
echo Installing / updating dependencies...
pip install -r requirements.txt --quiet
echo.
echo Starting Universal LLM Gateway v1.0...
echo   Proxy API  : http://localhost:8900/v1
echo   Dashboard  : http://localhost:8901
echo.
python main.py
echo.
echo Universal LLM Gateway stopped.
pause

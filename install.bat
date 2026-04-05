@echo off
title Universal LLM Gateway v1.0 - Setup
color 0B
echo Installing Universal LLM Gateway v1.0...
python -m pip install --upgrade pip --quiet
pip install -r requirements.txt
if not exist logs mkdir logs
echo.
echo Done! Run run.bat to start.
pause

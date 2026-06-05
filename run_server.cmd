@echo off
cd /d "%~dp0"
python -m uvicorn server:app --host 0.0.0.0 --port 8010 --log-level info

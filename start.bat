@echo off
rem 后台启动 不打字（没有黑窗口）。日志在 budazi.log
cd /d "%~dp0"
start "" ".venv\Scripts\pythonw.exe" -m budazi.app

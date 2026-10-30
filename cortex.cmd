@echo off
setlocal
if exist "%~dp0.venv\Scripts\python.exe" goto venv
python "%~dp0cortex.py" %*
exit /b %errorlevel%
:venv
"%~dp0.venv\Scripts\python.exe" "%~dp0cortex.py" %*
exit /b %errorlevel%

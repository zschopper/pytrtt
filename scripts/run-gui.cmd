@echo off
setlocal

cd /d "%~dp0.."
python -m pytrtt.qt_gui --recovery-in-game --debug-log %*

exit /b %errorlevel%

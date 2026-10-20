@echo off
setlocal

cd /d "%~dp0.."
python -m pytrtt.qt_gui --recovery-in-game %*

exit /b %errorlevel%

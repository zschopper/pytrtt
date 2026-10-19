@echo off
setlocal

cd /d "%~dp0.."

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -m pytrtt.gui %*
) else (
    py -3.13 -c "import sys" >nul 2>nul
    if not errorlevel 1 (
        py -3.13 -m pytrtt.gui %*
    ) else (
        py -3.14 -c "import sys" >nul 2>nul
        if not errorlevel 1 (
            py -3.14 -m pytrtt.gui %*
        ) else (
            where python >nul 2>nul
            if errorlevel 1 (
                echo Python or the project virtual environment was not found.
                echo Install Python 3.13 or 3.14, then try again.
                exit /b 1
            )
            python -m pytrtt.gui %*
        )
    )
)

exit /b %errorlevel%

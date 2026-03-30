@echo off
setlocal EnableExtensions

REM Stops the three windows opened by scripts\run.bat (by title).
REM Also force-stops ngrok in case the window title no longer matches.

taskkill /FI "WINDOWTITLE eq TrendLine Backend" /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq TrendLine Streamlit" /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq TrendLine ngrok" /F >nul 2>&1

taskkill /IM ngrok.exe /F >nul 2>&1

echo Stopped TrendLine backend / Streamlit / ngrok (where found).
echo If any window is still open, close it manually or end the process in Task Manager.
endlocal

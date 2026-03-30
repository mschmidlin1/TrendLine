@echo off
setlocal EnableExtensions
set "ROOT=%~dp0.."
cd /d "%ROOT%"

REM Random port in dynamic/private range (49152–65535) to avoid well-known ports
set /a PORT=49152 + %random% %% 16384

echo.
echo TrendLine launcher
echo ------------------
echo Streamlit + ngrok will use port: %PORT%
echo Basic auth: trendline / 1234water
echo.

start "TrendLine Backend" /D "%ROOT%" cmd /k "call .venv\Scripts\activate.bat && python trendline.py"
timeout /t 2 /nobreak >nul

start "TrendLine Streamlit" /D "%ROOT%" cmd /k "call .venv\Scripts\activate.bat && streamlit run trendline_streamlit.py --server.port %PORT%"
timeout /t 3 /nobreak >nul

start "TrendLine ngrok" cmd /k ngrok http %PORT% --basic-auth=trendline:1234water

echo Started backend, Streamlit (port %PORT%), and ngrok in separate windows.
echo To stop all: run scripts\stop.bat, or close each window (Alt+F4).
endlocal

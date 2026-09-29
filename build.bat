@echo off
echo Installing dependencies...
pip install -r requirements.txt || goto :err
echo Building executable...
pyinstaller --onefile --noconsole --name DroneFlightSimulator --collect-all ursina --collect-all panda3d main.py || goto :err
echo.
echo Done: dist\DroneFlightSimulator.exe
pause
exit /b 0
:err
echo Build failed.
pause
exit /b 1

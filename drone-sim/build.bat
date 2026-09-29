@echo off
echo Installing dependencies...
pip install -r requirements.txt
echo Building executable...
pyinstaller --onefile --noconsole --name DroneFlightSimulator --collect-all ursina --collect-all panda3d main.py
echo.
echo Done! Your executable is at dist\DroneFlightSimulator.exe
pause

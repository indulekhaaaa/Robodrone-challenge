@echo off
echo Installing dependencies...
python -m pip install -r requirements.txt || goto :error

echo Building DroneFlightSimulator.exe ...
python -m PyInstaller --onefile --noconsole --clean ^
  --name DroneFlightSimulator ^
  --collect-all ursina --collect-all panda3d ^
  --collect-all panda3d_gltf --collect-all panda3d_simplepbr ^
  main.py || goto :error

echo.
echo Done! Your executable is at dist\DroneFlightSimulator.exe
pause
exit /b 0

:error
echo Build failed. Check that Python 3.10+ is installed and on PATH.
pause
exit /b 1

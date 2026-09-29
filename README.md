# Drone Flight Training Simulator
Python + Ursina (Panda3D). Full quadcopter flight model, 30 buildings, 8 scoring rings, two landing pads, 3 camera modes, live HUD.

The training environment includes an earthy arena with boundary rails, runway markers,
trees, distant mountains, and animated birds. The terracotta practice rings remain the
main flight challenge and award points when flown through.

## Controls
| Key | Action |
|---|---|
| SPACE / LEFT SHIFT | Throttle up / down |
| W / S | Pitch forward / back |
| A / D | Roll left / right |
| Q / E | Yaw left / right |
| R | Reset |
| C | Cycle camera |
| H | Help overlay |
| ESC | Quit |

Hover throttle is ~50%. Descending faster than 4.5 m/s or landing tilted more than 15 deg is a crash.

## Run from source
    pip install -r requirements.txt
    python main.py

## Build the .exe (Windows)
Double-click `build.bat` -> `dist\DroneFlightSimulator.exe`

# Drone Flight Training Simulator

Built with Python + the Ursina game engine (Panda3D under the hood).

## Features
- Full 6-axis quadcopter flight model: throttle, pitch, roll, yaw
- Physics: gravity, lift, tilt-based horizontal thrust, air drag
- Crash detection (hard landings, tilted landings, building collisions)
- 30 procedurally placed buildings
- 8 orange practice rings worth points
- Two landing pads (HOME and PAD B) with precision-landing scoring
- Three cameras: chase, FPV, high orbit
- Live HUD: altitude, speed, throttle %, score

## Controls
| Key | Action |
|-----|--------|
| SPACE | Throttle up |
| LEFT SHIFT | Throttle down |
| W / S | Pitch forward / backward |
| A / D | Roll left / right |
| Q / E | Yaw left / right |
| R | Reset drone |
| C | Cycle camera modes |
| H | Toggle help overlay |
| ESC | Quit |

Tip: hover throttle is ~50%. Hold SPACE until you lift off, then feather it.

## Run from source
```
pip install -r requirements.txt
python main.py
```

## Build the .exe (Windows)
1. Install Python 3.10+ (tick "Add Python to PATH").
2. Double-click `build.bat`.
3. Get `dist\DroneFlightSimulator.exe` - runs on any Windows 10/11 PC.

## Flight model notes
- Lift is proportional to throttle; ~50% throttle equals gravity (hover).
- Pitch/roll redirect thrust horizontally, so you drift the way you tilt.
- Air drag slows the drone when you level out.
- Descending faster than 4.5 m/s, or touching down tilted more than 15 deg, is a crash.

# Drone Flight Training Simulator

Built with Python + the Ursina game engine (Panda3D under the hood for hardware-accelerated rendering).

## Features
- Full 6-axis quadcopter flight model: throttle, pitch, roll, yaw
- Physics: gravity, lift, tilt-based horizontal thrust, air drag
- Crash detection (hard landings, tilted landings, building collisions)
- 3D world with 30 procedurally placed buildings
- 8 orange practice rings: fly through them to score points
- Two landing pads (HOME and PAD B) with precision-landing scoring
- Three camera modes: chase, FPV, high orbit
- Live HUD: altitude, speed, throttle %, score

## Controls
| Key | Action |
|---|---|
| SPACE | Throttle up |
| LEFT SHIFT | Throttle down |
| W / S | Pitch forward / backward |
| A / D | Roll left / right |
| Q / E | Yaw left / right |
| R | Reset drone (and score) |
| C | Cycle camera modes |
| H | Toggle help overlay |
| ESC | Quit |

Tip: hover throttle is ~50%. Hold SPACE until you lift off, then feather it.

## Build the .exe (Windows)
1. Install Python 3.10+ from https://python.org (tick "Add Python to PATH").
2. Double-click `build.bat`.
3. Your executable appears at `dist\DroneFlightSimulator.exe`. It runs on any Windows 10/11 PC without Python.

## Run from source
```
pip install -r requirements.txt
python main.py
```

## Project structure
```
drone-sim/
├── main.py           # entire simulator: physics, world, HUD, cameras
├── requirements.txt  # ursina + pyinstaller
├── build.bat         # one-click Windows EXE builder
└── README.md
```

## Flight model notes
- Lift is proportional to throttle; at ~50% throttle lift equals gravity (stable hover).
- Tilting (pitch/roll) redirects thrust horizontally, so you drift in the direction of tilt.
- Air drag slows the drone when you level out.
- Descending faster than 4.5 m/s, or touching down tilted more than 15 degrees, is a crash.

## Scoring
- Ring fly-through: +50
- Landing on a pad: up to +100, based on distance from the pad centre (within 3 m)

## Team rules
- Fork the repo, then start the project.
- Every team member contributes at least once.
- One contribution from the team every 20 minutes.

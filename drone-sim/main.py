"""Drone Flight Training Simulator - Python + Ursina (Panda3D).

Physics, world, HUD and cameras all live in this single file.
"""
import math
import random

from ursina import *

# ----------------------------------------------------------------------------
# Tunable constants
# ----------------------------------------------------------------------------
GRAVITY = 9.81
MAX_THRUST = 2 * GRAVITY      # at 100% throttle; 50% == hover
THROTTLE_RATE = 0.6           # throttle change per second while key held
MAX_TILT = 28                 # degrees of pitch / roll at full stick
TILT_RESPONSE = 6.0           # how quickly the drone reaches target tilt
YAW_RATE = 90                 # degrees per second
DRAG = 0.55                   # linear air drag coefficient
CRASH_SPEED = 4.5             # m/s vertical touchdown limit
CRASH_TILT = 15               # degrees tilt limit on touchdown
BODY_H = 0.15                 # drone centre height when sitting on ground
WORLD_HALF = 100              # world is 200 x 200

HOME = Vec3(0, BODY_H, 0)
PADS = [
    {"name": "HOME", "pos": Vec3(0, 0, 0), "radius": 4, "color": color.azure},
    {"name": "PAD B", "pos": Vec3(-45, 0, 40), "radius": 4, "color": color.magenta},
]
RING_POSITIONS = [
    (0, 6, 25), (20, 8, 50), (45, 10, 60), (65, 8, 35),
    (60, 12, 0), (40, 7, -30), (10, 9, -45), (-25, 8, -20),
]
RING_RADIUS = 3.0
RING_HIT_DISTANCE = 2.6
NUM_BUILDINGS = 30

CAM_NAMES = ["Chase", "FPV", "High orbit"]

HELP_TEXT = (
    "CONTROLS\n"
    "SPACE / L-SHIFT : throttle up / down\n"
    "W / S : pitch forward / back\n"
    "A / D : roll left / right\n"
    "Q / E : yaw left / right\n"
    "R : reset    C : camera    H : help    ESC : quit\n"
    "Hover is ~50% throttle. Land gently and level!"
)


# ----------------------------------------------------------------------------
# App + world
# ----------------------------------------------------------------------------
app = Ursina(title="Drone Flight Training Simulator", vsync=False)
window.exit_button.visible = False
window.fps_counter.enabled = True

Sky()
ground = Entity(
    model="plane",
    scale=WORLD_HALF * 2,
    color=color.green.tint(-0.35),
    texture="white_cube",
    texture_scale=(WORLD_HALF, WORLD_HALF),
)

# Landing pads
for pad in PADS:
    Entity(
        model="cube",
        position=pad["pos"] + Vec3(0, 0.02, 0),
        scale=(pad["radius"] * 2, 0.04, pad["radius"] * 2),
        color=pad["color"],
    )
    Text(
        text=pad["name"],
        world_space=True,
        position=pad["pos"] + Vec3(0, 0.1, -pad["radius"] - 0.5),
        rotation_x=90,
        scale=12,
        origin=(0, 0),
        color=color.white,
    )

# Rings
rings = []
for i, (x, y, z) in enumerate(RING_POSITIONS):
    nx, ny, nz = RING_POSITIONS[(i + 1) % len(RING_POSITIONS)]
    ring = Entity(position=(x, y, z), rotation_y=math.degrees(math.atan2(nx - x, nz - z)))
    segs = []
    for k in range(20):
        a = k / 20 * math.tau
        segs.append(
            Entity(
                parent=ring,
                model="cube",
                scale=0.45,
                position=(math.cos(a) * RING_RADIUS, math.sin(a) * RING_RADIUS, 0),
                color=color.orange,
            )
        )
    rings.append({"entity": ring, "segments": segs, "passed": False})

# Buildings (procedurally placed, deterministic seed so everyone sees same map)
rng = random.Random(7)
buildings = []
attempts = 0
while len(buildings) < NUM_BUILDINGS and attempts < 2000:
    attempts += 1
    w, d, h = rng.uniform(4, 10), rng.uniform(4, 10), rng.uniform(8, 30)
    x = rng.uniform(-WORLD_HALF + 10, WORLD_HALF - 10)
    z = rng.uniform(-WORLD_HALF + 10, WORLD_HALF - 10)
    if any(math.hypot(x - p["pos"].x, z - p["pos"].z) < 14 for p in PADS):
        continue
    if any(math.hypot(x - rx, z - rz) < 9 for rx, _, rz in RING_POSITIONS):
        continue
    shade = rng.uniform(0.35, 0.7)
    Entity(model="cube", position=(x, h / 2, z), scale=(w, h, d), color=color.rgb32(shade * 255, shade * 255, (shade + 0.05) * 255))
    buildings.append((x - w / 2, x + w / 2, z - d / 2, z + d / 2, h))


# ----------------------------------------------------------------------------
# HUD
# ----------------------------------------------------------------------------
hud = Text(text="", position=window.top_left + Vec2(0.02, -0.02), scale=1.2, color=color.white)
message = Text(text="", origin=(0, 0), position=(0, 0.25), scale=2, color=color.yellow)
help_overlay = Text(text=HELP_TEXT, origin=(0, 0), position=(0, -0.3), scale=1.1, color=color.white)


# ----------------------------------------------------------------------------
# Simulator
# ----------------------------------------------------------------------------
class DroneSim(Entity):
    def __init__(self):
        super().__init__()
        self.drone = Entity(position=HOME)
        self.body = Entity(parent=self.drone, model="cube", color=color.dark_gray, scale=(0.5, 0.12, 0.5))
        self.nose = Entity(parent=self.drone, model="cube", color=color.red, scale=(0.15, 0.1, 0.15), position=(0, 0.02, 0.3))
        for ang in (45, -45):
            Entity(parent=self.drone, model="cube", color=color.gray, scale=(1.3, 0.05, 0.07), rotation_y=ang)
        self.rotors = []
        for sx in (-1, 1):
            for sz in (-1, 1):
                self.rotors.append(
                    Entity(parent=self.drone, model="cube", color=color.light_gray,
                           scale=(0.4, 0.02, 0.06), position=(sx * 0.46, 0.08, sz * 0.46))
                )
        self.cam_mode = 0
        self.msg_timer = 0.0
        self.reset()

    # ---- state ----------------------------------------------------------
    def reset(self):
        self.drone.position = HOME
        self.vel = Vec3(0, 0, 0)
        self.throttle = 0.0
        self.pitch = self.roll = self.yaw = 0.0
        self.crashed = False
        self.airborne = False
        self.score = 0
        self.body.color = color.dark_gray
        self.drone.rotation = Vec3(0, 0, 0)
        for r in rings:
            r["passed"] = False
            for s in r["segments"]:
                s.color = color.orange
        message.text = ""

    def flash(self, text, col=color.yellow, seconds=2.5):
        message.text = text
        message.color = col
        self.msg_timer = seconds

    def crash(self, reason):
        self.crashed = True
        self.vel = Vec3(0, 0, 0)
        self.body.color = color.red
        self.flash(f"CRASHED: {reason}\nPress R to reset", color.red, 9999)

    # ---- input ----------------------------------------------------------
    def input(self, key):
        if key == "r":
            self.reset()
        elif key == "c":
            self.cam_mode = (self.cam_mode + 1) % len(CAM_NAMES)
        elif key == "h":
            help_overlay.enabled = not help_overlay.enabled
        elif key == "escape":
            application.quit()

    # ---- main loop ------------------------------------------------------
    def update(self):
        dt = min(time.dt, 1 / 30)
        if not self.crashed:
            self.step_physics(dt)
        self.update_camera(dt)
        self.update_hud(dt)

    def step_physics(self, dt):
        # Throttle
        self.throttle += (held_keys["space"] - held_keys["left shift"]) * THROTTLE_RATE * dt
        self.throttle = clamp(self.throttle, 0, 1)

        # Attitude (smoothly follows the stick, self-levels when released)
        tp = (held_keys["w"] - held_keys["s"]) * MAX_TILT
        tr = (held_keys["d"] - held_keys["a"]) * MAX_TILT
        k = min(1, TILT_RESPONSE * dt)
        self.pitch = lerp(self.pitch, tp, k)
        self.roll = lerp(self.roll, tr, k)
        self.yaw += (held_keys["e"] - held_keys["q"]) * YAW_RATE * dt
        self.drone.rotation = Vec3(self.pitch, self.yaw, self.roll)

        # Forces: lift along the drone's up axis + gravity + drag
        up = self.drone.up
        accel = up * (self.throttle * MAX_THRUST) + Vec3(0, -GRAVITY, 0)
        self.vel += accel * dt
        self.vel -= self.vel * DRAG * dt

        pos = self.drone.position + self.vel * dt

        # World boundary
        if abs(pos.x) > WORLD_HALF:
            pos.x = clamp(pos.x, -WORLD_HALF, WORLD_HALF)
            self.vel.x = 0
        if abs(pos.z) > WORLD_HALF:
            pos.z = clamp(pos.z, -WORLD_HALF, WORLD_HALF)
            self.vel.z = 0

        # Buildings
        for (x0, x1, z0, z1, h) in buildings:
            if x0 - 0.4 < pos.x < x1 + 0.4 and z0 - 0.4 < pos.z < z1 + 0.4 and pos.y < h + 0.2:
                self.drone.position = pos
                self.crash("hit a building")
                return

        # Ground contact
        if pos.y <= BODY_H:
            if self.airborne:
                impact = -self.vel.y
                tilt = math.degrees(math.acos(clamp(up.y, -1, 1)))
                if impact > CRASH_SPEED:
                    pos.y = BODY_H
                    self.drone.position = pos
                    self.crash(f"hard landing ({impact:.1f} m/s)")
                    return
                if tilt > CRASH_TILT:
                    pos.y = BODY_H
                    self.drone.position = pos
                    self.crash(f"tilted landing ({tilt:.0f} deg)")
                    return
                self.score_landing(pos)
                self.airborne = False
            pos.y = BODY_H
            self.vel.y = max(self.vel.y, 0)
            # ground friction
            self.vel.x *= math.exp(-6 * dt)
            self.vel.z *= math.exp(-6 * dt)
        elif pos.y > BODY_H + 0.3:
            self.airborne = True

        self.drone.position = pos

        # Rings
        for r in rings:
            if not r["passed"] and distance(pos, r["entity"].position) < RING_HIT_DISTANCE:
                r["passed"] = True
                self.score += 100
                for s in r["segments"]:
                    s.color = color.lime
                self.flash("+100 RING!", color.lime, 1.0)
                if all(x["passed"] for x in rings):
                    self.score += 500
                    self.flash("ALL RINGS CLEARED! +500", color.gold, 4.0)

        # Spin rotors
        for i, rotor in enumerate(self.rotors):
            rotor.rotation_y += (300 + self.throttle * 2500) * dt * (1 if i % 2 else -1)

    def score_landing(self, pos):
        for pad in PADS:
            d = math.hypot(pos.x - pad["pos"].x, pos.z - pad["pos"].z)
            if d < pad["radius"]:
                pts = int(50 + 100 * (1 - d / pad["radius"]))
                self.score += pts
                self.flash(f"Landed on {pad['name']}! +{pts}", color.cyan, 3.0)
                return

    # ---- camera + HUD ---------------------------------------------------
    def update_camera(self, dt):
        p = self.drone.position
        if self.cam_mode == 0:  # chase
            yaw = math.radians(self.yaw)
            back = Vec3(math.sin(yaw), 0, math.cos(yaw))
            target = p - back * 8 + Vec3(0, 3, 0)
            camera.position = lerp(camera.position, target, min(1, 5 * dt))
            camera.look_at(p + Vec3(0, 1, 0))
        elif self.cam_mode == 1:  # FPV
            camera.position = p + self.drone.up * 0.15 + self.drone.forward * 0.3
            camera.rotation = self.drone.rotation
        else:  # high orbit
            camera.position = lerp(camera.position, p + Vec3(0, 35, -30), min(1, 3 * dt))
            camera.look_at(p)

    def update_hud(self, dt):
        alt = max(0, self.drone.y - BODY_H)
        speed = self.vel.length()
        hud.text = (
            f"ALT   {alt:6.1f} m\n"
            f"SPEED {speed:6.1f} m/s\n"
            f"THR   {self.throttle * 100:5.0f} %\n"
            f"SCORE {self.score}\n"
            f"CAM   {CAM_NAMES[self.cam_mode]}"
        )
        if self.msg_timer > 0:
            self.msg_timer -= dt
            if self.msg_timer <= 0:
                message.text = ""


sim = DroneSim()
camera.fov = 90

if __name__ == "__main__":
    app.run()

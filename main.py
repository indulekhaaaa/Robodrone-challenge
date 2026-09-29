"""Drone Flight Training Simulator - Python + Ursina (Panda3D)."""
import math
import random
from ursina import *

# ---------------------------------------------------------------- constants
G = 9.81               # gravity (m/s^2)
MAX_TILT = 30          # max pitch/roll (deg)
YAW_RATE = 100         # deg/s
CRASH_VSPEED = 4.5     # m/s
CRASH_TILT = 15        # deg
GROUND_Y = 0.15        # drone centre height when landed
PADS = {'HOME': Vec3(0, 0, 0), 'PAD B': Vec3(60, 0, 60)}
RING_DEFS = [(0, 5, 25), (15, 6, 45), (-20, 8, 60), (-40, 5, 40),
             (-50, 7, 10), (-30, 4, -25), (20, 6, -40), (50, 5, -10)]
RING_RADIUS = 3

app = Ursina(title='Drone Flight Training Simulator', borderless=False)
window.exit_button.visible = False
window.fps_counter.enabled = True
camera.fov = 80
Sky()

# -------------------------------------------------------------------- world
Entity(model='plane', scale=600, texture='white_cube',
       texture_scale=(300, 300), color=color.rgb(70, 130, 70))

pad_colors = {'HOME': color.lime, 'PAD B': color.azure}
for name, p in PADS.items():
    Entity(model='cube', scale=(6, 0.1, 6), position=p + Vec3(0, 0.05, 0), color=color.dark_gray)
    Entity(model='cube', scale=(4.5, 0.12, 4.5), position=p + Vec3(0, 0.06, 0), color=pad_colors[name])
    Entity(model='cube', scale=(1, 0.14, 1), position=p + Vec3(0, 0.07, 0), color=color.white)
    Entity(model='cube', scale=(0.2, 5, 0.2), position=p + Vec3(3.5, 2.5, 3.5), color=pad_colors[name])

random.seed(7)
rings = []
for (rx, ry, rz) in RING_DEFS:
    parts = []
    for i in range(20):
        a = i / 20 * math.tau
        parts.append(Entity(model='cube', color=color.orange, scale=0.45,
                            position=(rx + math.cos(a) * RING_RADIUS,
                                      ry + math.sin(a) * RING_RADIUS, rz)))
    rings.append({'x': rx, 'y': ry, 'z': rz, 'done': False, 'parts': parts})

keep_clear = [Vec3(p.x, 0, p.z) for p in PADS.values()] + [Vec3(r[0], 0, r[2]) for r in RING_DEFS]
buildings = []
while len(buildings) < 30:
    x, z = random.uniform(-110, 110), random.uniform(-110, 110)
    if any(distance_xz(Vec3(x, 0, z), c) < 14 for c in keep_clear):
        continue
    w, d, h = random.uniform(5, 12), random.uniform(5, 12), random.uniform(6, 30)
    shade = random.randint(90, 170)
    Entity(model='cube', position=(x, h / 2, z), scale=(w, h, d),
           color=color.rgb(shade, shade, shade + 15), texture='white_cube')
    buildings.append((x, z, w, d, h))

# -------------------------------------------------------------------- drone
drone = Entity(position=(0, GROUND_Y, 0))
body = Entity(parent=drone, model='cube', scale=(0.5, 0.1, 0.5), color=color.black66)
Entity(parent=drone, model='cube', scale=(0.12, 0.08, 0.2), position=(0, 0, 0.3), color=color.red)  # nose
rotors = []
for sx, sz in [(1, 1), (-1, 1), (1, -1), (-1, -1)]:
    Entity(parent=drone, model='cube', scale=(0.5, 0.03, 0.04),
           position=(sx * 0.15, 0, sz * 0.15), rotation_y=45 * sx * sz, color=color.gray)
    rotors.append(Entity(parent=drone, model='cube', scale=(0.35, 0.01, 0.05),
                         position=(sx * 0.32, 0.07, sz * 0.32), color=color.yellow))


class State:
    vx = vy = vz = 0.0
    throttle = 0.0
    pitch = roll = yaw = 0.0
    airborne = False
    crashed = False
    score = 0
    cam_mode = 0


s = State()

# ---------------------------------------------------------------------- HUD
hud = Text(text='', position=window.top_left + Vec2(0.02, -0.02), origin=(-.5, .5), scale=1.2)
banner = Text(text='', origin=(0, 0), y=0.2, scale=2.5, color=color.red)
toast = Text(text='', origin=(0, 0), y=0.1, scale=1.6, color=color.yellow)
help_text = Text(origin=(.5, .5), position=window.top_right + Vec2(-0.02, -0.02), scale=1,
                 text=('SPACE/SHIFT throttle   W/S pitch   A/D roll   Q/E yaw\n'
                       'R reset   C camera   H help   ESC quit\n'
                       'Fly through orange rings, land on pads.'))
toast_timer = 0.0


def show(msg, t=2.5):
    global toast_timer
    toast.text, toast_timer = msg, t


# ------------------------------------------------------------------ actions
def reset():
    drone.position = (0, GROUND_Y, 0)
    s.vx = s.vy = s.vz = 0.0
    s.throttle = s.pitch = s.roll = s.yaw = 0.0
    s.airborne = s.crashed = False
    s.score = 0
    body.color = color.black66
    banner.text = ''
    for r in rings:
        r['done'] = False
        for p in r['parts']:
            p.color = color.orange


def crash(reason):
    s.crashed = True
    s.vx = s.vy = s.vz = 0.0
    body.color = color.red
    banner.text = f'CRASHED: {reason}\nPress R to reset'


def score_landing():
    for name, p in PADS.items():
        d = distance_xz(drone.position, p)
        if d < 3:
            pts = int(100 * (1 - d / 3))
            s.score += pts
            show(f'Landed on {name}: +{pts} (offset {d:.1f} m)')
            return
    show('Safe landing (off pad)')


def flight(dt):
    # --- inputs
    s.throttle = clamp(s.throttle + (held_keys['space'] - held_keys['left shift']) * 0.6 * dt, 0, 1)
    tgt_p = (held_keys['w'] - held_keys['s']) * MAX_TILT
    tgt_r = (held_keys['d'] - held_keys['a']) * MAX_TILT
    k = min(1, 6 * dt)
    s.pitch += (tgt_p - s.pitch) * k
    s.roll += (tgt_r - s.roll) * k
    s.yaw += (held_keys['e'] - held_keys['q']) * YAW_RATE * dt

    # --- forces: thrust follows tilt; hover at 50% throttle
    thrust = s.throttle * 2 * G
    p, r, y = math.radians(s.pitch), math.radians(s.roll), math.radians(s.yaw)
    lift = thrust * math.cos(p) * math.cos(r)
    fwd, side = thrust * math.sin(p), thrust * math.sin(r)
    ax = fwd * math.sin(y) + side * math.cos(y)
    az = fwd * math.cos(y) - side * math.sin(y)
    s.vx += ax * dt
    s.vz += az * dt
    s.vy += (lift - G) * dt

    # --- air drag
    dh, dv = max(0, 1 - 0.6 * dt), max(0, 1 - 0.3 * dt)
    s.vx *= dh
    s.vz *= dh
    s.vy *= dv

    prev_z = drone.z
    drone.x += s.vx * dt
    drone.y += s.vy * dt
    drone.z += s.vz * dt
    drone.rotation = (s.pitch, s.yaw, -s.roll)

    # --- ground / landing
    if drone.y <= GROUND_Y:
        if s.airborne:
            s.airborne = False
            if s.vy < -CRASH_VSPEED:
                return crash(f'hard landing ({-s.vy:.1f} m/s)')
            if max(abs(s.pitch), abs(s.roll)) > CRASH_TILT:
                return crash('tilted landing')
            score_landing()
        drone.y = GROUND_Y
        s.vy = max(0, s.vy)
        fr = max(0, 1 - 6 * dt)
        s.vx *= fr
        s.vz *= fr
    else:
        s.airborne = True

    # --- building collision
    for (bx, bz, w, d, h) in buildings:
        if abs(drone.x - bx) < w / 2 + 0.3 and abs(drone.z - bz) < d / 2 + 0.3 and drone.y < h + 0.1:
            return crash('hit a building')

    # --- rings
    for rg in rings:
        if rg['done']:
            continue
        crossed = (prev_z - rg['z']) * (drone.z - rg['z']) < 0
        if crossed and math.hypot(drone.x - rg['x'], drone.y - rg['y']) < RING_RADIUS:
            rg['done'] = True
            s.score += 50
            show('Ring! +50')
            for part in rg['parts']:
                part.color = color.lime


def update_camera(dt):
    y = math.radians(s.yaw)
    fwd = Vec3(math.sin(y), 0, math.cos(y))
    if s.cam_mode == 0:      # chase
        target = drone.position - fwd * 7 + Vec3(0, 2.5, 0)
        camera.position += (target - camera.position) * min(1, 5 * dt)
        camera.look_at(drone.position + Vec3(0, 0.5, 0))
    elif s.cam_mode == 1:    # FPV
        camera.position = drone.position + Vec3(0, 0.12, 0) + fwd * 0.3
        camera.rotation = (s.pitch, s.yaw, -s.roll)
    else:                    # high orbit
        target = drone.position + Vec3(0, 45, -35)
        camera.position += (target - camera.position) * min(1, 3 * dt)
        camera.look_at(drone.position)


def update():
    global toast_timer
    dt = time.dt
    if not s.crashed:
        flight(dt)
    for rt in rotors:
        rt.rotation_y += 1500 * (0.2 + s.throttle) * dt
    update_camera(dt)
    speed = math.sqrt(s.vx ** 2 + s.vy ** 2 + s.vz ** 2)
    hud.text = (f'ALT   {drone.y - GROUND_Y:6.1f} m\nSPEED {speed:6.1f} m/s\n'
                f'THR   {s.throttle * 100:5.0f} %\nSCORE {s.score}\n'
                f'CAM   {["Chase", "FPV", "Orbit"][s.cam_mode]}')
    if toast_timer > 0:
        toast_timer -= dt
        if toast_timer <= 0:
            toast.text = ''


def input(key):
    if key == 'r':
        reset()
    elif key == 'c':
        s.cam_mode = (s.cam_mode + 1) % 3
    elif key == 'h':
        help_text.enabled = not help_text.enabled
    elif key == 'escape':
        application.quit()


camera.position = (0, 3, -8)
app.run()

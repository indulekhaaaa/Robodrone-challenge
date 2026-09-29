"""Drone Flight Training Simulator - Python + Ursina (Panda3D)."""
from ursina import *
import math
import random

G = 9.81
MAX_TILT = 30.0          # degrees
HOVER = 0.5              # throttle where lift == gravity
HALF = 0.15              # half height of drone body
CRASH_SPEED = 4.5        # m/s vertical touchdown limit
CRASH_TILT = 15.0        # degrees
WORLD = 180

random.seed(7)
app = Ursina(title='Drone Flight Training Simulator', borderless=False)
window.exit_button.visible = False
window.fps_counter.enabled = True

# ---------------------------------------------------------------- world
Sky()
Entity(model='plane', scale=WORLD * 2, texture='white_cube',
       texture_scale=(WORLD, WORLD), color=color.rgb(70, 110, 70))

PADS = [
    ('HOME', Vec3(0, 0, 0), color.azure),
    ('PAD B', Vec3(60, 0, 60), color.yellow),
]
for name, pos, col in PADS:
    Entity(model='quad', rotation_x=90, position=(pos.x, 0.02, pos.z),
           scale=(8, 8), color=col)
    Text(text=name, parent=scene, position=(pos.x, 6, pos.z),
         scale=25, billboard=True, origin=(0, 0), color=color.white)

buildings = []  # (x, z, w, d, h)
while len(buildings) < 30:
    x, z = random.uniform(-WORLD + 15, WORLD - 15), random.uniform(-WORLD + 15, WORLD - 15)
    if any(math.hypot(x - p.x, z - p.z) < 16 for _, p, _ in PADS):
        continue
    w, d, h = random.uniform(6, 14), random.uniform(6, 14), random.uniform(10, 45)
    g = random.randint(90, 170)
    Entity(model='cube', position=(x, h / 2, z), scale=(w, h, d),
           texture='white_cube', texture_scale=(w / 3, h / 3),
           color=color.rgb(g, g, g + 20))
    buildings.append((x, z, w, d, h))

rings = []
RING_R = 4.0
for i in range(8):
    for _ in range(100):
        x, z = random.uniform(-90, 90), random.uniform(-90, 90)
        y = random.uniform(6, 22)
        if all(abs(x - b[0]) > b[2] / 2 + RING_R + 2 or abs(z - b[1]) > b[3] / 2 + RING_R + 2
               or y > b[4] + RING_R for b in buildings) and math.hypot(x, z) > 15:
            break
    ring = Entity(position=(x, y, z))
    for k in range(16):
        a = k / 16 * math.tau
        Entity(parent=ring, model='cube', color=color.orange, scale=(1.1, 1.1, 0.6),
               position=(math.cos(a) * RING_R, math.sin(a) * RING_R, 0))
    rings.append({'e': ring, 'done': False})

# ---------------------------------------------------------------- drone
drone = Entity(position=(0, HALF, 0))
Entity(parent=drone, model='cube', scale=(0.5, 0.15, 0.5), color=color.dark_gray)
Entity(parent=drone, model='cube', scale=(0.15, 0.1, 0.3), color=color.red, position=(0, 0.08, 0.2))  # nose marker
rotors = []
for sx, sz in [(1, 1), (-1, 1), (1, -1), (-1, -1)]:
    Entity(parent=drone, model='cube', scale=(0.6, 0.04, 0.04), color=color.gray,
           position=(sx * 0.3, 0, sz * 0.3), rotation_y=45 * sx * sz)
    rotors.append(Entity(parent=drone, model='cube', scale=(0.45, 0.01, 0.06),
                         color=color.white, position=(sx * 0.42, 0.08, sz * 0.42)))

# ---------------------------------------------------------------- state
S = dict(vel=Vec3(0, 0, 0), pitch=0.0, roll=0.0, yaw=0.0, throttle=0.0,
         grounded=True, scored_landing=False, crashed=False, score=0, cam=0,
         msg_t=0.0)

hud = Text(text='', position=(-0.87, 0.47), origin=(-0.5, 0.5), scale=1.2, color=color.white)
msg = Text(text='', origin=(0, 0), position=(0, 0.25), scale=2.5, color=color.yellow)
help_txt = Text(
    text=('SPACE/SHIFT throttle   W/S pitch   A/D roll   Q/E yaw\n'
          'R reset   C camera   H help   ESC quit\n'
          'Fly through orange rings, land on HOME / PAD B.'),
    origin=(0, 0.5), position=(0, -0.38), scale=1.1, color=color.light_gray)


def flash(text, t=1.5):
    msg.text = text
    S['msg_t'] = t


def reset():
    drone.position = Vec3(0, HALF, 0)
    S.update(vel=Vec3(0, 0, 0), pitch=0.0, roll=0.0, yaw=0.0, throttle=0.0,
             grounded=True, scored_landing=False, crashed=False)
    for r in rings:
        r['done'] = False
        r['e'].color = color.white


def crash(reason):
    if S['crashed']:
        return
    S['crashed'] = True
    S['vel'] = Vec3(0, 0, 0)
    flash(f'CRASH! {reason}', 2.0)
    invoke(reset, delay=2.0)


def land():
    """Called on first ground contact; scores precision landings."""
    for name, p, _ in PADS:
        d = math.hypot(drone.x - p.x, drone.z - p.z)
        if d < 4.5 and not S['scored_landing']:
            pts = int(200 * (1 - d / 4.5))
            S['score'] += pts
            S['scored_landing'] = True
            flash(f'{name} landing! +{pts}')
            return
    flash('Landed')


def update():
    dt = min(time.dt, 0.05)
    if S['crashed']:
        return

    hk = held_keys
    # throttle
    S['throttle'] += (hk['space'] - hk['left shift']) * 0.6 * dt
    S['throttle'] = max(0.0, min(1.0, S['throttle']))

    # attitude (smoothed toward commanded tilt, self-levels when released)
    k = min(1.0, 8 * dt)
    S['pitch'] += ((hk['w'] - hk['s']) * MAX_TILT - S['pitch']) * k
    S['roll'] += ((hk['d'] - hk['a']) * MAX_TILT - S['roll']) * k
    S['yaw'] += (hk['e'] - hk['q']) * 100 * dt

    pr, rr, yr = map(math.radians, (S['pitch'], S['roll'], S['yaw']))
    # thrust direction in body frame, then rotate by yaw
    lx, ly, lz = math.sin(rr), math.cos(pr) * math.cos(rr), math.sin(pr)
    tx = lx * math.cos(yr) + lz * math.sin(yr)
    tz = -lx * math.sin(yr) + lz * math.cos(yr)
    a = G * S["throttle"] / HOVER  # lift == gravity at hover throttle
    acc = Vec3(tx * a, ly * a - G, tz * a)

    v = S['vel'] + acc * dt
    v = Vec3(v.x * (1 - 0.6 * dt), v.y * (1 - 0.3 * dt), v.z * (1 - 0.6 * dt))  # air drag
    S['vel'] = v
    drone.position += v * dt
    drone.rotation = (S['pitch'], S['yaw'], S['roll'])

    # world bounds
    drone.x = max(-WORLD, min(WORLD, drone.x))
    drone.z = max(-WORLD, min(WORLD, drone.z))

    # ground contact
    if drone.y <= HALF:
        if not S['grounded']:
            tilt = max(abs(S['pitch']), abs(S['roll']))
            if -S['vel'].y > CRASH_SPEED:
                return crash('Descended too fast')
            if tilt > CRASH_TILT:
                return crash('Tilted landing')
            land()
        S['grounded'] = True
        drone.y = HALF
        S['vel'] = Vec3(v.x * 0.9 if S['throttle'] > 0.5 else 0, max(0, v.y), v.z * 0.9 if S['throttle'] > 0.5 else 0)
    else:
        S['grounded'] = False
        if drone.y > 1.5:
            S['scored_landing'] = False

    # building collision
    for bx, bz, w, d, h in buildings:
        if abs(drone.x - bx) < w / 2 + 0.3 and abs(drone.z - bz) < d / 2 + 0.3 and drone.y < h + 0.2:
            return crash('Hit a building')

    # rings
    for r in rings:
        if r['done']:
            continue
        p = r['e'].position
        if abs(drone.z - p.z) < 0.8 and math.hypot(drone.x - p.x, drone.y - p.y) < RING_R - 0.5:
            r['done'] = True
            r['e'].color = color.green
            S['score'] += 100
            flash('Ring! +100', 1.0)

    # visuals
    for rot in rotors:
        rot.rotation_y += 3000 * S['throttle'] * dt

    # camera
    fwd = Vec3(math.sin(yr), 0, math.cos(yr))
    if S['cam'] == 0:      # chase
        target = drone.position - fwd * 8 + Vec3(0, 3, 0)
        camera.position = lerp(camera.position, target, min(1, 6 * dt))
        camera.look_at(drone.position + Vec3(0, 1, 0))
    elif S['cam'] == 1:    # FPV
        camera.position = drone.position + Vec3(0, 0.1, 0) + fwd * 0.3
        camera.rotation = drone.rotation
    else:                  # high orbit
        camera.position = drone.position + Vec3(25, 35, -25)
        camera.look_at(drone.position)

    # HUD
    spd = math.hypot(v.x, v.z)
    hud.text = (f'ALT   {max(0, drone.y - HALF):6.1f} m\n'
                f'SPEED {spd:6.1f} m/s\n'
                f'THR   {S["throttle"] * 100:5.0f} %\n'
                f'RINGS {sum(r["done"] for r in rings)}/8\n'
                f'SCORE {S["score"]}')
    if S['msg_t'] > 0:
        S['msg_t'] -= dt
        if S['msg_t'] <= 0:
            msg.text = ''


def input(key):
    if key == 'r':
        reset()
    elif key == 'c':
        S['cam'] = (S['cam'] + 1) % 3
        flash(['Chase cam', 'FPV', 'High orbit'][S['cam']], 1.0)
    elif key == 'h':
        help_txt.enabled = not help_txt.enabled
    elif key == 'escape':
        application.quit()


camera.fov = 90
camera.position = (0, 3, -8)
app.run()
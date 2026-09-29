"""Drone Flight Training Simulator - Python + Ursina (Panda3D).

Graphics upgrade: mountain terrain with baked lighting, autumn/conifer forest,
golden-hour haze, drifting clouds, detailed drone with gimbal camera + blob shadow.
"""
from ursina import *
import math
import random
import wave
import struct

G = 9.81
MAX_TILT = 30.0          # degrees
HOVER = 0.5              # throttle where lift == gravity
HALF = 0.15              # half height of drone body
CRASH_SPEED = 4.5        # m/s vertical touchdown limit
CRASH_TILT = 15.0        # degrees
WORLD = 180
SESSION_TIME = 300.0     # seconds (5 min countdown, starts on takeoff)

random.seed(7)
app = Ursina(title='Drone Flight Training Simulator', borderless=False)
window.exit_button.visible = False
window.fps_counter.enabled = True
window.color = color.rgb(0.72, 0.82, 0.92)


# ---------------------------------------------------------------- helpers
def rgb(r, g, b):
    """0-255 colour helper (Ursina 8 expects 0-1 floats)."""
    return color.rgb(r / 255, g / 255, b / 255)


def shade(r, g, b, k=1.0):
    return color.rgb(min(1.0, r * k / 255), min(1.0, g * k / 255), min(1.0, b * k / 255))


def smooth(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def mix(c1, c2, t):
    return (c1[0] + (c2[0] - c1[0]) * t, c1[1] + (c2[1] - c1[1]) * t, c1[2] + (c2[2] - c1[2]) * t)


sky = Sky()

PADS = [
    ('HOME', Vec3(0, 0, 0)),
    ('PAD B', Vec3(60, 0, 60)),
]


# ---------------------------------------------------------------- terrain
def noise(x, z):
    """Cheap smooth pseudo-noise, roughly in [-1, 1]."""
    return (0.50 * math.sin(x * 0.019 + 1.3) * math.cos(z * 0.016 + 0.4)
            + 0.30 * math.sin(x * 0.043 + z * 0.037 + 2.0)
            + 0.20 * math.sin(z * 0.081 - x * 0.052 + 0.7))


def terrain_h(x, z):
    """Ground height: rolling hills in the play area, big mountains toward the edges,
    perfectly flat around the landing pads."""
    hills = 6 + 6 * noise(x, z)
    d = max(abs(x), abs(z))
    m = smooth((d - 95) / 180)
    ridge = (0.55 + 0.45 * math.sin(x * 0.025 + z * 0.018 + 1) * math.sin(z * 0.022 - x * 0.015)
             + 0.25 * abs(math.sin(x * 0.06 + z * 0.05)))
    h = hills + m * (30 + 110 * ridge)
    f = min(smooth((math.hypot(x - p.x, z - p.z) - 16) / 24) for _, p in PADS)
    return h * f


def build_terrain():
    half = WORLD + 150
    N = 176
    step = 2 * half / N
    H = [[terrain_h(-half + i * step, -half + j * step) for j in range(N + 1)] for i in range(N + 1)]
    sun = Vec3(0.45, 0.75, -0.35).normalized()
    verts, cols, tris = [], [], []
    olive, gold, rock, snow = (105, 115, 52), (196, 146, 52), (118, 108, 98), (240, 244, 250)
    for i in range(N + 1):
        for j in range(N + 1):
            x, z, h = -half + i * step, -half + j * step, H[i][j]
            hx = H[min(N, i + 1)][j] - H[max(0, i - 1)][j]
            hz = H[i][min(N, j + 1)] - H[i][max(0, j - 1)]
            n = Vec3(-hx, 2 * step, -hz).normalized()
            slope = 1 - n.y
            patch = noise(x * 1.7 + 40, z * 1.7 - 20)
            c = mix(olive, gold, smooth((patch + 0.2) / 0.8))
            c = mix(c, rock, smooth((h - 50) / 30) * 0.6)
            c = mix(c, rock, smooth((slope - 0.22) / 0.25))
            c = mix(c, snow, smooth((h - 78) / 22) * (1 - 0.5 * smooth((slope - 0.3) / 0.3)))
            light = 0.48 + 0.52 * max(0.0, n.dot(sun))
            jit = random.uniform(0.94, 1.06)
            warm = (1.06, 1.0, 0.9)
            verts.append(Vec3(x, h, z))
            cols.append(color.rgb(min(1, c[0] / 255 * light * warm[0] * jit),
                                  min(1, c[1] / 255 * light * warm[1] * jit),
                                  min(1, c[2] / 255 * light * warm[2] * jit)))
    for i in range(N):
        for j in range(N):
            a = i * (N + 1) + j
            b, c_, d = a + 1, a + N + 1, a + N + 2
            tris += [a, b, c_, c_, b, d]
    e = Entity(model=Mesh(vertices=verts, triangles=tris, colors=cols), double_sided=True)
    return e


build_terrain()

# landing pads
for name, pos in PADS:
    # concrete border, yellow pad, black "H" like a real helipad
    Entity(model='quad', rotation_x=90, position=(pos.x, 0.05, pos.z), scale=(10, 10), color=rgb(120, 120, 115))
    Entity(model='quad', rotation_x=90, position=(pos.x, 0.07, pos.z), scale=(8.5, 8.5), color=rgb(240, 200, 40))
    for dx in (-1.6, 1.6):
        Entity(model='quad', rotation_x=90, position=(pos.x + dx, 0.09, pos.z), scale=(1, 4.4), color=color.black)
    Entity(model='quad', rotation_x=90, position=(pos.x, 0.09, pos.z), scale=(3.2, 0.9), color=color.black)
    Text(text=name, parent=scene, position=(pos.x, 6, pos.z),
         scale=25, billboard=True, origin=(0, 0), color=color.black)

# ---------------------------------------------------------------- obstacles
BUILDING_COLORS = [(196, 164, 132), (170, 110, 90), (150, 150, 145), (220, 205, 175), (120, 130, 140)]
buildings = []  # (x, z, w, d, absolute_top_y)
while len(buildings) < 16:
    x, z = random.uniform(-WORLD + 15, WORLD - 15), random.uniform(-WORLD + 15, WORLD - 15)
    if any(math.hypot(x - p.x, z - p.z) < 26 for _, p in PADS):
        continue
    th = terrain_h(x, z)
    if th > 18:
        continue
    w, d, h = random.uniform(6, 14), random.uniform(6, 14), random.uniform(10, 40)
    top = th + h
    r_, g_, b_ = random.choice(BUILDING_COLORS)
    Entity(model='cube', position=(x, (th - 6 + top) / 2, z), scale=(w, top - th + 6, d),
           texture='white_cube', texture_scale=(w / 3, (h + 6) / 3), color=rgb(r_, g_, b_))
    Entity(model='cube', position=(x, top + 0.2, z), scale=(w + 0.3, 0.4, d + 0.3),
           color=rgb(r_ * 0.55, g_ * 0.55, b_ * 0.55))  # darker roof
    buildings.append((x, z, w, d, top))

rings = []
RING_R = 4.0
for i in range(8):
    for _ in range(100):
        x, z = random.uniform(-90, 90), random.uniform(-90, 90)
        y = terrain_h(x, z) + random.uniform(14, 26)   # always above the tree tops
        if all(abs(x - b[0]) > b[2] / 2 + RING_R + 2 or abs(z - b[1]) > b[3] / 2 + RING_R + 2
               or y > b[4] + RING_R for b in buildings) and math.hypot(x, z) > 15:
            break
    ring = Entity(position=(x, y, z))
    parts = []
    for k in range(16):
        a_ = k / 16 * math.tau
        parts.append(Entity(parent=ring, model='cube', color=color.orange, scale=(1.1, 1.1, 0.6),
                            position=(math.cos(a_) * RING_R, math.sin(a_) * RING_R, 0)))
    rings.append({'e': ring, 'parts': parts, 'done': False})


# ---------------------------------------------------------------- forest (one merged mesh)
def add_cone(V, T, C, x, y, z, r, h, col, sides=7):
    b = len(V)
    V.append(Vec3(x, y + h, z)); C.append(shade(*col, 1.25))
    rot = random.uniform(0, math.tau)
    for i in range(sides):
        a = rot + i / sides * math.tau
        V.append(Vec3(x + math.cos(a) * r, y, z + math.sin(a) * r)); C.append(shade(*col, 0.68))
    for i in range(sides):
        T += [b, b + 1 + (i + 1) % sides, b + 1 + i]


def add_blob(V, T, C, x, y, z, r, hh, col, sides=7):
    b = len(V)
    V.append(Vec3(x, y + hh, z)); C.append(shade(*col, 1.15))
    V.append(Vec3(x, y - hh * 0.8, z)); C.append(shade(*col, 0.6))
    rot = random.uniform(0, math.tau)
    for i in range(sides):
        a = rot + i / sides * math.tau
        V.append(Vec3(x + math.cos(a) * r, y, z + math.sin(a) * r)); C.append(shade(*col, 0.95))
    for i in range(sides):
        n0, n1 = b + 2 + i, b + 2 + (i + 1) % sides
        T += [b, n0, n1, b + 1, n1, n0]


AUTUMN = [(225, 130, 30), (240, 165, 40), (205, 95, 25), (215, 180, 50), (190, 70, 30)]
tree_grid = {}   # 10 m cells -> [(x, z, radius, top_y)]
TV, TT, TC = [], [], []
placed, tries = 0, 0
TREE_R = WORLD + 80
while placed < 3500 and tries < 40000:
    tries += 1
    x, z = random.uniform(-TREE_R, TREE_R), random.uniform(-TREE_R, TREE_R)
    th = terrain_h(x, z)
    if th > 60:
        continue
    if random.random() > 0.55 + 0.45 * noise(x * 1.3 + 11, z * 1.3 - 7):
        continue
    if any(math.hypot(x - p.x, z - p.z) < 20 for _, p in PADS):
        continue
    if any(abs(x - b[0]) < b[2] / 2 + 3 and abs(z - b[1]) < b[3] / 2 + 3 for b in buildings):
        continue
    s = random.uniform(0.8, 1.25)
    if noise(x * 0.9 - 30, z * 0.9 + 50) > 0.2:      # autumn patch
        add_cone(TV, TT, TC, x, th - 0.2, z, 0.28 * s, 2.6 * s, (85, 60, 40), 4)
        add_blob(TV, TT, TC, x, th + 4.0 * s, z, 2.2 * s, 2.4 * s, random.choice(AUTUMN))
        top, rad = th + 6.4 * s, 1.3 * s
    else:                                             # conifer
        g = random.randint(0, 20)
        col = (28 + g // 2, 72 + g, 40 + g // 2)
        H = 7.0 * s
        add_cone(TV, TT, TC, x, th + 0.3, z, 1.7 * s, H * 0.5, col)
        add_cone(TV, TT, TC, x, th + H * 0.3, z, 1.3 * s, H * 0.45, col)
        add_cone(TV, TT, TC, x, th + H * 0.55, z, 0.9 * s, H * 0.45, col)
        top, rad = th + H, 0.9 * s
    if abs(x) <= WORLD + 5 and abs(z) <= WORLD + 5:
        tree_grid.setdefault((int(x // 10), int(z // 10)), []).append((x, z, rad, top))
    placed += 1
Entity(model=Mesh(vertices=TV, triangles=TT, colors=TC), double_sided=True)


def tree_hit(px, py, pz):
    cx, cz = int(px // 10), int(pz // 10)
    for i in (cx - 1, cx, cx + 1):
        for j in (cz - 1, cz, cz + 1):
            for tx, tz, tr, top in tree_grid.get((i, j), ()):
                if py < top and (px - tx) ** 2 + (pz - tz) ** 2 < (tr + 0.3) ** 2:
                    return True
    return False


# ---------------------------------------------------------------- clouds
clouds = []
cloud_parts = []
for _ in range(16):
    c = Entity(position=(random.uniform(-350, 350), random.uniform(110, 170), random.uniform(-350, 350)))
    for _k in range(5):
        cloud_parts.append(Entity(parent=c, model='sphere',
                                  scale=(random.uniform(25, 45), random.uniform(8, 14), random.uniform(18, 30)),
                                  position=(random.uniform(-25, 25), random.uniform(-3, 3), random.uniform(-12, 12)),
                                  color=color.rgba(1, 1, 1, 0.9)))
    clouds.append(c)

# ---------------------------------------------------------------- drone
drone = Entity(position=(0, HALF, 0))
Entity(parent=drone, model='cube', scale=(0.34, 0.11, 0.52), color=rgb(205, 208, 212))              # body
Entity(parent=drone, model='sphere', scale=(0.30, 0.15, 0.46), position=(0, 0.04, 0), color=rgb(228, 231, 235))  # shell
Entity(parent=drone, model='cube', scale=(0.30, 0.04, 0.46), position=(0, -0.06, 0), color=rgb(50, 52, 56))      # belly
Entity(parent=drone, model='cube', scale=(0.08, 0.04, 0.10), color=color.red, position=(0, 0.11, 0.16))          # nose marker
for sx in (-1, 1):
    Entity(parent=drone, model='sphere', scale=0.05, color=rgb(20, 20, 24), position=(sx * 0.08, 0.0, 0.27))     # obstacle sensors
gimbal = Entity(parent=drone, model='sphere', scale=0.10, color=rgb(30, 30, 34), position=(0, -0.10, 0.20))
Entity(parent=gimbal, model='sphere', scale=0.5, color=rgb(60, 90, 120), position=(0, 0, 0.5))                  # lens

rotors, discs = [], []
for sx, sz in [(1, 1), (-1, 1), (1, -1), (-1, -1)]:
    Entity(parent=drone, model='cube', scale=(0.6, 0.035, 0.05), color=rgb(45, 48, 52),
           position=(sx * 0.3, 0, sz * 0.3), rotation_y=45 * sx * sz)                                          # arm
    Entity(parent=drone, model='sphere', scale=(0.11, 0.10, 0.11), color=rgb(60, 62, 66),
           position=(sx * 0.42, 0.03, sz * 0.42))                                                               # motor
    Entity(parent=drone, model='cube', scale=(0.02, 0.14, 0.02), color=rgb(40, 42, 46),
           position=(sx * 0.42, -0.08, sz * 0.42))                                                              # landing leg
    rot = Entity(parent=drone, position=(sx * 0.42, 0.09, sz * 0.42))
    Entity(parent=rot, model='cube', scale=(0.48, 0.008, 0.04), color=rgb(25, 25, 28))                          # blade
    rotors.append(rot)
    discs.append(Entity(parent=drone, model='circle', rotation_x=90, scale=0.5, double_sided=True,
                        position=(sx * 0.42, 0.095, sz * 0.42), color=color.rgba(0.9, 0.9, 0.9, 0)))           # motion blur

Entity(parent=drone, model='sphere', scale=0.06, color=color.red, position=(-0.42, 0.0, -0.42))      # port light
Entity(parent=drone, model='sphere', scale=0.06, color=color.green, position=(0.42, 0.0, -0.42))     # starboard light
beacon = Entity(parent=drone, model='sphere', scale=0.09, color=color.white, position=(0, -0.09, -0.15))  # blinking beacon

shadow = Entity(model='circle', rotation_x=90, double_sided=True, scale=1.4, color=color.rgba(0, 0, 0, 0.45))

# ---------------------------------------------------------------- state
S = dict(vel=Vec3(0, 0, 0), pitch=0.0, roll=0.0, yaw=0.0, throttle=0.0,
         grounded=True, scored_landing=False, crashed=False, score=0, cam=0,
         msg_t=0.0, timer=0.0, running=False, finished=False, best=None,
         left=SESSION_TIME, cd_started=False, over=False,
         battery=100.0, batt_warn=0,
         hold=True, lock=True, target=None, yaw_rate=0.0, cam_yaw=0.0, look=Vec3(0, 1, 0))

hud = Text(text='', position=(-0.87, 0.47), origin=(-0.5, 0.5), scale=1.2, color=color.white, background=True)
msg = Text(text='', origin=(0, 0), position=(0, 0.25), scale=2.5, color=color.yellow)
clock = Text(text='', origin=(0, 0), position=(0, 0.45), scale=2, color=color.white, background=True)
battery_txt = Text(text='', origin=(0.5, 0.5), position=(0.87, 0.47), scale=1.2, color=color.green, background=True)
help_txt = Text(
    text=('SPACE/SHIFT throttle   W/S pitch   A/D roll   Q/E yaw\n'
          'V altitude-hold   T target-lock   (Space/Shift = climb/descend)\n'
          'R restart   C camera   N weather   H help   ESC quit\n'
          'Fly through orange rings, land on HOME / PAD B.'),
    origin=(0, 0.5), position=(0, -0.38), scale=1.1, color=color.white, background=True)

assist_txt = Text(text='', origin=(0, 0), position=(0, 0.38), scale=1.1, color=color.cyan, background=True)


# ---------------------------------------------------------------- sound
# No audio files needed: the sounds are generated as .wav files at start-up.
SR = 22050


def _write_wav(path, samples):
    with wave.open(str(path), 'wb') as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(SR)
        f.writeframes(b''.join(struct.pack('<h', int(max(-1.0, min(1.0, v)) * 30000)) for v in samples))


def _make_sounds(folder):
    rng = random.Random(1)  # separate RNG so the world layout is unchanged
    motor = []
    for i in range(SR):
        t = i / SR
        tone = 0.5 * math.sin(math.tau * 110 * t) + 0.3 * math.sin(math.tau * 220 * t) + 0.2 * math.sin(math.tau * 330 * t)
        motor.append(0.8 * tone * (0.75 + 0.25 * math.sin(math.tau * 40 * t)))
    ding = []
    for i in range(int(SR * 0.5)):
        t = i / SR
        ding.append(0.6 * (math.sin(math.tau * 880 * t) + 0.5 * math.sin(math.tau * 1320 * t)) * math.exp(-6 * t))
    boom = []
    for i in range(int(SR * 0.8)):
        t = i / SR
        boom.append((0.7 * rng.uniform(-1, 1) + 0.6 * math.sin(math.tau * 60 * t)) * math.exp(-5 * t))
    _write_wav(folder / 'drone_motor.wav', motor)
    _write_wav(folder / 'drone_ding.wav', ding)
    _write_wav(folder / 'drone_boom.wav', boom)


_make_sounds(application.asset_folder)
motor_snd = Audio('drone_motor.wav', loop=True, autoplay=True, volume=0)
ding_snd = Audio('drone_ding.wav', loop=False, autoplay=False)
boom_snd = Audio('drone_boom.wav', loop=False, autoplay=False)


def update_sound():
    """Motor hum follows the throttle; silent when off, crashed or time is up."""
    on = not (S['crashed'] or S['over']) and S['throttle'] > 0.02
    motor_snd.volume = (0.25 + 0.55 * S['throttle']) if on else 0
    motor_snd.pitch = 0.7 + 0.9 * S['throttle']


# ---------------------------------------------------------------- post-flight report
REC = dict(active=False, t=0.0, acc=0.0, samples=[], batt0=100.0)
HAS_REPORT = [False]
chart_items = []

report_root = Entity(parent=camera.ui, enabled=False)
Entity(parent=report_root, model='quad', scale=(0.92, 0.56), position=(0, -0.09), z=0.05,
       color=color.rgba(0.04, 0.05, 0.08, 0.82))
Text(parent=report_root, text='POST-FLIGHT REPORT', origin=(0, 0), position=(0, 0.155), scale=1.2, color=color.yellow)
legend_alt = Text(parent=report_root, text='', origin=(-0.5, 0), position=(-0.43, -0.19), scale=0.8, color=color.cyan)
legend_spd = Text(parent=report_root, text='', origin=(-0.5, 0), position=(-0.43, -0.225), scale=0.8, color=color.orange)
legend_bat = Text(parent=report_root, text='', origin=(-0.5, 0), position=(-0.43, -0.26), scale=0.8, color=color.green)
time_txt = Text(parent=report_root, text='', origin=(-0.5, 0), position=(-0.43, -0.145), scale=0.7, color=color.light_gray)
stats_txt = Text(parent=report_root, text='', origin=(-0.5, 0.5), position=(0.04, 0.115), scale=0.85, color=color.white)
Text(parent=report_root, text='F: hide / show', origin=(0, 0), position=(0, -0.345), scale=0.7, color=color.gray)


def agl():
    """Altitude above the ground under the drone."""
    return max(0.0, drone.y - HALF - terrain_h(drone.x, drone.z))


def start_recording():
    REC.update(active=True, t=0.0, acc=0.0, samples=[], batt0=S['battery'])
    report_root.enabled = False


def record(dt, v):
    REC['t'] += dt
    REC['acc'] += dt
    if REC['acc'] >= 0.1:
        REC['acc'] -= 0.1
        REC['samples'].append((REC['t'], agl(), math.hypot(v.x, v.z),
                               S['battery'], Vec3(v.x, v.y, v.z)))


def _line(points, col):
    chart_items.append(Entity(parent=report_root, color=col,
                              model=Mesh(vertices=[Vec3(px, py, 0) for px, py in points], mode='line', thickness=2)))


def show_report(crash_reason=None, touch_speed=0.0, touch_tilt=0.0):
    REC['active'] = False
    smp = REC['samples']
    if len(smp) < (3 if crash_reason else 10):   # ignore tiny hops
        return
    T = smp[-1][0]
    max_alt = max(m[1] for m in smp)
    top = max(m[2] for m in smp)
    used = max(0.0, REC['batt0'] - smp[-1][3])

    vs = [m[4] for m in smp]
    if len(vs) >= 4:
        acc = [(vs[i] - vs[i - 1]) / 0.1 for i in range(1, len(vs))]
        jerk = [(acc[i] - acc[i - 1]).length() / 0.1 for i in range(1, len(acc))]
        sm = int(round(100 * math.exp(-(sum(jerk) / len(jerk)) / 20)))
        sm_label = 'very smooth' if sm >= 80 else 'smooth' if sm >= 60 else 'bumpy' if sm >= 40 else 'rough'
        sm_line = f'Smoothness: {sm}/100 ({sm_label})'
    else:
        sm_line = 'Smoothness: n/a (short flight)'

    if crash_reason:
        land_lines = ['Landing: CRASHED', f'  {crash_reason}']
    else:
        d, pad = min((math.hypot(drone.x - p.x, drone.z - p.z), n) for n, p in PADS)
        near = d < 4.5
        q = round(100 * (0.4 * max(0.0, 1 - touch_speed / CRASH_SPEED)
                         + 0.3 * max(0.0, 1 - touch_tilt / CRASH_TILT)
                         + 0.3 * (max(0.0, 1 - d / 4.5) if near else 0.0)))
        grade = 'excellent' if q >= 85 else 'good' if q >= 65 else 'rough' if q >= 40 else 'poor'
        land_lines = [f'Landing: {q}/100 ({grade})',
                      f'  {touch_speed:.1f} m/s down, {touch_tilt:.0f} deg tilt',
                      f'  {d:.1f} m from {pad} centre' if near else '  off the pad']

    stats_txt.text = '\n'.join([f'Duration: {T:.1f} s', f'Max altitude: {max_alt:.1f} m',
                                f'Top speed: {top:.1f} m/s', f'Battery used: {used:.0f} %',
                                '', sm_line, ''] + land_lines)
    legend_alt.text = f'Altitude (max {max_alt:.1f} m)'
    legend_spd.text = f'Speed (max {top:.1f} m/s)'
    legend_bat.text = 'Battery (0-100 %)'
    time_txt.text = f'time: 0 s to {T:.1f} s'

    for e in chart_items:
        destroy(e)
    chart_items.clear()
    x0, x1, y0, y1 = -0.43, 0.0, -0.12, 0.10
    _line([(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)], color.gray)
    pts = smp[::max(1, len(smp) // 120)]

    def xy(m, i, vmax):
        return (x0 + (x1 - x0) * m[0] / max(T, 0.1), y0 + (y1 - y0) * min(1.0, m[i] / vmax))

    _line([xy(m, 1, max(max_alt, 1.0)) for m in pts], color.cyan)
    _line([xy(m, 2, max(top, 1.0)) for m in pts], color.orange)
    _line([xy(m, 3, 100.0) for m in pts], color.green)
    report_root.enabled = True
    HAS_REPORT[0] = True


def fmt(t):
    m, sec = divmod(t, 60)
    return f'{int(m):02d}:{sec:05.2f}'


def flash(text, t=1.5):
    msg.text = text
    S['msg_t'] = t


def wrap180(a):
    return (a + 180) % 360 - 180


def pick_target():
    """Nearest ring that has not been flown through yet."""
    best, bd = None, 1e9
    for r in rings:
        if r['done']:
            continue
        d = (r['e'].position - drone.position).length()
        if d < bd:
            best, bd = r, d
    return best


def unhighlight():
    for r in rings:
        if not r['done']:
            for part in r['parts']:
                part.color = color.orange


overlay = Entity(parent=camera.ui, model='quad', scale=(4, 2), z=5, color=color.clear)

# name, sky/cloud tint, screen tint (r, g, b, alpha), fog (colour, (start, end)) or None
WEATHER = [
    ('Golden hour', (1.0, 0.93, 0.80), (1.0, 0.68, 0.22, 0.10), ((0.86, 0.80, 0.68), (70, 420))),
    ('Day', (1, 1, 1), (0, 0, 0, 0), ((0.72, 0.82, 0.92), (70, 420))),
    ('Sunset', (1.0, 0.62, 0.45), (0.9, 0.35, 0.1, 0.22), ((0.95, 0.6, 0.4), (80, 300))),
    ('Night', (0.12, 0.14, 0.30), (0.02, 0.03, 0.12, 0.6), ((0.03, 0.04, 0.1), (60, 250))),
    ('Foggy', (0.75, 0.78, 0.8), (0.75, 0.78, 0.8, 0.3), ((0.75, 0.78, 0.8), (15, 110))),
]
WX = [0]  # index of the current weather mode


def set_weather(i):
    name, sky_c, tint, fog = WEATHER[i]
    sky.color = color.rgb(*sky_c)
    overlay.color = color.rgba(*tint)
    for p in cloud_parts:
        p.color = color.rgba(sky_c[0], sky_c[1], sky_c[2], 0.9)
    if fog:
        scene.fog_color = color.rgb(*fog[0])
        scene.fog_density = fog[1]
        window.color = color.rgb(*fog[0])
    else:
        scene.fog_density = 0
    return name


def update_clock():
    m, sec = divmod(int(math.ceil(S['left'])), 60)
    clock.text = f'{m}:{sec:02d}' + ('' if S['cd_started'] else '  (starts on takeoff)')
    clock.color = color.red if S['left'] <= 30 else (color.yellow if S['left'] <= 60 else color.white)


def reset(hard=False):
    if hard:  # full restart: score and the 5-minute clock too
        S.update(score=0, left=SESSION_TIME, cd_started=False, over=False)
        msg.text = ''
        S['msg_t'] = 0.0
        update_clock()
        report_root.enabled = False
        HAS_REPORT[0] = False
        REC['active'] = False
    drone.position = Vec3(0, HALF, 0)
    S.update(vel=Vec3(0, 0, 0), pitch=0.0, roll=0.0, yaw=0.0, throttle=0.0,
             grounded=True, scored_landing=False, crashed=False,
             timer=0.0, running=False, finished=False,
             battery=100.0, batt_warn=0, target=None, yaw_rate=0.0, cam_yaw=0.0)
    for r in rings:
        r['done'] = False
        for part in r['parts']:
            part.color = color.orange


def crash(reason):
    if S['crashed']:
        return
    S['crashed'] = True
    S['vel'] = Vec3(0, 0, 0)
    flash(f'CRASH! {reason}', 2.0)
    boom_snd.play()
    show_report(crash_reason=reason)
    invoke(reset, delay=2.0)


def land():
    """Called on first ground contact; scores precision landings."""
    for name, p in PADS:
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
    update_sound()

    # drifting clouds
    for c in clouds:
        c.x += 3 * dt
        if c.x > 380:
            c.x = -380

    # 5-minute session countdown (runs through crashes, stops at 0)
    if S['cd_started'] and not S['over']:
        S['left'] -= dt
        if S['left'] <= 0:
            S['left'] = 0.0
            S['over'] = True
            msg.text = f'TIME UP!  Score {S["score"]}\nPress R to play again'
            S['msg_t'] = 0.0
    update_clock()
    if S['over']:
        S['vel'] = Vec3(0, 0, 0)
        return
    if S['crashed']:
        return

    hk = held_keys
    up_in = hk['space'] - hk['left shift']
    gh0 = terrain_h(drone.x, drone.z)
    alt_now = max(0.0, drone.y - HALF - gh0)

    # ---- target lock: pick the nearest unflown ring
    if S['lock']:
        if S['target'] is None or S['target']['done']:
            S['target'] = pick_target()
    else:
        S['target'] = None
    tgt = S['target']

    # ---- throttle: altitude-hold (smooth, climb-rate based) or classic manual
    if S['hold']:
        vs = up_in * 5.0                                   # commanded climb rate (m/s)
        if up_in < 0:
            vs = -min(5.0, 0.8 + alt_now * 0.6)            # gentle flare near the ground
        elif up_in == 0 and tgt is not None and hk['w'] and not S['grounded']:
            vs = max(-4.0, min(4.0, (tgt['e'].y - drone.y) * 0.8))   # line up with the ring
        ly0 = max(0.5, math.cos(math.radians(S['pitch'])) * math.cos(math.radians(S['roll'])))
        want = HOVER / ly0 + 0.10 * (vs - S['vel'].y)
        if S['grounded'] and up_in <= 0:
            want = 0.0
        S['throttle'] += (want - S['throttle']) * min(1.0, 6 * dt)
    else:
        S['throttle'] += up_in * 0.6 * dt
    S['throttle'] = max(0.0, min(1.0, S['throttle']))

    # battery: drains with throttle while flying (~4 min of hovering); motors cut at 0%
    if not S['grounded'] or S['throttle'] > 0.05:
        S['battery'] = max(0.0, S['battery'] - (0.1 + 0.64 * S['throttle']) * dt)
    if S['battery'] <= 0:
        S['throttle'] = 0.0
    level = 2 if S['battery'] <= 0 else (1 if S['battery'] <= 20 else 0)
    if level > S['batt_warn']:
        flash('Battery empty - press R' if level == 2 else 'Low battery!', 2.0)
    S['batt_warn'] = level

    # attitude (smoothed toward commanded tilt, self-levels when released)
    k = min(1.0, 6 * dt)
    S['pitch'] += ((hk['w'] - hk['s']) * MAX_TILT - S['pitch']) * k
    S['roll'] += ((hk['d'] - hk['a']) * MAX_TILT - S['roll']) * k
    yaw_in = hk['e'] - hk['q']
    want_rate = yaw_in * 90.0
    if tgt is not None and yaw_in == 0 and not S['grounded']:
        ddx, ddz = tgt['e'].x - drone.x, tgt['e'].z - drone.z
        if math.hypot(ddx, ddz) > 6:                       # stop steering once we're on top of it
            err = wrap180(math.degrees(math.atan2(ddx, ddz)) - S['yaw'])
            want_rate = max(-90.0, min(90.0, err * 2.2))
        else:
            want_rate = 0.0
    S['yaw_rate'] += (want_rate - S['yaw_rate']) * min(1.0, 5 * dt)
    S['yaw'] += S['yaw_rate'] * dt

    pr, rr, yr = map(math.radians, (S['pitch'], S['roll'], S['yaw']))
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

    # ground contact (terrain height under the drone)
    gh = terrain_h(drone.x, drone.z)
    if drone.y <= gh + HALF:
        if not S['grounded']:
            tilt = max(abs(S['pitch']), abs(S['roll']))
            if -S['vel'].y > CRASH_SPEED:
                return crash('Descended too fast')
            if tilt > CRASH_TILT:
                return crash('Tilted landing')
            land()
            show_report(touch_speed=-S['vel'].y, touch_tilt=tilt)
        S['grounded'] = True
        drone.y = gh + HALF
        S['vel'] = Vec3(v.x * 0.9 if S['throttle'] > 0.5 else 0, max(0, v.y), v.z * 0.9 if S['throttle'] > 0.5 else 0)
    else:
        S['grounded'] = False
        S['cd_started'] = True  # 5-minute clock starts on first takeoff
        if not REC['active']:
            start_recording()
        if not S['finished']:
            S['running'] = True  # ring stopwatch starts on takeoff
        if drone.y - gh > 1.5:
            S['scored_landing'] = False

    # building + tree collision
    for bx, bz, w, d, top in buildings:
        if abs(drone.x - bx) < w / 2 + 0.3 and abs(drone.z - bz) < d / 2 + 0.3 and drone.y < top + 0.2:
            return crash('Hit a building')
    if drone.y - gh < 10 and tree_hit(drone.x, drone.y, drone.z):
        return crash('Hit a tree')

    # rings
    for r in rings:
        if r['done']:
            continue
        p = r['e'].position
        if abs(drone.z - p.z) < 0.8 and math.hypot(drone.x - p.x, drone.y - p.y) < RING_R - 0.5:
            r['done'] = True
            for part in r['parts']:
                part.color = color.green
            S['score'] += 100
            flash('Ring! +100', 1.0)
            ding_snd.play()
            if all(x['done'] for x in rings) and not S['finished']:
                S['finished'] = True
                S['running'] = False
                if S['best'] is None or S['timer'] < S['best']:
                    S['best'] = S['timer']
                flash(f'ALL RINGS! Time {fmt(S["timer"])}', 3.0)

    if S['running']:
        S['timer'] += dt

    if REC['active']:
        record(dt, v)

    # visuals: spinning props with motion-blur discs, blinking beacon, ground shadow
    for rot in rotors:
        rot.rotation_y += 3000 * S['throttle'] * dt
    blur = max(0.0, min(0.28, (S['throttle'] - 0.15) * 0.5))
    for dsc in discs:
        dsc.color = color.rgba(0.9, 0.9, 0.9, blur)
    beacon.enabled = int(time.time() * 2) % 2 == 0
    alt = max(0.0, drone.y - HALF - gh)
    shadow.position = (drone.x, gh + 0.12, drone.z)
    shadow.scale = 1.4 + alt * 0.04
    shadow.color = color.rgba(0, 0, 0, max(0.08, 0.45 - alt * 0.012))

    # camera (never dips below the terrain)
    fwd = Vec3(math.sin(yr), 0, math.cos(yr))
    spd = math.hypot(v.x, v.z)
    if S['cam'] == 0:      # chase (heading and look-point are low-pass filtered)
        S['cam_yaw'] += wrap180(S['yaw'] - S['cam_yaw']) * min(1, 3 * dt)
        cy = math.radians(S['cam_yaw'])
        cf = Vec3(math.sin(cy), 0, math.cos(cy))
        target = drone.position - cf * (8 + min(spd, 15) * 0.25) + Vec3(0, 3, 0)
        target.y = max(target.y, terrain_h(target.x, target.z) + 2.0)
        camera.position = lerp(camera.position, target, min(1, 5 * dt))
        S['look'] = lerp(S['look'], drone.position + Vec3(0, 1, 0), min(1, 10 * dt))
        camera.look_at(S['look'])
    elif S['cam'] == 1:    # FPV
        camera.position = drone.position + Vec3(0, 0.1, 0) + fwd * 0.3
        camera.rotation = drone.rotation
    else:                  # high orbit
        camera.position = drone.position + Vec3(25, 35, -25)
        camera.y = max(camera.y, terrain_h(camera.x, camera.z) + 2.0)
        camera.look_at(drone.position)

    camera.fov = lerp(camera.fov, 85 + min(spd, 20) * 0.75, min(1, 3 * dt))   # speed feel

    # HUD
    hud.text = (f'ALT   {alt:6.1f} m\n'
                f'SPEED {spd:6.1f} m/s\n'
                f'THR   {S["throttle"] * 100:5.0f} %\n'
                f'RINGS {sum(r["done"] for r in rings)}/8\n'
                f'TIME  {fmt(S["timer"])}\n'
                f'BEST  {fmt(S["best"]) if S["best"] is not None else "--:--.--"}\n'
                f'SCORE {S["score"]}')
    if tgt is not None:
        ddx, ddz = tgt['e'].x - drone.x, tgt['e'].z - drone.z
        dist = (tgt['e'].position - drone.position).length()
        err = wrap180(math.degrees(math.atan2(ddx, ddz)) - S['yaw'])
        arrow = '<<' if err < -8 else ('>>' if err > 8 else '[ LOCKED ]')
        lock_line = f'LOCK RING {rings.index(tgt) + 1}  {dist:4.0f} m  {arrow}'
        pulse = 0.5 + 0.5 * math.sin(time.time() * 6)
        for part in tgt['parts']:
            part.color = color.rgb(1, 0.9, 0.2 + 0.8 * pulse)
    else:
        lock_line = 'LOCK ' + ('- none -' if S['lock'] else 'OFF')
    assist_txt.text = f'ALT-HOLD {"ON" if S["hold"] else "OFF"}   {lock_line}'

    pct = S['battery']
    n = int(round(pct / 5))
    battery_txt.text = f'BATTERY {pct:4.0f} %\n[{"=" * n}{"-" * (20 - n)}]'
    battery_txt.color = color.green if pct > 50 else (color.yellow if pct > 20 else color.red)
    if S['msg_t'] > 0:
        S['msg_t'] -= dt
        if S['msg_t'] <= 0:
            msg.text = ''


def input(key):
    if key == 'r':
        reset(hard=True)
    elif key == 'n':
        WX[0] = (WX[0] + 1) % len(WEATHER)
        name = set_weather(WX[0])
        if not S['over']:
            flash(f'{name} mode', 1.2)
    elif key == 'f' and HAS_REPORT[0]:
        report_root.enabled = not report_root.enabled
    elif key == 'c':
        S['cam'] = (S['cam'] + 1) % 3
        flash(['Chase cam', 'FPV', 'High orbit'][S['cam']], 1.0)
    elif key == 'v':
        S['hold'] = not S['hold']
        flash('Altitude hold ' + ('ON' if S['hold'] else 'OFF'), 1.0)
    elif key == 't':
        S['lock'] = not S['lock']
        S['target'] = None
        unhighlight()
        flash('Target lock ' + ('ON' if S['lock'] else 'OFF'), 1.0)
    elif key == 'h':
        help_txt.enabled = not help_txt.enabled
    elif key == 'escape':
        application.quit()


update_clock()
set_weather(0)
camera.fov = 90
camera.position = (0, 3, -8)
app.run()
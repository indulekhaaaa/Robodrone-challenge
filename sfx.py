"""Procedural sound effects for the drone simulator.

Sounds are generated as WAV files at startup (pure Python, no assets, no extra
dependencies), so the PyInstaller .exe needs nothing bundled.
"""
import math
import os
import random
import struct
import tempfile
import wave

RATE = 22050


# ------------------------------------------------------------ sound builders
def _tone(freq, dur, vol=1.0, decay=6.0):
    return [vol * math.sin(2 * math.pi * freq * i / RATE) * math.exp(-decay * i / RATE)
            for i in range(int(RATE * dur))]


def _noise(dur, vol=1.0, decay=6.0, seed=1):
    rng = random.Random(seed)
    return [vol * rng.uniform(-1, 1) * math.exp(-decay * i / RATE)
            for i in range(int(RATE * dur))]


def _mix(*tracks):
    n = max(len(t) for t in tracks)
    return [sum(t[i] for t in tracks if i < len(t)) for i in range(n)]


def _concat(*tracks):
    out = []
    for t in tracks:
        out.extend(t)
    return out


def _rotor():
    """1 second loop; every component has a whole number of cycles, so it loops cleanly."""
    out = []
    for i in range(RATE):
        t = i / RATE
        wobble = 0.6 + 0.4 * math.sin(2 * math.pi * 8 * t)
        out.append(0.45 * math.sin(2 * math.pi * 90 * t)
                   + 0.30 * math.sin(2 * math.pi * 180 * t)
                   + 0.20 * wobble * math.sin(2 * math.pi * 270 * t)
                   + 0.10 * math.sin(2 * math.pi * 540 * t))
    return out


def _write(path, samples):
    with wave.open(path, 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(b''.join(struct.pack('<h', int(max(-1, min(1, s)) * 32767)) for s in samples))


# ------------------------------------------------------------------ manager
class Sfx:
    """Usage: sfx = Sfx(app.loader), then call rotor(), ring(), crash(), thud(), chime()."""

    def __init__(self, loader):
        self.muted = False
        self.ok = False
        try:
            from panda3d.core import Filename
            folder = tempfile.mkdtemp(prefix='dronesim_sfx_')

            def load(name, samples):
                path = os.path.join(folder, name + '.wav')
                _write(path, samples)
                return loader.loadSfx(Filename.fromOsSpecific(path))

            self._rotor = load('rotor', _rotor())
            self._ring = load('ring', _mix(_tone(880, 0.5, 0.6, 7), _tone(1318.5, 0.5, 0.4, 7)))
            self._crash = load('crash', _mix(_noise(0.8, 0.5, 5), _tone(55, 0.8, 0.5, 4)))
            self._thud = load('thud', _mix(_tone(80, 0.25, 0.9, 14), _noise(0.1, 0.2, 30, seed=2)))
            self._chime = load('chime', _concat(_tone(523.25, 0.15, 0.6, 4),
                                                _tone(659.25, 0.15, 0.6, 4),
                                                _tone(783.99, 0.45, 0.6, 5)))
            self._rotor.setLoop(True)
            self._rotor.setVolume(0)
            self._rotor.play()
            self.ok = True
        except Exception as e:  # never let audio problems stop the sim
            print('Sound disabled:', e)

    def _play(self, snd, vol=1.0):
        if self.ok and not self.muted:
            snd.setVolume(vol)
            snd.play()

    def rotor(self, throttle):
        """Call every frame. Pitch and volume follow throttle (0..1); 0 = silent."""
        if not self.ok:
            return
        if self.muted or throttle < 0.02:
            self._rotor.setVolume(0)
            return
        self._rotor.setVolume(0.15 + 0.45 * throttle)
        self._rotor.setPlayRate(0.6 + 1.2 * throttle)

    def ring(self):
        self._play(self._ring, 0.7)

    def crash(self):
        self._play(self._crash, 1.0)

    def thud(self):
        self._play(self._thud, 0.8)

    def chime(self):
        self._play(self._chime, 0.8)

    def toggle_mute(self):
        self.muted = not self.muted
        return self.muted
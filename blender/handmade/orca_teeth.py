"""Orca teeth: a healthy row beside a row worn flat. Units are centimetres.

Facts the model is built from:
  * An orca has 10 to 14 cone-shaped teeth on each side of each jaw. They interlock when the mouth closes.
  * A whole tooth is about 10 to 13 cm long and roughly 2.5 cm across; a little under half of it stands above
    the gum, and the tip curves slightly backward.
  * Orcas that feed on sharks grind their teeth down on the rough skin. In such animals the crowns are worn flat,
    down to the gum line, and the dark pulp cavity in the middle of the tooth can be exposed.
Sources: NOAA Fisheries, killer whale species page; Ford et al. (2011), "Shark predation and tooth wear in a
  population of northeastern Pacific killer whales", Aquatic Biology 11.
Shown: two short pieces of lower jaw side by side, healthy teeth on the left, worn teeth on the right.
"""
import math
import random

import kit3d as k

NAMES = ["orca teeth", "killer whale teeth", "worn orca teeth", "orca tooth wear"]
TITLE = "Orca teeth: healthy and worn flat"
FRONT = 0
ELEVATION = 16
SWING = 24
SIZE = "1920x1080"
MARGIN = 1.12

SPACING = 4.6          # cm between teeth along the jaw
N = 5


def _tooth(name, x, y, crown, lean, worn=False):
    """One tooth standing on the gum at (x, y): `crown` cm above the gum; a worn tooth is a flat stump."""
    r = 1.25
    if worn:
        prof = [(0.0, -1.2), (r * 0.9, -1.2), (r, 0.0), (r * 0.98, crown * 0.7), (r * 0.9, crown), (r * 0.3, crown + 0.03), (0.0, crown + 0.03)]
    else:
        prof = [(0.0, -1.2), (r * 0.9, -1.2), (r, 0.0), (r * 0.9, crown * 0.3), (r * 0.62, crown * 0.65),
                (r * 0.3, crown * 0.9), (r * 0.1, crown * 0.99), (0.0, crown)]
    t = k.lathe(name, prof, segments=40)
    for v in t.data.vertices:                      # the tip curves back (toward -x here)
        h = max(0.0, v.co.z) / max(0.1, crown)
        v.co.x -= lean * h * h
    t.location = (x, y, 0.0)
    k.smooth(t, 60)
    return t


def _jaw(name, x0, worn, rnd):
    parts = []
    length = SPACING * N + 2.0
    gum = k.box(name + "_gum", (length, 5.2, 3.4), (x0 + length / 2 - 1.0 - SPACING / 2 + SPACING / 2, 0.0, -1.7))
    k.bevel(gum, 1.3, segments=6)
    k.subsurf(gum, 1)
    k.smooth(gum, 70)
    k.assign(gum, k.material(name + "_gum_m", (0.36, 0.20, 0.20), roughness=0.42, colour2=(0.24, 0.13, 0.14), variation_scale=0.5, bump=0.12, bump_scale=3.0))
    parts.append(gum)
    ivory = k.material(name + "_ivory", (0.80, 0.74, 0.60), roughness=0.32, colour2=(0.62, 0.52, 0.36), variation_scale=0.6)
    pulp = k.material(name + "_pulp", (0.10, 0.06, 0.05), roughness=0.6)
    for i in range(N):
        x = x0 + i * SPACING + SPACING / 2
        if worn:
            h = rnd.uniform(0.25, 0.7)
            t = _tooth(f"{name}_t{i}", x, 0.0, h, 0.0, worn=True)
            k.assign(t, ivory)
            dot = k.cylinder(f"{name}_p{i}", 0.42, 0.06, (x, 0.0, h + 0.03), segments=24)
            k.assign(dot, pulp)
            parts += [t, dot]
        else:
            t = _tooth(f"{name}_t{i}", x, 0.0, rnd.uniform(4.6, 5.4), rnd.uniform(0.7, 1.0))
            k.assign(t, ivory)
            parts.append(t)
    return parts


def build():
    rnd = random.Random(3)
    half = SPACING * N + 2.0
    return _jaw("healthy", -half - 1.2, False, rnd) + _jaw("worn", 1.2, True, rnd)

"""The Great Pyramid of Giza (pyramid of Khufu) as it stands today.

Facts the model is built from (metres):
  base                230.3 on each side, sides facing the four cardinal points
  height              138.5 today (146.6 when built: the capstone and the smooth casing stones are gone)
  slope               about 51.8 degrees, which the base and original height give
  courses             203 courses of core limestone blocks remain; they are thickest at the bottom (about 1.5)
                      and thin toward the top (about 0.55), with a few thicker bands on the way up (e.g. course 35)
  top                 a flat platform about 12 across where the last courses and capstone are missing
  original entrance   on the NORTH face, about 17 above the ground and 7.3 EAST of the centre line, under two
                      layers of huge gabled (inverted-V) limestone blocks
  robbers' tunnel     the opening tourists use today, cut in AD 820 for caliph al-Ma'mun: lower (about 7 up) and
                      on the centre line of the north face
  stone               yellowish-grey local limestone, weathered and stepped (no casing)

Sources: M. Lehner, The Complete Pyramids (1997); W. M. F. Petrie, The Pyramids and Temples of Gizeh (1883)
(course heights, entrance position); J. Romer, The Great Pyramid (2007).
"""
import math
import random

import bmesh
import bpy
from mathutils import Matrix, Vector

import kit3d as k

NAMES = ["great pyramid of giza", "great pyramid", "pyramid of khufu", "khufu pyramid", "pyramid of cheops", "pyramids giza"]
TITLE = "Great Pyramid of Giza"
FRONT = 180        # show the north face (the one with the entrances) to the camera
ELEVATION = 12

BASE, H_NOW, H_ORIG, COURSES = 230.3, 138.5, 146.6, 203


def course_heights() -> list[float]:
    """203 course heights that add up to today's height: thick at the bottom, thinner above, with thicker bands."""
    thick = {35: 1.27, 36: 1.0, 44: 1.05, 67: 0.9, 90: 0.95, 98: 1.0, 118: 0.9, 144: 0.8}
    hs = []
    for i in range(COURSES):
        t = i / (COURSES - 1)
        h = 0.55 + (1.5 - 0.55) * math.exp(-t * 9.0)       # 1.5 m at the base, settling to about 0.55 m
        hs.append(thick.get(i + 1, h))
    scale = H_NOW / sum(hs)
    return [h * scale for h in hs]


def half_side(z: float) -> float:
    return BASE / 2 * (1 - z / H_ORIG)


def build():
    rnd = random.Random(2560)        # the same pyramid every time
    stone = k.material("limestone", (0.50, 0.375, 0.20), roughness=0.92, colour2=(0.33, 0.245, 0.135), variation_scale=0.045,
                       bump=0.35, bump_scale=0.22, blocks={"size": (1.5, 400.0), "mortar": 0.03, "depth": 0.3, "wrap": True})
    dark = k.material("opening", (0.015, 0.012, 0.01), roughness=1.0)
    gable = k.material("gable limestone", (0.66, 0.56, 0.38), roughness=0.85, bump=0.3, bump_scale=1.0)
    bedrock = k.material("bedrock", (0.40, 0.31, 0.18), roughness=0.95, colour2=(0.50, 0.40, 0.24), variation_scale=0.03,
                         bump=0.6, bump_scale=0.3)

    # cut-outs in the north face (x0, x1, z0, z1, depth): the original entrance under its gables, and al-Ma'mun's tunnel
    ENT_X, ENT_Z = 7.3, 17.0
    notches = [(ENT_X - 5.5, ENT_X + 5.5, ENT_Z - 1.5, ENT_Z + 9.5, 4.5),
               (-2.6, 2.6, 5.6, 9.4, 3.0)]

    bm = bmesh.new()

    def add_box(x0, x1, y0, y1, z0, z1):
        if x1 - x0 <= 0.01 or y1 - y0 <= 0.01:
            return
        m = bmesh.ops.create_cube(bm, size=1.0)
        for v in m["verts"]:
            v.co = Vector((x0 + (v.co.x + 0.5) * (x1 - x0), y0 + (v.co.y + 0.5) * (y1 - y0), z0 + (v.co.z + 0.5) * (z1 - z0)))

    z = 0.0
    for h in course_heights():
        a = half_side(z + h * 0.5) + rnd.uniform(-0.12, 0.12)      # each course is laid slightly unevenly
        cut = [n for n in notches if n[2] < z + h and n[3] > z]
        if not cut:
            add_box(-a, a, -a, a, z, z + h)
        else:
            x0, x1, _z0, _z1, depth = cut[0]
            add_box(-a, a, -a, a - depth, z, z + h)               # the body, set back behind the opening
            add_box(-a, x0, a - depth, a, z, z + h)               # the face west of the opening
            add_box(x1, a, a - depth, a, z, z + h)                # the face east of it
        z += h
    body = k.new_object("Great Pyramid", bm)
    k.assign(body, stone)

    parts = [body]
    # the gabled blocks over the original entrance: two layers of paired slabs leaning together (an inverted V)
    back = half_side(ENT_Z + 4.0) - 4.5
    for layer, (zc, length) in enumerate([(ENT_Z + 3.2, 4.6), (ENT_Z + 6.0, 5.2)]):
        for side in (-1, 1):
            slab = k.box(f"gable {layer}{'W' if side < 0 else 'E'}", (length, 1.6, 1.15))
            slab.matrix_world = (Matrix.Translation((ENT_X + side * length * 0.36, back + 0.9, zc))
                                 @ Matrix.Rotation(math.radians(38 * side), 4, "Y"))   # the pair meets at the TOP: Λ
            k.assign(slab, gable)
            k.bevel(slab, 0.06, 1)
            parts.append(slab)
    lintel = k.box("lintel", (3.2, 1.6, 0.9), (ENT_X, back + 0.9, ENT_Z + 1.35))
    k.assign(lintel, gable)
    parts.append(lintel)
    door = k.box("original entrance", (1.05, 0.5, 1.2), (ENT_X, back + 0.3, ENT_Z + 0.3))
    k.assign(door, dark)
    parts.append(door)
    tunnel_back = half_side(7.5) - 3.0
    tunnel = k.box("robbers tunnel", (2.2, 0.5, 2.4), (0.0, tunnel_back + 0.3, 7.4))
    k.assign(tunnel, dark)
    parts.append(tunnel)

    # the rock it stands on: a low, uneven platform a little wider than the base
    bmg = bmesh.new()
    bmesh.ops.create_grid(bmg, x_segments=48, y_segments=48, size=BASE * 0.56)
    for v in bmg.verts:
        edge = max(abs(v.co.x), abs(v.co.y)) / (BASE * 0.56)
        v.co.z = -0.4 - 3.0 * max(0.0, edge - 0.9) / 0.1 + rnd.uniform(-0.15, 0.15)
    ground = k.new_object("bedrock", bmg)
    k.solidify(ground, 2.5)
    k.assign(ground, bedrock)
    k.smooth(ground, 60)
    parts.append(ground)
    return parts

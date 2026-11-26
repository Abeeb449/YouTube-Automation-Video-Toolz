"""Shark skin under a microscope (dermal denticles of a great white). Units here are millimetres.

Facts the model is built from:
  * A shark's skin is covered in placoid scales, also called dermal denticles ("skin teeth"). Each one is built
    like a tooth: a hard enamel-like crown on a short stalk rooted in the skin.
  * On a fast shark such as the great white the crowns are small, about 0.2 to 0.5 mm long, and packed tightly.
  * Each crown carries ridges (usually three) running front to back and ending in points that face the tail.
  * The crowns overlap like roof tiles, pointing backward, which is why the skin feels smooth stroked toward the
    tail and like sandpaper stroked toward the head.
Sources: Smithsonian Ocean, "Shark skin"; Florida Museum of Natural History, ichthyology (placoid scales);
  Reif, W.-E. (1985) on the squamation of sharks.
Left out on purpose: the stalks' roots and the soft skin between them cannot be seen from above, so only the
  stalk tops and a plain skin surface are modelled.
"""
import math
import random

import kit3d as k

NAMES = ["shark skin", "dermal denticles", "shark scales", "placoid scales", "great white shark skin"]
TITLE = "Shark skin (dermal denticles)"
FRONT = 20            # the points of the scales face the viewer's right and slightly away
ELEVATION = 56        # looked at from above, at a slant, as under a microscope
SWING = 18
SIZE = "1920x1080"
MARGIN = 0.46         # the patch fills the picture and runs past its edges
SUN = {"azimuth": 115, "elevation": 20, "strength": 5.2, "colour": (1.0, 0.95, 0.88), "sky": (0.30, 0.36, 0.44), "sky_strength": 0.6}

L, W = 0.40, 0.30     # one crown: length and width, mm
COLS, ROWS = 15, 18


def _crown(verts, quads, tints, cx, cy, rot, size, tint):
    """One crown: a shield that rises toward the rear, with three ridges that end in three points."""
    nu, nv = 12, 12
    base = len(verts)
    c, s = math.cos(rot), math.sin(rot)
    for layer in (0, 1):                                  # top surface, then the underside (it has thickness)
        for i in range(nu + 1):
            u = i / nu
            for j in range(nv + 1):
                v = -1 + 2 * j / nv
                ridge = math.cos(1.5 * math.pi * v) ** 2          # 1 on the three ridges (v = -2/3, 0, 2/3), 0 between
                end = 1.0 - 0.30 * (1 - ridge)                    # the rear edge is scalloped into three points
                x = (u * end - 0.45) * L * size
                half = (0.30 + 0.70 * math.sin(math.pi * min(1.0, u * 1.15 + 0.12)) ** 0.8) * (W / 2) * size
                y = v * half
                z = (0.05 + 0.20 * u ** 1.3) * size + 0.070 * size * ridge ** 1.5 * (0.25 + 0.75 * u)
                z -= 0.022 * size * abs(v) ** 2                   # the crown is slightly arched side to side
                if layer:
                    z -= 0.035 * size
                verts.append((cx + x * c - y * s, cy + x * s + y * c, z))
                tints.append(tint * (0.70 + 0.5 * ridge ** 2 * (0.4 + 0.6 * u)))
    row = nv + 1
    for layer in (0, 1):
        off = base + layer * (nu + 1) * row
        for i in range(nu):
            for j in range(nv):
                a = off + i * row + j
                q = (a, a + row, a + row + 1, a + 1)
                quads.append(q if not layer else q[::-1])
    under = base + (nu + 1) * row
    for i in range(nu):                                   # close the two long edges and the two ends
        for j in (0, nv):
            a, b = base + i * row + j, base + (i + 1) * row + j
            quads.append((a, b, under + (i + 1) * row + j, under + i * row + j) if j else (b, a, under + i * row + j, under + (i + 1) * row + j))
    for j in range(nv):
        for i in (0, nu):
            a, b = base + i * row + j, base + i * row + j + 1
            quads.append((b, a, under + i * row + j, under + i * row + j + 1) if i else (a, b, under + i * row + j + 1, under + i * row + j))


def build():
    rnd = random.Random(5)
    verts, quads, tints = [], [], []
    px, py = L * 0.80, W * 1.30                            # spacing: each crown overlaps the one behind it a little, like roof tiles
    for r in range(ROWS):
        for cidx in range(COLS):
            cx = (cidx - COLS / 2 + (0.5 if r % 2 else 0.0)) * px + rnd.uniform(-0.012, 0.012)
            cy = (r - ROWS / 2) * py * 0.5 + rnd.uniform(-0.01, 0.01)
            _crown(verts, quads, tints, cx, cy, rnd.uniform(-0.07, 0.07), rnd.uniform(0.92, 1.08), rnd.uniform(0.85, 1.12))
    scales = k.mesh_from_arrays("denticles", verts, quads, tints)
    k.smooth(scales, 50)
    k.assign(scales, k.stone_material("enamel", colour=(0.50, 0.54, 0.57), dust=(0.70, 0.74, 0.76), stain=(0.20, 0.23, 0.26), grain=0.15))
    for m in scales.data.materials:
        m.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.32
    skin = k.box("skin", (COLS * px * 1.02, ROWS * py * 0.5 * 1.04, 0.05), (0.0, -py * 0.25, 0.0))
    k.assign(skin, k.material("skin", (0.10, 0.12, 0.14), roughness=0.7))
    return [scales, skin]

"""The Great Pyramid of Giza (pyramid of Khufu) as it stands today.

Facts the model is built from (metres):
  base                230.3 on each side, sides facing the four cardinal points
  height              138.5 today (146.6 when built: the capstone and the smooth casing stones are gone)
  slope               about 51.8 degrees, which the base and original height give
  courses             203 courses of core limestone blocks remain; they are thickest at the bottom (about 1.5)
                      and thin toward the top (about 0.55), with a few thicker bands on the way up (e.g. course 35)
  blocks              rough core blocks, mostly 1 to 2 wide, laid unevenly; the corners and edges are the most broken
  top                 a flat platform about 12 across where the last courses and capstone are missing, with a few
                      loose blocks and a metal mast that marks the original height (8.1 above the platform)
  original entrance   on the NORTH face, about 17 above the ground and 7.3 EAST of the centre line, under two
                      layers of huge gabled (inverted-V) limestone blocks
  robbers' tunnel     the opening tourists use today, cut in AD 820 for caliph al-Ma'mun: lower (about 7 up) and
                      on the centre line of the north face
  stone               yellowish-grey local limestone, weathered brown in patches, pale dust on every ledge
  ground              the levelled rock of the Giza plateau and desert sand, with fallen stone along the base

Left out on purpose (their exact positions were not checked): the three queens' pyramids to the east, the boat
pits, the other Giza pyramids, and the 19th-century gash on the south face.

Sources: M. Lehner, The Complete Pyramids (1997); W. M. F. Petrie, The Pyramids and Temples of Gizeh (1883)
(course heights, entrance position); J. Romer, The Great Pyramid (2007).
"""
import math
import random

import kit3d as k
from mathutils import Matrix

NAMES = ["great pyramid of giza", "great pyramid", "pyramid of khufu", "khufu pyramid", "pyramid of cheops", "pyramids giza"]
TITLE = "Great Pyramid of Giza"
FRONT = 180        # show the north face (the one with the entrances) to the camera
ELEVATION = 9
SIZE = "1920x1080"
MARGIN = 1.5        # room around the pyramid for the desert it stands on
SUN = {"azimuth": 68, "elevation": 27, "strength": 4.2, "sky": (0.30, 0.33, 0.40), "sky_strength": 0.5}     # low afternoon sun from the west, raking across the north face

BASE, H_NOW, H_ORIG, COURSES = 230.3, 138.5, 146.6, 203
ENT_X, ENT_Z = 7.3, 17.0
# openings in the north face (x0, x1, z0, z1, depth): the original entrance under its gables, and al-Ma'mun's tunnel
NOTCHES = [(ENT_X - 5.5, ENT_X + 5.5, ENT_Z - 1.5, ENT_Z + 9.5, 4.5), (-2.6, 2.6, 5.6, 9.4, 3.0)]


def course_heights() -> list[float]:
    """203 course heights that add up to today's height: thick at the bottom, thinner above, with thicker bands."""
    thick = {35: 1.27, 36: 1.0, 44: 1.05, 67: 0.9, 90: 0.95, 98: 1.0, 118: 0.9, 144: 0.8}
    hs = []
    for i in range(COURSES):
        t = i / (COURSES - 1)
        hs.append(thick.get(i + 1, 0.55 + (1.5 - 0.55) * math.exp(-t * 9.0)))
    scale = H_NOW / sum(hs)
    return [h * scale for h in hs]


def half_side(z: float) -> float:
    return BASE / 2 * (1 - z / H_ORIG)


# the four faces: (outward normal, direction along the face)
FACES = {"N": ((0, 1), (1, 0)), "S": ((0, -1), (1, 0)), "E": ((1, 0), (0, 1)), "W": ((-1, 0), (0, 1))}


def build():
    rnd = random.Random(2560)        # the same pyramid every time
    verts, quads, tints = [], [], []

    def quad(p0, p1, p2, p3, tint, normal):
        """One four-sided face, wound so that it faces `normal`."""
        ax, ay, az = p1[0] - p0[0], p1[1] - p0[1], p1[2] - p0[2]
        bx, by, bz = p3[0] - p0[0], p3[1] - p0[1], p3[2] - p0[2]
        n = (ay * bz - az * by, az * bx - ax * bz, ax * by - ay * bx)
        pts = (p0, p1, p2, p3) if n[0] * normal[0] + n[1] * normal[1] + n[2] * normal[2] >= 0 else (p0, p3, p2, p1)
        i = len(verts)
        verts.extend(pts)
        tints.extend((tint,) * 4)
        quads.append((i, i + 1, i + 2, i + 3))

    def at(face, s, depth_from_centre, z):
        (nx, ny), (ux, uy) = FACES[face]
        return (nx * depth_from_centre + ux * s, ny * depth_from_centre + uy * s, z)

    def block(face, s0, s1, front, z0, z1, back, tint):
        """One stone block of a course: its front, its top (the step you would stand on) and its two ends."""
        (nx, ny), (ux, uy) = FACES[face]
        n3, up, u3 = (nx, ny, 0), (0, 0, 1), (ux, uy, 0)
        quad(at(face, s0, front, z0), at(face, s1, front, z0), at(face, s1, front, z1), at(face, s0, front, z1), tint, n3)
        quad(at(face, s0, front, z1), at(face, s1, front, z1), at(face, s1, back, z1), at(face, s0, back, z1), tint * 1.04, up)
        quad(at(face, s0, front, z0), at(face, s0, back, z0), at(face, s0, back, z1), at(face, s0, front, z1), tint * 0.9,
             (-u3[0], -u3[1], 0))
        quad(at(face, s1, front, z0), at(face, s1, back, z0), at(face, s1, back, z1), at(face, s1, front, z1), tint * 0.9, u3)

    hs = course_heights()
    zs = [0.0]
    for h in hs:
        zs.append(zs[-1] + h)
    for ci, h in enumerate(hs):
        z0, z1 = zs[ci], zs[ci + 1]
        a = half_side(z0 + h * 0.5)
        a_next = half_side(z1 + (hs[ci + 1] * 0.5 if ci + 1 < COURSES else 0.0))
        tread = (a - a_next) + 0.9                       # how far the top of a block runs back under the next course
        size = 1.0 - 0.3 * ci / COURSES                  # blocks get a little smaller toward the top
        for face in FACES:
            # an opening is a ragged gash, not a neat window: its edges wander from course to course
            cut = [(n[0] + rnd.uniform(-1.3, 0.6), n[1] + rnd.uniform(-0.6, 1.3), n[2], n[3], n[4])
                   for n in NOTCHES if face == "N" and n[2] < z1 and n[3] > z0]
            # the solid core behind the blocks (seen only through gaps and where blocks are missing)
            spans = [(-a, a, 0.9)]
            if cut:
                x0, x1, _z0, _z1, depth = cut[0]
                spans = [(-a, x0, 0.9), (x0, x1, depth), (x1, a, 0.9)]
                n3 = (0, 1, 0)
                for xs in (x0, x1):                       # the side walls of the opening
                    quad(at(face, xs, a - 0.9, z0), at(face, xs, a - depth, z0), at(face, xs, a - depth, z1),
                         at(face, xs, a - 0.9, z1), 0.62, (1 if xs == x0 else -1, 0, 0))
            for s0, s1, depth in spans:
                (nx, ny), _u = FACES[face]
                quad(at(face, s0, a - depth, z0), at(face, s1, a - depth, z0), at(face, s1, a - depth, z1),
                     at(face, s0, a - depth, z1), 0.5 if depth < 1 else 0.7, (nx, ny, 0))
            # the blocks of this course, one after another along the face
            s = -a
            while s < a - 0.2:
                w = min(rnd.uniform(0.95, 2.0) * size, a - s)
                s0, s1 = s, s + w - 0.035                 # a hair's gap: the joint between two blocks
                s += w
                if cut and s1 > cut[0][0] and s0 < cut[0][1]:
                    # inside an opening the outer blocks are gone: what shows is the rough masonry further in
                    deep = cut[0][4] + rnd.uniform(-0.5, 0.3)
                    block(face, s0, s1, a - deep, z0, z1, a - deep - 1.2, rnd.uniform(0.55, 0.8))
                    continue
                edge = min(s0 + a, a - s1)                # distance to the nearest corner of the pyramid
                setback = rnd.uniform(0.0, 0.2)
                r = rnd.random()
                if edge < 5.0 and r < 0.38:               # corners are the most broken part
                    setback = rnd.uniform(0.35, 1.25) * (1 - edge / 8.0)
                elif r < 0.03:                            # here and there a block has fallen out or broken back
                    setback = rnd.uniform(0.5, 1.0)
                tint = rnd.uniform(0.8, 1.08)
                r2 = rnd.random()
                if r2 < 0.07:
                    tint = rnd.uniform(0.6, 0.76)         # a darker, more weathered stone
                elif r2 > 0.95:
                    tint = rnd.uniform(1.1, 1.2)          # a paler one
                block(face, s0, s1, a - setback, z0, z1 - rnd.uniform(0.0, 0.07) * h, a - setback - tread, tint)
    # floor and ceiling of the two openings, so nothing shows through
    for x0, x1, zc0, zc1, depth in NOTCHES:
        for zz, up in ((zc0, 1), (zc1, -1)):
            a = half_side(zz)
            quad(at("N", x0, a - 0.5, zz), at("N", x1, a - 0.5, zz), at("N", x1, a - depth - 0.5, zz),
                 at("N", x0, a - depth - 0.5, zz), 0.7, (0, 0, up))

    # the top platform and the few loose blocks left on it
    top = half_side(H_NOW)
    quad((-top, -top, H_NOW), (top, -top, H_NOW), (top, top, H_NOW), (-top, top, H_NOW), 0.95, (0, 0, 1))
    for _ in range(14):
        bx, by = rnd.uniform(-top + 1, top - 2), rnd.uniform(-top + 1, top - 2)
        w, d, hh = rnd.uniform(0.8, 1.8), rnd.uniform(0.7, 1.3), rnd.uniform(0.35, 0.6)
        block("N", bx, bx + w, by + d, H_NOW, H_NOW + hh, by, rnd.uniform(0.75, 1.05))
        quad((bx, by, H_NOW), (bx + w, by, H_NOW), (bx + w, by, H_NOW + hh), (bx, by, H_NOW + hh), 0.85, (0, -1, 0))

    # fallen stone along the foot of each face
    for face in FACES:
        for _ in range(170):
            s = rnd.uniform(-BASE / 2 - 4, BASE / 2 + 4)
            out = BASE / 2 + abs(rnd.gauss(0, 4.5)) + 0.4
            w, d, hh = rnd.uniform(0.5, 1.7), rnd.uniform(0.5, 1.4), rnd.uniform(0.25, 0.9)
            block(face, s, s + w, out + d, -0.05, hh, out, rnd.uniform(0.7, 1.1))

    body = k.mesh_from_arrays("Great Pyramid", verts, quads, tints)
    k.assign(body, k.stone_material("limestone", colour=(0.56, 0.42, 0.23), dust=(0.70, 0.58, 0.38), stain=(0.30, 0.21, 0.11)))
    parts = [body]

    # the gabled blocks over the original entrance: two layers of paired slabs leaning together (an inverted V)
    gable = k.material("gable limestone", (0.62, 0.50, 0.31), roughness=0.9, colour2=(0.50, 0.39, 0.23), variation_scale=0.4,
                       bump=0.4, bump_scale=1.2)
    dark = k.material("opening", (0.012, 0.01, 0.008), roughness=1.0)
    back = half_side(ENT_Z + 4.0) - 4.5
    for layer, (zc, length) in enumerate([(ENT_Z + 3.2, 4.6), (ENT_Z + 6.0, 5.2)]):
        for side in (-1, 1):
            slab = k.box(f"gable {layer}{'W' if side < 0 else 'E'}", (length, 1.6, 1.15))
            slab.matrix_world = (Matrix.Translation((ENT_X + side * length * 0.36, back + 0.9, zc))
                                 @ Matrix.Rotation(math.radians(38 * side), 4, "Y"))   # the pair meets at the TOP: Λ
            k.assign(slab, gable)
            k.bevel(slab, 0.07, 2)
            parts.append(slab)
    lintel = k.box("lintel", (3.4, 1.6, 0.95), (ENT_X, back + 0.9, ENT_Z + 1.35))
    k.assign(lintel, gable)
    k.bevel(lintel, 0.06, 2)
    parts.append(lintel)
    for name, size, loc in (("original entrance", (1.05, 0.5, 1.2), (ENT_X, back + 0.3, ENT_Z + 0.3)),
                            ("robbers tunnel", (2.2, 0.5, 2.4), (0.0, half_side(7.5) - 3.0 + 0.3, 7.4))):
        hole = k.box(name, size, loc)
        k.assign(hole, dark)
        parts.append(hole)

    # the mast on the summit that marks where the tip once was
    mast = k.cylinder("summit mast", 0.09, H_ORIG - H_NOW, (0, 0, H_NOW + (H_ORIG - H_NOW) / 2), segments=10)
    k.assign(mast, k.material("iron", (0.10, 0.09, 0.08), roughness=0.6, metallic=0.8))
    parts.append(mast)

    # the plateau it stands on: level under the pyramid, sand rolling away and fading out
    parts.append(k.desert_ground("giza plateau", radius=520.0, flat_radius=180.0, relief=3.0, seed=11, segments=220,
                                 fade_from=0.40, screen_fade=0.13,
                                 colour=(0.33, 0.25, 0.14), colour2=(0.42, 0.33, 0.20)))
    return parts

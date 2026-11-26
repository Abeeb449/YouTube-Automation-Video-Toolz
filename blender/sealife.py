"""Sharks and whales for ytauto, modelled from measurements in Blender (used by creatures3d.py).

The body is a loft: elliptical cross-sections placed along the animal's length from its real proportions and
smoothed with a subdivision surface. Every fin is a thin lofted foil between its leading and trailing edge, so
fins have real thickness, a sharp trailing edge and the right outline from any camera. Colour patterns (a great
white's countershading, an orca's eye patch, saddle and flank patch, gill slits, spots) are procedural materials
drawn in the animal's own coordinates, so they stay in place while it swims.

Units: one animal is about 4 units long, nose at +X, back at +Z, the animal's LEFT side at +Y.

Facts the models are built from (TL = total length):
  Great white (Carcharodon carcharias): spindle body, deepest (about 0.2 TL) under the first dorsal fin; conical
    snout; black eye; five gill slits in front of the pectoral fin; tall triangular first dorsal over the rear of
    the pectoral base; tiny second dorsal and anal fins; keel on the tail stock; crescent tail, lower lobe almost
    as long as the upper. Slate grey above, white below, with a sharp ragged line between; pectoral fins white
    underneath with black tips.
  Bronze whaler (Carcharhinus brachyurus): slender (depth about 0.15 TL), long pointed snout, first dorsal with a
    pointed tip, long pectoral fins, upper tail lobe much longer than the lower. Bronze to olive-grey above,
    white below.
  Broadnose sevengill (Notorynchus cepedianus): broad blunt head, SEVEN gill slits, ONE small dorsal fin set far
    back above the pelvic fins, long low upper tail lobe with a notch near its tip. Grey-brown with small dark
    and pale spots, cream below.
  Orca (Orcinus orca), adult male: depth about 0.22 TL, rounded head with a short beak, paddle-shaped flippers
    about 0.2 TL long, horizontal flukes about 0.3 TL across, dorsal fin up to 1.8 m tall (about 0.2 TL), straight
    and triangular. Black; white lower jaw, throat and belly with a lobe rising up the rear flank; a white oval
    patch above and behind each eye; a grey saddle behind the dorsal fin; flukes white underneath.
  Port and Starboard (South Africa): two adult males whose dorsal fins have collapsed. Port's fin lies over to
    his LEFT, Starboard's to his RIGHT (the sailors' words for left and right).
Sources: FAO species catalogue (sharks of the world); NOAA Fisheries species pages (white shark, killer whale);
  Towner et al. 2022 and the Port and Starboard sighting records for the two fins.
"""
import math

import bmesh
import bpy
from mathutils import Vector


def hexcol(h, a=1.0):
    h = h.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    lin = [((c + 0.055) / 1.055) ** 2.4 if c > 0.04045 else c / 12.92 for c in (r, g, b)]
    return (*lin, a)


# ------------------------------------------------------------------------------------------ curves
def _pchip(xs, ys):
    """Smooth curve through the points that never overshoots them (xs ascending) → f(x)."""
    n = len(xs)
    h = [xs[i + 1] - xs[i] for i in range(n - 1)]
    d = [(ys[i + 1] - ys[i]) / h[i] for i in range(n - 1)]
    m = [d[0]] + [0.0 if d[i - 1] * d[i] <= 0 else 2 * d[i - 1] * d[i] / (d[i - 1] + d[i]) for i in range(1, n - 1)] + [d[-1]]

    def f(x):
        x = min(max(x, xs[0]), xs[-1])
        i = max(0, min(n - 2, next((k for k in range(n - 1) if x <= xs[k + 1]), n - 2)))
        t = (x - xs[i]) / h[i]
        return ((2 * t ** 3 - 3 * t ** 2 + 1) * ys[i] + (t ** 3 - 2 * t ** 2 + t) * h[i] * m[i]
                + (-2 * t ** 3 + 3 * t ** 2) * ys[i + 1] + (t ** 3 - t ** 2) * h[i] * m[i + 1])
    return f


def _v(p):
    return Vector((p[0], 0.0, p[1])) if len(p) == 2 else Vector(p)


def _resample(pts, n):
    """n points evenly spaced along a smooth curve through pts."""
    pts = [_v(p) for p in pts]
    ext = [pts[0] * 2 - pts[1]] + pts + [pts[-1] * 2 - pts[-2]]
    dense = []
    for i in range(1, len(ext) - 2):
        p0, p1, p2, p3 = ext[i - 1], ext[i], ext[i + 1], ext[i + 2]
        for k in range(14):
            t = k / 14
            dense.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t
                                + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3))
    dense.append(pts[-1])
    acc = [0.0]
    for a, b in zip(dense, dense[1:]):
        acc.append(acc[-1] + (b - a).length)
    out = []
    for j in range(n):
        s = acc[-1] * j / (n - 1)
        k = max(0, min(len(dense) - 2, max(i for i, v in enumerate(acc) if v <= s + 1e-9)))
        out.append(dense[k].lerp(dense[k + 1], (s - acc[k]) / max(1e-9, acc[k + 1] - acc[k])))
    return out


# ------------------------------------------------------------------------------------------ geometry
def _object(name, bm, smooth=True, levels=2):
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    for p in me.polygons:
        p.use_smooth = smooth
    if levels:
        sub = ob.modifiers.new("sub", "SUBSURF")
        sub.levels = levels
        sub.render_levels = levels
    return ob


def loft_body(name, stations, ring=24, rings=44, y0=0.0):
    """stations: [(x, z_centre, half_width, half_height_up, half_height_down)] from the nose (largest x) to the
    tail; the first and last are the tips. → one closed, smooth body."""
    st = sorted(stations, key=lambda s: s[0])
    xs = [s[0] for s in st]
    fz, fw, fu, fd = (_pchip(xs, [s[k] for s in st]) for k in (1, 2, 3, 4))
    bm = bmesh.new()
    loops = []
    for j in range(1, rings):
        u = 0.5 - 0.5 * math.cos(math.pi * j / rings)            # rings crowd toward nose and tail, where it curves most
        x = xs[0] + (xs[-1] - xs[0]) * u
        zc, hw, hu, hd = fz(x), max(1e-3, fw(x)), max(1e-3, fu(x)), max(1e-3, fd(x))
        loop = []
        for k in range(ring):
            a = 2 * math.pi * k / ring
            c, s = math.cos(a), math.sin(a)
            loop.append(bm.verts.new((x, y0 + hw * c, zc + (hu if s >= 0 else hd) * s)))
        loops.append(loop)
    tail = bm.verts.new((xs[0], y0, st[0][1]))
    nose = bm.verts.new((xs[-1], y0, st[-1][1]))
    for a, b in zip(loops, loops[1:]):
        for k in range(ring):
            bm.faces.new((a[k], a[(k + 1) % ring], b[(k + 1) % ring], b[k]))
    for k in range(ring):
        bm.faces.new((tail, loops[0][(k + 1) % ring], loops[0][k]))
        bm.faces.new((nose, loops[-1][k], loops[-1][(k + 1) % ring]))
    return _object(name, bm)


_SECTION = [(0.0, 0.0), (0.10, 0.72), (0.34, 1.0), (0.70, 0.62), (1.0, 0.0), (0.70, -0.62), (0.34, -1.0), (0.10, -0.72)]


def fin(name, lead, trail, thick, tip_thick=None, n=10, warp=None):
    """A fin as a lofted foil. lead / trail: the leading and trailing edge from root to tip ((x, z) pairs for a
    fin on the midline, else (x, y, z)). thick: thickness at the root. warp(point) bends the finished outline
    (a collapsed dorsal fin)."""
    L, T = _resample(lead, n), _resample(trail, n)
    if warp:
        L, T = [warp(p) for p in L], [warp(p) for p in T]
    tip_thick = thick * 0.18 if tip_thick is None else tip_thick
    bm = bmesh.new()
    loops, nrm = [], Vector((0, 1, 0))
    for i in range(n):
        chord = T[i] - L[i]
        a = L[max(0, i - 1)].lerp(T[max(0, i - 1)], 0.5)
        b = L[min(n - 1, i + 1)].lerp(T[min(n - 1, i + 1)], 0.5)
        c = chord.cross(b - a)
        if c.length > 1e-6:
            c.normalize()
            nrm = c if c.dot(nrm) >= 0 or i == 0 else -c
        th = thick + (tip_thick - thick) * (i / (n - 1)) ** 0.8
        loops.append([bm.verts.new(L[i] + chord * f + nrm * (o * th / 2)) for f, o in _SECTION])
    m = len(_SECTION)
    for a, b in zip(loops, loops[1:]):
        for k in range(m):
            bm.faces.new((a[k], a[(k + 1) % m], b[(k + 1) % m], b[k]))
    bm.faces.new(loops[-1])
    return _object(name, bm)


def mirror_y(pts):
    return [(p[0], -p[1], p[2]) for p in pts]


def collapse(z0, height, side, angle=118.0, start=0.04, end=0.42):
    """Warp for a dorsal fin that has folded over: it stands for its first few centimetres, then folds to one side
    (side +1 = the animal's left, -1 = its right) and lies over with its tip pointing down."""
    steps = 60

    def path(u):
        y = z = 0.0
        for k in range(int(max(0.0, min(1.0, u)) * steps)):
            t = (k + 0.5) / steps
            e = min(1.0, max(0.0, (t - start) / (end - start)))
            phi = math.radians(angle) * e * e * (3 - 2 * e)
            y += math.sin(phi) * height / steps
            z += math.cos(phi) * height / steps
        return y, z

    def warp(p):
        y, z = path((p.z - z0) / height)
        return Vector((p.x, p.y + side * y, z0 + z))
    return warp


def ball(name, loc, r, mat):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=r, location=loc, segments=20, ring_count=10)
    o = bpy.context.active_object
    o.name = name
    bpy.ops.object.shade_smooth()
    o.data.materials.append(mat)
    return o


# ------------------------------------------------------------------------------------------ materials
class Skin:
    """A material painted with formulas in the animal's own coordinates (x along the body, z up)."""

    def __init__(self, name, rough=0.4):
        self.mat = bpy.data.materials.new(name)
        self.mat.use_nodes = True
        self.nt = self.mat.node_tree
        self.bsdf = self.nt.nodes["Principled BSDF"]
        self.bsdf.inputs["Roughness"].default_value = rough
        tc = self.nt.nodes.new("ShaderNodeTexCoord")
        self.obj = tc.outputs["Object"]
        sep = self.nt.nodes.new("ShaderNodeSeparateXYZ")
        self.nt.links.new(self.obj, sep.inputs[0])
        self.x, self.y, self.z = sep.outputs["X"], sep.outputs["Y"], sep.outputs["Z"]
        geo = self.nt.nodes.new("ShaderNodeNewGeometry")
        sn = self.nt.nodes.new("ShaderNodeSeparateXYZ")
        self.nt.links.new(geo.outputs["Normal"], sn.inputs[0])
        self.nz = sn.outputs["Z"]

    def _in(self, node, i, v):
        if isinstance(v, (int, float)):
            node.inputs[i].default_value = v
        else:
            self.nt.links.new(v, node.inputs[i])

    def m(self, op, a, b=None, c=None):
        n = self.nt.nodes.new("ShaderNodeMath")
        n.operation = op
        self._in(n, 0, a)
        if b is not None:
            self._in(n, 1, b)
        if c is not None:
            self._in(n, 2, c)
        return n.outputs[0]

    def above(self, v, edge, soft=0.02):
        """1 where v > edge, 0 below, with a soft step."""
        n = self.nt.nodes.new("ShaderNodeMapRange")
        n.interpolation_type = "SMOOTHSTEP"
        self._in(n, 0, v)
        if isinstance(edge, (int, float)):
            n.inputs[1].default_value, n.inputs[2].default_value = edge - soft / 2, edge + soft / 2
        else:
            self._in(n, 0, self.m("SUBTRACT", v, edge))
            n.inputs[1].default_value, n.inputs[2].default_value = -soft / 2, soft / 2
        return n.outputs[0]

    def inv(self, v):
        return self.m("SUBTRACT", 1.0, v)

    def band(self, v, lo, hi, soft=0.02):
        return self.m("MULTIPLY", self.above(v, lo, soft), self.inv(self.above(v, hi, soft)))

    def curve(self, pts):
        """A height that changes along the body: [(x, z), …] → z(x), straight between the points."""
        pts = sorted(pts)
        x0, x1 = pts[0][0], pts[-1][0]
        z0, z1 = min(p[1] for p in pts), max(p[1] for p in pts)
        span = (z1 - z0) or 1.0
        n = self.nt.nodes.new("ShaderNodeFloatCurve")
        cv = n.mapping.curves[0]
        while len(cv.points) < len(pts):
            cv.points.new(0.5, 0.5)
        for cp, (x, z) in zip(cv.points, pts):
            cp.location = ((x - x0) / (x1 - x0), (z - z0) / span)
            cp.handle_type = "VECTOR"
        n.mapping.update()
        mr = self.nt.nodes.new("ShaderNodeMapRange")
        self._in(mr, 0, self.x)
        mr.inputs[1].default_value, mr.inputs[2].default_value = x0, x1
        self.nt.links.new(mr.outputs[0], n.inputs["Value"])
        return self.m("MULTIPLY_ADD", n.outputs[0], span, z0)

    def ellipse(self, cx, cz, rx, rz, rot=0.0, soft=0.12):
        """1 inside an ellipse drawn on the animal's side (x, z), tilted by rot degrees."""
        dx, dz = self.m("SUBTRACT", self.x, cx), self.m("SUBTRACT", self.z, cz)
        c, s = math.cos(math.radians(rot)), math.sin(math.radians(rot))
        u = self.m("ADD", self.m("MULTIPLY", dx, c), self.m("MULTIPLY", dz, s))
        w = self.m("SUBTRACT", self.m("MULTIPLY", dz, c), self.m("MULTIPLY", dx, s))
        d = self.m("SQRT", self.m("ADD", self.m("POWER", self.m("DIVIDE", u, rx), 2.0), self.m("POWER", self.m("DIVIDE", w, rz), 2.0)))
        return self.inv(self.above(d, 1.0, soft))

    def noise(self, scale, detail=3.0, stretch=(1, 1, 1)):
        mp = self.nt.nodes.new("ShaderNodeMapping")
        mp.inputs["Scale"].default_value = stretch
        self.nt.links.new(self.obj, mp.inputs[0])
        n = self.nt.nodes.new("ShaderNodeTexNoise")
        n.inputs["Scale"].default_value = scale
        n.inputs["Detail"].default_value = detail
        self.nt.links.new(mp.outputs[0], n.inputs["Vector"])
        return n.outputs["Fac"]

    def mix(self, fac, a, b):
        n = self.nt.nodes.new("ShaderNodeMixRGB")
        self._in(n, 0, fac)
        for i, v in ((1, a), (2, b)):
            if isinstance(v, tuple):
                n.inputs[i].default_value = v
            else:
                self.nt.links.new(v, n.inputs[i])
        return n.outputs[0]

    def either(self, a, b):
        return self.m("MAXIMUM", a, b)

    def both(self, a, b):
        return self.m("MULTIPLY", a, b)

    def finish(self, colour, bump=0.0, bump_scale=60.0):
        self.nt.links.new(colour, self.bsdf.inputs["Base Color"])
        if bump:
            bp = self.nt.nodes.new("ShaderNodeBump")
            bp.inputs["Strength"].default_value = bump
            bp.inputs["Distance"].default_value = 0.01
            self.nt.links.new(self.noise(bump_scale, 4.0), bp.inputs["Height"])
            self.nt.links.new(bp.outputs["Normal"], self.bsdf.inputs["Normal"])
        return self.mat


def plain(name, col, rough=0.35):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = col
    b.inputs["Roughness"].default_value = rough
    return m


def _give(obs, mat):
    for o in obs:
        o.data.materials.clear()
        o.data.materials.append(mat)


# ------------------------------------------------------------------------------------------ sharks
def _shark_skin(name, top, belly, line, gills, mouth, spots=None, band=None, rough=0.46):
    """Countershading: `top` above the ragged line z = line(x), `belly` below; gill slits; the mouth line."""
    s = Skin(name, rough)
    wob = s.m("MULTIPLY", s.m("SUBTRACT", s.noise(7.0, 2.0, (1, 0.2, 1)), 0.5), 0.09)        # the line wanders
    upper = s.above(s.m("ADD", s.z, wob), s.curve(line), 0.035)
    col = s.mix(upper, belly, top)
    mott = s.m("MULTIPLY", s.m("SUBTRACT", s.noise(2.6, 4.0), 0.5), 0.5)                    # cloudy tone on the back
    col = s.mix(s.both(upper, s.m("MAXIMUM", mott, 0.0)), col, tuple(c * 0.72 for c in top[:3]) + (1,))
    if band:                                    # a pale stripe along the flank
        zc, half, colour, x0, x1 = band
        col = s.mix(s.m("MULTIPLY", s.both(s.band(s.z, zc - half, zc + half, half), s.band(s.x, x0, x1, 0.3)), 0.45), col, colour)
    if spots:                                   # small dark and pale spots on the back and sides
        dark, pale, scale = spots
        n1 = s.noise(scale, 1.0)
        col = s.mix(s.both(upper, s.above(n1, 0.69, 0.04)), col, dark)
        col = s.mix(s.m("MULTIPLY", s.both(upper, s.above(s.noise(scale * 1.7, 1.0), 0.73, 0.04)), 0.6), col, pale)
    gx0, gx1, gz0, gz1, count, slant = gills
    gx = s.m("ADD", s.x, s.m("MULTIPLY", s.z, slant))
    step = (gx1 - gx0) / count
    slit = s.inv(s.above(s.m("PINGPONG", s.m("SUBTRACT", gx, gx0 + step * 0.5), step / 2), step * 0.085, step * 0.07))
    slit = s.both(s.both(slit, s.band(gx, gx0 - step * 0.2, gx1 - step * 0.35, 0.01)), s.band(s.z, gz0, gz1, 0.05))
    col = s.mix(s.m("MULTIPLY", slit, 0.86), col, (0.012, 0.014, 0.016, 1))
    mx0, mx1, mz0, mz1, width = mouth
    zline = s.curve([(mx0, mz0), ((mx0 + mx1) / 2, (mz0 + mz1) / 2 - 0.012), (mx1, mz1)])
    lip = s.both(s.band(s.m("SUBTRACT", s.z, zline), -width, width, width), s.band(s.x, mx0, mx1, 0.02))
    col = s.mix(s.m("MULTIPLY", lip, 0.9), col, (0.02, 0.012, 0.012, 1))
    return s.finish(col, bump=0.08, bump_scale=90.0)


def _shark_fin_skin(name, top, belly, rough=0.46, tip=None):
    """Fins: the back colour on top, the belly colour underneath (pectoral fins), optionally dark-tipped."""
    s = Skin(name, rough)
    col = s.mix(s.above(s.nz, -0.25, 0.3), belly, top)
    if tip:                                     # dark tips on the underside, beyond |y| = tip
        out = s.above(s.m("ABSOLUTE", s.y), tip, 0.08)
        col = s.mix(s.both(out, s.inv(s.above(s.nz, -0.25, 0.3))), col, (0.02, 0.022, 0.025, 1))
    return s.finish(col, bump=0.05, bump_scale=90.0)


POSE = "swim"       # set by creatures3d.py: "beached" presses the ground-side fins flat under the body


def _tucked(pts, root):
    """A side fin pressed back against the body (the fin an animal is lying on)."""
    return [(x - 0.3 * abs(y - root[1]), root[1] * 0.8 + (y - root[1]) * 0.04, root[2] * 0.6 + (z - root[2]) * 0.06) for x, y, z in pts]


def _pair(name, lead, trail, thick, **kw):
    left_lead, left_trail = lead, trail
    if POSE == "beached":           # the animal lies on its left side: that fin is under it, the other stands free
        left_lead, left_trail = _tucked(lead, lead[0]), _tucked(trail, lead[0])
    return [fin(name + "L", left_lead, left_trail, thick, **kw), fin(name + "R", mirror_y(lead), mirror_y(trail), thick, **kw)]


def see_through(objects, tint=(0.35, 0.75, 1.0)):
    """Turn finished parts into clear glass with a lit outline, so what is inside can be shown."""
    done = set()
    for o in objects:
        for slot in o.material_slots:
            m = slot.material
            if not m or m.name in done:
                continue
            done.add(m.name)
            nt = m.node_tree
            b = nt.nodes["Principled BSDF"]
            lw = nt.nodes.new("ShaderNodeLayerWeight")
            lw.inputs["Blend"].default_value = 0.28
            ramp = nt.nodes.new("ShaderNodeMath")          # alpha: nearly clear face-on, solid toward the outline
            ramp.operation = "MULTIPLY_ADD"
            nt.links.new(lw.outputs["Facing"], ramp.inputs[0])
            ramp.inputs[1].default_value, ramp.inputs[2].default_value = 0.85, 0.10
            nt.links.new(ramp.outputs[0], b.inputs["Alpha"])
            em = "Emission Color" if "Emission Color" in b.inputs else "Emission"
            b.inputs[em].default_value = (*tint, 1)
            es = nt.nodes.new("ShaderNodeMath")
            es.operation = "MULTIPLY"
            nt.links.new(lw.outputs["Facing"], es.inputs[0])
            es.inputs[1].default_value = 1.6
            nt.links.new(es.outputs[0], b.inputs["Emission Strength"])
            for attr, val in (("blend_method", "BLEND"), ("shadow_method", "NONE"), ("show_transparent_back", False),
                              ("surface_render_method", "BLENDED")):
                if hasattr(m, attr):
                    try:
                        setattr(m, attr, val)
                    except Exception:  # noqa: BLE001 — an option this Blender version does not have
                        pass


def shark_liver():
    """A great white's liver: two long lobes that fill most of the body cavity, from behind the gills to the
    pelvic fins — a quarter to a third of the animal's weight."""
    m = bpy.data.materials.new("liver")
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = hexcol("#c7772e")
    b.inputs["Roughness"].default_value = 0.35
    em = "Emission Color" if "Emission Color" in b.inputs else "Emission"
    b.inputs[em].default_value = hexcol("#e08a2c")
    b.inputs["Emission Strength"].default_value = 1.1
    lobes = []
    for sd in (1, -1):
        o = loft_body(f"liver{sd}", [(1.00, -0.03, 0, 0, 0), (0.86, -0.05, 0.08, 0.13, 0.13), (0.50, -0.08, 0.13, 0.215, 0.22),
                                      (0.05, -0.09, 0.13, 0.21, 0.215), (-0.32, -0.09, 0.10, 0.15, 0.15),
                                      (-0.60, -0.08, 0.05, 0.06, 0.06), (-0.70, -0.08, 0, 0, 0)], ring=16, rings=24, y0=0.115 * sd)
        o.data.materials.append(m)
        lobes.append(o)
    return lobes


def build_great_white(liver=False):
    body = loft_body("greatWhite", [
        (2.00, 0.03, 0, 0, 0), (1.93, 0.03, 0.045, 0.035, 0.045), (1.78, 0.035, 0.115, 0.095, 0.115),
        (1.58, 0.04, 0.185, 0.17, 0.185), (1.32, 0.04, 0.25, 0.25, 0.27), (1.02, 0.03, 0.30, 0.32, 0.345),
        (0.66, 0.02, 0.335, 0.375, 0.39), (0.28, 0.02, 0.34, 0.395, 0.40), (-0.12, 0.02, 0.305, 0.36, 0.36),
        (-0.52, 0.02, 0.235, 0.275, 0.27), (-0.86, 0.03, 0.155, 0.17, 0.165), (-1.10, 0.04, 0.115, 0.085, 0.085),
        (-1.26, 0.05, 0.075, 0.06, 0.06), (-1.34, 0.05, 0, 0, 0)])
    top, belly = hexcol("#566068"), hexcol("#e6e9e8")
    skin = _shark_skin("gw_skin", top, belly,
                       line=[(-1.34, 0.0), (-0.9, -0.02), (-0.3, -0.05), (0.4, -0.06), (1.0, -0.02), (1.5, 0.01), (2.0, 0.03)],
                       gills=(0.82, 1.15, -0.16, 0.20, 5, -0.22), mouth=(1.22, 1.70, -0.13, -0.105, 0.011))
    body.data.materials.append(skin)
    fins = [fin("dorsal1", [(0.60, 0.30), (0.44, 0.54), (0.28, 0.72), (0.14, 0.80)], [(-0.02, 0.30), (0.04, 0.47), (0.07, 0.64), (0.10, 0.79)], 0.085),
            fin("dorsal2", [(-0.76, 0.13), (-0.82, 0.21), (-0.86, 0.25)], [(-0.93, 0.14), (-0.905, 0.19), (-0.89, 0.245)], 0.03, n=6),
            fin("anal", [(-0.88, -0.10), (-0.94, -0.19), (-0.98, -0.23)], [(-1.04, -0.10), (-1.02, -0.16), (-1.01, -0.225)], 0.03, n=6),
            fin("tailUp", [(-1.06, 0.085), (-1.30, 0.30), (-1.56, 0.52), (-1.84, 0.70)], [(-1.50, 0.05), (-1.60, 0.20), (-1.76, 0.46), (-1.92, 0.685)], 0.07),
            fin("tailLow", [(-1.06, 0.0), (-1.26, -0.20), (-1.48, -0.40), (-1.70, -0.54)], [(-1.50, 0.05), (-1.54, -0.10), (-1.66, -0.34), (-1.78, -0.53)], 0.065)]
    pect = _pair("pect", [(0.90, 0.24, -0.17), (0.70, 0.50, -0.30), (0.46, 0.70, -0.42), (0.24, 0.84, -0.50)],
                 [(0.44, 0.24, -0.22), (0.40, 0.46, -0.32), (0.28, 0.66, -0.43), (0.18, 0.82, -0.50)], 0.07)
    pelv = _pair("pelv", [(-0.40, 0.13, -0.23), (-0.52, 0.20, -0.33), (-0.62, 0.24, -0.39)],
                 [(-0.66, 0.11, -0.22), (-0.66, 0.18, -0.31), (-0.66, 0.23, -0.385)], 0.035, n=6)
    _give(fins, _shark_fin_skin("gw_fin", top, top))
    _give(pect + pelv, _shark_fin_skin("gw_pect", top, belly, tip=0.60))
    eye = plain("eye", hexcol("#020203"), rough=0.05)
    for sd in (1, -1):
        ball(f"eye{sd}", (1.60, 0.168 * sd, 0.085), 0.03, eye)
    if liver:
        see_through([body] + fins + pect + pelv)
        shark_liver()
    return body, (-1.92, 2.0), "yaw"


def build_bronze_whaler():
    body = loft_body("bronzeWhaler", [
        (2.00, 0.0, 0, 0, 0), (1.94, 0.0, 0.035, 0.025, 0.03), (1.76, 0.01, 0.10, 0.07, 0.08),
        (1.50, 0.02, 0.17, 0.14, 0.15), (1.20, 0.02, 0.22, 0.21, 0.22), (0.80, 0.02, 0.255, 0.27, 0.28),
        (0.36, 0.02, 0.26, 0.295, 0.30), (-0.10, 0.02, 0.235, 0.265, 0.265), (-0.55, 0.02, 0.17, 0.20, 0.195),
        (-0.92, 0.03, 0.105, 0.125, 0.12), (-1.14, 0.04, 0.065, 0.075, 0.07), (-1.22, 0.04, 0, 0, 0)])
    top, belly = hexcol("#6f6248"), hexcol("#e9e7df")
    skin = _shark_skin("bw_skin", top, belly,
                       line=[(-1.22, 0.0), (-0.6, -0.05), (0.3, -0.07), (1.0, -0.03), (1.6, 0.0), (2.0, 0.0)],
                       gills=(0.88, 1.14, -0.11, 0.13, 5, -0.2), mouth=(1.30, 1.74, -0.10, -0.075, 0.009),
                       band=(0.02, 0.05, hexcol("#b8ab8e"), -0.9, 0.5))
    body.data.materials.append(skin)
    fins = [fin("dorsal1", [(0.50, 0.24), (0.34, 0.46), (0.18, 0.60), (0.04, 0.66)], [(0.02, 0.24), (0.03, 0.36), (0.02, 0.52), (0.01, 0.65)], 0.06),
            fin("dorsal2", [(-0.72, 0.11), (-0.80, 0.17), (-0.86, 0.19)], [(-0.90, 0.12), (-0.90, 0.15), (-0.89, 0.185)], 0.025, n=6),
            fin("anal", [(-0.74, -0.09), (-0.82, -0.17), (-0.88, -0.20)], [(-0.92, -0.09), (-0.91, -0.14), (-0.905, -0.195)], 0.025, n=6),
            fin("tailUp", [(-1.08, 0.07), (-1.38, 0.30), (-1.70, 0.56), (-2.00, 0.78)], [(-1.26, 0.02), (-1.50, 0.16), (-1.82, 0.50), (-2.03, 0.76)], 0.05),
            fin("tailLow", [(-1.06, -0.01), (-1.22, -0.16), (-1.36, -0.30), (-1.46, -0.38)], [(-1.26, 0.02), (-1.34, -0.08), (-1.42, -0.24), (-1.49, -0.37)], 0.04, n=7)]
    pect = _pair("pect", [(0.84, 0.19, -0.14), (0.62, 0.42, -0.28), (0.38, 0.62, -0.42), (0.16, 0.74, -0.50)],
                 [(0.46, 0.19, -0.18), (0.38, 0.40, -0.30), (0.24, 0.58, -0.42), (0.11, 0.72, -0.50)], 0.055)
    pelv = _pair("pelv", [(-0.34, 0.10, -0.19), (-0.44, 0.16, -0.27), (-0.52, 0.19, -0.31)],
                 [(-0.56, 0.09, -0.18), (-0.56, 0.14, -0.25), (-0.555, 0.18, -0.305)], 0.03, n=6)
    _give(fins, _shark_fin_skin("bw_fin", top, top))
    _give(pect + pelv, _shark_fin_skin("bw_pect", top, belly, tip=0.60))
    eye = plain("eye", hexcol("#15130c"), rough=0.08)
    for sd in (1, -1):
        ball(f"eye{sd}", (1.56, 0.152 * sd, 0.05), 0.027, eye)
    return body, (-2.03, 2.0), "yaw"


def build_sevengill():
    body = loft_body("sevengill", [
        (2.00, 0.0, 0, 0, 0), (1.95, 0.0, 0.10, 0.045, 0.05), (1.82, 0.01, 0.20, 0.10, 0.11),
        (1.60, 0.02, 0.26, 0.16, 0.17), (1.25, 0.02, 0.28, 0.22, 0.23), (0.80, 0.02, 0.27, 0.26, 0.27),
        (0.30, 0.02, 0.25, 0.26, 0.27), (-0.20, 0.02, 0.21, 0.23, 0.23), (-0.65, 0.02, 0.15, 0.17, 0.165),
        (-1.00, 0.03, 0.095, 0.11, 0.105), (-1.24, 0.04, 0.06, 0.07, 0.065), (-1.32, 0.04, 0, 0, 0)])
    top, belly = hexcol("#7a7468"), hexcol("#e4dfd2")
    skin = _shark_skin("sg_skin", top, belly,
                       line=[(-1.32, -0.02), (-0.5, -0.08), (0.4, -0.10), (1.2, -0.08), (1.8, -0.03), (2.0, -0.01)],
                       gills=(0.98, 1.50, -0.17, 0.12, 7, -0.25), mouth=(1.52, 1.90, -0.10, -0.085, 0.009),
                       spots=(hexcol("#1c1b19"), hexcol("#d9d6cc"), 34.0))
    body.data.materials.append(skin)
    fins = [fin("dorsal", [(-0.46, 0.17), (-0.58, 0.29), (-0.68, 0.35), (-0.74, 0.37)], [(-0.82, 0.16), (-0.80, 0.24), (-0.78, 0.32), (-0.765, 0.365)], 0.04, n=7),
            fin("anal", [(-0.84, -0.10), (-0.92, -0.17), (-0.98, -0.20)], [(-1.06, -0.09), (-1.03, -0.14), (-1.01, -0.195)], 0.028, n=6),
            # long, low upper lobe with a notch close to the tip
            fin("tailUp", [(-1.14, 0.075), (-1.42, 0.21), (-1.74, 0.36), (-2.03, 0.47)], [(-1.30, 0.03), (-1.52, 0.10), (-1.80, 0.24), (-2.04, 0.44)], 0.045),
            fin("tailTip", [(-1.86, 0.33), (-1.93, 0.26), (-1.98, 0.22)], [(-1.98, 0.40), (-2.02, 0.32), (-2.03, 0.24)], 0.02, n=5),
            fin("tailLow", [(-1.12, 0.0), (-1.24, -0.10), (-1.34, -0.17), (-1.42, -0.20)], [(-1.30, 0.03), (-1.36, -0.03), (-1.42, -0.12), (-1.45, -0.195)], 0.035, n=7)]
    pect = _pair("pect", [(0.98, 0.24, -0.16), (0.82, 0.44, -0.26), (0.64, 0.58, -0.34), (0.50, 0.66, -0.38)],
                 [(0.60, 0.24, -0.20), (0.56, 0.40, -0.28), (0.50, 0.54, -0.35), (0.45, 0.64, -0.38)], 0.05)
    pelv = _pair("pelv", [(-0.30, 0.12, -0.20), (-0.42, 0.19, -0.27), (-0.50, 0.22, -0.30)],
                 [(-0.56, 0.10, -0.19), (-0.555, 0.16, -0.25), (-0.545, 0.21, -0.295)], 0.03, n=6)
    _give(fins, _shark_fin_skin("sg_fin", top, top))
    _give(pect + pelv, _shark_fin_skin("sg_pect", top, belly))
    eye = plain("eye", hexcol("#0c0d0c"), rough=0.08)
    for sd in (1, -1):
        ball(f"eye{sd}", (1.72, 0.222 * sd, 0.06), 0.024, eye)
    return body, (-2.04, 2.0), "yaw"


def build_bony_fish():
    """An ordinary bony fish shown as clear glass with its swim bladder lit inside: the small bag of gas under
    the backbone that lets most fish hang in the water without sinking."""
    body = loft_body("fish", [
        (2.00, 0.0, 0, 0, 0), (1.92, 0.0, 0.06, 0.07, 0.08), (1.65, 0.02, 0.17, 0.24, 0.26), (1.20, 0.03, 0.24, 0.42, 0.44),
        (0.60, 0.03, 0.26, 0.52, 0.52), (0.0, 0.03, 0.23, 0.48, 0.47), (-0.60, 0.03, 0.16, 0.34, 0.33),
        (-1.10, 0.03, 0.09, 0.18, 0.17), (-1.42, 0.03, 0.05, 0.10, 0.10), (-1.52, 0.03, 0, 0, 0)])
    silver = plain("fish_skin", hexcol("#9fb2bd"), rough=0.3)
    body.data.materials.append(silver)
    fins = [fin("dorsal", [(0.70, 0.50), (0.40, 0.78), (-0.10, 0.74), (-0.55, 0.50)], [(-0.70, 0.36), (-0.66, 0.42), (-0.62, 0.46), (-0.58, 0.49)], 0.03),
            fin("anal", [(-0.20, -0.44), (-0.40, -0.66), (-0.62, -0.60)], [(-0.80, -0.26), (-0.74, -0.40), (-0.66, -0.58)], 0.025, n=7),
            fin("tailUp", [(-1.40, 0.08), (-1.66, 0.36), (-1.92, 0.62)], [(-1.62, 0.03), (-1.74, 0.22), (-1.95, 0.60)], 0.03, n=7),
            fin("tailLow", [(-1.40, -0.02), (-1.66, -0.30), (-1.92, -0.56)], [(-1.62, 0.03), (-1.74, -0.16), (-1.95, -0.54)], 0.03, n=7)]
    pect = _pair("pect", [(1.10, 0.24, -0.10), (0.92, 0.38, -0.24), (0.70, 0.46, -0.36)], [(0.86, 0.24, -0.20), (0.76, 0.34, -0.30), (0.66, 0.44, -0.37)], 0.02, n=6)
    _give(fins + pect, silver)
    eye = plain("eye", hexcol("#050607"), rough=0.05)
    for sd in (1, -1):
        ball(f"eye{sd}", (1.62, 0.165 * sd, 0.10), 0.05, eye)
    see_through([body] + fins + pect, tint=(0.55, 0.85, 1.0))
    gas = bpy.data.materials.new("bladder")
    gas.use_nodes = True
    b = gas.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = hexcol("#e8f3f6")
    b.inputs["Roughness"].default_value = 0.15
    em = "Emission Color" if "Emission Color" in b.inputs else "Emission"
    b.inputs[em].default_value = hexcol("#dff4ff")
    b.inputs["Emission Strength"].default_value = 1.3
    bl = loft_body("bladder", [(0.95, 0.20, 0, 0, 0), (0.80, 0.21, 0.07, 0.07, 0.07), (0.35, 0.22, 0.11, 0.11, 0.11),
                               (-0.15, 0.21, 0.10, 0.09, 0.09), (-0.50, 0.19, 0.05, 0.05, 0.05), (-0.62, 0.19, 0, 0, 0)], ring=16, rings=20)
    bl.data.materials.append(gas)
    return body, (-1.95, 2.0), "yaw"


# ------------------------------------------------------------------------------------------ orcas
def _orca_skin():
    s = Skin("orca_skin", 0.36)
    black, white, grey = hexcol("#08090b"), hexcol("#f2f3f1"), hexcol("#596168")
    # white underside: lower jaw and throat, a narrow belly stripe, then a lobe that climbs the rear flank
    under = s.inv(s.above(s.z, s.curve([(-1.85, -0.02), (-1.45, -0.07), (-1.10, -0.20), (-0.20, -0.33), (0.55, -0.31),
                                        (0.95, -0.22), (1.30, -0.13), (1.62, -0.085), (1.86, -0.062), (2.0, -0.055)]), 0.025))
    flank = s.both(s.ellipse(-0.66, -0.17, 0.50, 0.19, rot=-13, soft=0.10), s.inv(s.above(s.z, 0.08, 0.05)))
    eye = s.ellipse(1.345, 0.118, 0.150, 0.052, rot=-9, soft=0.05)
    col = s.mix(s.either(s.either(under, flank), eye), black, white)
    saddle = s.both(s.ellipse(-0.40, 0.34, 0.30, 0.10, rot=12, soft=0.6), s.above(s.z, 0.20, 0.10))
    col = s.mix(s.m("MULTIPLY", saddle, 0.6), col, grey)
    return s.finish(col, bump=0.02, bump_scale=40.0)


def _orca_fluke_skin():
    s = Skin("orca_fluke", 0.36)
    return s.finish(s.mix(s.above(s.nz, -0.35, 0.3), hexcol("#eef0ee"), hexcol("#08090b")))


def build_orca(dorsal="male"):
    """dorsal: 'male' (tall, straight) · 'female' (shorter, curved back) · 'port' / 'starboard' (a male's fin that
    has collapsed to the animal's left / right)."""
    body = loft_body("orca", [
        (2.00, -0.07, 0, 0, 0), (1.95, -0.06, 0.07, 0.065, 0.06), (1.82, -0.03, 0.155, 0.16, 0.14),
        (1.60, 0.0, 0.245, 0.265, 0.225), (1.25, 0.01, 0.335, 0.36, 0.33), (0.80, 0.02, 0.405, 0.425, 0.40),
        (0.30, 0.02, 0.43, 0.455, 0.435), (-0.20, 0.02, 0.39, 0.425, 0.405), (-0.70, 0.03, 0.285, 0.335, 0.315),
        (-1.15, 0.04, 0.165, 0.245, 0.225), (-1.50, 0.04, 0.09, 0.155, 0.135), (-1.76, 0.04, 0.055, 0.07, 0.06),
        (-1.86, 0.04, 0, 0, 0)])
    body.data.materials.append(_orca_skin())
    black = plain("orca_black", hexcol("#08090b"), rough=0.36)
    z0 = 0.36
    if dorsal == "female":
        d = fin("dorsal", [(0.44, z0), (0.26, 0.62), (0.06, 0.80), (-0.14, 0.86)], [(-0.10, z0 + 0.02), (-0.10, 0.56), (-0.14, 0.74), (-0.18, 0.855)], 0.09)
    else:
        warp = collapse(z0 + 0.10, 0.80, +1 if dorsal == "port" else -1) if dorsal in ("port", "starboard") else None
        d = fin("dorsal", [(0.52, z0), (0.38, 0.74), (0.26, 1.04), (0.15, 1.26)], [(-0.10, z0 + 0.02), (0.0, 0.72), (0.07, 1.02), (0.11, 1.25)], 0.10, n=14, warp=warp)
    flip = _pair("flipper", [(1.08, 0.30, -0.20), (0.96, 0.58, -0.36), (0.72, 0.82, -0.52), (0.46, 0.95, -0.62)],
                 [(0.62, 0.30, -0.27), (0.44, 0.52, -0.41), (0.32, 0.74, -0.55), (0.30, 0.92, -0.62)], 0.085, tip_thick=0.04)
    fluke = _pair("fluke", [(-1.50, 0.05, 0.04), (-1.72, 0.30, 0.045), (-1.93, 0.52, 0.05), (-2.07, 0.63, 0.055)],
                  [(-1.92, 0.0, 0.04), (-1.99, 0.22, 0.045), (-2.07, 0.45, 0.05), (-2.11, 0.62, 0.055)], 0.06)
    _give([d] + flip, black)
    _give(fluke, _orca_fluke_skin())
    eye = plain("eye", hexcol("#020203"), rough=0.05)
    for sd in (1, -1):
        ball(f"eye{sd}", (1.52, 0.262 * sd, -0.015), 0.022, eye)
    return body, (-2.11, 2.0), "pitch"


BUILDERS = {
    "greatWhite": build_great_white, "greatWhiteLiver": lambda: build_great_white(liver=True), "bronzeWhaler": build_bronze_whaler, "sevengill": build_sevengill,
    "fishBladder": build_bony_fish,
    "orca": lambda: build_orca("female"), "orcaMale": lambda: build_orca("male"),
    "orcaPort": lambda: build_orca("port"), "orcaStarboard": lambda: build_orca("starboard"),
}

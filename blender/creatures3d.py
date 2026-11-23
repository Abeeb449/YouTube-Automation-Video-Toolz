"""Procedural 3D sea creatures for ytauto — built, rigged, animated and rendered entirely from code in Blender.

Each creature is grown from a "spine" with Blender's Skin modifier (organic tubes) + subdivision, given a
procedural PBR material (no textures to download), rigged with an automatic armature, and animated with a
looping swim cycle. Output: a transparent PNG/WebP image sequence ("sprite") that ytauto composites into
videos with all the usual motion, camera moves and timing.

Usage (headless):
  blender -b --factory-startup -P blender/creatures3d.py -- --creature leopardSeal --view side \
      --out remotion/public/sprites/leopardSeal/side --frames 48 --size 1280x640 [--still]

Views: side (profile, facing right) · three_quarter (front-left 3/4, facing right) · below (seen from beneath)
       · rest (lying on land/ice, side view, for split shots)
"""
import argparse
import math
import sys

import bpy
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
ap = argparse.ArgumentParser()
ap.add_argument("--creature", default="leopardSeal")
ap.add_argument("--view", default="side")
ap.add_argument("--out", required=True)
ap.add_argument("--frames", type=int, default=48)
ap.add_argument("--size", default="1280x640")
ap.add_argument("--engine", default="EEVEE")
ap.add_argument("--samples", type=int, default=32)
ap.add_argument("--still", action="store_true")
args = ap.parse_args(argv)
W, H = (int(v) for v in args.size.split("x"))


def hexcol(h, a=1.0):
    h = h.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    lin = [((c + 0.055) / 1.055) ** 2.4 if c > 0.04045 else c / 12.92 for c in (r, g, b)]
    return (*lin, a)


# ------------------------------------------------------------------------------------------ geometry
def skin_body(name, spine, branches=()):
    """spine: [(x, y, z, rx, ry)], branches: [(attach_index, [(x, y, z, rx, ry), ...])] → skinned mesh object."""
    verts, edges, radii = [], [], []
    for i, (x, y, z, rx, ry) in enumerate(spine):
        verts.append((x, y, z))
        radii.append((rx, ry))
        if i:
            edges.append((i - 1, i))
    for attach, pts in branches:
        prev = attach
        for (x, y, z, rx, ry) in pts:
            verts.append((x, y, z))
            radii.append((rx, ry))
            edges.append((prev, len(verts) - 1))
            prev = len(verts) - 1
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, edges, [])
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    bpy.context.view_layer.objects.active = ob
    ob.select_set(True)
    mod = ob.modifiers.new("skin", "SKIN")
    mod.use_smooth_shade = True
    for i, r in enumerate(radii):
        ob.data.skin_vertices[0].data[i].radius = r
    ob.data.skin_vertices[0].data[0].use_root = True
    sub = ob.modifiers.new("sub", "SUBSURF")
    sub.levels = 2
    sub.render_levels = 3
    return ob


def skin_parts(name, spine, limbs, body_mat=None, limb_mat=None):
    """Body from a spine + each limb as its own skinned part (overlapping the body), joined into one mesh."""
    body = skin_body(name, spine)
    apply_all(body)
    if body_mat:
        body.data.materials.append(body_mat)
    parts = [body]
    for j, pts in enumerate(limbs):
        limb = skin_body(f"{name}_limb{j}", pts)
        apply_all(limb)
        if limb_mat:
            limb.data.materials.append(limb_mat)
        parts.append(limb)
    bpy.ops.object.select_all(action="DESELECT")
    for p in parts:
        p.select_set(True)
    bpy.context.view_layer.objects.active = body
    bpy.ops.object.join()
    return body


def apply_all(ob):
    bpy.context.view_layer.objects.active = ob
    for m in list(ob.modifiers):
        bpy.ops.object.modifier_apply(modifier=m.name)


def sphere(name, loc, r, mat):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=r, location=loc, segments=24, ring_count=12)
    o = bpy.context.active_object
    o.name = name
    bpy.ops.object.shade_smooth()
    o.data.materials.append(mat)
    return o


# ------------------------------------------------------------------------------------------ materials
def mat_spotted(name, base, dark, belly, spot_scale=7.0, rough=0.38, mouth=None):
    """Wet skin: base colour, darker procedural spots (Voronoi), lighter belly (object Z gradient)."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(tc.outputs["Object"], sep.inputs[0])
    # belly gradient: lower half lighter
    belly_ramp = nt.nodes.new("ShaderNodeMapRange")
    belly_ramp.inputs["From Min"].default_value = -0.25
    belly_ramp.inputs["From Max"].default_value = 0.12
    nt.links.new(sep.outputs["Z"], belly_ramp.inputs["Value"])
    mix_belly = nt.nodes.new("ShaderNodeMix")
    mix_belly.data_type = "RGBA"
    mix_belly.inputs["A"].default_value = belly
    mix_belly.inputs["B"].default_value = base
    nt.links.new(belly_ramp.outputs["Result"], mix_belly.inputs["Factor"])
    # spots
    vor = nt.nodes.new("ShaderNodeTexVoronoi")
    vor.inputs["Scale"].default_value = spot_scale
    vor.inputs["Randomness"].default_value = 1.0
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 3.0
    warp = nt.nodes.new("ShaderNodeVectorMath")
    warp.operation = "ADD"
    nt.links.new(tc.outputs["Object"], warp.inputs[0])
    nt.links.new(noise.outputs["Color"], warp.inputs[1])
    scale_w = nt.nodes.new("ShaderNodeVectorMath")
    scale_w.operation = "SCALE"
    scale_w.inputs["Scale"].default_value = 0.15
    nt.links.new(noise.outputs["Color"], scale_w.inputs[0])
    nt.links.new(tc.outputs["Object"], warp.inputs[0])
    nt.links.new(scale_w.outputs[0], warp.inputs[1])
    nt.links.new(warp.outputs[0], vor.inputs["Vector"])
    spot = nt.nodes.new("ShaderNodeMapRange")
    spot.inputs["From Min"].default_value = 0.16
    spot.inputs["From Max"].default_value = 0.24
    spot.inputs["To Min"].default_value = 1.0
    spot.inputs["To Max"].default_value = 0.0
    nt.links.new(vor.outputs["Distance"], spot.inputs["Value"])
    # fewer spots on the belly
    spot_mask = nt.nodes.new("ShaderNodeMath")
    spot_mask.operation = "MULTIPLY"
    nt.links.new(spot.outputs["Result"], spot_mask.inputs[0])
    nt.links.new(belly_ramp.outputs["Result"], spot_mask.inputs[1])
    mix_spot = nt.nodes.new("ShaderNodeMix")
    mix_spot.data_type = "RGBA"
    nt.links.new(spot_mask.outputs[0], mix_spot.inputs["Factor"])
    nt.links.new(mix_belly.outputs["Result"], mix_spot.inputs["A"])
    mix_spot.inputs["B"].default_value = dark
    final = mix_spot.outputs["Result"]
    if mouth:  # paint a long dark jawline: z ≈ z0 + slope*(x - x0) for x in [x0, x1]
        x0, x1, z0, slope, width = mouth
        line = nt.nodes.new("ShaderNodeMath"); line.operation = "MULTIPLY"; line.inputs[1].default_value = slope
        dx = nt.nodes.new("ShaderNodeMath"); dx.operation = "SUBTRACT"; dx.inputs[1].default_value = x0
        nt.links.new(sep.outputs["X"], dx.inputs[0]); nt.links.new(dx.outputs[0], line.inputs[0])
        zt = nt.nodes.new("ShaderNodeMath"); zt.operation = "ADD"; zt.inputs[1].default_value = z0
        nt.links.new(line.outputs[0], zt.inputs[0])
        diff = nt.nodes.new("ShaderNodeMath"); diff.operation = "SUBTRACT"
        nt.links.new(sep.outputs["Z"], diff.inputs[0]); nt.links.new(zt.outputs[0], diff.inputs[1])
        ab = nt.nodes.new("ShaderNodeMath"); ab.operation = "ABSOLUTE"; nt.links.new(diff.outputs[0], ab.inputs[0])
        band = nt.nodes.new("ShaderNodeMapRange")
        band.inputs["From Min"].default_value = width * 0.5; band.inputs["From Max"].default_value = width
        band.inputs["To Min"].default_value = 1.0; band.inputs["To Max"].default_value = 0.0
        nt.links.new(ab.outputs[0], band.inputs["Value"])
        xin = nt.nodes.new("ShaderNodeMapRange")
        xin.inputs["From Min"].default_value = x0; xin.inputs["From Max"].default_value = x0 + 0.08
        nt.links.new(sep.outputs["X"], xin.inputs["Value"])
        xout = nt.nodes.new("ShaderNodeMapRange")
        xout.inputs["From Min"].default_value = x1; xout.inputs["From Max"].default_value = x1 - 0.05
        nt.links.new(sep.outputs["X"], xout.inputs["Value"])
        m1 = nt.nodes.new("ShaderNodeMath"); m1.operation = "MULTIPLY"
        nt.links.new(band.outputs["Result"], m1.inputs[0]); nt.links.new(xin.outputs["Result"], m1.inputs[1])
        m2 = nt.nodes.new("ShaderNodeMath"); m2.operation = "MULTIPLY"
        nt.links.new(m1.outputs[0], m2.inputs[0]); nt.links.new(xout.outputs["Result"], m2.inputs[1])
        mm = nt.nodes.new("ShaderNodeMix"); mm.data_type = "RGBA"
        nt.links.new(m2.outputs[0], mm.inputs["Factor"]); nt.links.new(final, mm.inputs["A"])
        mm.inputs["B"].default_value = (0.012, 0.012, 0.014, 1)
        final = mm.outputs["Result"]
    nt.links.new(final, bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = rough
    # subtle skin bump
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.08
    nt.links.new(noise.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    for key in ("Specular IOR Level", "Specular"):
        if key in bsdf.inputs:
            bsdf.inputs[key].default_value = 0.6
            break
    if "Coat Weight" in bsdf.inputs:  # wet sheen (Blender 4.x)
        bsdf.inputs["Coat Weight"].default_value = 0.35
        bsdf.inputs["Coat Roughness"].default_value = 0.15
    return m


def mat_plain(name, col, rough=0.3, metallic=0.0, emission=None, strength=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = col
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metallic
    if emission is not None:
        key = "Emission Color" if "Emission Color" in b.inputs else "Emission"
        b.inputs[key].default_value = emission
        b.inputs["Emission Strength"].default_value = strength
    return m


# ------------------------------------------------------------------------------------------ creatures
def build_leopard_seal():
    # Big reptilian head on a clearly narrower neck, heavy shoulders, long tapering body,
    # long fore flippers and broad paddle-shaped hind flippers.
    spine = [
        (-1.78, 0, 0.0, 0.08, 0.06),
        (-1.45, 0, 0.0, 0.19, 0.17),
        (-0.95, 0, 0.0, 0.32, 0.30),
        (-0.40, 0, 0.0, 0.41, 0.39),
        (0.15, 0, 0.0, 0.45, 0.42),
        (0.62, 0, 0.03, 0.36, 0.34),
        (0.92, 0, 0.07, 0.24, 0.23),    # neck: obvious constriction
        (1.16, 0, 0.11, 0.34, 0.33),    # wide skull
        (1.42, 0, 0.10, 0.33, 0.28),
        (1.70, 0, 0.06, 0.25, 0.19),    # long broad snout
        (1.95, 0, 0.02, 0.15, 0.11),
        (2.12, 0, 0.0, 0.07, 0.05),
    ]
    limbs = [
        [(0.55, 0.24, -0.15, 0.15, 0.07), (0.35, 0.44, -0.40, 0.13, 0.04), (0.05, 0.52, -0.60, 0.10, 0.028), (-0.25, 0.55, -0.72, 0.05, 0.02)],
        [(0.55, -0.24, -0.15, 0.15, 0.07), (0.35, -0.44, -0.40, 0.13, 0.04), (0.05, -0.52, -0.60, 0.10, 0.028), (-0.25, -0.55, -0.72, 0.05, 0.02)],
        [(-1.62, 0.07, 0.0, 0.10, 0.07), (-1.95, 0.17, 0.02, 0.18, 0.05), (-2.30, 0.27, 0.04, 0.26, 0.035)],
        [(-1.62, -0.07, 0.0, 0.10, 0.07), (-1.95, -0.17, -0.02, 0.18, 0.05), (-2.30, -0.27, -0.04, 0.26, 0.035)],
    ]
    if args.view == "rest":  # hauled out on ice: fore flippers tucked along the flanks, belly on the ground
        limbs[0] = [(0.5, 0.30, -0.25, 0.13, 0.05), (0.2, 0.42, -0.36, 0.11, 0.03), (-0.15, 0.45, -0.40, 0.07, 0.02)]
        limbs[1] = [(0.5, -0.30, -0.25, 0.13, 0.05), (0.2, -0.42, -0.36, 0.11, 0.03), (-0.15, -0.45, -0.40, 0.07, 0.02)]
        limbs[2] = [(-1.62, 0.07, -0.05, 0.10, 0.07), (-1.95, 0.17, -0.12, 0.18, 0.05), (-2.30, 0.27, -0.18, 0.24, 0.03)]
        limbs[3] = [(-1.62, -0.07, -0.05, 0.10, 0.07), (-1.95, -0.17, -0.12, 0.18, 0.05), (-2.30, -0.27, -0.18, 0.24, 0.03)]
    skin = mat_spotted("ls_skin", hexcol("#4a545c"), hexcol("#22272b"), hexcol("#b7c1c7"), spot_scale=5.5,
                       mouth=(1.30, 2.10, -0.035, -0.06, 0.035))
    fin = mat_spotted("ls_fin", hexcol("#3e474e"), hexcol("#22272b"), hexcol("#5a646b"), spot_scale=9.0)
    body = skin_parts("leopardSeal", spine, limbs, body_mat=skin, limb_mat=fin)
    eye = mat_plain("eye", hexcol("#030405"), rough=0.04)
    for side in (1, -1):
        sphere(f"eye{side}", (1.56, 0.24 * side, 0.2), 0.045, eye)
    return body, [(-2.4, 2.14)]


def build_sea_lion(pup=False):
    """Eared seal (sea lion / fur seal): sleek torpedo body, distinct head with a pointed muzzle,
    small external ears, long fore flippers, hind flippers attached right at the tail."""
    k = 0.62 if pup else 1.0
    spine = [
        (-1.40, 0, 0.0, 0.08, 0.06),
        (-1.15, 0, 0.0, 0.19, 0.17),
        (-0.70, 0, 0.0, 0.31, 0.28),
        (-0.15, 0, 0.0, 0.38, 0.35),
        (0.35, 0, 0.03, 0.36, 0.33),
        (0.72, 0, 0.08, 0.23, 0.22),    # neck
        (0.98, 0, 0.14, 0.22, 0.21),    # head
        (1.18, 0, 0.14, 0.19, 0.17),
        (1.36, 0, 0.11, 0.11, 0.10),    # pointed muzzle
        (1.47, 0, 0.09, 0.05, 0.05),
    ]
    limbs = [
        [(0.40, 0.22, -0.15, 0.14, 0.05), (0.20, 0.42, -0.42, 0.13, 0.03), (-0.05, 0.50, -0.62, 0.10, 0.02), (-0.30, 0.52, -0.72, 0.05, 0.015)],
        [(0.40, -0.22, -0.15, 0.14, 0.05), (0.20, -0.42, -0.42, 0.13, 0.03), (-0.05, -0.50, -0.62, 0.10, 0.02), (-0.30, -0.52, -0.72, 0.05, 0.015)],
        [(-1.30, 0.06, -0.02, 0.09, 0.05), (-1.62, 0.15, -0.06, 0.12, 0.03), (-1.88, 0.22, -0.08, 0.15, 0.02)],
        [(-1.30, -0.06, -0.02, 0.09, 0.05), (-1.62, -0.15, -0.06, 0.12, 0.03), (-1.88, -0.22, -0.08, 0.15, 0.02)],
    ]
    if args.view == "rest":  # on land: chest propped up on fore flippers planted forward, hind flippers flat
        limbs[0] = [(0.42, 0.24, -0.16, 0.14, 0.05), (0.60, 0.36, -0.34, 0.12, 0.04), (0.80, 0.42, -0.42, 0.10, 0.025), (0.98, 0.44, -0.43, 0.05, 0.02)]
        limbs[1] = [(0.42, -0.24, -0.16, 0.14, 0.05), (0.60, -0.36, -0.34, 0.12, 0.04), (0.80, -0.42, -0.42, 0.10, 0.025), (0.98, -0.44, -0.43, 0.05, 0.02)]
        limbs[2] = [(-1.30, 0.08, -0.10, 0.09, 0.05), (-1.55, 0.2, -0.28, 0.12, 0.03), (-1.75, 0.3, -0.34, 0.14, 0.02)]
        limbs[3] = [(-1.30, -0.08, -0.10, 0.09, 0.05), (-1.55, -0.2, -0.28, 0.12, 0.03), (-1.75, -0.3, -0.34, 0.14, 0.02)]
    g = 1.12 if pup else 1.0   # pups are chubbier
    spine = [(x * k, y, z * k, rx * k * g, ry * k * g) for x, y, z, rx, ry in spine]
    limbs = [[(x * k, y * k, z * k, rx * k, ry * k) for x, y, z, rx, ry in pts] for pts in limbs]
    fur = mat_spotted("sl_fur", hexcol("#5f4330" if not pup else "#4e4741"), hexcol("#3f2b1d"),
                      hexcol("#8a6a50" if not pup else "#6b625a"), spot_scale=45.0, rough=0.42)
    fin = mat_plain("sl_fin", hexcol("#2f221a"), rough=0.5)
    body = skin_parts("seaLion", spine, limbs, body_mat=fur, limb_mat=fin)
    eye = mat_plain("eye", hexcol("#050505"), rough=0.04)
    for side in (1, -1):
        sphere(f"eye{side}", (1.16 * k, 0.15 * k * side, 0.23 * k), 0.036 * k, eye)
    nose = mat_plain("nose", hexcol("#141010"), rough=0.3)
    sphere("nose", (1.47 * k, 0, 0.11 * k), 0.035 * k, nose)
    ear = mat_plain("ear", hexcol("#2c1f16"), rough=0.6)
    for side in (1, -1):
        bpy.ops.mesh.primitive_cone_add(radius1=0.02 * k, depth=0.05 * k, location=(1.0 * k, 0.19 * k * side, 0.28 * k))
        c = bpy.context.active_object
        c.rotation_euler = (math.radians(-50 * side), math.radians(-70), 0)
        c.data.materials.append(ear)
    return body, [(-1.9 * k, 1.5 * k)]


def build_penguin():
    # Built lying along X (head at +X) so it swims like the others; "stand" view rotates it upright.
    spine = [(-0.62, 0, 0.0, 0.07, 0.07), (-0.48, 0, 0.0, 0.22, 0.20), (-0.15, 0, 0.0, 0.31, 0.28),
             (0.20, 0, 0.0, 0.27, 0.25), (0.46, 0, 0.0, 0.18, 0.17), (0.62, 0, 0.0, 0.17, 0.16), (0.74, 0, 0.0, 0.07, 0.06)]
    limbs = [[(0.15, 0.26, -0.05, 0.07, 0.025), (-0.12, 0.36, -0.12, 0.05, 0.02), (-0.32, 0.4, -0.16, 0.03, 0.015)],
             [(0.15, -0.26, -0.05, 0.07, 0.025), (-0.12, -0.36, -0.12, 0.05, 0.02), (-0.32, -0.4, -0.16, 0.03, 0.015)],
             [(-0.55, 0.1, -0.12, 0.05, 0.03), (-0.66, 0.14, -0.2, 0.06, 0.02)],
             [(-0.55, -0.1, -0.12, 0.05, 0.03), (-0.66, -0.14, -0.2, 0.06, 0.02)]]
    m = bpy.data.materials.new("peng")
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(tc.outputs["Object"], sep.inputs[0])
    mr = nt.nodes.new("ShaderNodeMapRange")          # white belly = lower half (-Z), black back
    mr.inputs["From Min"].default_value = 0.02
    mr.inputs["From Max"].default_value = -0.04
    nt.links.new(sep.outputs["Z"], mr.inputs["Value"])
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    mix.inputs["A"].default_value = hexcol("#121417")
    mix.inputs["B"].default_value = hexcol("#eeeeea")
    nt.links.new(mr.outputs["Result"], mix.inputs["Factor"])
    nt.links.new(mix.outputs["Result"], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.45
    feet = mat_plain("feet", hexcol("#d9938c"), rough=0.5)
    flip = mat_plain("flipper", hexcol("#14161a"), rough=0.45)
    body = skin_parts("penguin", spine, limbs[:2], body_mat=m, limb_mat=flip)
    for j, pts in enumerate(limbs[2:]):
        f = skin_body(f"foot{j}", pts); apply_all(f); f.data.materials.append(feet)
        bpy.ops.object.select_all(action="DESELECT"); f.select_set(True); body.select_set(True)
        bpy.context.view_layer.objects.active = body; bpy.ops.object.join()
    eye = mat_plain("eye", hexcol("#050505"), rough=0.05)
    for side in (1, -1):
        sphere(f"eye{side}", (0.6, 0.12 * side, 0.08), 0.022, eye)
    beak = mat_plain("beak", hexcol("#1e1b19"), rough=0.4)
    bpy.ops.mesh.primitive_cone_add(radius1=0.045, depth=0.2, location=(0.83, 0, 0.0), rotation=(0, math.radians(90), 0))
    bpy.context.active_object.data.materials.append(beak)
    return body, [(-0.72, 0.95)]


REST_LIFT = {"seaLion": -0.42, "furSeal": -0.42, "seaLionPup": -0.35, "leopardSeal": -0.08}
BUILDERS = {"leopardSeal": build_leopard_seal, "seaLion": build_sea_lion, "furSeal": build_sea_lion,
            "seaLionPup": lambda: build_sea_lion(pup=True), "penguin": build_penguin}


# ------------------------------------------------------------------------------------------ rig + swim cycle
def rig_and_animate(body, extent, frames, mode):
    """Armature along X with automatic weights; a travelling wave from head to tail (pitch for side views)."""
    x0, x1 = extent
    n = 7
    # merge eyes, ears, nose into the body first so automatic weights make them follow every bend
    parts = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    bpy.ops.object.select_all(action="DESELECT")
    for o in parts:
        o.select_set(True)
    bpy.context.view_layer.objects.active = body
    if len(parts) > 1:
        bpy.ops.object.join()
    bpy.ops.object.armature_add(location=(0, 0, 0))
    arm = bpy.context.active_object
    bpy.ops.object.mode_set(mode="EDIT")
    eb = arm.data.edit_bones
    eb.remove(eb[0])
    prev = None
    bones = []
    for i in range(n):
        a = x1 - (x1 - x0) * i / n
        b = x1 - (x1 - x0) * (i + 1) / n
        bone = eb.new(f"b{i}")
        bone.head = (a, 0, 0)
        bone.tail = (b, 0, 0)
        if prev:
            bone.parent = prev
            bone.use_connect = True
        prev = bone
        bones.append(bone.name)
    bpy.ops.object.mode_set(mode="OBJECT")
    body.select_set(True)
    arm.select_set(True)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.parent_set(type="ARMATURE_AUTO")
    if mode == "still_rest":
        pb = arm.pose.bones
        lift = REST_LIFT.get(args.creature, 0.0)   # sea lions prop the chest and head up on their fore flippers
        # The chain's root is at the head: tilt the root up, then level the rear half again, so only head+chest rise.
        for name in bones:
            pb[name].rotation_mode = "XYZ"
        pb[bones[0]].rotation_euler = (lift * 0.35, 0, 0)
        pb[bones[1]].rotation_euler = (lift * 0.65, 0, 0)
        pb[bones[2]].rotation_euler = (-lift * 1.0, 0, 0)
        return arm
    pb = arm.pose.bones
    for f in range(frames + 1):
        ph = 2 * math.pi * f / frames
        for i, name in enumerate(bones):
            amp = 0.025 + 0.11 * (i / (n - 1)) ** 1.6     # stronger toward the tail
            pb[name].rotation_mode = "XYZ"
            pb[name].rotation_euler = (0, 0, amp * math.sin(ph - i * 0.75)) if mode == "yaw" else (amp * math.sin(ph - i * 0.75), 0, 0)
            pb[name].keyframe_insert("rotation_euler", frame=f + 1)
    for fc in (arm.animation_data.action.fcurves if arm.animation_data else []):
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"
    return arm


# ------------------------------------------------------------------------------------------ scene
def setup_scene(view):
    sc = bpy.context.scene
    sc.render.resolution_x, sc.render.resolution_y = W, H
    sc.render.film_transparent = True
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "RGBA"
    sc.frame_start, sc.frame_end = 1, args.frames
    sc.render.fps = 24
    if args.engine.upper().startswith("CYCLES"):
        sc.render.engine = "CYCLES"
        sc.cycles.device = "CPU"
        sc.cycles.samples = args.samples
        sc.cycles.use_denoising = bool(getattr(bpy.app.build_options, "openimagedenoise", False))
    else:
        sc.render.engine = "BLENDER_EEVEE_NEXT" if "BLENDER_EEVEE_NEXT" in [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items] else "BLENDER_EEVEE"
        ee = sc.eevee
        for attr, val in (("taa_render_samples", args.samples), ("use_gtao", True), ("use_soft_shadows", True),
                          ("use_ssr", True), ("use_bloom", False)):
            if hasattr(ee, attr):
                setattr(ee, attr, val)
    sc.view_settings.view_transform = "AgX" if "AgX" in [v.identifier for v in sc.view_settings.bl_rna.properties["view_transform"].enum_items] else "Filmic"
    sc.view_settings.look = "None"
    # underwater light: cool dim world, a soft key from above, a cyan rim from behind, warm-neutral fill
    w = bpy.data.worlds.new("w")
    w.use_nodes = True
    w.node_tree.nodes["Background"].inputs[0].default_value = hexcol("#1d4a63")
    w.node_tree.nodes["Background"].inputs[1].default_value = 0.35
    sc.world = w

    def area(name, loc, energy, size, col, target=(0, 0, 0)):
        ld = bpy.data.lights.new(name, "AREA")
        ld.energy, ld.size, ld.color = energy, size, col
        lo = bpy.data.objects.new(name, ld)
        lo.location = loc
        sc.collection.objects.link(lo)
        d = Vector(target) - Vector(loc)
        lo.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()

    area("key", (0.8, -2.5, 4.5), 260, 3.5, (0.86, 0.95, 1.0))      # sunlight filtering down
    area("rim", (-2.5, 3.5, 2.2), 320, 2.5, (0.45, 0.8, 1.0))       # cyan back-light separates it from dark water
    area("fill", (2.0, -5.0, -1.8), 45, 5.0, (0.55, 0.65, 0.75))     # bounce from below

    cam_d = bpy.data.cameras.new("cam")
    cam = bpy.data.objects.new("cam", cam_d)
    sc.collection.objects.link(cam)
    sc.camera = cam
    cam_d.type = "ORTHO"
    if view == "three_quarter":
        cam_d.type = "PERSP"
        cam_d.lens = 50
        cam.location = (4.2, -7.0, 1.6)
    elif view == "below":
        cam.location = (0, 0, -9)
    else:  # side / rest: long lens, slightly above → reads as 3D but stays a clean profile
        cam_d.type = "PERSP"
        cam_d.lens = 85
        cam.location = (0, -11, 1.6)
    d = Vector((0, 0, 0)) - cam.location
    cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    return cam


def frame_object(cam, obj_extent, view):
    x0, x1 = obj_extent
    span = (x1 - x0)
    if cam.data.type == "ORTHO":
        cam.data.ortho_scale = span * 1.12
        cam.location.x = (x0 + x1) / 2
    elif view in ("side", "rest"):
        # distance so the creature fills ~88% of the frame width at 85 mm (sensor 36 mm)
        dist = span * 1.14 * cam.data.lens / 36.0
        cam.location = Vector(((x0 + x1) / 2, -dist, dist * 0.14))
        d = Vector(((x0 + x1) / 2, 0, 0)) - cam.location
        cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    else:
        cam.location = Vector(((x0 + x1) / 2 + 3.6, -6.4, 1.4)) * (span / 3.9)
        d = Vector(((x0 + x1) / 2, 0, 0)) - cam.location
        cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()


def fit_camera_to_bounds(cam, objs, margin=1.1):
    """Aim the camera at the evaluated bounding box of the posed creature and size it to fill the frame."""
    import bpy_extras  # noqa: F401
    deps = bpy.context.evaluated_depsgraph_get()
    pts = []
    for o in objs:
        ev = o.evaluated_get(deps)
        me = ev.to_mesh()
        pts += [ev.matrix_world @ v.co for v in me.vertices]
        ev.to_mesh_clear()
    if not pts:
        return
    mn = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    mx = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    c = (mn + mx) / 2
    w = (mx.x - mn.x) * margin
    h = (mx.z - mn.z) * margin
    aspect = W / H
    # Blender fits ortho_scale / lens to the LARGER frame dimension
    span = max(w, h * aspect) if W >= H else max(h, w / aspect)
    d = cam.location - c if cam.data.type != "ORTHO" else Vector((0, -1, 0))
    if cam.data.type == "ORTHO":
        cam.data.ortho_scale = span
        cam.location = Vector((c.x, cam.location.y, c.z))
    else:
        dist = span * cam.data.lens / 36.0
        dirv = (cam.location - c).normalized()
        cam.location = c + dirv * dist
        cam.rotation_euler = (c - cam.location).to_track_quat("-Z", "Y").to_euler()


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    build = BUILDERS[args.creature]
    body, ext = build()
    extent = ext[0]
    view = args.view
    if view in ("rest", "stand"):
        mode = "still_rest"
    else:
        mode = "pitch" if view in ("side", "three_quarter") else "yaw"
    arm = rig_and_animate(body, extent, args.frames, mode)
    if view == "below":
        arm.rotation_euler = (0, 0, 0)
    if args.creature == "penguin" and view == "stand":
        arm.rotation_euler = (0, math.radians(-90), 0)   # head up
    cam = setup_scene(view)
    frame_object(cam, (extent[0], extent[1]), view)
    if view == "stand":  # tall subject: frame vertically
        cam.data.type = "ORTHO"
        cam.data.ortho_scale = (extent[1] - extent[0]) * 1.15
        cam.location = Vector((0.0, -9.0, 0.1))
        cam.rotation_euler = (math.radians(90), 0, 0)
    meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    bpy.context.scene.frame_set(1)
    fit_camera_to_bounds(cam, meshes, margin=1.12 if view != "three_quarter" else 1.18)
    sc = bpy.context.scene
    sc.render.filepath = f"{args.out}/" + ("still" if args.still else "f_####")
    if args.still:
        sc.frame_set(max(1, args.frames // 4))
        bpy.ops.render.render(write_still=True)
    else:
        bpy.ops.render.render(animation=True)


main()

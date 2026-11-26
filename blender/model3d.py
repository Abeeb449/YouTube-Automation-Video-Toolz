"""Any 3D model file → a turning, lit, transparent image sequence ("sprite set") that videos animate.

  blender -b --factory-startup -P blender/model3d.py -- --model file.glb --out DIR [--frames 72] [--size 1280x720]
                                                         [--swing 32] [--still] [--tint "#c8b48a"]

Reads glTF/GLB (also Draco-compressed), STL, OBJ, PLY and FBX. The model is centred, scaled to a standard size
and stood on its base; a model without materials (STL scans, print files) gets a soft studio clay finish in
`--tint`. The camera swings `--swing` degrees to each side of the front and back again (a seamless loop), a little
above eye level, so the subject always reads as a solid 3D object. Lighting is a three-point studio set-up that
suits any dark documentary backdrop.
"""
import argparse
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
ap = argparse.ArgumentParser()
ap.add_argument("--model")
ap.add_argument("--build")       # a hand-built model: a script in blender/handmade/ with a build() function
ap.add_argument("--views", action="store_true")   # check sheet: front, right, back, left and from above (5 stills)
ap.add_argument("--out", required=True)
ap.add_argument("--frames", type=int, default=96)
ap.add_argument("--size", default="1280x720")
ap.add_argument("--swing", type=float, default=32.0)      # degrees to each side
ap.add_argument("--elevation", type=float, default=14.0)  # camera height angle
ap.add_argument("--front", type=float, default=0.0)       # turn the model's front (degrees about the vertical)
ap.add_argument("--tint", default="#cfc6b4")
ap.add_argument("--engine", default="EEVEE")
ap.add_argument("--samples", type=int, default=8)   # looks the same as 24 on these studio shots, 2x faster
ap.add_argument("--still", action="store_true")
args = ap.parse_args(argv)
W, H = (int(x) for x in args.size.lower().split("x"))


def hex_rgb(h: str):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)) + (1.0,)


def import_model(path: Path):
    ext = path.suffix.lower()
    before = set(bpy.data.objects)
    if ext in (".glb", ".gltf"):
        bpy.ops.import_scene.gltf(filepath=str(path))
    elif ext == ".stl":
        try:
            bpy.ops.wm.stl_import(filepath=str(path))
        except Exception:  # noqa: BLE001 — older builds
            bpy.ops.import_mesh.stl(filepath=str(path))
    elif ext == ".obj":
        bpy.ops.wm.obj_import(filepath=str(path))
    elif ext == ".ply":
        try:
            bpy.ops.wm.ply_import(filepath=str(path))
        except Exception:  # noqa: BLE001
            bpy.ops.import_mesh.ply(filepath=str(path))
    elif ext == ".fbx":
        bpy.ops.import_scene.fbx(filepath=str(path))
    else:
        raise SystemExit(f"Unsupported 3D model format {ext!r} (use glb, gltf, stl, obj, ply or fbx)")
    return [o for o in bpy.data.objects if o not in before]


def world_bounds(meshes):
    lo, hi = Vector((1e18,) * 3), Vector((-1e18,) * 3)
    for o in meshes:
        for c in o.bound_box:
            p = o.matrix_world @ Vector(c)
            lo = Vector(map(min, lo, p))
            hi = Vector(map(max, hi, p))
    return lo, hi


def main():
    # empty scene
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    sc = bpy.context.scene
    if args.build:
        # a hand-built model: run its script (it uses blender/kit3d.py) and take what it made
        import runpy
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        before = set(bpy.data.objects)
        mod = runpy.run_path(args.build)
        mod["build"]()
        new = [o for o in bpy.data.objects if o not in before]
        for name, attr in (("FRONT", "front"), ("ELEVATION", "elevation"), ("SWING", "swing")):
            if name in mod:
                setattr(args, attr, float(mod[name]))
    elif args.model:
        new = import_model(Path(args.model))
    else:
        raise SystemExit("Give --model FILE or --build SCRIPT")
    meshes = [o for o in new if o.type == "MESH" and len(o.data.polygons)]
    if not meshes:
        raise SystemExit("The model holds no surfaces to render")
    for o in new:                       # cameras, lights and helpers that came with the file are not wanted
        if o.type in ("CAMERA", "LIGHT"):
            bpy.data.objects.remove(o, do_unlink=True)
    bpy.context.view_layer.update()

    # one pivot for the whole model: centre it, stand it on z = 0, scale its longest side to 2 units
    lo, hi = world_bounds(meshes)
    size = hi - lo
    longest = max(size.x, size.y, size.z) or 1.0
    pivot = bpy.data.objects.new("pivot", None)
    sc.collection.objects.link(pivot)
    roots = [o for o in new if o.name in bpy.data.objects and o.parent is None]
    for o in roots:
        o.parent = pivot
    k = 2.0 / longest
    centre = (lo + hi) / 2
    pivot.scale = (k, k, k)
    pivot.location = (-centre.x * k, -centre.y * k, -lo.z * k)
    turn = bpy.data.objects.new("turn", None)      # the model's own facing
    sc.collection.objects.link(turn)
    pivot.parent = turn
    turn.rotation_euler = (0, 0, math.radians(args.front))
    bpy.context.view_layer.update()
    lo, hi = world_bounds(meshes)
    height = hi.z - lo.z
    radius = max(hi.x - lo.x, hi.y - lo.y) / 2

    # a model with no material of its own (STL scans, print files) gets a soft clay finish
    clay = None
    for o in meshes:
        has = any(s.material and s.material.use_nodes for s in o.material_slots)
        if not has:
            if clay is None:
                clay = bpy.data.materials.new("clay")
                clay.use_nodes = True
                b = clay.node_tree.nodes.get("Principled BSDF")
                b.inputs["Base Color"].default_value = hex_rgb(args.tint)
                b.inputs["Roughness"].default_value = 0.62
            o.data.materials.clear()
            o.data.materials.append(clay)
            for p in o.data.polygons:
                p.use_smooth = True

    # render settings
    sc.render.resolution_x, sc.render.resolution_y = W, H
    sc.render.resolution_percentage = 100
    sc.render.film_transparent = True
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "RGBA"
    engines = [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items]
    if args.engine.upper().startswith("CYCLES"):
        sc.render.engine = "CYCLES"
        sc.cycles.device = "CPU"
        sc.cycles.samples = args.samples
        sc.cycles.use_denoising = bool(getattr(bpy.app.build_options, "openimagedenoise", False))
    else:
        sc.render.engine = "BLENDER_EEVEE_NEXT" if "BLENDER_EEVEE_NEXT" in engines else "BLENDER_EEVEE"
        for attr, val in (("taa_render_samples", args.samples), ("use_gtao", True), ("use_soft_shadows", True)):
            if hasattr(sc.eevee, attr):
                setattr(sc.eevee, attr, val)
    try:
        sc.view_settings.view_transform = "Filmic"
        sc.view_settings.look = "Medium High Contrast"
    except Exception:  # noqa: BLE001
        pass

    # studio light: dim neutral world, warm key, cool rim from behind, soft fill
    world = bpy.data.worlds.new("w")
    world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    bg.inputs[0].default_value = (0.045, 0.055, 0.07, 1)
    bg.inputs[1].default_value = 1.0
    sc.world = world
    mid = Vector((0, 0, height / 2))

    def area(name, loc, power, size_, colour):
        ld = bpy.data.lights.new(name, "AREA")
        ld.energy, ld.size, ld.color = power, size_, colour
        ob = bpy.data.objects.new(name, ld)
        ob.location = loc
        sc.collection.objects.link(ob)
        ob.rotation_euler = (mid - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
        return ob

    area("key", (2.6, -3.4, height + 2.6), 420, 3.2, (1.0, 0.95, 0.88))
    area("rim", (-2.8, 3.6, height + 1.4), 520, 2.6, (0.62, 0.82, 1.0))
    area("fill", (-3.4, -2.2, height * 0.6), 120, 4.5, (0.82, 0.88, 1.0))

    # camera on a rig that swings around the vertical axis
    cam_d = bpy.data.cameras.new("cam")
    cam_d.lens = 70
    cam = bpy.data.objects.new("cam", cam_d)
    sc.collection.objects.link(cam)
    sc.camera = cam
    rig = bpy.data.objects.new("rig", None)
    rig.location = mid
    sc.collection.objects.link(rig)
    cam.parent = rig
    # distance so the whole model stays in frame at every angle of the swing
    half_w = max(radius, 0.05)
    half_h = max(height / 2, 0.05)
    fov_h = 2 * math.atan(36 / 2 / cam_d.lens)
    fov_v = 2 * math.atan((36 * H / W) / 2 / cam_d.lens)
    dist = max(half_w / math.tan(fov_h / 2), half_h / math.tan(fov_v / 2)) * 1.22 + radius
    el = math.radians(args.elevation)
    cam.location = (0, -dist * math.cos(el), dist * math.sin(el))
    cam.rotation_euler = (math.radians(90) - el, 0, 0)

    if args.views:      # the builder's check sheet: every side, then from above
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        for i, (turn_deg, el_deg) in enumerate([(0, args.elevation), (90, args.elevation), (180, args.elevation),
                                                (270, args.elevation), (35, 58)]):
            e = math.radians(el_deg)
            cam.location = (0, -dist * math.cos(e), dist * math.sin(e))
            cam.rotation_euler = (math.radians(90) - e, 0, 0)
            rig.rotation_euler = (0, 0, math.radians(turn_deg))
            sc.render.filepath = str(out / f"{i + 1:04d}.png")
            bpy.ops.render.render(write_still=True)
        print(f"model3d: 5 check views → {out}")
        return
    n = 1 if args.still else max(2, args.frames)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for i in range(n):
        # a smooth there-and-back swing: frame 0 and frame n meet, so the set loops without a jump
        phase = 0.0 if n == 1 else math.sin(2 * math.pi * i / n)
        rig.rotation_euler = (0, 0, math.radians(args.swing) * phase + math.radians(18))
        sc.render.filepath = str(out / f"{i + 1:04d}.png")
        bpy.ops.render.render(write_still=True)
    print(f"model3d: {n} frame(s) → {out}")


main()

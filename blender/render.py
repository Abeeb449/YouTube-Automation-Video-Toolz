"""Headless Blender renderer used by ytauto.

Run by ytauto as:
  blender -b --factory-startup -P blender/render.py -- --mode template --template intro --out DIR ...
  blender -b my.blend          -P blender/render.py -- --mode file --out DIR ...

Templates are built procedurally (no binary .blend files needed):
  intro   3D extruded title that flips up, camera dolly, floating glowing orbs
  spin    title slowly spinning on a reflective floor

Props (JSON, via --props): text, subtext, color (hex), accent (hex), bg (hex), font (path to .ttf),
resolution_percentage (default 50 for templates, 100 for .blend files)
Works with Blender 3.6+ / 4.x. Uses Cycles on the CPU so it runs on machines without a GPU.
"""
import argparse
import json
import math
import random
import sys

import bpy

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
ap = argparse.ArgumentParser()
ap.add_argument("--mode", default="template")
ap.add_argument("--template", default="intro")
ap.add_argument("--out", required=True)
ap.add_argument("--duration", type=float, default=5)
ap.add_argument("--width", type=int, default=1920)
ap.add_argument("--height", type=int, default=1080)
ap.add_argument("--fps", type=int, default=30)
ap.add_argument("--samples", type=int, default=16)
ap.add_argument("--props", default="{}")
args = ap.parse_args(argv)
props = json.loads(args.props)
frames = max(1, round(args.duration * args.fps))


def hex_rgba(h, a=1.0):
    h = h.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    # sRGB -> linear
    lin = [((c + 0.055) / 1.055) ** 2.4 if c > 0.04045 else c / 12.92 for c in (r, g, b)]
    return (*lin, a)


def setup_render(scene):
    scene.render.resolution_x = args.width
    scene.render.resolution_y = args.height
    # CPU path tracing is slow; templates render at 50% and ffmpeg upscales (set the
    # "resolution_percentage" prop to 100 for full quality). .blend files default to 100.
    scene.render.resolution_percentage = int(props.get("resolution_percentage", 50 if args.mode == "template" else 100))
    scene.render.fps = args.fps
    scene.frame_start = 1
    scene.frame_end = frames
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.filepath = f"{args.out}/frame_#####"
    if scene.render.engine != "CYCLES" and args.mode == "file":
        return  # respect the engine saved in a user's .blend
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = args.samples
    scene.cycles.use_adaptive_sampling = True
    # Official Blender builds ship OpenImageDenoise; some distro builds don't.
    scene.cycles.use_denoising = bool(getattr(bpy.app.build_options, "openimagedenoise", False))
    scene.render.use_persistent_data = True
    # Few bounces: these scenes are simple, and it keeps CPU renders fast.
    scene.cycles.max_bounces = 3
    scene.cycles.diffuse_bounces = 1
    scene.cycles.glossy_bounces = 2
    scene.cycles.transmission_bounces = 0
    scene.cycles.volume_bounces = 0
    scene.cycles.transparent_max_bounces = 2
    scene.cycles.adaptive_threshold = 0.05


def material(name, color, metallic=0.0, rough=0.4, emission=None, strength=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    bsdf = m.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = color
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Roughness"].default_value = rough
    if emission is not None:
        key = "Emission Color" if "Emission Color" in bsdf.inputs else "Emission"
        bsdf.inputs[key].default_value = emission
        bsdf.inputs["Emission Strength"].default_value = strength
    return m


def add_text(body, size, z, mat, extrude=0.12, font=None):
    curve = bpy.data.curves.new("txt", type="FONT")
    curve.body = body
    curve.size = size
    curve.extrude = extrude
    curve.bevel_depth = extrude * 0.25
    curve.bevel_resolution = 3
    curve.align_x = "CENTER"
    curve.align_y = "CENTER"
    if font:
        try:
            curve.font = bpy.data.fonts.load(font)
        except Exception:  # noqa: BLE001
            pass
    obj = bpy.data.objects.new("txt", curve)
    bpy.context.scene.collection.objects.link(obj)
    obj.location = (0, 0, z)
    obj.rotation_euler = (math.radians(90), 0, 0)
    obj.data.materials.append(mat)
    # Shrink very long titles so they fit the frame.
    if len(body) > 14:
        obj.scale = (14 / len(body),) * 3
    return obj


def add_camera(start, end, target):
    cam_data = bpy.data.cameras.new("cam")
    cam_data.lens = 40
    cam = bpy.data.objects.new("cam", cam_data)
    bpy.context.scene.collection.objects.link(cam)
    bpy.context.scene.camera = cam
    c = cam.constraints.new("TRACK_TO")
    c.target = target
    c.track_axis = "TRACK_NEGATIVE_Z"
    c.up_axis = "UP_Y"
    cam.location = start
    cam.keyframe_insert("location", frame=1)
    cam.location = end
    cam.keyframe_insert("location", frame=frames)
    return cam


def add_light(loc, energy, size=5, color=(1, 1, 1)):
    ld = bpy.data.lights.new("area", type="AREA")
    ld.energy = energy
    ld.size = size
    ld.color = color
    lo = bpy.data.objects.new("area", ld)
    lo.location = loc
    bpy.context.scene.collection.objects.link(lo)
    t = lo.constraints.new("TRACK_TO")
    t.target = bpy.data.objects.get("pivot")
    t.track_axis = "TRACK_NEGATIVE_Z"
    t.up_axis = "UP_Y"
    return lo


def world(color, strength=1.0):
    w = bpy.data.worlds.new("world")
    w.use_nodes = True
    bg = w.node_tree.nodes.get("Background")
    bg.inputs[0].default_value = color
    bg.inputs[1].default_value = strength
    bpy.context.scene.world = w


def build_template(name):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    text = str(props.get("text", "MY CHANNEL"))
    subtext = props.get("subtext")
    color = hex_rgba(props.get("color", "#f8fafc"))
    accent = hex_rgba(props.get("accent", "#facc15"))
    bg = hex_rgba(props.get("bg", "#0b1020"))
    font = props.get("font")

    pivot = bpy.data.objects.new("pivot", None)
    scene.collection.objects.link(pivot)
    world(bg, 0.6)

    title_mat = material("title", color, metallic=0.85, rough=0.25)
    title = add_text(text, 1.6, 0.4 if subtext else 0, title_mat, font=font)
    if subtext:
        add_text(str(subtext), 0.55, -0.9, material("sub", accent, emission=accent, strength=2.5), extrude=0.03, font=font)

    # Floor for reflections
    bpy.ops.mesh.primitive_plane_add(size=60, location=(0, 0, -1.6))
    bpy.context.active_object.data.materials.append(material("floor", bg, metallic=0.0, rough=0.55))

    add_light((-6, -6, 6), 900, 6)
    add_light((6, -4, 3), 500, 4, (accent[0] * 0.5 + 0.5, accent[1] * 0.5 + 0.5, accent[2] * 0.5 + 0.5))
    add_light((0, 6, 4), 700, 8)

    if name == "intro":
        # Title flips up and scales in during the first second.
        settle = min(frames, int(args.fps * 1.2))
        title.rotation_euler = (math.radians(0), 0, 0)
        title.scale = tuple(s * 0.2 for s in title.scale)
        title.keyframe_insert("rotation_euler", frame=1)
        title.keyframe_insert("scale", frame=1)
        title.rotation_euler = (math.radians(90), 0, 0)
        title.scale = tuple(s * 5 for s in title.scale)
        title.keyframe_insert("rotation_euler", frame=settle)
        title.keyframe_insert("scale", frame=settle)
        rnd = random.Random(7)
        orb_mat = material("orb", accent, emission=accent, strength=6)
        for _ in range(28):
            loc = (rnd.uniform(-12, 12), rnd.uniform(2, 14), rnd.uniform(-1, 7))
            bpy.ops.mesh.primitive_uv_sphere_add(radius=rnd.uniform(0.05, 0.22), location=loc, segments=16, ring_count=8)
            orb = bpy.context.active_object
            orb.data.materials.append(orb_mat)
            orb.keyframe_insert("location", frame=1)
            orb.location = (loc[0], loc[1], loc[2] + rnd.uniform(0.5, 1.5))
            orb.keyframe_insert("location", frame=frames)
        add_camera((0, -16, 2.5), (0, -11, 0.6), pivot)
    elif name == "spin":
        title.keyframe_insert("rotation_euler", frame=1)
        title.rotation_euler = (math.radians(90), 0, math.radians(360 * max(1, round(args.duration / 6))))
        title.keyframe_insert("rotation_euler", frame=frames)
        add_camera((0, -12, 3), (0, -10, 1.5), pivot)
    else:
        raise SystemExit(f"Unknown Blender template {name!r} (available: intro, spin)")
    return scene


if args.mode == "file":
    scene = bpy.context.scene
    start = scene.frame_start
    setup_render(scene)
    # Render `duration` worth of frames starting at the file's own first frame.
    scene.frame_start = start
    scene.frame_end = start + frames - 1
else:
    scene = build_template(args.template)
    setup_render(scene)

bpy.ops.render.render(animation=True)

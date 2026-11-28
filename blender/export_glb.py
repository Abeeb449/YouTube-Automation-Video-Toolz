"""Export one of the hand-built animals as a real 3D file (GLB) for the live 3D scenes (remotion/src/stage).

    blender -b --factory-startup -P blender/export_glb.py -- --creature greatWhite --out /path/greatWhite.glb

The animal is built exactly as for the picture sets (blender/sealife.py). Its painted skin, which Blender draws with
formulas, is baked into one colour picture so the same pattern shows in the browser's 3D. Parts that a scene may
show or hide on their own (a liver, a swim bladder) stay separate objects with their own names.
Beside the GLB a small JSON says how long the animal is in model units, how it swims and where its named points are
(eye, dorsal fin, liver …), so labels can be pinned to them.
"""
import argparse
import json
import sys
from pathlib import Path

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sealife  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--creature", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--tex", type=int, default=2048)
ap.add_argument("--levels", type=int, default=2)
args = ap.parse_args(sys.argv[sys.argv.index("--") + 1:])

# Named points in the animal's own coordinates (x toward the nose, y to its left, z up), read off the model's numbers.
POINTS = {
    "greatWhite": {"nose": (2.0, 0, 0.03), "eye": (1.60, 0.17, 0.085), "mouth": (1.46, 0.0, -0.13), "gills": (0.98, 0.31, 0.0),
                   "dorsal": (0.16, 0, 0.78), "chest": (0.72, 0.2, -0.33), "liver": (0.25, 0.0, -0.08), "belly": (0.2, 0, -0.38),
                   "tail": (-1.84, 0, 0.66), "back": (0.3, 0, 0.41), "flank": (0.2, 0.34, 0.0), "pectoral": (0.3, 0.8, -0.48)},
    "orca": {"nose": (2.0, 0, -0.07), "eye": (1.52, 0.262, -0.015), "eyepatch": (1.345, 0.34, 0.118), "mouth": (1.75, 0, -0.12),
             "dorsal": (-0.1, 0, 0.84), "dorsalBase": (0.2, 0, 0.44), "saddle": (-0.40, 0.2, 0.34), "flipper": (0.5, 0.9, -0.6),
             "fluke": (-2.0, 0, 0.05), "belly": (0.3, 0, -0.42), "flank": (0.3, 0.43, 0.0), "back": (0.9, 0, 0.44)},
    "sevengill": {"nose": (2.0, 0, 0), "eye": (1.72, 0.22, 0.06), "gills": (1.24, 0.27, -0.02), "dorsal": (-0.7, 0, 0.36),
                  "chest": (0.9, 0.2, -0.22), "liver": (0.4, 0, -0.06), "belly": (0.3, 0, -0.26), "tail": (-2.0, 0, 0.45), "flank": (0.3, 0.26, 0)},
    "bronzeWhaler": {"nose": (2.0, 0, 0), "eye": (1.66, 0.14, 0.05), "dorsal": (0.3, 0, 0.6), "tail": (-1.9, 0, 0.6), "flank": (0.3, 0.26, 0)},
    "fishBladder": {"nose": (2.0, 0, 0), "bladder": (0.2, 0, 0.21), "eye": (1.62, 0.165, 0.10)},
}
POINTS["orcaMale"] = {**POINTS["orca"], "dorsal": (0.14, 0, 1.24)}
POINTS["orcaPort"] = {**POINTS["orca"], "dorsal": (0.2, 0.42, 0.74)}
POINTS["orcaStarboard"] = {**POINTS["orca"], "dorsal": (0.2, -0.42, 0.74)}
SEPARATE = ("liver", "bladder")          # parts kept as their own objects (shown, hidden or lit by the scene)


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = 1
    sc.cycles.use_denoising = False          # not needed for flat colour, and missing from some Blender builds
    name = args.creature
    sealife.POSE = "swim"
    if name == "greatWhite":
        body, extent, swim = sealife.build_great_white()
        sealife.shark_liver()
    elif name == "sevengill":
        body, extent, swim = sealife.build_sevengill()
        for o in sealife.shark_liver():           # the same organ, a little smaller and further back in this body
            o.scale = (0.86, 0.80, 0.62)
            o.location = (0.12, 0.0, -0.01)
    elif name == "fishBladder":
        # the bony fish is built as glass; here its skin stays solid and the scene makes it see-through
        keep, sealife.see_through = sealife.see_through, lambda *a, **k: None
        body, extent, swim = sealife.build_bony_fish()
        sealife.see_through = keep
    else:
        body, extent, swim = sealife.BUILDERS[name]()
    meshes = [o for o in sc.objects if o.type == "MESH"]
    for o in meshes:
        for m in o.modifiers:
            if m.type == "SUBSURF":
                m.levels = m.render_levels = args.levels
    dg = bpy.context.evaluated_depsgraph_get()
    skin, parts = [], []
    for o in meshes:
        bpy.context.view_layer.objects.active = o
        for o2 in sc.objects:
            o2.select_set(o2 is o)
        bpy.ops.object.convert(target="MESH")
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
        (parts if o.name.startswith(SEPARATE) else skin).append(o)
    # one skin object, one colour picture
    for o2 in sc.objects:
        o2.select_set(o2 in skin)
    bpy.context.view_layer.objects.active = body
    bpy.ops.object.join()
    ob = bpy.context.view_layer.objects.active
    ob.name = "skin"
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=1.15, island_margin=0.004, area_weight=0.0)
    bpy.ops.object.mode_set(mode="OBJECT")
    img = bpy.data.images.new("skin", args.tex, args.tex, alpha=False)
    for slot in ob.material_slots:
        nt = slot.material.node_tree
        node = nt.nodes.new("ShaderNodeTexImage")
        node.image = img
        nt.nodes.active = node
        # only the painted colour is wanted (no light, no shine, no glass): it is sent out as a plain glow and baked
        bsdf = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
        out = next((n for n in nt.nodes if n.type == "OUTPUT_MATERIAL"), None)
        if bsdf and out:
            glow = nt.nodes.new("ShaderNodeEmission")
            base = bsdf.inputs["Base Color"]
            if base.is_linked:
                nt.links.new(base.links[0].from_socket, glow.inputs["Color"])
            else:
                glow.inputs["Color"].default_value = base.default_value
            nt.links.new(glow.outputs[0], out.inputs["Surface"])
        nt.nodes.active = node
    sc.render.bake.margin = 12
    bpy.ops.object.bake(type="EMIT")
    tex_path = Path(args.out).with_suffix(".png")
    img.filepath_raw = str(tex_path)
    img.file_format = "PNG"
    img.save()
    # the exported material: the baked picture, nothing else
    mat = bpy.data.materials.new(f"{name}_skin")
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = img
    nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.42
    ob.data.materials.clear()
    ob.data.materials.append(mat)
    for p in ob.data.polygons:
        p.material_index = 0
        p.use_smooth = True
    # separate parts: one object per kind
    kinds = {}
    for p in parts:
        kinds.setdefault(next(k for k in SEPARATE if p.name.startswith(k)), []).append(p)
    for kind, obs in kinds.items():
        for o2 in sc.objects:
            o2.select_set(o2 in obs)
        bpy.context.view_layer.objects.active = obs[0]
        if len(obs) > 1:
            bpy.ops.object.join()
        part = bpy.context.view_layer.objects.active
        part.name = kind
        plain = bpy.data.materials.new(kind)
        plain.use_nodes = True
        col = (0.80, 0.42, 0.10, 1.0) if kind == "liver" else (0.86, 0.94, 0.97, 1.0)
        plain.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = col
        part.data.materials.clear()
        part.data.materials.append(plain)
    for o2 in sc.objects:
        o2.select_set(o2.type == "MESH")
    bpy.ops.export_scene.gltf(filepath=args.out, export_format="GLB", use_selection=True, export_apply=True,
                              export_yup=True, export_image_format="JPEG", export_jpeg_quality=92,
                              export_animations=False, export_materials="EXPORT")
    tex_path.unlink(missing_ok=True)
    tris = sum(len(p.vertices) - 2 for o in sc.objects if o.type == "MESH" for p in o.data.polygons)
    meta = {"creature": name, "tail": extent[0], "nose": extent[1], "swim": swim, "triangles": tris,
            "points": {k: [v[0], v[2], -v[1]] for k, v in POINTS.get(name, {}).items()},      # → y up, like the GLB
            "parts": sorted(kinds)}
    Path(args.out).with_suffix(".json").write_text(json.dumps(meta, indent=1))
    print("EXPORTED", args.out, tris, "triangles")


main()

"""Building blocks for hand-built 3D models (blender/handmade/*.py).

A hand-built model is made only when no free-licence model of the subject exists. It must be TRUE to the real
thing: real proportions (work in metres), every part in its real place and facing its real direction, nothing
invented. Each model script states its facts and sources at the top; `python -m ytauto model <name> --views`
renders it from every side so it can be compared with reference photos before it is used in a video.

Conventions: Z is up, +Y is north (or the subject's back), +X is east (its right-hand side seen from behind).
Units are metres; the renderer scales the finished model to fit the frame.

What is here: procedural PBR materials (colour variation, roughness and bump from noise; brick/block joints),
and modelling helpers that wrap Blender's own tools: lathe (screw), bevel, subdivision surface, solidify, array,
boolean cut, displacement, smooth shading with sharp edges kept.
"""
import math

import bmesh
import bpy
from mathutils import Vector


# ------------------------------------------------------------------------------------------------ objects
def new_object(name: str, bm: "bmesh.types.BMesh") -> bpy.types.Object:
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def box(name: str, size, location=(0, 0, 0)) -> bpy.types.Object:
    """A box `size` = (x, y, z) metres with its centre at `location`."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co = Vector((v.co.x * size[0], v.co.y * size[1], v.co.z * size[2])) + Vector(location)
    return new_object(name, bm)


def cylinder(name: str, radius: float, depth: float, location=(0, 0, 0), segments: int = 48, axis: str = "Z"):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=segments, radius1=radius, radius2=radius, depth=depth)
    ob = new_object(name, bm)
    ob.rotation_euler = {"Z": (0, 0, 0), "X": (0, math.pi / 2, 0), "Y": (math.pi / 2, 0, 0)}[axis]
    ob.location = location
    return ob


def lathe(name: str, profile, segments: int = 64) -> bpy.types.Object:
    """Spin a profile [(radius, z), …] around the Z axis (vases, domes, columns, nozzles, bells)."""
    bm = bmesh.new()
    rings = []
    for r, z in profile:
        rings.append([bm.verts.new((r * math.cos(2 * math.pi * k / segments), r * math.sin(2 * math.pi * k / segments), z))
                      for k in range(segments)])
    for a, b in zip(rings, rings[1:]):
        for k in range(segments):
            bm.faces.new((a[k], a[(k + 1) % segments], b[(k + 1) % segments], b[k]))
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
    return new_object(name, bm)


def select_only(ob) -> None:
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob


def join(name: str, objects) -> bpy.types.Object:
    objects = [o for o in objects if o is not None]
    select_only(objects[0])
    for o in objects:
        o.select_set(True)
    bpy.ops.object.join()
    objects[0].name = name
    return objects[0]


# ------------------------------------------------------------------------------------------------ modifiers
def bevel(ob, width: float, segments: int = 2, angle_deg: float = 30.0):
    m = ob.modifiers.new("bevel", "BEVEL")
    m.width, m.segments, m.limit_method, m.angle_limit = width, segments, "ANGLE", math.radians(angle_deg)
    return m


def subsurf(ob, levels: int = 2):
    m = ob.modifiers.new("subsurf", "SUBSURF")
    m.levels = m.render_levels = levels
    return m


def solidify(ob, thickness: float):
    m = ob.modifiers.new("solidify", "SOLIDIFY")
    m.thickness = thickness
    return m


def array(ob, count: int, offset):
    m = ob.modifiers.new("array", "ARRAY")
    m.count, m.use_relative_offset, m.use_constant_offset = count, False, True
    m.constant_offset_displace = offset
    return m


def boolean_cut(ob, cutter):
    """Cut `cutter` out of `ob` (doors, windows, sockets); the cutter is hidden afterwards."""
    m = ob.modifiers.new("cut", "BOOLEAN")
    m.operation, m.object, m.solver = "DIFFERENCE", cutter, "EXACT"
    cutter.hide_render = True
    cutter.display_type = "WIRE"
    return m


def weather(ob, strength: float, scale: float, seed: int = 0):
    """Break up perfect surfaces: a noise displacement along the normals (erosion, hand-made unevenness)."""
    tex = bpy.data.textures.new(f"weather{seed}", "CLOUDS")
    tex.noise_scale = scale
    m = ob.modifiers.new("weather", "DISPLACE")
    m.texture, m.strength, m.texture_coords = tex, strength, "GLOBAL"
    return m


def smooth(ob, angle_deg: float = 35.0) -> None:
    """Smooth shading that keeps real edges sharp."""
    for p in ob.data.polygons:
        p.use_smooth = True
    try:
        ob.data.use_auto_smooth = True                       # Blender 4.0
        ob.data.auto_smooth_angle = math.radians(angle_deg)
    except AttributeError:                                    # 4.1+: smoothing by angle is a modifier
        try:
            select_only(ob)
            bpy.ops.object.shade_smooth_by_angle(angle=math.radians(angle_deg))
        except Exception:  # noqa: BLE001
            pass


# ------------------------------------------------------------------------------------------------ materials
def material(name: str, colour, roughness: float = 0.6, metallic: float = 0.0, colour2=None, variation_scale: float = 4.0,
             bump: float = 0.0, bump_scale: float = 40.0, blocks=None, emission=None):
    """A procedural PBR material.
      colour / colour2   base colour and a second colour it drifts toward (patchy stone, tarnish, dirt)
      bump               strength of a fine noise bump (grain, pitting); bump_scale = how fine
      blocks             {"size": (length, height), "mortar": width, "depth": 0-1, "wrap": bool} cuts block/brick
                         joints into the surface (masonry, tiles, panels), mapped in object space; wrap = joints
                         run around the four walls of a building instead of across its plan
      emission           (colour, strength) for lights and glowing parts"""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Metallic"].default_value = metallic
    rgba = lambda c: (c[0], c[1], c[2], 1.0)   # noqa: E731
    coord = nt.nodes.new("ShaderNodeTexCoord")
    if colour2 is not None:
        noise = nt.nodes.new("ShaderNodeTexNoise")
        noise.inputs["Scale"].default_value = variation_scale
        noise.inputs["Detail"].default_value = 6.0
        nt.links.new(coord.outputs["Object"], noise.inputs["Vector"])
        ramp = nt.nodes.new("ShaderNodeValToRGB")
        ramp.color_ramp.elements[0].position, ramp.color_ramp.elements[1].position = 0.35, 0.7
        ramp.color_ramp.elements[0].color, ramp.color_ramp.elements[1].color = rgba(colour), rgba(colour2)
        nt.links.new(noise.outputs["Fac"], ramp.inputs["Fac"])
        nt.links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    else:
        bsdf.inputs["Base Color"].default_value = rgba(colour)
    height = None
    if bump:
        fine = nt.nodes.new("ShaderNodeTexNoise")
        fine.inputs["Scale"].default_value = bump_scale
        fine.inputs["Detail"].default_value = 8.0
        nt.links.new(coord.outputs["Object"], fine.inputs["Vector"])
        height = fine.outputs["Fac"]
    if blocks:
        brick = nt.nodes.new("ShaderNodeTexBrick")
        brick.offset = 0.5
        brick.inputs["Scale"].default_value = 1.0
        brick.inputs["Mortar Size"].default_value = blocks.get("mortar", 0.02)
        brick.inputs["Mortar Smooth"].default_value = 0.4
        brick.inputs["Brick Width"].default_value = blocks["size"][0]
        brick.inputs["Row Height"].default_value = blocks["size"][1]
        brick.inputs["Color1"].default_value = (1, 1, 1, 1)
        brick.inputs["Color2"].default_value = (0.86, 0.86, 0.86, 1)
        brick.inputs["Mortar"].default_value = (0, 0, 0, 1)
        if blocks.get("wrap"):
            # joints that run around a four-sided building: along each wall horizontally (x + y), up the wall (z)
            sep = nt.nodes.new("ShaderNodeSeparateXYZ")
            add = nt.nodes.new("ShaderNodeMath")
            add.operation = "ADD"
            comb = nt.nodes.new("ShaderNodeCombineXYZ")
            nt.links.new(coord.outputs["Object"], sep.inputs[0])
            nt.links.new(sep.outputs["X"], add.inputs[0])
            nt.links.new(sep.outputs["Y"], add.inputs[1])
            nt.links.new(add.outputs[0], comb.inputs["X"])
            nt.links.new(sep.outputs["Z"], comb.inputs["Y"])
            nt.links.new(comb.outputs[0], brick.inputs["Vector"])
        else:
            nt.links.new(coord.outputs["Object"], brick.inputs["Vector"])
        if height is not None:
            mix = nt.nodes.new("ShaderNodeMath")
            mix.operation = "MULTIPLY"
            lift = nt.nodes.new("ShaderNodeMath")
            lift.operation = "ADD"
            scale = nt.nodes.new("ShaderNodeMath")
            scale.operation = "MULTIPLY"
            scale.inputs[1].default_value = 0.35
            nt.links.new(height, scale.inputs[0])
            nt.links.new(brick.outputs["Color"], lift.inputs[0])
            nt.links.new(scale.outputs[0], lift.inputs[1])
            height = lift.outputs[0]
        else:
            height = brick.outputs["Color"]
    if height is not None:
        b = nt.nodes.new("ShaderNodeBump")
        b.inputs["Strength"].default_value = max(bump, blocks.get("depth", 0.6) if blocks else 0.0)
        b.inputs["Distance"].default_value = 0.05
        nt.links.new(height, b.inputs["Height"])
        nt.links.new(b.outputs["Normal"], bsdf.inputs["Normal"])
    if emission:
        try:
            bsdf.inputs["Emission Color"].default_value = rgba(emission[0])     # 4.0+
        except KeyError:
            bsdf.inputs["Emission"].default_value = rgba(emission[0])
        bsdf.inputs["Emission Strength"].default_value = emission[1]
    return m


def assign(ob, mat) -> None:
    ob.data.materials.clear()
    ob.data.materials.append(mat)

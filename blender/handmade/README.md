# Hand-built 3D models

A model lives here only when **no free-licence model of the subject exists** (the toolkit looks in the free
libraries first: `python -m ytauto broll <project>` shows what it found). Each file is one subject, built in
Blender from code with the kit in `blender/kit3d.py`, so it renders the same everywhere and can be corrected.

## The standard every model must meet

1. **True to the real thing.** Before modelling, collect the real facts: dimensions, proportions, the parts and
   where each one sits, which way the subject faces, its materials and colours. Write them at the top of the file
   with the sources they came from. Never guess a shape, a number or a position; if a fact can't be found, leave
   the part out and say so.
2. **Real units and directions.** Work in metres. Z is up, +Y is north (or the subject's back), +X is east.
   A part that is on the north face in reality is on +Y in the model. `FRONT` turns the side viewers should see
   toward the camera.
3. **Built with Blender's proper tools**, not rough shapes: lathe for anything turned, bevels on every hard edge,
   subdivision surfaces for organic forms, boolean cuts for openings, arrays for repeated parts, displacement for
   weathering, procedural PBR materials (colour variation, roughness, bump, block joints).
4. **Checked from every side.** `python -m ytauto model "<name>"` renders the front, both sides, the back and the
   top into one sheet. Compare it with reference photos part by part and fix what differs before the model is
   used. Send the sheet to the creator with the list of facts, so they can confirm it.
5. **Named.** `NAMES` lists what a script may call it; `model: "<any of those names>"` (or a video about it) then
   uses this model before any library.

## A model file

```python
"""<Subject>. Facts the model is built from (metres): … Sources: …"""
import kit3d as k

NAMES = ["great pyramid of giza", "great pyramid", "pyramid of khufu"]
TITLE = "Great Pyramid of Giza"
FRONT = 180          # degrees: turn this side to the camera
ELEVATION = 12       # camera height angle

def build():
    ...              # make the objects, give them materials, return them
```

`great_pyramid.py` is the reference example.

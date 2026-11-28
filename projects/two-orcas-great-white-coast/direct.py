"""Director's notes for "The Two Orcas That Emptied a Great White Shark Coast" → script.yaml.

Every picture in this video is a live 3D shot built for the sentence it sits under (the `Shot3D` template): a real
place (a beach, the open sea, a kelp reef, the sea from the air, a dark studio for looking inside an animal), animals
that swim through it, a camera that moves, and graphics pinned to the picture that arrive on the narrator's words.
Only the animals of this story are in it: great whites, the two orcas, sevengill and bronze whaler sharks.

The narration is taken from script.txt word for word. P(n, shots) gives the next n sentences, read as one passage,
their shots; a later shot in the list starts on its `cut` word.

    python projects/two-orcas-great-white-coast/direct.py        # rewrites script.yaml beside it
"""
import os
import re
import sys
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
from ytauto.scriptfmt import parse_script  # noqa: E402

script = parse_script((HERE / "script.txt").read_text(encoding="utf-8"))
SENT = [s for p in script.paras for s in re.split(r'(?<=[.!?])\s+(?=[A-Z"])', p.text)]
scenes: list[dict] = []
_pos = 0


def P(n: int, shots, chapter: str | None = None, mood: str | None = None, **extra) -> None:
    """The next n sentences of the script, read as one passage, with their shots."""
    global _pos
    text = " ".join(SENT[_pos:_pos + n])
    _pos += n
    sc: dict = {}
    if chapter:
        sc["chapter"] = chapter
    if mood:
        sc["mood"] = mood
    sc["text"] = text
    shots = shots if isinstance(shots, list) else [shots]
    sc["visuals" if len(shots) > 1 else "visual"] = shots if len(shots) > 1 else shots[0]
    sc.update(extra)
    scenes.append(sc)


# ------------------------------------------------------------------------------------------ shot helpers
def shot(env, cast, camera, gfx=None, cut=None, props=None, **kw):
    v = {"remotion": "Shot3D", "props": {"env": env, "cast": cast, "camera": camera, "gfx": gfx or [], **({"props": props} if props else {}), **kw}}
    if cut is not None:
        v["cut"] = cut
    return v


def animal(model, ident, length, path=None, **kw):
    a = {"id": ident, "model": model, "length": length, **kw}
    if path:
        a["path"] = [{"u": u, "p": p} for u, p in path]
    return a


def gw(ident, length=4.4, path=None, lo=False, **kw):
    return animal("greatWhiteLo" if lo else "greatWhite", ident, length, path, **kw)


def sg(ident, length=2.3, path=None, lo=False, **kw):
    return animal("sevengillLo" if lo else "sevengill", ident, length, path, **kw)


def bw(ident, length=2.7, path=None, lo=False, **kw):
    return animal("bronzeWhalerLo" if lo else "bronzeWhaler", ident, length, path, **kw)


def port(path=None, **kw):
    return animal("orcaPort", "port", 8.4, path, **kw)


def star(path=None, **kw):
    return animal("orcaStarboard", "star", 8.1, path, **kw)


def orca(ident, path=None, length=6.6, male=False, **kw):
    return animal("orcaMale" if male else "orca", ident, length, path, **kw)


def carcass(ident, x, z, length, heading, side=1, kind=gw, **kw):
    """A shark washed ashore, lying on its belly and leaning a little to one side (the sea is toward -z)."""
    return kind(ident, length, pos=[x, (0.083 if kind is gw else 0.06) * length, z], heading=heading, roll=-17 * side, pose="limp", **{"wound": "chest", **kw})


def cam(*keys):
    """Camera keys: (u, position, look-at[, extra])."""
    out = []
    for k in keys:
        d = {"u": k[0], "pos": k[1], "look": k[2]}
        if len(k) > 3:
            d.update(k[3])
        out.append(d)
    return out


def follow(actor, a, b, fov=38, point=None, mid=None):
    """A camera that travels with an animal: where it sits beside it at the start and at the end."""
    keys = [{"u": 0, "pos": a, "rel": actor, "look": actor, "fov": fov}]
    if mid:
        keys.append({"u": 0.5, "pos": mid, "rel": actor, "look": actor, "fov": fov})
    keys.append({"u": 1, "pos": b, "rel": actor, "look": actor, "fov": fov})
    if point:
        for k in keys:
            k["point"] = point
    return keys


def mcam(*keys):
    """Map and globe camera keys: (u, [lon, lat], distance, tilt, bearing[, extra])."""
    out = []
    for k in keys:
        d = {"u": k[0], "over": list(k[1]), "dist": k[2], "tilt": k[3], "bearing": k[4], "fov": 34}
        if len(k) > 5:
            d.update(k[5])
        out.append(d)
    return out


def MAP(bbox, **kw):
    return {"kind": "map", "map": {"bbox": bbox, **kw}}


def GLOBE(**kw):
    return {"kind": "globe", "map": kw}


def pin(place, when=None, **kw):
    return {"lon": place[0], "lat": place[1], **({"at": when} if when is not None else {}), **kw}


def geo(place, h=7):
    return {"geo": list(place), "h": h}


def at(actor, point=None):
    return {"actor": actor, **({"point": point} if point else {})}


def tag(when, anchor, text, sub=None, dir="ne", **kw):
    return {"type": "tag", "at": when, "anchor": anchor, "text": text, **({"sub": sub} if sub else {}), "dir": dir, **kw}


def line(when, text, hi=None, **kw):
    return {"type": "line", "at": when, "text": text, **({"hi": hi} if hi else {}), **kw}


def stamp(when, text, sub=None, **kw):
    return {"type": "stamp", "at": when, "text": text, **({"sub": sub} if sub else {}), **kw}


def chapter(n, text):
    return {"type": "chapter", "at": 0.25, "n": f"{n:02d}", "text": text}


def note(when, anchor, text, **kw):
    return {"type": "note", "at": when, "anchor": anchor, "text": text, **kw}


def across(y, z0=0.0, z1=0.0, x0=-14.0, x1=12.0, rise=0.5, bow=1.5):
    """A swim past the camera from left to right (or right to left with x0 > x1), in a gentle curve."""
    return [(0, [x0, y, z0]), (0.5, [(x0 + x1) / 2, y + rise / 2, (z0 + z1) / 2 + bow]), (1, [x1, y + rise, z1])]


def tape(when, x, z, length, heading, label=None, off=0.75, **kw):
    """A measuring line on the sand along a carcass at (x, z), on the camera's side of it (the camera stands at +z)."""
    import math
    c, sn = math.cos(math.radians(heading)), math.sin(math.radians(heading))
    a = [round(x - length / 2 * c, 2), 0.03, round(z + length / 2 * sn + off, 2)]
    b = [round(x + length / 2 * c, 2), 0.03, round(z - length / 2 * sn + off, 2)]
    if a[0] > b[0]:
        a, b = b, a
    return {"type": "measure", "at": when, "from": {"world": a}, "to": {"world": b}, "value": length, "unit": " m", "off": 0,
            **({"label": label} if label else {}), **kw}


def milling(make, n, y, x_span=22.0, z_near=6.0, z_far=-9.0, travel=9.0, length=2.2, prefix="s"):
    """n animals cruising slowly to and fro through the picture, spread through its depth."""
    out = []
    for i in range(n):
        d = 1 if i % 2 else -1
        x0 = -x_span / 2 + x_span * ((i * 0.37) % 1.0)
        z = z_near + (z_far - z_near) * ((i * 0.61 + 0.2) % 1.0)
        yy = y + 0.9 * ((i * 0.43) % 1.0)
        out.append(make(f"{prefix}{i}", round(length * (0.88 + 0.24 * ((i * 0.29) % 1.0)), 2),
                        [(0, [round(x0 - d * travel / 2, 2), round(yy, 2), round(z, 2)]), (0.5, [round(x0, 2), round(yy + 0.15, 2), round(z + 0.8 * d, 2)]),
                         (1, [round(x0 + d * travel / 2, 2), round(yy, 2), round(z + 0.3, 2)])], lo=True))
    return out


SEA = {"kind": "sea", "depth": 0.3}
DEEP = {"kind": "sea", "depth": 0.6}
COAST = {"kind": "sea", "depth": 0.25, "water": "teal", "floor": 14}
REEF = {"kind": "sea", "depth": 0.3, "water": "green", "floor": 11, "kelp": True}
STUDIO = {"kind": "studio"}
AIR = {"kind": "aerial", "water": "teal", "floor": 17}
DAWN = {"kind": "beach", "sky": "dawn", "sun": [-0.55, 0.42, 0.72]}
GREY = {"kind": "beach", "sky": "overcast", "sun": [0.4, 0.7, 0.6]}
DUSK = {"kind": "beach", "sky": "dusk", "sun": [-0.78, 0.24, 0.3]}       # low sun from the side: warm light, long shadows

# places [longitude, latitude]
CAPE_TOWN, GANSBAAI, DYER = (18.42, -33.92), (19.35, -34.58), (19.42, -34.68)
FALSE_BAY, SEAL_ISLAND, REEF_SITE = (18.65, -34.22), (18.58, -34.14), (18.47, -34.24)
MOSSEL, ALGOA, LUDERITZ, DURBAN = (22.13, -34.18), (25.70, -33.85), (15.16, -26.65), (31.03, -29.86)
FARALLON, SAN_FRANCISCO, GULF_CAL, PORTLAND = (-123.0, 37.70), (-122.42, 37.77), (-110.6, 26.2), (141.6, -38.35)
CAPE = [[17.2, -35.7], [23.4, -33.0]]
SOUTH_AFRICA = [[13.5, -37.5], [34.0, -25.5]]

# ====================================================================================== 1. HOOK
P(4, [
    # the big female on the sand: the camera comes in low over the wet beach and rises to take her in
    shot({"kind": "beach", "sky": "dawn", "sun": [-0.55, 0.42, 0.72]},
         [carcass("her", 0, 2.6, 4.9, 8)],
         # along the body from the tail, close to the sand, then back and up to take all of her in
         cam((0, [-5.6, 0.45, 4.6], [-1.6, 0.42, 2.6], {"fov": 34}), (0.42, [0.9, 0.62, 5.7], [1.0, 0.4, 2.6], {"fov": 34}),
             (1, [-0.8, 2.0, 10.6], [0.1, 0.25, 2.6], {"fov": 34})),
         [stamp("May", "May 2017", "Franskraal beach · South Africa"),
          tape("almost", 0, 2.6, 4.9, 8, "nose to tail")]),
    # alive: nothing in the sea troubles an animal this size
    shot(SEA, [gw("shark", 4.9, [(0, [-13, -5.2, -6]), (0.5, [-1.5, -4.7, 1.2]), (1, [10, -4.2, -2.5])])],
         cam((0, [3.5, -5.2, 12.5], "shark"), (1, [-1.5, -4.3, 8.2], "shark")),
         [line("enemies", "Almost no enemies in the sea", "no enemies")], cut="A shark that"),
    # the wound, then the inside: the liver is there, and then it is not
    shot(STUDIO,
         [gw("her", 4.9, pos=[0, 0, 0], heading=25, roll=-38, pitch=4, spin=-4, pose="swim", amp=0.45, wound="chest",
             xray={"at": "chest+0.1", "d": 0.5}, parts={"liver": {"at": "chest+0.1", "out": "gone"}})],
         cam((0, [1.7, -1.7, 7.8], [0.3, -0.2, 0], {"fov": 36}), (1, [0.4, -1.2, 5.3], [0.4, -0.2, 0], {"fov": 36})),
         [tag("tear", at("her", "chest"), "One clean tear", "across her chest", "sw", out="chest+0.1"),
          tag("gone", at("her", "liver"), "The liver", "missing", "ne", len=230)], cut="Yet"),
    # three more along the same shore
    shot({"kind": "beach", "sky": "dusk", "sun": [0.62, 0.2, -0.76]},
         [carcass("b", -9, 2.3, 3.7, 165, -1), carcass("c", 4.5, 1.9, 4.2, 14), carcass("d", 19, 2.8, 3.4, 196, -1)],
         cam((0, [-17, 1.1, 8.5], [-9, 0.4, 2.3], {"fov": 36}), (1, [-11, 6.0, 16], [5, 0.2, 2.2], {"fov": 36})),
         [{"type": "note", "at": "three", "anchor": at("b", "back"), "text": "4 May", "dy": -90},
          {"type": "note", "at": "three+0.35", "anchor": at("c", "back"), "text": "Late May", "dy": -80},
          {"type": "note", "at": "three+0.7", "anchor": at("d", "back"), "text": "June", "dy": -70},
          line("same", "Three more · the same wound", "same wound")], cut="weeks"),
], chapter="Intro", mood="mystery")

P(3, [
    # out of the gloom: two orcas, each with a folded fin
    shot(DEEP,
         [port([(0, [-20, -9, -17]), (0.55, [-3, -8, -3.5]), (1, [15, -7.4, 6])], shadow={"from": 1, "to": 0, "u": 0.1, "d": 2.2}),
          star([(0, [-24, -11.2, -11]), (0.55, [-6.5, -10.6, 2]), (1, [11, -10, 11.5])], shadow={"from": 1, "to": 0, "u": 0.16, "d": 2.2})],
         cam((0, [4, -9.6, 14], [-6, -9, -2], {"fov": 40}), (1, [7.5, -9, 17.5], [2, -8.8, 3], {"fov": 40})),
         [tag("name-0.5", at("port", "dorsal"), "Port", "fin folded to his left", "nw"),
          tag("name", at("star", "dorsal"), "Starboard", "fin folded to his right", "se")]),
    # the bay from the air: the sharks are there, the orcas arrive, the sharks are gone
    shot({"kind": "aerial", "water": "teal", "floor": 17},
         [port([(0, [-40, -3, 5]), (0.4, [-13, -3, 2]), (1, [14, -3, -2])]),
          star([(0, [-44, -3.6, -4]), (0.4, [-17, -3.6, -5]), (1, [9, -3.6, -8])]),
          gw("g1", 4.6, [(0, [5, -3.6, 6]), (0.28, [0, -3.6, 2]), (0.46, [5, -3.6, -2]), (1, [46, -3.6, 20])]),
          gw("g2", 4.2, [(0, [12, -4.2, -6]), (0.28, [7, -4.2, -9]), (0.46, [12, -4.2, -12]), (1, [48, -4.2, -30])]),
          gw("g3", 4.9, [(0, [-5, -4, -9]), (0.28, [0, -4, -6]), (0.44, [6, -4, -8]), (1, [44, -4, -6])]),
          gw("g4", 3.8, [(0, [-9, -4.6, 9]), (0.3, [-4, -4.6, 11]), (0.46, [2, -4.6, 14]), (1, [34, -4.6, 36])]),
          gw("g5", 4.4, [(0, [16, -3.8, 3]), (0.28, [13, -3.8, 7]), (0.46, [18, -3.8, 10]), (1, [50, -3.8, 24])]),
          gw("g6", 4.0, [(0, [2, -5, -15]), (0.28, [7, -5, -17]), (0.46, [13, -5, -19]), (1, [40, -5, -38])]),
          gw("g7", 4.3, [(0, [-12, -4.4, -2]), (0.28, [-8, -4.4, 2]), (0.42, [-3, -4.4, 5]), (1, [38, -4.4, 8])])],
         cam((0, [2, 36, 0.5], [2, 0, 0], {"fov": 40}), (1, [6, 31, 0.5], [6, 0, 0], {"fov": 40})),
         [stamp("bay", "Gansbaai", "“The great white shark capital of the world”", size=70)], cut="Over"),
    # the title, with the two of them passing overhead
    shot(SEA,
         [port([(0, [-22, -3.4, -9]), (1, [20, -2.8, -1])]), star([(0, [-27, -4.6, -3]), (1, [15, -4.2, 4])])],
         cam((0, [0, -9.5, 13], [-4, -3.5, -3], {"fov": 42}), (1, [2, -9, 12], [6, -3.2, 0], {"fov": 42})),
         [{"type": "dim", "at": "did-0.3", "to": 0.34},
          {"type": "title", "at": "did-0.2", "kicker": "Beast Atlas", "size": 128,
           "lines": ["The two orcas", "that emptied a", {"text": "great white shark coast", "accent": True}]}], cut="This is"),
], mood="tension")

# ====================================================================================== 2. THE SHARK CAPITAL
P(3, [
    # the coast from the air: the fishing town, then the city it lies southeast of
    shot(MAP(CAPE, pins=[pin(GANSBAAI, "town"), pin(CAPE_TOWN, "southeast")]), [],
         mcam((0, (19.0, -34.3), 150, 64, -6), (1, (19.3, -34.55), 78, 46, 10)),
         [chapter(1, "The shark capital"),
          tag("town+0.2", geo(GANSBAAI), "Gansbaai", "fishing town", "se"),
          tag("southeast+0.3", geo(CAPE_TOWN), "Cape Town", None, "nw")]),
    # out to the island, low over the swell
    shot({"kind": "surface", "sky": "day", "swell": 0.35}, [],
         cam((0, [0, 2.2, 150], [0, 3, 0], {"fov": 30}), (1, [18, 3.4, 96], [0, 3, 0], {"fov": 30})),
         [tag("offshore", {"prop": "isle", "point": "top"}, "Dyer Island", "a few kilometres offshore", "ne", len=150),
          line("colony", "A large colony of Cape fur seals", "seals")],
         props=[{"kind": "island", "id": "isle", "pos": [0, 0, 0], "radius": 70, "height": 5, "stretch": 2.4}], cut="A few"),
    # and under the water around it
    shot(COAST,
         [gw("a", 4.6, across(-5.5, -4, 1, -16, 12)), gw("b", 3.9, across(-8, 6, 2, 15, -13, 0.3, -2)), gw("c", 4.2, across(-3.6, -14, -8, -22, 8, 0.2))],
         follow("a", [5, 0.3, 11], [-2.5, 0.9, 7.5]),
         [line("follow-0.4", "Where there are seals, great whites follow", "great whites")], cut="Where"),
])

P(4, [
    # the cage in the water and a shark coming to look
    shot({"kind": "sea", "depth": 0.2, "water": "teal"},
         [gw("g", 4.5, [(0, [-15, -2.8, 9]), (0.55, [-1.5, -1.9, 5.6]), (1, [11, -2.4, 8.5])]),
          gw("h", 3.8, across(-6.5, 13, 9, 14, -12, 0.4, 2))],
         cam((0, [5.5, -4.4, 13.5], [-1.3, -0.9, 2.6], {"fov": 40}), (1, [2.6, -3.5, 10.5], [-1.3, -0.9, 2.6], {"fov": 40})),
         [line("every", "Here on almost every day of the year", "every day")],
         props=[{"kind": "boat", "id": "boat", "pos": [0, 0, 0], "cage": True}]),
    # the law
    shot(MAP(SOUTH_AFRICA), [],
         mcam((0, (24.0, -31.5), 175, 70, 0), (1, (23.0, -32.5), 140, 58, 6)),
         [{"type": "count", "at": "1991-0.2", "from": 1960, "to": 1991, "d": 0.9, "plain": True, "x": 0.28, "y": 0.4, "size": 210, "kicker": "South Africa", "label": "Great whites protected by law"},
          line("first", "The first country to do so", "first")], cut="South Africa"),
    # the boats
    shot({"kind": "surface", "sky": "day", "swell": 0.3},
         [gw("fin", 4.4, [(0, [-22, -0.72, 14]), (1, [16, -0.72, 9])])],
         cam((0, [-20, 2.4, 24], [0, 1, 0], {"fov": 34}), (1, [-11, 2.0, 19], [3, 1, 0], {"fov": 34})),
         [{"type": "count", "at": "80,000-0.3", "to": 80000, "d": 1.5, "x": 0.7, "y": 0.32, "size": 190, "kicker": "Shark tourism", "label": "visitors a year", "prefix": "", "suffix": "+"}],
         props=[{"kind": "boat", "id": "b1", "pos": [0, 0, 0], "heading": 18, "cage": True},
                {"kind": "boat", "id": "b2", "pos": [26, 0, -34], "heading": -30, "cage": True, "length": 12},
                {"kind": "boat", "id": "b3", "pos": [-34, 0, -58], "heading": 60, "length": 10},
                {"kind": "island", "id": "isle", "pos": [10, 0, -240], "radius": 80, "height": 5, "stretch": 2.4}], cut="After that"),
])

P(5, [
    # every trip is written down
    shot({"kind": "surface", "sky": "overcast", "swell": 0.3},
         [gw("fin", 4.6, [(0, [-14, -0.7, 9]), (0.5, [0, -0.7, 6.5]), (1, [13, -0.74, 10])])],
         cam((0, [-9, 1.7, 15], [0, 0.9, 1], {"fov": 36}), (1, [-5, 1.5, 12.5], [1, 0.9, 1], {"fov": 36})),
         [{"type": "rows", "at": "log", "title": "Boat log", "side": "right", "y": 0.2, "w": 560,
           "rows": [{"k": "Trip 1", "v": "3 sharks"}, {"k": "Trip 2", "v": "5 sharks"}, {"k": "Trip 3", "v": "2 sharks"}, {"k": "Trip 4", "v": "4 sharks"}]},
          line("record", "Years of notes became a scientific record", "scientific record")],
         props=[{"kind": "boat", "id": "boat", "pos": [1, 0, 1], "heading": 12, "cage": True}]),
    # the record, with its two short gaps
    shot(COAST, [gw("a", 4.4, across(-6, -10, -6, -20, 14, 0.4), lo=True), gw("b", 4.0, across(-8, -18, -12, 18, -14, 0.3, -2), lo=True)],
         cam((0, [0, -6, 14], [0, -6.4, 0], {"fov": 40}), (1, [3, -5.6, 12], [0, -6.4, 0], {"fov": 40})),
         [{"type": "dim", "at": 0.0, "to": 0.3},
          {"type": "timeline", "at": 0.2, "from": 2005, "to": 2017, "title": "The logbook record", "sub": "gaps of a week or more without a great white",
           "spans": [{"from": 2007.3, "to": 2007.5, "label": "1 week", "at": "One gap"}, {"from": 2016.3, "to": 2016.75, "label": "3 weeks", "at": "three"}],
           "marks": []},
          {"type": "count", "at": "only", "to": 2, "d": 0.5, "x": 0.82, "y": 0.3, "size": 200, "kicker": "before 2017", "label": "gaps in the record"}], cut="Before"),
])

P(1, shot(SEA, [],
          cam((0, [0, -6, 12], [3, -6.4, 0], {"fov": 42}), (1, [6, -5.4, 9], [12, -6, -4], {"fov": 42})),
          [{"type": "dots", "at": 0.15, "n": 90, "cols": 30, "size": 22, "gap": 12, "x": 0.5, "y": 0.34, "title": "Early 2017", "sub": "days with a great white", "from": 90,
            "lit": [{"at": "began", "to": 22, "d": 2.2}]},
           line("empty", "The logbooks began to fill with empty days", "empty days")]))

# ====================================================================================== 3. BODIES ON THE BEACH
P(3, shot(GREY, [carcass("f", 0, 2.4, 2.6, -12, wound=None)],
          cam((0, [5.5, 0.5, 6.2], [0.2, 0.3, 2.4], {"fov": 34}), (0.5, [0.5, 0.9, 6.6], [0, 0.25, 2.4], {"fov": 34}), (1, [-3.6, 1.6, 7.4], [0, 0.2, 2.4], {"fov": 34})),
          [chapter(2, "Bodies on the beach"),
           stamp("February", "February 2017", "A beach near Gansbaai"),
           tape("2.6", 0, 2.4, 2.6, -12, "young female", size=70),
           tag("whole", at("f", "back"), "Body whole", "cause unknown", "ne")], mood="mystery"))

P(6, [
    # from high above the tide line
    shot(DAWN, [carcass("her", 0, 2.6, 4.9, 8)],
         cam((0, [-6, 9.5, 12], [0, 0.3, 2.6], {"fov": 30}), (1, [3, 5.2, 11], [0.2, 0.3, 2.6], {"fov": 30})),
         [stamp("third", "3 May 2017", "Franskraal beach")]),
    # the tape along her side
    shot(DAWN, [carcass("her", 0, 2.6, 4.9, 8)],
         cam((0, [-4.2, 0.8, 7.4], [-0.6, 0.45, 2.6], {"fov": 36}), (1, [2.8, 1.1, 8.2], [0.4, 0.4, 2.6], {"fov": 36})),
         [tape("measured", 0, 2.6, 4.9, 8, "about 16 feet"),
          {"type": "count", "at": "weight", "to": 1110, "d": 1.2, "x": 0.8, "y": 0.26, "size": 150, "kicker": "weight", "label": "kilograms"},
          line("larger", "The largest great white ever dissected in South Africa", "largest")], cut="Biologist"),
    # a year earlier, alive
    shot(COAST, [gw("her", 4.9, across(-5, -2, 2, -15, 11))],
         follow("her", [-4, 0.4, 10], [3.5, 0.8, 7]),
         [stamp("alive", "A year earlier", "Dyer Island · last logged alive")], cut="Boat crews"),
])

P(2, shot(STUDIO,
          [gw("her", 4.9, pos=[0, 0, 0], heading=18, roll=-64, pitch=5, spin=-3, pose="still", wound="chest",
              xray={"at": "Inside-0.2", "d": 0.7}, parts={"liver": {"at": "Inside-0.2", "out": "missing-0.2"}})],
          cam((0, [1.6, -1.5, 5.0], [0.55, -0.3, 0], {"fov": 34}), (1, [1.0, -1.0, 3.4], [0.6, -0.3, 0], {"fov": 34})),
          [tag("tear", at("her", "chest"), "The tear", "between her front fins", "sw", out="Inside-0.2"),
           tag("missing-0.1", at("her", "liver"), "Only the liver", "missing", "ne", len=210)]))

P(5, [
    shot(DUSK, [carcass("m", 0, 2.4, 4.0, 172, -1)],
         cam((0, [-5, 0.6, 6.4], [0, 0.35, 2.4], {"fov": 34}), (1, [-1.2, 1.3, 7.6], [0.3, 0.3, 2.4], {"fov": 34})),
         [stamp("next", "4 May 2017", "A male · the next day"),
          tag("gone", at("m", "liver"), "Liver", "gone", "nw"),
          tag("heart", at("m", "gills"), "Heart", "gone", "ne")]),
    # all four along one stretch of coast
    shot(GREY, [carcass("a", -10, 2.2, 4.9, 8, lo=True), carcass("b", -3, 3.0, 4.0, 172, -1, lo=True), carcass("c", 4, 2.1, 3.6, 20, lo=True), carcass("d", 10.5, 2.8, 3.3, 190, -1, lo=True)],
         cam((0, [-15, 2.6, 11], [-7, 0.3, 2.4], {"fov": 38}), (1, [0, 8.5, 19], [0.5, 0.2, 2.4], {"fov": 38})),
         [note("Two", at("a", "back"), "3 May", dy=-80), note("Two+0.25", at("b", "back"), "4 May", dy=-80),
          note("later", at("c", "back"), "Late May", dy=-80), note("June", at("d", "back"), "June", dy=-80),
          line("four", "All four · the same torn chest", "same torn chest")], cut="Two more"),
    # what was left on the skin
    shot(STUDIO, [gw("s", 4.4, pos=[0, 0, 0], heading=18, roll=-10, spin=-3, pose="swim", amp=0.4)],
         cam((0, [1.2, 0.3, 4.6], [0.6, 0.05, 0], {"fov": 34}), (1, [0.2, 0.2, 3.5], [0.5, 0.05, 0], {"fov": 34})),
         [{"type": "ring", "at": "scratches-0.4", "anchor": at("s", "flank"), "r": 120},
          tag("scratches", at("s", "flank"), "Tooth scratches", "left by orcas", "ne", len=200)], cut="On two"),
])

P(2, [
    shot({"kind": "sea", "depth": 0.75},
         [port(across(-9, -9, -3, -24, 16, 0.5), shadow=0.93), star(across(-11.5, -4, 3, -29, 11, 0.5), shadow=0.93)],
         cam((0, [3, -10.5, 15], [-6, -10, -3], {"fov": 40}), (1, [6, -10, 17], [3, -10, 0], {"fov": 40})),
         [line("idea", "She had a good idea who had done it", "who")]),
    shot(STUDIO, [sg("s", 2.4, pos=[0, 0, 0], heading=22, roll=-30, spin=-5, pose="swim", amp=0.5, wound=None)],
         cam((0, [0.9, -0.5, 3.9], [0.15, -0.05, 0], {"fov": 34}), (1, [0.2, -0.35, 2.9], [0.2, -0.05, 0], {"fov": 34})),
         [tag("different", at("s", "gills"), "Broadnose sevengill shark", "a different kind of shark", "ne", len=170)], cut="She had"),
], mood="tension")

# ====================================================================================== 4. TWO BENT FINS
P(4, [
    shot(MAP([[17.6, -34.9], [19.6, -33.6]], pins=[pin(REEF_SITE, "reef"), pin(CAPE_TOWN, "beside")],
             zones=[{"lon": FALSE_BAY[0], "lat": FALSE_BAY[1], "km": 20, "at": "False"}]), [],
         mcam((0, (18.7, -34.1), 120, 66, 0), (1, (18.5, -34.22), 62, 44, -12)),
         [chapter(3, "Two bent fins"),
          stamp("Two", "2015", "False Bay · beside Cape Town"),
          tag("reef+0.2", geo(REEF_SITE, 5), "The divers' reef", None, "sw")]),
    # the reef on a good day
    shot(REEF,
         milling(sg, 13, -9.9, 24, 5, -10, 8, 2.2),
         cam((0, [-3, -9.2, 11], [0, -9.2, 0], {"fov": 44}), (1, [2.5, -8.8, 8.5], [0, -9.1, -1], {"fov": 44})),
         [{"type": "count", "at": "count", "to": 70, "d": 1.4, "x": 0.8, "y": 0.28, "size": 200, "kicker": "on a good dive", "label": "sevengill sharks"}], cut="On a good"),
    shot(REEF, [sg("s", 2.4, across(-10.0, -1, 1, -9, 8, 0.15, 0.8))],
         follow("s", [1.5, 0.4, 4.6], [-1.2, 0.5, 3.6], fov=36),
         [tag("smaller", at("s", "gills"), "Seven gill slits", "most sharks have five", "ne"),
          line("seabed", "Hunts close to the seabed", "seabed")], cut="Sevengills are"),
    # the same reef, empty
    shot(REEF, [],
         cam((0, [-4, -9.4, 11], [0, -9.2, 0], {"fov": 44}), (1, [3, -8.9, 8], [1, -9.1, -2], {"fov": 44})),
         [stamp("ninth", "9 November 2015", "The same reef"),
          {"type": "count", "at": "none-0.15", "from": 70, "to": 0, "d": 0.7, "x": 0.8, "y": 0.28, "size": 200, "kicker": "that day", "label": "sevengill sharks"}], cut="On the ninth"),
], mood="mystery")

P(5, [
    shot(REEF, [sg("a", 2.3, pos=[-1.5, -10.75, 0.5], heading=25, roll=78, pose="limp"), sg("b", 2.0, pos=[3.2, -10.78, -2.5], heading=160, roll=-82, pose="limp"),
                sg("c", 2.2, pos=[-5.5, -10.76, -4], heading=-70, roll=95, pose="limp")],
         cam((0, [-6, -10.0, 6], [-1.5, -10.6, 0], {"fov": 40}), (1, [1.5, -9.7, 5], [0.5, -10.7, -0.5], {"fov": 40})),
         [line("carcasses", "Carcasses on the seabed", "carcasses")]),
    shot(GREY, [carcass(f"k{i}", -9 + 4.6 * i, 2.2 + 0.5 * (i % 2), 2.0 + 0.15 * (i % 3), 20 + 150 * (i % 2), 1 if i % 2 else -1, kind=sg, lo=True) for i in range(5)],
         cam((0, [-12, 1.0, 7], [-6, 0.2, 2.4], {"fov": 36}), (1, [-2, 4.6, 12], [1, 0.1, 2.4], {"fov": 36})),
         [stamp("April", "April 2016", "False Bay"),
          {"type": "count", "at": "five", "to": 5, "d": 0.6, "x": 0.82, "y": 0.26, "size": 190, "kicker": "examined", "label": "sevengill sharks"}], cut="More washed"),
    shot(STUDIO,
         [sg("s", 2.4, pos=[0, 0, 0], heading=18, roll=-62, pitch=5, spin=-3, pose="still",
             xray={"at": "liver-0.6", "d": 0.6}, parts={"liver": {"at": "liver-0.6", "out": "liver+0.15"}})],
         cam((0, [0.8, -0.8, 2.7], [0.3, -0.15, 0], {"fov": 34}), (1, [0.5, -0.55, 1.9], [0.32, -0.15, 0], {"fov": 34})),
         [tag("torn", at("s", "chest"), "Torn chest", None, "sw", out="liver-0.6"),
          tag("liver+0.1", at("s", "liver"), "No liver", None, "ne", len=170),
          line("marks", "Orca tooth marks on the skin", "orca")], cut="Each one"),
    shot(REEF,
         [port(across(-5.5, -12, -5, -26, 14, 0.4), shadow=0.55), star(across(-7.5, -7, 0, -31, 9, 0.4), shadow=0.55)],
         cam((0, [2, -9.6, 12], [-6, -7, -4], {"fov": 44}), (1, [5, -9.4, 13], [3, -6.6, 0], {"fov": 44})),
         [{"type": "dim", "at": "proof-0.3", "to": 0.3},
          {"type": "title", "at": "proof-0.2", "kicker": "the first proof", "size": 96, "lines": ["Orcas were killing sharks", {"text": "for a single organ", "accent": True}]}], cut="Her work"),
], mood="tension")

P(3, [
    # the two of them at the surface
    shot({"kind": "surface", "sky": "overcast", "swell": 0.3},
         [port([(0, [-22, -1.7, 4]), (0.3, [-10, -0.66, 5]), (0.6, [1, -1.5, 6]), (1, [15, -0.68, 7])]),
          star([(0, [-27, -0.7, -3]), (0.3, [-15, -1.6, -2]), (0.6, [-4, -0.66, -1]), (1, [10, -1.5, 0])])],
         cam((0, [-2, 1.3, 19], [-9, 0.5, 2], {"fov": 30}), (1, [3, 1.2, 18], [6, 0.5, 3], {"fov": 30})),
         [line("fins", "Their tall back fins have folded over", "folded over")]),
    # seen from behind: one fin to each side
    shot(STUDIO,
         [port(pos=[0, 0, -3.4], heading=0, pose="swim", amp=0.5), star(pos=[0, 0, 3.4], heading=0, pose="swim", amp=0.5)],
         cam((0, [-15, 4.6, -2.5], [2, 0.7, 0], {"fov": 36}), (1, [-13.5, 3.2, 2.5], [2, 0.7, 0], {"fov": 36})),
         [tag("left", at("port", "dorsal"), "Leans left", None, "nw"),
          tag("right", at("star", "dorsal"), "Leans right", None, "ne")], cut="One fin"),
    shot(STUDIO,
         [port(pos=[0, 0, -4.6], heading=90, pose="swim", amp=0.5), star(pos=[0, 0, 4.6], heading=90, pose="swim", amp=0.5)],
         cam((0, [-3, 17, 0.4], [1, 0, 0], {"fov": 40}), (1, [-1, 14, 0.4], [1, 0, 0], {"fov": 40})),
         [{"type": "versus", "at": "named", "y": 0.70, "size": 120, "left": {"title": "sailors' word for left", "value": "Port", "hot": True},
           "right": {"title": "sailors' word for right", "value": "Starboard", "hot": True}}], cut="Local boat"),
])

P(4, [
    shot(SEA,
         [port([(0, [-6, -6, -24]), (1, [4, -5.4, 3])]), star([(0, [3, -7.2, -28]), (1, [11, -6.6, -1])])],
         cam((0, [6, -6.4, 13], [0, -6, -8], {"fov": 40}), (1, [9, -6.2, 15], [5, -6, 0], {"fov": 40})),
         [tag("old", at("port", "back"), "Age", "unknown", "nw"),
          line("hints", "They may be half-brothers", "half-brothers")]),
    # where they have been seen
    shot(MAP([[10.5, -37.5], [30.5, -24.0]], pins=[pin(LUDERITZ, "place"), pin(ALGOA, "east")],
             routes=[{"points": [list(LUDERITZ), [15.8, -29.5], [17.2, -32.6], [18.1, -34.4], [19.9, -35.1], [22.6, -34.5], [24.8, -34.4], list(ALGOA)], "at": "Since", "d": 3.2}]), [],
         mcam((0, (17.0, -29.0), 150, 68, 0), (1, (21.5, -32.8), 170, 58, 4)),
         [tag("place+0.2", geo(LUDERITZ), "Lüderitz, Namibia", "2009", "ne"),
          tag("east+0.2", geo(ALGOA), "Port Elizabeth", "the eastern end of their range", "nw")], cut="Sighting"),
])

P(2, [
    shot(AIR,
         [port(across(-3, 3, -1, -30, 20, 0)), star(across(-3.6, -6, -9, -35, 15, 0))],
         cam((0, [-6, 34, 0.5], [-6, 0, 0], {"fov": 40}), (1, [4, 30, 0.5], [4, 0, 0], {"fov": 40})),
         [stamp("pair", "February 2017", "Off Gansbaai"),
          line("before", "Seen the day before the first dead shark", "day before")]),
    shot(STUDIO, [gw("s", 4.6, pos=[0, 0, 0], heading=20, roll=-8, spin=-5, pose="swim", amp=0.5, xray=True, parts={"liver": {"at": 0.0, "glow": 1.0}})],
         cam((0, [1.6, 0.6, 7.6], [0.2, 0, 0], {"fov": 36}), (1, [0.4, 0.3, 5.4], [0.3, -0.05, 0], {"fov": 36})),
         [{"type": "title", "at": "why", "size": 120, "v": "bottom", "pad": 110, "lines": ["Why only", {"text": "the liver?", "accent": True}]}], cut="The next"),
])

# ====================================================================================== 5. WHY THE LIVER
P(5, [
    shot(SEA, [gw("s", 4.6, [(0, [-12, -5.6, 0]), (0.5, [-1, -5.2, 1.2]), (1, [10, -5.5, 0])])],
         follow("s", [3, 0.2, 10.5], [-3, 0.6, 8]),
         [chapter(4, "Why the liver"),
          line("afloat-0.5", "How does a shark stay afloat?", "afloat")]),
    # an ordinary fish and its bag of gas
    shot(STUDIO, [animal("fishBladder", "f", 3.2, pos=[0, 0, 0], heading=18, spin=-5, pose="swim", amp=0.55, xray=True, parts={"bladder": {"at": 0.0, "glow": 1.0}})],
         cam((0, [1.2, 0.3, 5.6], [0.1, 0, 0], {"fov": 34}), (1, [0.3, 0.2, 4.2], [0.1, 0, 0], {"fov": 34})),
         [tag("bladder", at("f", "bladder"), "Swim bladder", "a small bag of gas", "ne", len=170)], cut="Most fish"),
    # the shark's answer
    shot(STUDIO, [gw("s", 4.6, pos=[0, 0, 0], heading=20, roll=-8, spin=-4, pose="swim", amp=0.5, xray={"at": 0.0, "d": 0.6}, parts={"liver": {"at": "liver-0.5", "glow": 1.0}})],
         cam((0, [1.9, 0.5, 8.4], [0.2, 0, 0], {"fov": 36}), (1, [0.2, 0.3, 5.6], [0.3, -0.05, 0], {"fov": 36})),
         [tag("liver", at("s", "liver"), "The liver", "huge and oily", "ne", len=230),
          {"type": "gauge", "at": "quarter-0.4", "label": "Share of the body's weight", "from": 0, "to": 0.33, "d": 1.6, "show": "¼ to ⅓", "x": 0.08, "y": 0.74, "w": 620},
          line("fat", "Most of it is fat", "fat", y=64)], cut="A shark uses"),
])

P(2, [
    # fuel for crossing an ocean
    shot(GLOBE(routes=[{"points": [[19.3, -35.0], [45, -38], [80, -36], [110, -30]], "at": "long-0.3", "d": 4.2, "arc": 0}], pins=[pin((19.3, -35.0), 0.2), pin((112, -27), "ocean")]), [],
         mcam((0, (35, -30), 96, 90, 0), (1, (85, -28), 86, 90, 0)),
         [{"type": "gauge", "at": 0.3, "runAt": "burns", "label": "Liver fat", "from": 1, "to": 0.32, "d": 4.0, "x": 0.08, "y": 0.76, "w": 600},
          line("engine", "Burned like fuel on long ocean crossings", "fuel", y=64)]),
    # what that means to an orca
    shot(SEA,
         [gw("s", 4.8, across(-5.2, 0, 1, -11, 10, 0.3), xray={"at": "liver-0.6", "d": 0.8}, parts={"liver": {"at": "liver-0.6", "glow": 1.1}}),
          port([(0, [-27, -9.5, -9]), (1, [1, -7.6, -5])])],
         follow("s", [4.5, -0.2, 11], [-1, 0.4, 8.5]),
         [tag("hundreds", at("s", "liver"), "Hundreds of kilograms", "of rich food in one place", "ne", len=210)], cut="For an orca"),
])

P(5, [
    shot(STUDIO, [], cam((0, [-4, 2.4, 13.5], [0, 0.45, 0], {"fov": 32}), (1, [2, 1.8, 11.5], [0, 0.45, 0], {"fov": 32})),
         [tag("teeth", {"prop": "teeth", "point": "tip"}, "Orca teeth", "sharp cones", "ne")],
         props=[{"kind": "teeth", "id": "teeth", "pos": [0, 0, 0]}]),
    # shark skin, close enough to see what it is made of
    shot(STUDIO, [], cam((0, [-7, 1.6, 4.6], [-2, 0.2, 0], {"fov": 30}), (1, [1.5, 1.1, 3.4], [3, 0.2, 0], {"fov": 30})),
         [tag("scales", {"prop": "skin", "point": "scale"}, "Scales shaped like teeth", "shark skin, magnified", "ne", len=190),
          line("sandpaper", "It feels like sandpaper", "sandpaper")],
         props=[{"kind": "denticles", "id": "skin", "pos": [0, 0, 0]}], cut="Shark skin"),
    # the same teeth after years of it
    shot(STUDIO, [], cam((0, [2, 1.8, 11.5], [0, 0.4, 0], {"fov": 32}), (1, [-1.5, 1.4, 9.5], [0, 0.35, 0], {"fov": 32})),
         [tag("flat", {"prop": "teeth", "point": "row"}, "Worn flat", "by a diet of shark", "ne", len=200)],
         props=[{"kind": "teeth", "id": "teeth", "pos": [0, 0, 0], "wear": "wear-0.2", "wearD": 1.8}], cut="Orcas that"),
    shot({"kind": "sea", "depth": 0.5},
         [port(across(-7, -8, -2, -24, 16, 0.4)), star(across(-9.4, -3, 4, -29, 11, 0.4))],
         cam((0, [4, -8, 15], [-6, -8, -2], {"fov": 40}), (1, [7, -7.6, 17], [3, -8, 2], {"fov": 40})),
         [{"type": "rows", "at": 0.2, "title": "Since 1969", "side": "left", "y": 0.2, "w": 700,
           "rows": [{"k": "Dead orcas washed up", "v": "3", "hot": True, "at": "three"}, {"k": "Teeth", "v": "worn flat", "at": "flat-worn"}, {"k": "In the stomach", "v": "shark", "at": "remains"}]},
          line("belong", "Port and Starboard: the shark-eating type", "shark-eating")], cut="Since"),
])

P(2, [
    shot(SEA,
         [gw("s", 4.6, across(-5.0, 1, 2, -8, 8, 0.2), xray={"at": "tear", "d": 0.6}, parts={"liver": {"at": "tear", "glow": 1.1}}),
          star([(0, [-20, -8.5, -6]), (0.6, [-5, -6.4, 0.5]), (1, [1, -5.9, 1.0])])],
         follow("s", [3.5, -0.4, 9.5], [0.5, 0.2, 7]),
         [{"type": "ring", "at": "tear", "anchor": at("s", "chest"), "r": 70},
          line("richest", "The richest part, with very little chewing", "richest")]),
    # the sharks' answer
    shot(AIR,
         [gw(f"g{i}", 3.8 + 0.2 * (i % 4), [(0, [-8 + 6 * (i % 4), -3.6 - 0.3 * i, -12 + 7 * (i // 4) + 3 * (i % 2)]), (0.35, [-3 + 6 * (i % 4), -3.6 - 0.3 * i, -9 + 7 * (i // 4)]),
                                               (1, [48 + 4 * (i % 3), -3.6 - 0.3 * i, -30 + 22 * (i // 4) + 8 * (i % 4)])], lo=True) for i in range(8)],
         cam((0, [2, 38, 0.5], [2, 0, 0], {"fov": 40}), (1, [9, 33, 0.5], [9, 0, 0], {"fov": 40})),
         [line("answered", "The great whites answered with a move of their own", "move")], cut="The great whites"),
])

# ====================================================================================== 6. THE EMPTY SEA
P(3, [
    shot(SEA,
         [gw(f"g{i}", 4.0 + 0.2 * (i % 3), [(0, [-6 + 4 * i, -5 - 0.6 * (i % 3), 2 - 2 * (i % 2)]), (1, [-2 + 6 * i, -7 - 0.5 * i, -46 - 4 * (i % 3)])], lo=True, out=3.2 + 0.25 * i) for i in range(5)],
         cam((0, [0, -5.5, 12], [4, -6, -10], {"fov": 44}), (1, [1, -5.3, 10], [6, -6.4, -14], {"fov": 44})),
         [chapter(5, "The empty sea"),
          {"type": "title", "at": 0.25, "size": 190, "lines": ["They left."], "out": "team"}]),
    shot({"kind": "sea", "depth": 0.4}, [],
         cam((0, [0, -6, 12], [4, -6.4, 0], {"fov": 42}), (1, [5, -5.6, 9], [12, -6, -4], {"fov": 42})),
         [{"type": "count", "at": "five", "to": 5.5, "decimals": 1, "d": 1.2, "x": 0.5, "y": 0.4, "size": 230, "kicker": "the study", "label": "years of boat sightings and tag signals"}], cut="team"),
    # the tagged sharks leaving
    shot(MAP([[18.3, -35.5], [20.9, -34.0]], pins=[pin(GANSBAAI, 0.2)],
             flows=[{"from": list(DYER), "to": [20.7, -35.0], "via": [[19.9, -34.95]], "at": "tracked", "d": 5.5, "n": 14, "spread": 16},
                    {"from": [18.75, -34.75], "to": list(DYER), "at": 0.4, "d": 4.0, "n": 2, "spread": 2, "color": "#FB9002"}]), [],
         mcam((0, (19.4, -34.72), 86, 60, 0), (1, (19.75, -34.8), 70, 48, 10)),
         [tag(0.4, geo(GANSBAAI), "Gansbaai", None, "nw"),
          {"type": "count", "at": "Fourteen", "to": 14, "d": 1.0, "x": 0.8, "y": 0.26, "size": 200, "kicker": "tracked leaving", "label": "tagged great whites"},
          line("orcas", "Gone when the orcas were near", "orcas")], cut="Fourteen"),
], mood="mystery")

P(4, [
    shot(COAST, [], cam((0, [0, -6, 12], [3, -6.4, 0], {"fov": 42}), (1, [6, -5.4, 9], [12, -6, -4], {"fov": 42})),
         [{"type": "bars", "at": 0.2, "title": "How long the sharks stayed away", "y": 0.3, "w": 1200, "max": 100,
           "bars": [{"label": "After the first attacks", "value": 22, "show": "weeks", "at": "weeks"}, {"label": "Later", "value": 92, "show": "months", "at": "months", "hot": True}]}]),
    shot(COAST, [], cam((0, [6, -5.4, 9], [12, -6, -4], {"fov": 42}), (1, [10, -5.0, 7], [18, -6, -6], {"fov": 42})),
         [{"type": "timeline", "at": 0.15, "from": 2016, "to": 2020, "y": 0.6, "w": 1300, "title": "Great white sightings, Gansbaai", "sub": "falling for two and a half years",
           "spans": [{"from": 2017.1, "to": 2019.6, "label": "sightings keep dropping", "at": "dropping"}], "marks": [{"year": 2017.1, "label": "first attacks", "at": 0.5, "hot": True, "up": False}]}], cut="Sightings"),
    # a boat with nothing to show
    shot({"kind": "surface", "sky": "overcast", "swell": 0.35}, [],
         cam((0, [-16, 2.6, 20], [0, 1, 0], {"fov": 34}), (1, [-6, 2.0, 22], [1, 1, 0], {"fov": 34})),
         [line("without", "Back without seeing a single great white", "single")],
         props=[{"kind": "boat", "id": "boat", "pos": [0, 0, 0], "heading": 25, "cage": True}], cut="On many"),
])

P(2, shot(SEA,
          [gw("s", 4.4, [(0, [8, -5, 2]), (0.45, [1, -5.2, 3]), (0.7, [-1, -5.6, 7]), (1, [6, -6.5, 22])]),
           port(across(-7, -22, -17, -32, 14, 0.3), shadow=0.5), star(across(-9, -18, -13, -37, 9, 0.3), shadow=0.5)],
          cam((0, [3, -5.4, 14], [0, -5.6, 0], {"fov": 42}), (1, [5, -5.2, 15], [1, -5.8, 2], {"fov": 42})),
          [{"type": "versus", "at": "wild", "y": 0.16, "size": 96, "left": {"title": "where lions hunt", "value": "Wild dogs", "sub": "keep away", "at": "wild"},
            "right": {"title": "where orcas hunt", "value": "Great whites", "sub": "keep away", "hot": True, "at": "lions"}},
           line("fear", "The fear of being hunted was enough", "fear")]))

P(6, [
    # the other side of the world
    shot(GLOBE(routes=[{"points": [list(GANSBAAI), [-30, 5], [-90, 30], list(FARALLON)], "at": 0.4, "d": 2.6, "arc": 5}], pins=[pin(GANSBAAI, 0.1), pin(FARALLON, "world-0.2")]), [],
         mcam((0, (5, -20), 100, 90, 0), (1, (-105, 30), 84, 90, 0)),
         [tag("world", geo(FARALLON, 3), "California", "the other side of the world", "ne")]),
    shot(MAP([[-124.6, 36.6], [-121.2, 38.8]], pins=[pin(FARALLON, 0.2), pin(SAN_FRANCISCO, "near")],
             routes=[{"points": [[-123.9, 38.4], [-123.3, 37.9], [-122.95, 37.62], [-123.2, 37.1]], "at": "passed-0.3", "d": 2.2, "color": "#FB9002"}]), [],
         mcam((0, (-122.9, 37.75), 110, 64, 0), (1, (-123.0, 37.7), 70, 46, -10)),
         [stamp("second", "2 November 2009", "Southeast Farallon Island"),
          tag("near+0.2", geo(SAN_FRANCISCO), "San Francisco", None, "ne"),
          {"type": "timer", "at": "stayed", "to": 2.5, "decimals": 1, "unit": "hours", "label": "the orcas stayed", "d": 1.6, "x": 0.92, "y": 0.68}], cut="On the second"),
    # seventeen tagged sharks, then none
    shot(MAP([[-123.5, 37.3], [-122.5, 38.1]], pins=[pin(FARALLON, 0.0, pulse=False)],
             flows=[{"from": [-123.02, 37.72], "to": [-122.98, 37.68], "at": 0.0, "d": 3.0, "n": 17, "spread": 5, "loop": True, "out": "Within"},
                    {"from": [-123.0, 37.7], "to": [-123.45, 37.35], "via": [[-123.2, 37.6]], "at": "Within", "d": 3.6, "n": 17, "spread": 7}]), [],
         mcam((0, (-123.0, 37.7), 44, 58, 0), (1, (-123.08, 37.64), 56, 50, 12)),
         [{"type": "count", "at": "Seventeen", "to": 17, "d": 0.8, "x": 0.2, "y": 0.3, "size": 190, "kicker": "that day", "label": "tagged great whites", "out": "Within"},
          {"type": "count", "at": "Within+0.2", "from": 17, "to": 0, "d": 1.6, "x": 0.2, "y": 0.3, "size": 190, "kicker": "within eight hours", "label": "left at the island"},
          line("Sixteen", "Sixteen stayed away for the rest of the season", "sixteen")], cut="Seventeen"),
])

P(2, [
    shot({"kind": "surface", "sky": "day", "swell": 0.45}, [],
         cam((0, [-40, 3.0, 150], [0, 6, 0], {"fov": 30}), (1, [-10, 4.0, 110], [0, 6, 0], {"fov": 30})),
         [{"type": "bars", "at": 0.3, "title": "Elephant seals killed by sharks", "y": 0.56, "w": 1100, "max": 7,
           "bars": [{"label": "A normal year", "value": 7, "show": "7 in 7", "at": "fewer-0.6"}, {"label": "A year when orcas visited", "value": 1, "show": "as few as 1 in 7", "at": "seventh-0.5", "hot": True}]}],
         props=[{"kind": "island", "id": "isle", "pos": [0, 0, 0], "radius": 60, "height": 14, "stretch": 1.6, "top": "#9a9484"}]),
    shot({"kind": "sea", "depth": 0.3},
         [orca("o", across(-4.4, -2, 1, -18, 9, 0.3), 7.0), gw("s", 4.2, across(-3.6, 2, 3, -6, 13, 0.2), xray={"at": "liver-0.5", "d": 0.6}, parts={"liver": {"at": "liver-0.5", "out": "liver+0.5"}})],
         follow("s", [5, -0.6, 11], [1, 0, 8.5]),
         [stamp("October", "October 1997", "Farallon Islands"),
          line("only", "It ate only the liver", "liver")], cut="Back in"),
])

P(2, shot(AIR, [],
          cam((0, [-10, 34, 0.5], [-10, 0, 0], {"fov": 40}), (1, [6, 30, 0.5], [6, 0, 0], {"fov": 40})),
          [{"type": "hud", "at": 0.2, "label": "Drone", "alt": 60, "note": "South Africa · no footage yet", "clock": 0, "out": "changed"},
           {"type": "dim", "at": "changed", "to": 0.3},
           {"type": "title", "at": "changed", "size": 260, "lines": [{"text": "2022", "accent": True}], "kicker": "that changed in"}]))

# ====================================================================================== 7. CAUGHT ON CAMERA
P(3, [
    shot(MAP(CAPE, pins=[pin(GANSBAAI, 0.2, pulse=False), pin(MOSSEL, "over")],
             routes=[{"points": [list(GANSBAAI), [20.2, -35.0], [21.3, -34.75], list(MOSSEL)], "at": "east-0.6", "d": 2.2}]), [],
         mcam((0, (20.3, -34.5), 150, 62, 0), (1, (21.9, -34.25), 76, 46, -8)),
         [chapter(6, "Caught on camera"),
          stamp("sixteenth", "16 May 2022", "Mossel Bay"),
          tag("over+0.2", geo(MOSSEL), "Mossel Bay", "further east", "nw")]),
    # what the drone saw
    shot(AIR,
         [gw("s", 3.6, [(0, [-6, -3.2, 2]), (0.5, [6, -3.2, -3]), (1, [19, -3.2, 3])]),
          star([(0, [-21, -3.5, 5]), (0.5, [-8, -3.5, 0]), (1, [6, -3.5, 4])]),
          orca("o1", [(0, [-24, -4, -6]), (0.5, [-11, -4, -9]), (1, [3, -4, -5])], 6.4),
          orca("o2", [(0, [-28, -3.8, 13]), (0.5, [-14, -3.8, 9]), (1, [0, -3.8, 12])], 6.0),
          orca("o3", [(0, [-31, -4.2, 0]), (0.5, [-18, -4.2, -3]), (1, [-4, -4.2, -1])], 7.4, male=True),
          orca("o4", [(0, [-34, -4.4, -13]), (0.5, [-21, -4.4, -15]), (1, [-7, -4.4, -11])], 5.6)],
         cam((0, [-9, 40, 0.5], [-9, 0, 0], {"fov": 40}), (1, [5, 36, 0.5], [5, 0, 0], {"fov": 40})),
         [{"type": "hud", "at": 0.0, "label": "Drone · Mossel Bay", "alt": 60, "clock": 600},
          {"type": "ring", "at": "chasing", "anchor": at("s"), "r": 80},
          tag("chasing+0.2", at("s"), "Great white shark", None, "ne"),
          tag("Starboard-0.3", at("star", "dorsal"), "Starboard", "one of the five", "sw")], cut="Below"),
], mood="tension")

P(4, [
    shot(AIR,
         [gw("s", 3.6, [(0, [-16, -3.2, -2]), (0.5, [0, -3.2, 3]), (1, [15, -3.2, -3])]),
          star([(0, [-27, -3.5, 2]), (0.5, [-11, -3.5, 6]), (1, [5, -3.5, 0])]),
          orca("o1", [(0, [-30, -4, -9]), (0.5, [-14, -4, -5]), (1, [2, -4, -10])], 6.4),
          orca("o3", [(0, [-34, -4.2, 8]), (0.5, [-19, -4.2, 11]), (1, [-3, -4.2, 6])], 7.4, male=True)],
         cam((0, [-12, 38, 0.5], [-12, 0, 0], {"fov": 40}), (1, [4, 36, 0.5], [4, 0, 0], {"fov": 40})),
         [{"type": "hud", "at": 0.0, "label": "Drone · Mossel Bay", "alt": 60, "clock": 1500},
          {"type": "timer", "at": "lasted", "to": 3600, "d": 2.2, "label": "the chase", "x": 0.92, "y": 0.2, "size": 120}]),
    # the circling trick
    shot(AIR,
         [gw("s", 3.6, [(0, [3.2, -3.0, 0]), (0.125, [2.3, -3.0, 2.3]), (0.25, [0, -3.0, 3.2]), (0.375, [-2.3, -3.0, 2.3]), (0.5, [-3.2, -3.0, 0]), (0.625, [-2.3, -3.0, -2.3]),
                         (0.75, [0, -3.0, -3.2]), (0.875, [2.3, -3.0, -2.3]), (1, [3.2, -3.0, 0])]),
          orca("o1", [(0, [-1.5, -3.8, -0.5]), (0.5, [0.5, -3.8, 0.4]), (1, [1.6, -3.8, -0.3])], 6.4)],
         cam((0, [0, 21, 0.4], [0, 0, 0], {"fov": 40}), (1, [0.5, 17, 0.4], [0.5, 0, 0], {"fov": 40})),
         [{"type": "hud", "at": 0.0, "label": "Drone · Mossel Bay", "alt": 30, "clock": 2100},
          tag("circles", at("s"), "Tight circles", "keeping the hunter in sight", "ne", len=170)], cut="Twice"),
    # five against one
    shot(AIR,
         [gw("s", 3.6, [(0, [2.6, -3.0, 0]), (0.25, [0, -3.0, 2.6]), (0.5, [-2.6, -3.0, 0]), (0.75, [0, -3.0, -2.6]), (1, [2.6, -3.0, 0])]),
          orca("o1", [(0, [-1.2, -3.8, -0.4]), (1, [1.0, -3.8, 0.4])], 6.4),
          star([(0, [-22, -3.5, 9]), (1, [-7, -3.5, 5])]),
          orca("o2", [(0, [20, -3.8, 12]), (1, [8, -3.8, 6])], 6.0),
          orca("o3", [(0, [18, -4.2, -14]), (1, [6, -4.2, -7])], 7.4, male=True),
          orca("o4", [(0, [-16, -4.4, -15]), (1, [-5, -4.4, -8])], 5.6)],
         cam((0, [0, 30, 0.4], [0, 0, 0], {"fov": 40}), (1, [0, 36, 0.4], [0, 0, 0], {"fov": 40})),
         [{"type": "hud", "at": 0.0, "label": "Drone · Mossel Bay", "alt": 50, "clock": 2700},
          note("Five", at("o1"), "1"), note("Five+0.15", at("star"), "2"), note("Five+0.3", at("o2"), "3"), note("Five+0.45", at("o3"), "4"), note("Five+0.6", at("o4"), "5"),
          line("watch", "It could only watch one at a time", "one")], cut="Five orcas"),
])

P(4, [
    shot({"kind": "sea", "depth": 0.25, "water": "teal"},
         [gw("s", 3.6, across(-3.4, 0.5, 1.5, -7, 9, 0.2), xray={"at": "liver-0.8", "d": 0.5}, parts={"liver": {"at": "liver-0.8", "glow": 1.2}}),
          orca("o", [(0, [-21, -6.2, -5]), (0.7, [-1.5, -4.2, 0.2]), (1, [5.5, -3.9, 1.0])], 6.4)],
         follow("s", [4.5, -0.6, 9.5], [1.5, -0.1, 6.5]),
         [{"type": "ring", "at": "right", "anchor": at("s", "liver"), "r": 84},
          tag("right+0.2", at("s", "liver"), "Right where the liver sits", None, "ne", len=190)]),
    shot(AIR, [star(across(-3.5, 4, 0, -10, 34, 0)), orca("o1", across(-4, -5, -8, -14, 30, 0), 6.4), orca("o3", across(-4.2, 11, 8, -18, 26, 0), 7.4, male=True)],
         cam((0, [0, 38, 0.5], [0, 0, 0], {"fov": 40}), (1, [10, 36, 0.5], [10, 0, 0], {"fov": 40})),
         [{"type": "hud", "at": 0.0, "label": "Drone · Mossel Bay", "alt": 60, "clock": 4200},
          {"type": "count", "at": "three", "to": 3, "d": 0.5, "x": 0.8, "y": 0.3, "size": 210, "prefix": "+", "kicker": "scientists think", "label": "more sharks died that day"}], cut="Scientists"),
    shot(STUDIO,
         [star(pos=[0, 0, 0], heading=0, pose="swim", amp=0.5), orca("o1", pos=[-3, 0, -5.2], heading=0, pose="swim", amp=0.5, length=6.4),
          orca("o2", pos=[-3, 0, 5.2], heading=0, pose="swim", amp=0.5, length=6.0), orca("o3", pos=[-6.5, 0, -10.4], heading=0, pose="swim", amp=0.5, length=7.4, male=True),
          orca("o4", pos=[-6.5, 0, 10.4], heading=0, pose="swim", amp=0.5, length=5.6)],
         cam((0, [-20, 9, -2], [-2, 0, 0], {"fov": 40}), (1, [-18, 7.5, 3], [-2, 0, 0], {"fov": 40})),
         [note(0.3, at("star"), "Known shark hunter", dy=-70),
          note("Four", at("o1"), "New", fill="#F7F7F8", dy=-60), note("Four+0.12", at("o2"), "New", fill="#F7F7F8", dy=-60),
          note("Four+0.24", at("o3"), "New", fill="#F7F7F8", dy=-60), note("Four+0.36", at("o4"), "New", fill="#F7F7F8", dy=-60),
          line("learn", "Orcas learn from one another", "learn")], cut="Four of"),
])

P(2, shot({"kind": "surface", "sky": "day", "swell": 0.3}, [],
          cam((0, [-18, 2.4, 24], [0, 4.6, 0], {"fov": 34}), (1, [-9, 2.0, 21], [2, 4.4, 0], {"fov": 34})),
          [{"type": "dots", "at": 0.2, "n": 45, "cols": 15, "size": 26, "gap": 13, "x": 0.5, "y": 0.1, "title": "Mossel Bay survey boats", "sub": "great whites seen", "from": 45,
            "lit": [{"at": "45", "to": 1, "d": 1.6}], "readout": "in 45 days"},
           line("every", "Before the hunt: great whites on every trip", "every trip", out="45")],
          props=[{"kind": "boat", "id": "boat", "pos": [0, 0, 0], "heading": 20}]))

P(7, [
    shot(SEA, [star(across(-6, 0, 2, -20, 12, 0.4))],
         follow("star", [8, 0.5, 16], [0, 1.5, 12], fov=40),
         [stamp("alone", "A year later", "Starboard, alone")]),
    # the young shark
    shot({"kind": "sea", "depth": 0.25, "water": "teal"},
         [gw("s", 2.5, [(0, [-2, -3.6, 1]), (0.5, [6, -3.2, 3]), (1, [14, -3.4, 0])]), star([(0, [-24, -5, -2]), (0.5, [-8, -4, 2]), (1, [7, -3.8, 0])])],
         follow("s", [3.5, 0.2, 9], [-1, 0.8, 7.5]),
         [stamp("eighteenth", "18 June 2023", "Mossel Bay"),
          tag("2.5", at("s", "dorsal"), "Young great white", "about 2.5 metres", "ne")], cut="On the"),
    shot({"kind": "sea", "depth": 0.25, "water": "teal"},
         [gw("s", 2.5, across(-3.4, 0.6, 1.2, -3, 5, 0.1, 0.5), turn=[{"at": "Within", "d": 1.4, "roll": 150, "limp": True}],
             xray={"at": "torn", "d": 0.5}, parts={"liver": {"at": "torn", "out": "liver"}}),
          star([(0, [-9.5, -3.9, -0.4]), (0.5, [-3.6, -3.6, 0.5]), (1, [0.4, -3.5, 1.0])])],
         follow("s", [3.2, -0.3, 6.5], [1.5, 0.2, 5]),
         [{"type": "ring", "at": "fin", "anchor": at("s", "pectoral"), "r": 60},
          tag("fin", at("s", "pectoral"), "By the side fin", None, "se"),
          {"type": "timer", "at": "Within", "to": 120, "d": 2.4, "label": "from catch to liver", "x": 0.92, "y": 0.14}], cut="He grabbed"),
    # a hundred metres away
    shot({**AIR, "swell": 0.05}, [star(pos=[-50, -3.5, 0], heading=15, pose="swim"), port(pos=[50, -3.5, 2], heading=-170, pose="swim")],
         cam((0, [0, 96, 0.6], [0, 0, 0], {"fov": 50}), (1, [0, 88, 0.6], [0, 0, 0], {"fov": 50})),
         [{"type": "hud", "at": 0.0, "label": "Drone · Mossel Bay", "alt": 90, "clock": 300},
          tag(0.3, at("star"), "Starboard", "the hunt", "sw"), tag(0.5, at("port"), "Port", "keeps his distance", "ne"),
          {"type": "measure", "at": "hundred-0.3", "from": at("star"), "to": at("port"), "value": 100, "decimals": 0, "unit": " m", "off": -90, "size": 80}], cut="Port stayed"),
    shot(GREY, [carcass("x", 0, 2.4, 3.5, 12)],
         cam((0, [4.5, 0.6, 6.6], [0.2, 0.3, 2.4], {"fov": 34}), (1, [-2.5, 1.4, 8], [0, 0.25, 2.4], {"fov": 34})),
         [tape("3.5", 0, 2.4, 3.5, 12, "a second great white", size=70),
          line("four", "Great whites stayed away for about four months", "four months")], cut="A second"),
], mood="tension")

P(1, shot(COAST,
          [bw(f"b{i}", 2.5 + 0.1 * (i % 3), across(-5.5 - 0.5 * (i % 3), -20 + 3 * i, -8 + 2.5 * i, -22 - 2 * i, 12 - i, 0.3, 1.0), lo=True, at=0.6 + 0.35 * i) for i in range(5)],
          cam((0, [1, -5.6, 13], [0, -5.8, -4], {"fov": 42}), (1, [4, -5.4, 11], [1, -5.8, -4], {"fov": 42})),
          [line("other", "Other animals began to take their place", "take their place")]))

# ====================================================================================== 8. A COAST REARRANGED
P(3, [
    shot(COAST,
         [bw(f"b{i}", 2.5 + 0.12 * (i % 4), across(-4.8 - 0.55 * (i % 3), -8 + 2.6 * i - 9 * (i // 4), -4 + 2.4 * i - 9 * (i // 4), (-16 - 2 * (i % 3)), (13 + (i % 4)), 0.3, 1.0), lo=True) for i in range(7)],
         follow("b1", [4, 0.2, 8], [-1.5, 0.6, 6], fov=40),
         [chapter(7, "A coast rearranged"),
          tag("whaler", at("b1", "dorsal"), "Bronze whaler", "a smaller shark", "ne")]),
    # the two side by side
    shot(STUDIO, [gw("g", 4.5, pos=[0, 0.75, 0], heading=14, pose="swim", amp=0.5, spin=-2), bw("b", 2.8, pos=[0.3, -1.05, 1.2], heading=14, pose="swim", amp=0.6, spin=-2)],
         cam((0, [1.4, 0.4, 9.2], [0.2, -0.1, 0], {"fov": 36}), (1, [0, 0.2, 7.2], [0.2, -0.1, 0], {"fov": 36})),
         [tag("eat", at("g", "dorsal"), "Great white", "the hunter", "ne"),
          tag("smaller", at("b", "tail"), "Bronze whaler", "the hunted", "sw")], cut="Great whites eat"),
    shot({"kind": "sea", "depth": 0.2, "water": "teal"},
         [bw("a", 2.8, [(0, [-13, -2.6, 8]), (0.55, [-1.2, -1.9, 5.4]), (1, [10, -2.3, 8])]), bw("b", 2.5, across(-3.4, 11, 7.5, 13, -11, 0.2, 1.5)),
          bw("c", 2.6, across(-5, 14, 12, -16, 12, 0.3, 1))],
         cam((0, [5.5, -4.2, 13], [-1.3, -0.9, 2.6], {"fov": 40}), (1, [2.8, -3.4, 10.6], [-1.3, -0.9, 2.6], {"fov": 40})),
         [line("most", "Bronze whalers on most trips", "most trips")],
         props=[{"kind": "boat", "id": "boat", "pos": [0, 0, 0], "cage": True}], cut="Today"),
])

P(6, [
    shot(MAP([[17.6, -34.9], [19.6, -33.6]], pins=[pin(SEAL_ISLAND, "change")], zones=[{"lon": FALSE_BAY[0], "lat": FALSE_BAY[1], "km": 20, "at": 0.2}]), [],
         mcam((0, (18.7, -34.2), 110, 64, 0), (1, (18.6, -34.16), 60, 46, 8)),
         [stamp("False", "False Bay", "Beside Cape Town"),
          tag("change+0.2", geo(SEAL_ISLAND, 5), "Seal Island", None, "ne")]),
    # what the island was famous for
    shot({"kind": "surface", "sky": "dawn", "swell": 0.3, "sun": [-0.5, 0.3, -0.8]},
         [gw("s", 3.9, [(0, [-9, -7, 3]), (0.34, [-2, -1.5, 1.5]), (0.5, [1.2, 3.4, 0.8]), (0.66, [4.2, -1.2, 0.2]), (1, [10, -6, -1])])],
         cam((0, [-3, 1.6, 22], [0, 2.4, 0], {"fov": 30}), (1, [1, 1.5, 19], [1, 2.2, 0], {"fov": 30})),
         [line("leaping", "Great whites leaping clear of the water", "leaping")],
         props=[{"kind": "island", "id": "isle", "pos": [-30, 0, -190], "radius": 55, "height": 4, "stretch": 2.6},
                {"kind": "spray", "id": "up", "pos": [-0.6, 0, 1.2], "u": 0.38, "power": 1.0}, {"kind": "spray", "id": "down", "pos": [4.0, 0, 0.3], "u": 0.63, "power": 0.75}], cut="Seal Island"),
    # the survey record
    shot({"kind": "surface", "sky": "overcast", "swell": 0.35}, [],
         cam((0, [20, 2.4, 150], [0, 3, 0], {"fov": 30}), (1, [-6, 3.2, 120], [0, 3, 0], {"fov": 30})),
         [{"type": "timeline", "at": 0.2, "from": 2000, "to": 2020, "every": 2, "y": 0.72, "w": 1400, "titleUp": 235, "title": "Seal Island surveys", "sub": "great whites recorded",
           "spans": [{"from": 2000, "to": 2018.6, "label": "great whites every season", "at": "surveyed", "color": "rgba(247,247,248,0.8)"},
                     {"from": 2018.65, "to": 2020, "label": "none", "at": "no"}], "marks": []}],
         props=[{"kind": "island", "id": "isle", "pos": [0, 0, 0], "radius": 55, "height": 4, "stretch": 2.6}], cut="Shark scientist"),
    # the beaches
    shot({"kind": "beach", "sky": "day", "sun": [0.3, 0.75, 0.5]}, [],
         cam((0, [-14, 2.2, 14], [0, 0.6, -8], {"fov": 36}), (1, [-4, 3.4, 16], [6, 0.4, -8], {"fov": 36})),
         [{"type": "bars", "at": 0.2, "title": "Great white sightings · Cape Town beaches", "y": 0.2, "w": 1200, "max": 320,
           "bars": [{"label": "2011", "value": 300, "show": "300+", "at": "300"}, {"label": "2019", "value": 0, "show": "0", "at": "2019", "hot": True}]}], cut="On the beaches"),
])

P(3, [
    shot(COAST, [sg("a", 2.4, across(-12.6, -2, 1, -14, 10, 0.2, 1)), sg("b", 2.1, across(-11.8, 5, 3, 13, -12, 0.2, -1)), sg("c", 2.2, across(-12.2, -7, -5, -20, 8, 0.2, 1))],
         follow("a", [2.5, 0.6, 6.5], [-1.5, 0.9, 5], fov=40),
         [tag("never", at("a", "gills"), "Sevengill sharks", "never recorded here before", "ne")]),
    shot({"kind": "surface", "sky": "day", "swell": 0.4}, [],
         cam((0, [-30, 2.6, 130], [0, 3, 0], {"fov": 30}), (1, [0, 3.4, 96], [0, 3, 0], {"fov": 30})),
         [{"type": "count", "at": "six", "to": 6, "d": 1.0, "x": 0.5, "y": 0.34, "size": 260, "prefix": "×", "kicker": "Cape fur seal sightings", "label": "about six times as many"}],
         props=[{"kind": "island", "id": "isle", "pos": [0, 0, 0], "radius": 55, "height": 4, "stretch": 2.6}], cut="Reported"),
    # who gained and who lost
    shot(REEF, [sg("a", 2.3, across(-9.6, -2, 0, -13, 10, 0.2, 1), lo=True), sg("b", 2.0, across(-9.0, 4, 2, 12, -11, 0.2, -1), lo=True)],
         cam((0, [-3, -9.2, 11], [0, -9.2, 0], {"fov": 44}), (1, [2.5, -8.8, 8.5], [0, -9.1, -1], {"fov": 44})),
         [{"type": "dim", "at": 0.0, "to": 0.28},
          {"type": "rows", "at": 0.15, "title": "False Bay without its great whites", "side": "left", "y": 0.2, "w": 820,
           "rows": [{"k": "Great whites", "v": "gone", "at": 0.3}, {"k": "Sevengill sharks", "v": "up", "hot": True, "at": 0.5}, {"k": "Cape fur seals", "v": "up × 6", "hot": True, "at": 0.7},
                    {"k": "Fish that seals eat", "v": "down", "at": "fish"}, {"k": "Small sharks", "v": "down", "at": "small"}]}], cut="The fish"),
])

P(3, [
    shot(REEF, [port(across(-6, -4, 1, -22, 14, 0.4)), star(across(-8, 1, 6, -27, 9, 0.4))],
         cam((0, [4, -8.6, 14], [-6, -7, -2], {"fov": 42}), (1, [7, -8.2, 16], [3, -7, 2], {"fov": 42})),
         [line("kept", "Port and Starboard kept hunting", "kept hunting")]),
    # one visit
    shot(GREY,
         [carcass(f"k{i}", -24 + 2.7 * i + 0.8 * (i % 3), 1.7 + 0.9 * ((i * 7) % 4) / 3 + 0.5 * (i % 2), 1.9 + 0.12 * (i % 5), (25 + 47 * i) % 360, 1 if i % 2 else -1, kind=sg, lo=True) for i in range(19)],
         cam((0, [-26, 2.0, 9], [-14, 0.2, 2.4], {"fov": 38}), (1, [-4, 9.5, 19], [4, 0.1, 2.4], {"fov": 38})),
         [stamp("February", "February 2023", "Near Gansbaai", out="Nearly-0.2"),
          {"type": "count", "at": "twenty", "to": 20, "d": 1.2, "x": 0.8, "y": 0.24, "size": 210, "kicker": "after a single visit", "label": "sharks washed up"},
          line("Nearly", "Nearly all sevengills · each with its liver removed", "liver removed")], cut="In February"),
])

P(2, shot({"kind": "sea", "depth": 0.7},
          [port(across(-8, -8, -3, -22, 16, 0.4), shadow=0.8), star(across(-10.4, -3, 3, -27, 11, 0.4), shadow=0.8)],
          cam((0, [3, -9.5, 15], [-5, -9, -3], {"fov": 40}), (1, [6, -9, 17], [3, -9, 0], {"fov": 40})),
          [{"type": "dim", "at": 0.2, "to": 0.3},
           {"type": "title", "at": "case", "size": 170, "lines": ["Case closed?"], "out": "Several"},
           {"type": "title", "at": "second-0.3", "size": 150, "kicker": "several shark scientists say it is missing", "lines": ["A second", {"text": "suspect", "accent": True}]}], mood="tension"))

# ====================================================================================== 9. THE SECOND SUSPECT
P(5, [
    shot(MAP(SOUTH_AFRICA, pins=[pin(GANSBAAI, 0.4, pulse=False), pin(MOSSEL, 0.6, pulse=False), pin(ALGOA, 0.8, pulse=False), pin(DURBAN, 1.0, pulse=False)]), [],
         mcam((0, (20.0, -33.5), 150, 70, 0), (1, (26.0, -32.5), 170, 58, 0)),
         [chapter(8, "The second suspect"),
          stamp("2023", "The 2023 study", "Great white records from the whole coast"),
          line("steady", "Numbers looked steady overall", "steady")]),
    # down in the west, up in the east
    shot(MAP(SOUTH_AFRICA, zones=[{"lon": 18.9, "lat": -34.5, "km": 120, "at": "fallen", "color": "#F7F7F8"}, {"lon": 25.9, "lat": -34.0, "km": 130, "at": "risen", "color": "#FDE302"}]), [],
         mcam((0, (22.3, -33.6), 165, 62, 0), (1, (22.6, -33.9), 150, 54, 0)),
         [tag("fallen+0.2", geo((18.9, -34.5), 4), "West", "sightings fell", "sw"),
          tag("risen+0.2", geo((25.9, -34.0), 4), "East", "sightings rose", "ne")], cut="Sightings"),
    shot(MAP([[23.0, -35.2], [28.5, -32.2]], pins=[pin(ALGOA, 0.2)]), [],
         mcam((0, (25.7, -33.9), 96, 60, 0), (1, (25.8, -34.0), 78, 50, 8)),
         [tag(0.4, geo(ALGOA), "Algoa Bay", None, "nw"),
          {"type": "bars", "at": 0.3, "title": "Great whites caught by shore anglers", "x": 0.66, "y": 0.5, "w": 900, "max": 62,
           "bars": [{"label": "2013", "value": 6, "at": "six"}, {"label": "2019", "value": 59, "at": "59", "hot": True}]}], cut="At Algoa"),
    shot(MAP(SOUTH_AFRICA, pins=[pin(GANSBAAI, 0.1, pulse=False), pin(ALGOA, 0.1, pulse=False)],
             flows=[{"from": [19.4, -34.9], "to": [25.9, -34.2], "via": [[21.0, -35.2], [23.5, -34.7]], "at": 0.3, "d": 5.5, "n": 34, "spread": 22}]), [],
         mcam((0, (21.0, -33.8), 150, 60, 0), (1, (23.8, -33.8), 150, 54, 4)),
         [line("moved", "Moved east, away from the orcas", "east")], cut="To that team"),
])

P(3, shot(COAST, [gw("a", 4.2, across(-6, -14, -9, -22, 12, 0.3), lo=True)],
          cam((0, [0, -6, 13], [2, -6.3, 0], {"fov": 42}), (1, [4, -5.6, 11], [8, -6, -3], {"fov": 42})),
          [{"type": "dim", "at": 0.0, "to": 0.3},
           stamp("2024", "2024", "Another group pushes back", y=820),
           {"type": "timeline", "at": "sightings-0.5", "from": 2008, "to": 2020, "every": 2, "y": 0.66, "w": 1400, "title": "Great white sightings in False Bay",
            "spans": [{"from": 2012, "to": 2015, "label": "about three years", "at": "three"}],
            "marks": [{"year": 2012, "label": "Sightings start to fall", "at": "falling-0.4", "hot": True}, {"year": 2015, "label": "Port and Starboard first seen hunting here", "at": "before", "up": False}]}]))

P(5, [
    shot(MAP([[27.5, -33.5], [34.5, -26.5]], pins=[pin(DURBAN, "people")], zones=[{"lon": 31.3, "lat": -29.6, "km": 170, "at": "province-1.2", "color": "#FB9002"}]), [],
         mcam((0, (30.6, -30.2), 130, 62, 0), (1, (31.0, -29.9), 90, 48, -10)),
         [line("people", "This group pointed to people", "people", out="protect"),
          tag("protect", geo(DURBAN), "KwaZulu-Natal", "nets and baited hooks off swimming beaches", "nw")]),
    # the net itself
    shot({"kind": "sea", "depth": 0.25, "water": "teal", "floor": 9},
         [gw("s", 3.4, [(0, [-13, -4, 18]), (0.7, [-1, -3.6, 5]), (1, [2.5, -3.5, 2.6])])],
         cam((0, [-13, -4.6, 8.5], [2, -3, 0], {"fov": 42}), (1, [-9, -4, 7], [2, -3, 0], {"fov": 42})),
         [tag(0.5, {"prop": "net", "point": "mid"}, "Shark net", "KwaZulu-Natal", "nw"),
          {"type": "rows", "at": "Between", "title": "1978 to 2018", "side": "right", "y": 0.2, "w": 620,
           "rows": [{"k": "Great whites caught", "v": "1,317", "at": "caught"}, {"k": "Died", "v": "1,108", "hot": True, "at": "died-0.5"}, {"k": "Each year", "v": "about 28", "at": "28"}]}],
         props=[{"kind": "net", "id": "net", "pos": [0, 0, 0], "heading": 20, "length": 70}], cut="Shark nets"),
    shot({"kind": "sea", "depth": 0.6},
         [port(across(-8, -8, -3, -22, 16, 0.4), shadow=0.45), star(across(-10.4, -3, 3, -27, 11, 0.4), shadow=0.45)],
         cam((0, [3, -9.5, 15], [-5, -9, -3], {"fov": 40}), (1, [6, -9, 17], [3, -9, 0], {"fov": 40})),
         [{"type": "dim", "at": 0.0, "to": 0.25},
          {"type": "versus", "at": 0.2, "y": 0.3, "size": 190, "left": {"title": "Nets and hooks · 1978 to 2018", "value": 1108, "sub": "great whites killed", "at": 0.2},
           "right": {"title": "Orcas · since 2017", "value": 8, "sub": "great whites known killed", "hot": True, "at": "eight-0.3", "d": 0.6}}], cut="Orcas, by"),
])

P(4, [
    shot({"kind": "surface", "sky": "overcast", "swell": 0.45}, [],
         cam((0, [-20, 2.6, 24], [0, 1, 0], {"fov": 34}), (1, [-10, 2.0, 20], [2, 1, 0], {"fov": 34})),
         [line("add", "Fishing boats add to the pressure", "pressure")],
         props=[{"kind": "boat", "id": "boat", "pos": [0, 0, 0], "heading": 30, "length": 14, "color": "#c7d0d6"}]),
    shot({"kind": "sea", "depth": 0.3},
         [gw("s", 4.0, [(0, [-16, -6, 9]), (1, [6, -4.6, 3])]), bw("a", 2.4, across(-4.5, -6, -4, 14, -12, 0.2, -1), lo=True)],
         cam((0, [-11, -4.6, 12], [2, -3, 0], {"fov": 42}), (1, [-6, -4, 10], [3, -3, 0], {"fov": 42})),
         [tag("lines", {"prop": "line", "point": "mid"}, "Longline", "hooks that catch great whites too", "ne")],
         props=[{"kind": "longline", "id": "line", "pos": [0, -1.2, 0], "heading": 15, "length": 90}], cut="They take"),
    # how few there are
    shot({"kind": "sea", "depth": 0.5}, [],
         cam((0, [0, -6, 12], [4, -6.4, 0], {"fov": 42}), (1, [5, -5.6, 9], [12, -6, -4], {"fov": 42})),
         [{"type": "dim", "at": 0.0, "to": 0.25},
          {"type": "dots", "at": 0.15, "n": 800, "cols": 50, "size": 13, "gap": 7, "x": 0.5, "y": 0.2, "title": "South Africa's great whites", "sub": "a few hundred to about a thousand", "from": 800,
           "lit": [{"at": "losing", "to": 560, "d": 3.2}], "readout": "left"}], cut="South Africa's"),
])

P(4, shot(AIR,
          [gw(f"g{i}", 3.9 + 0.2 * (i % 3), [(0, [-6 + 6 * (i % 3), -3.8 - 0.3 * i, -8 + 8 * (i // 3)]), (0.45, [-1 + 6 * (i % 3), -3.8 - 0.3 * i, -5 + 8 * (i // 3)]), (1, [46, -3.8 - 0.3 * i, -20 + 20 * (i // 3) + 6 * (i % 3)])], lo=True) for i in range(6)]
          + [port([(0, [-46, -3, 4]), (0.5, [-16, -3, 2]), (1, [10, -3, -1])]), star([(0, [-50, -3.6, -5]), (0.5, [-20, -3.6, -6]), (1, [5, -3.6, -8])])],
          cam((0, [2, 36, 0.5], [2, 0, 0], {"fov": 40}), (1, [6, 32, 0.5], [6, 0, 0], {"fov": 40})),
          [{"type": "dim", "at": 0.0, "to": 0.25},
           {"type": "title", "at": 0.2, "size": 150, "v": "top", "pad": 150, "lines": ["Who is right?"], "out": "both"},
           {"type": "versus", "at": "both", "y": 0.3, "size": 110, "left": {"title": "the orcas", "value": "Sudden exits", "sub": "a busy bay quiet within days", "hot": True, "at": "sudden-0.3"},
            "right": {"title": "nets and fishing", "value": "Fewer sharks", "sub": "left to come back", "at": "Years"}}]))

# ====================================================================================== 10. OTHER OCEANS
P(5, [
    shot(GLOBE(pins=[pin(GANSBAAI, 0.0, pulse=False), pin(GULF_CAL, "Gulf")], routes=[{"points": [list(GANSBAAI), [-40, 0], [-90, 22], list(GULF_CAL)], "at": 0.3, "d": 2.6, "arc": 5}]), [],
         mcam((0, (0, -15), 100, 90, 0), (1, (-106, 25), 76, 90, 0)),
         [chapter(9, "Other oceans"),
          tag("Gulf+0.3", geo(GULF_CAL, 3), "Gulf of California", "Moctezuma's pod · 2020 and 2022", "ne")]),
    # up to the surface and over
    shot({"kind": "sea", "depth": 0.15},
         [gw("s", 2.4, [(0, [-7, -5, 1]), (0.5, [0, -1.6, 1.2]), (1, [4, -0.9, 1.0])], turn=[{"at": "roll-0.2", "d": 1.6, "roll": 180, "limp": True}]),
          orca("o", [(0, [-13, -7, 0]), (0.5, [-4, -3.2, 0.6]), (1, [0.5, -2.4, 0.8])], 6.6), orca("p", across(-5, -8, -5, -20, 6, 0.6), 6.0)],
         follow("s", [4, -0.8, 9], [1.5, -1.6, 6.5]),
         [line("push", "Pushed to the surface and rolled onto its back", "rolled")], cut="Those orcas"),
    shot({"kind": "sea", "depth": 0.15},
         [gw("s", 2.4, pos=[0, -1.0, 0], heading=10, roll=180, pose="limp", xray={"at": "liver-0.6", "d": 0.6}, parts={"liver": {"at": "liver-0.6", "out": "liver+0.2"}}),
          orca("o", [(0, [-6.5, -2.6, -1.2]), (1, [-4.8, -2.3, -0.6])], 6.6)],
         cam((0, [2.6, -2.2, 5.2], [0, -1.0, 0], {"fov": 38}), (1, [1.2, -1.8, 4.0], [0, -1.0, 0], {"fov": 38})),
         [tag("limp", at("s", "belly"), "Tonic immobility", "upside down, the shark goes limp", "ne", len=170)], cut="A shark held"),
])

P(3, shot(SEA,
          [gw("s", 2.3, across(-4.6, 0.5, 1.5, -8, 8, 0.2)), orca("o", across(-7.2, -7, -4, -22, 6, 0.5), 6.8, shadow=0.45)],
          follow("s", [3.5, 0.3, 7.5], [-0.5, 0.8, 6]),
          [tag("young", at("s", "dorsal"), "Young great white", None, "ne"),
           line("experience", "Young sharks may have no experience of orcas yet", "no experience")]))

P(3, [
    shot(GLOBE(pins=[pin(PORTLAND, "Portland-0.5")]), [],
         mcam((0, (120, -20), 96, 90, 0), (1, (140, -35), 70, 90, 0)),
         [stamp("Australia", "October 2023", "Portland, Victoria · Australia"),
          tag("Portland", geo(PORTLAND, 3), "Portland", None, "nw")]),
    shot({"kind": "beach", "sky": "day", "sun": [0.4, 0.7, 0.55]}, [carcass("x", 0, 2.5, 4.7, 10)],
         cam((0, [4.8, 0.6, 7], [0.4, 0.4, 2.5], {"fov": 34}), (1, [-1.5, 1.2, 8], [0.2, 0.35, 2.5], {"fov": 34})),
         [tape(0.2, 0, 2.5, 4.7, 10, size=70),
          tag("gone", at("x", "flank"), "Liver", "gone", "nw"),
          note("DNA-0.2", at("x", "chest"), "Orca DNA in the bite wound", dy=-150, size=26)], cut="Its liver"),
])

P(1, shot(GLOBE(pins=[pin(GANSBAAI, "news-0.6")]), [],
          mcam((0, (120, -32), 84, 90, 0), (1, (24, -31), 70, 90, 0)),
          [{"type": "title", "at": "2026-0.2", "size": 250, "v": "bottom", "pad": 130, "align": "left", "lines": [{"text": "2026", "accent": True}], "sub": "news from South Africa"}]))

# ====================================================================================== 11. THE RETURN
P(4, [
    shot({"kind": "surface", "sky": "day", "swell": 0.3},
         [gw("s", 2.6, [(0, [-16, -0.52, 10]), (0.5, [-2, -0.5, 7]), (1, [12, -0.52, 9])])],
         cam((0, [-10, 1.9, 17], [0, 0.8, 2], {"fov": 34}), (1, [-5, 1.6, 14], [2, 0.8, 2], {"fov": 34})),
         [chapter(10, "The return"),
          stamp("twenty-third", "23 September 2026", "Seal Island · False Bay"),
          tag("young", at("s", "dorsal"), "A young great white", None, "ne")],
         props=[{"kind": "boat", "id": "boat", "pos": [2, 0, 0], "heading": 14},
                {"kind": "island", "id": "isle", "pos": [-20, 0, -180], "radius": 55, "height": 4, "stretch": 2.6}]),
    shot({"kind": "sea", "depth": 0.2, "water": "green"},
         [gw("s", 2.6, [(0, [-12, -3, -4]), (0.6, [-1, -2.6, 4]), (1, [4, -2.8, 10])])],
         cam((0, [3, -3.4, 11], [-4, -2.8, 0], {"fov": 40}), (1, [5, -3.2, 12], [0, -2.7, 4], {"fov": 40})),
         [line("first", "The first seen there in about eight years", "eight years")],
         props=[{"kind": "boat", "id": "boat", "pos": [-2, 0, -3], "heading": 14}], cut="The crew"),
    shot({"kind": "sea", "depth": 0.2, "water": "teal"},
         [gw("a", 3.8, [(0, [-14, -2.8, 9]), (0.6, [-1.5, -1.9, 5.5]), (1, [9, -2.4, 8])]), gw("b", 3.3, [(0, [15, -4, 11]), (0.6, [4, -3, 7]), (1, [-8, -3.4, 9.5])])],
         cam((0, [5.5, -4.4, 13.5], [-1.3, -0.9, 2.6], {"fov": 40}), (1, [2.6, -3.5, 10.5], [-1.3, -0.9, 2.6], {"fov": 40})),
         [stamp("third", "3 November 2026", "Off Gansbaai", out="first-0.4"),
          line("year", "The first in more than a year", "more than a year")],
         props=[{"kind": "boat", "id": "boat", "pos": [0, 0, 0], "cage": True}], cut="Six weeks"),
], mood="hope")

P(5, [
    shot(COAST, [gw("a", 3.8, across(-5.5, -1, 2, -13, 10, 0.3)), gw("b", 3.3, across(-7, -6, -3, -18, 7, 0.3))],
         follow("a", [4, 0.3, 10], [-2, 0.8, 7.5]),
         [line("hopeful", "A few sharks are a hopeful sign", "hopeful", out="early"),
          line("early", "Too early to call it a return", "too early")]),
    shot(MAP([[17.0, -35.6], [20.6, -33.2]],
             routes=[{"points": [[17.6, -34.6], [18.2, -34.75], [18.75, -34.6], [18.9, -34.3]], "at": "reported-0.3", "d": 2.4, "color": "#FDE302"},
                     {"points": [[17.5, -34.3], [18.0, -34.9], [19.0, -35.1], [20.0, -34.95]], "at": "reported", "d": 2.6, "color": "#FB9002"}]), [],
         mcam((0, (18.7, -34.5), 110, 62, 0), (1, (18.9, -34.6), 92, 52, 6)),
         [stamp("still", "Early 2026", "Around the Cape"),
          tag("reported+0.8", geo((18.9, -34.3), 4), "Port", None, "ne"), tag("reported+1.1", geo((20.0, -34.95), 4), "Starboard", None, "se"),
          line("apart", "Sometimes swimming apart", "apart")], cut="Port and"),
])

P(4, [
    shot(SEA,
         [port([(0, [-22, -3.4, -9]), (1, [20, -2.8, -1])]), star([(0, [-27, -4.6, -3]), (1, [15, -4.2, 4])])],
         cam((0, [0, -9.5, 13], [-4, -3.5, -3], {"fov": 42}), (1, [2, -9, 12], [6, -3.2, 0], {"fov": 42})),
         [{"type": "dim", "at": 0.0, "to": 0.3},
          {"type": "title", "at": 0.2, "size": 112, "lines": ["Did two orcas empty", {"text": "a great white shark coast?", "accent": True}]}]),
    shot(MAP(CAPE, pins=[pin(GANSBAAI, 0.2), pin(MOSSEL, 0.5)], zones=[{"lon": GANSBAAI[0], "lat": GANSBAAI[1] - 0.1, "km": 26, "at": 0.3}, {"lon": MOSSEL[0], "lat": MOSSEL[1] - 0.1, "km": 26, "at": 0.6}]), [],
         mcam((0, (20.6, -34.5), 150, 62, 0), (1, (20.8, -34.5), 130, 54, 0)),
         [tag(0.4, geo(GANSBAAI), "Gansbaai", "they did", "nw"), tag(0.7, geo(MOSSEL), "Mossel Bay", "they did", "ne"),
          line("cameras", "More than once, and on camera", "on camera")], cut="At Gansbaai"),
    shot({"kind": "sea", "depth": 0.3, "water": "teal", "floor": 9},
         [gw("s", 3.4, [(0, [-14, -4, 17]), (1, [1, -3.5, 4])])],
         cam((0, [-12, -4.4, 9], [2, -3, 0], {"fov": 42}), (1, [-8, -4, 7.5], [2, -3, 0], {"fov": 42})),
         [line("help", "Across the wider coast, they had help", "help")],
         props=[{"kind": "net", "id": "net", "pos": [0, 0, 0], "heading": 20, "length": 70}], cut="Across"),
])

P(6, [
    shot(SEA, [gw("s", 2.5, across(-5, 0, 2, -10, 9, 0.3)), orca("o", across(-9.5, -20, -15, -34, 8, 0.4), 6.8, shadow=0.8)],
         follow("s", [4, 0.3, 8.5], [-1.5, 0.8, 6.5]),
         [line("born", "Born knowing to flee, or learned?", "learned")]),
    # the last word
    shot(SEA,
         [port([(0, [-24, -4, -10]), (1, [22, -3.2, -2])]), star([(0, [-30, -5.4, -4]), (1, [16, -4.8, 4])]), gw("s", 4.2, across(-8, 8, 6, 16, -16, 0.3, -1), lo=True)],
         cam((0, [0, -9.5, 14], [-3, -4, -3], {"fov": 42}), (1, [2, -9.2, 13], [5, -3.6, 0], {"fov": 42})),
         [{"type": "dim", "at": 0.0, "to": 0.32},
          {"type": "title", "at": 0.15, "size": 150, "lines": ["What do you think?"], "sub": "Tell us in the comments", "out": "more-0.4"},
          {"type": "title", "at": "more-0.3", "size": 150, "kicker": "more stories like this", "lines": [{"text": "Beast Atlas", "accent": True}], "sub": "Subscribe"}],
         cut="What do", exit="fade"),
], mood="wonder")

assert _pos == len(SENT), f"{len(SENT) - _pos} sentences of the script have no shot"

# ------------------------------------------------------------------------------------------ checks
def _norm(w):
    return re.sub(r"[^\w]", "", w.lower())


def _has(phrase, text):
    phrase = re.sub(r"(#\d+)?([+-]\d+(\.\d+)?)?$", "", phrase)
    toks, want = [_norm(w) for w in text.split()], [_norm(w) for w in phrase.split() if _norm(w)]
    return any(all(toks[i + j] == want[j] or (j == len(want) - 1 and toks[i + j].startswith(want[j])) for j in range(len(want)))
               for i in range(len(toks) - len(want) + 1))


def _cue_words(node, text, where):
    if isinstance(node, dict):
        for k, v in node.items():
            if k in ("at", "out", "cut") and isinstance(v, str):
                if not _has(v, text):
                    raise SystemExit(f"{where}: the word {v!r} is not in the passage: {text}")
            else:
                _cue_words(v, text, where)
    elif isinstance(node, list):
        for v in node:
            _cue_words(v, text, where)


for _i, _sc in enumerate(scenes):
    _cue_words({k: v for k, v in _sc.items() if k != "text"}, _sc["text"], f"passage {_i + 1}")

# ------------------------------------------------------------------------------------------------ thumbnail
# Real photos, cut out and turned black and white (thumbnail/), on black, with two to four huge words: the look
# of the owner's reference thumbnails. Each layout exists in white + red and in the channel's colours (white over
# yellow running into orange). `use` names the one that is drawn; `ytauto thumbnail <project> --all` draws them all.
_T = "thumbnail/"
_LAYOUTS = {
    "shark-killers": {"headline": "SHARK|KILLERS", "accent": "KILLERS", "text": {"at": "left", "width": 0.47, "y": 0.735},
                      "images": [{"file": _T + "orcas-two.png", "x": 0.635, "y": 0.40, "w": 0.74}],
                      "spot": {"x": 0.62, "y": 0.4, "r": 0.45, "strength": 0.07}},
    "only-ate-the-liver": {"headline": "ONLY ATE THE LIVER", "accent": "LIVER", "text": {"at": "top-left", "width": 0.905},
                           "images": [{"file": _T + "orcas-two.png", "x": 0.70, "y": 0.61, "w": 0.60},
                                      {"file": _T + "great-white.png", "x": 0.20, "y": 0.80, "w": 0.38}],
                           "arrow": {"from": [0.10, 0.27], "to": [0.21, 0.64], "bend": 0.30}},
    "they-hunt-great-whites": {"headline": "THEY HUNT GREAT WHITES", "accent": "GREAT WHITES", "text": {"at": "top", "width": 0.93},
                               "images": [{"file": _T + "great-white.png", "x": 0.47, "y": 0.66, "w": 0.98}],
                               "spot": {"x": 0.55, "y": 0.66, "r": 0.5, "strength": 0.06}},
    "great-white-hunters": {"headline": "THE|GREAT WHITE|HUNTERS", "accent": "GREAT WHITE", "text": {"at": "right", "width": 0.50, "x": 0.965},
                            "photo": {"file": _T + "orcas-two-photo.jpg", "side": "left", "width": 0.72},
                            "tag": "South Africa", "dust": False},
    "great-white-killers": {"headline": "GREAT WHITE|KILLERS", "accent": "KILLERS", "text": {"at": "left", "width": 0.44, "font": "condensed"},
                            "images": [{"file": _T + "great-white.png", "x": 0.43, "y": 0.53, "w": 1.3, "fade": [0.34, 0.60]}],
                            "spot": {"x": 0.75, "y": 0.5, "r": 0.45, "strength": 0.06}},
}
THUMBNAIL = {
    "text": "ONLY ATE THE LIVER",
    "use": "only-ate-the-liver-red",
    "designs": {f"{name}-{scheme}": {"look": "noir", "scheme": scheme, **layout,
                                     **({"stroke": True} if scheme == "brand" and name in ("shark-killers", "great-white-killers") else {})}
                for name, layout in _LAYOUTS.items() for scheme in ("red", "brand")},
    "credits": [
        "Two orcas breaching: Robert Pitman, NOAA (public domain) — https://commons.wikimedia.org/wiki/File:Killerwhales_jumping.jpg",
        "Great white shark: © brendanboyd, CC BY 4.0, cut out and shown in black and white — https://www.inaturalist.org/photos/451580189",
    ],
}

# ------------------------------------------------------------------------------------------ write
SAMPLE = int(os.environ.get("ORCA_SAMPLE", "0"))        # only the first N scenes (a sample of the look and the voice)
OUT = Path(os.environ.get("ORCA_OUT", HERE))
doc = {
    "preset": "ocean",
    "title": script.title,
    "description": ("In May 2017 a great white shark almost five metres long washed up on a South African beach with its liver "
                    "missing. This is the story of Port and Starboard, the two orcas that learned to hunt great whites, the bay "
                    "they emptied, and the argument among scientists over how much of the blame is theirs.\n\n"
                    "The animals and events in this video are shown as 3D reconstructions, except where real photos or footage are credited below."),
    "tags": ["orca", "great white shark", "Port and Starboard", "Gansbaai", "False Bay", "Mossel Bay", "South Africa",
             "killer whale", "shark liver", "ocean documentary", "wildlife documentary", "animals"],
    "sources": script.sources,
    "thumbnail": THUMBNAIL,
    "youtube": {"privacy": "private", "category_id": 15, "synthetic_media": True},
    # The voice tells each passage in one go (voice.delivery: told): a natural rise and fall inside sentences, the same
    # register, pace and loudness throughout. padding: the breath between two passages.
    "settings": {"padding": 0.55, "voice": {"delivery": "told"}},
    "scenes": scenes[:SAMPLE] if SAMPLE else scenes,
}
head = ('# The Two Orcas That Emptied a Great White Shark Coast.\n'
        '# Written by direct.py from script.txt (the narration is the script, word for word). Change the shots in\n'
        '# direct.py and run it again; this file is what gets rendered.\n')
OUT.mkdir(parents=True, exist_ok=True)
(OUT / "script.yaml").write_text(head + yaml.safe_dump(doc, sort_keys=False, allow_unicode=True, width=130), encoding="utf-8")
print(f"{len(doc['scenes'])} scenes, {sum(len(s['text'].split()) for s in doc['scenes'])} words → {OUT / 'script.yaml'}")

"""Director's notes for "The Two Orcas That Emptied a Great White Shark Coast" → script.yaml.

Every picture in this video is a live 3D shot built for the sentence it sits under (the `Shot3D` template): a real
place (a beach, the open sea, a kelp reef, the sea from the air, a dark studio for looking inside an animal), animals
that swim through it, a camera that moves, and graphics pinned to the picture that arrive on the narrator's words.
Only the animals of this story are in it: great whites, the two orcas, sevengill and bronze whaler sharks.

The narration is taken from script.txt word for word. P(n, shots) gives the next n sentences, read as one passage,
their shots; a later shot in the list starts on its `cut` word.

    python projects/two-orcas-great-white-coast/direct3d.py        # rewrites script.yaml beside it
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
def shot(env, cast, camera, gfx=None, cut=None, **kw):
    v = {"remotion": "Shot3D", "props": {"env": env, "cast": cast, "camera": camera, "gfx": gfx or [], **kw}}
    if cut is not None:
        v["cut"] = cut
    return v


def animal(model, ident, length, path=None, **kw):
    a = {"id": ident, "model": model, "length": length, **kw}
    if path:
        a["path"] = [{"u": u, "p": p} for u, p in path]
    return a


def gw(ident, length=4.4, path=None, **kw):
    return animal("greatWhite", ident, length, path, **kw)


def port(path=None, **kw):
    return animal("orcaPort", "port", 8.4, path, **kw)


def star(path=None, **kw):
    return animal("orcaStarboard", "star", 8.1, path, **kw)


def carcass(ident, x, z, length, heading, side=1, **kw):
    """A shark washed ashore, lying on its belly and leaning a little to one side (the sea is toward -z)."""
    return gw(ident, length, pos=[x, 0.083 * length, z], heading=heading, roll=-17 * side, pose="limp", wound="chest", **kw)


def cam(*keys):
    """Camera keys: (u, position, look-at[, extra])."""
    out = []
    for k in keys:
        d = {"u": k[0], "pos": k[1], "look": k[2]}
        if len(k) > 3:
            d.update(k[3])
        out.append(d)
    return out


def at(actor, point=None):
    return {"actor": actor, **({"point": point} if point else {})}


def tag(when, anchor, text, sub=None, dir="ne", **kw):
    return {"type": "tag", "at": when, "anchor": anchor, "text": text, **({"sub": sub} if sub else {}), "dir": dir, **kw}


def line(when, text, hi=None, **kw):
    return {"type": "line", "at": when, "text": text, **({"hi": hi} if hi else {}), **kw}


def stamp(when, text, sub=None, **kw):
    return {"type": "stamp", "at": when, "text": text, **({"sub": sub} if sub else {}), **kw}


SEA = {"kind": "sea", "depth": 0.3}
DEEP = {"kind": "sea", "depth": 0.6}
STUDIO = {"kind": "studio"}

# ====================================================================================== 1. HOOK
P(4, [
    # the big female on the sand: the camera comes in low over the wet beach and rises to take her in
    shot({"kind": "beach", "sky": "dawn", "sun": [-0.55, 0.42, 0.72]},
         [carcass("her", 0, 2.6, 4.9, 8)],
         # along the body from the tail, close to the sand, then back and up to take all of her in
         cam((0, [-5.6, 0.45, 4.6], [-1.6, 0.42, 2.6], {"fov": 34}), (0.42, [0.9, 0.62, 5.7], [1.0, 0.4, 2.6], {"fov": 34}),
             (1, [-0.8, 2.0, 10.6], [0.1, 0.25, 2.6], {"fov": 34})),
         [stamp("May", "May 2017", "Franskraal beach · South Africa"),
          # the measuring line lies on the sand in front of her, from under the tail to under the nose
          {"type": "measure", "at": "almost", "from": {"world": [-2.43, 0.03, 4.05]}, "to": {"world": [2.43, 0.03, 3.4]}, "value": 4.9, "unit": " m", "label": "nose to tail", "off": 0}]),
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
    "youtube": {"privacy": "private", "category_id": 15, "synthetic_media": True},
    # The voice tells each passage in one go (voice.delivery: told): a natural rise and fall inside sentences, the same
    # register, pace and loudness throughout. padding: the breath between two passages.
    "settings": {"padding": 0.55, "voice": {"delivery": "told"}},
    "scenes": scenes[:SAMPLE] if SAMPLE else scenes,
}
head = ('# The Two Orcas That Emptied a Great White Shark Coast.\n'
        '# Written by direct3d.py from script.txt (the narration is the script, word for word). Change the shots in\n'
        '# direct3d.py and run it again; this file is what gets rendered.\n')
OUT.mkdir(parents=True, exist_ok=True)
(OUT / "script.yaml").write_text(head + yaml.safe_dump(doc, sort_keys=False, allow_unicode=True, width=130), encoding="utf-8")
print(f"{len(doc['scenes'])} scenes, {sum(len(s['text'].split()) for s in doc['scenes'])} words → {OUT / 'script.yaml'}")

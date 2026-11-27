"""3D creature sprites: Blender renders each creature once as a looping, transparent image sequence
(blender/creatures3d.py); videos then composite these with all the usual motion and camera work.

  python -m ytauto sprites                 # render every missing set
  python -m ytauto sprites --force leopardSeal:side
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path

from .utils import REPO_ROOT, YtautoError, log, run, which

SPRITE_DIR = REPO_ROOT / "remotion" / "public" / "sprites"
# creature → {view: frames}; frames == 1 means a still pose
SETS: dict[str, dict[str, int]] = {
    "leopardSeal": {"side": 48, "three_quarter": 48, "rest": 1},
    "seaLion": {"side": 48, "rest": 1},
    "seaLionPup": {"side": 48, "rest": 1},
    "leopardSealHead": {"jaw": 36},          # close-up: the jaw opens to show canines + tricuspid cheek teeth
    # sharks and whales modelled from measurements (blender/sealife.py)
    "greatWhite": {"side": 48, "top": 48, "beached": 1, "three_quarter": 48, "upside": 1},
    "orcaPort": {"side": 48, "top": 48, "three_quarter": 48},          # collapsed fin lying to his LEFT
    "orcaStarboard": {"side": 48, "top": 48, "three_quarter": 48},     # collapsed fin lying to his RIGHT
    "greatWhiteLiver": {"side": 48},         # see-through body with the liver lit inside
    "sevengill": {"side": 48, "beached": 1, "top": 48},
    "orca": {"side": 48, "top": 48},         # the usual curved dorsal fin (females, young males)
    "bronzeWhaler": {"side": 48},
    "orcaMale": {"side": 48},                # adult male: tall straight dorsal fin
    "fishBladder": {"side": 48},             # a see-through bony fish with its swim bladder lit inside
}
SIZE = "1280x640"
SIZES = {"leopardSealHead": "1280x720"}
SAMPLES = {c: 16 for c in ("greatWhite", "greatWhiteLiver", "orca", "orcaMale", "orcaPort", "orcaStarboard", "sevengill", "bronzeWhaler", "fishBladder")}
ONCE = {"leopardSealHead"}                   # plays once and holds the last frame (not a loop)


def sprite_ready(creature: str, view: str) -> bool:
    d = SPRITE_DIR / creature / view
    n = SETS.get(creature, {}).get(view)
    return bool(n) and d.is_dir() and len(list(d.glob("*.webp"))) >= n


def keep_set(creature: str, view: str, cache: Path) -> None:
    """Parallel rendering: a set this machine had to render travels in the project's cache, so the other machines
    use the very same pictures instead of rendering them again."""
    kept = cache / "sprites" / creature / view
    if sprite_ready(creature, view) and not kept.is_dir():
        kept.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(SPRITE_DIR / creature / view, kept)


def restore_set(creature: str, view: str, cache: Path) -> None:
    kept = cache / "sprites" / creature / view
    if kept.is_dir() and not sprite_ready(creature, view):
        shutil.rmtree(SPRITE_DIR / creature / view, ignore_errors=True)
        (SPRITE_DIR / creature).mkdir(parents=True, exist_ok=True)
        shutil.copytree(kept, SPRITE_DIR / creature / view)


def render_set(creature: str, view: str, frames: int, force: bool = False) -> Path:
    out = SPRITE_DIR / creature / view
    if sprite_ready(creature, view) and not force:
        return out
    blender = os.environ.get("YTAUTO_BLENDER") or which("blender")
    if not blender:
        raise YtautoError("Blender is needed to render 3D creature sprites")
    tmp = out.with_name(view + ".tmp")
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    log(f"Rendering 3D sprite {creature}/{view} ({frames} frame{'s' if frames > 1 else ''}) with Blender …")
    cmd = [blender, "-b", "--factory-startup", "-P", REPO_ROOT / "blender" / "creatures3d.py", "--",
           "--creature", creature, "--view", view, "--out", tmp, "--frames", str(max(frames, 1)), "--size", SIZES.get(creature, SIZE)]
    if creature in SAMPLES:
        cmd += ["--samples", str(SAMPLES[creature])]
    if frames <= 1:
        cmd.append("--still")
    run(cmd)
    pngs = sorted(tmp.glob("*.png"))
    if not pngs:
        raise YtautoError(f"Blender produced no frames for {creature}/{view}")
    # the finished set is built beside its place and moved in whole, so a half-written set is never seen (or committed)
    final, out = out, out.with_name(view + ".new.tmp")
    shutil.rmtree(out, ignore_errors=True)
    out.mkdir(parents=True)
    for i, p in enumerate(pngs, 1):  # WebP with alpha: ~10x smaller than PNG, crisp at 1080p
        run(["ffmpeg", "-y", "-v", "error", "-i", p, "-c:v", "libwebp", "-lossless", "0", "-q:v", "88",
             "-compression_level", "6", out / f"{i:04d}.webp"])
    # exact visible bounds of the creature in the frame → lets videos size and ground it precisely
    import json

    from PIL import Image
    boxes = []
    for p in {pngs[0], pngs[len(pngs) // 2], pngs[-1]}:   # union over the motion (a jaw opening changes the bounds)
        im = Image.open(p)
        boxes.append(im.getchannel("A").point(lambda v: 255 if v > 24 else 0).getbbox() or (0, 0, im.width, im.height))
    bbox = (min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes))
    (out / "meta.json").write_text(json.dumps({"frames": len(pngs), "w": im.width, "h": im.height, "bbox": bbox, "fps": 24,
                                               "loop": creature not in ONCE}))
    shutil.rmtree(tmp, ignore_errors=True)
    shutil.rmtree(final, ignore_errors=True)
    out.rename(final)
    return final


def manifest() -> dict:
    """{creature: {view: meta}} for every rendered set (passed to the Remotion templates)."""
    import json

    out: dict = {}
    for creature, views in SETS.items():
        for view in views:
            m = SPRITE_DIR / creature / view / "meta.json"
            if m.exists() and sprite_ready(creature, view):
                out.setdefault(creature, {})[view] = json.loads(m.read_text())
    return out


def ensure_all(force: list[str] | None = None) -> None:
    force = force or []
    for creature, views in SETS.items():
        for view, frames in views.items():
            render_set(creature, view, frames, force=f"{creature}:{view}" in force or creature in force)


def used_sprites(project) -> set[tuple[str, str]]:
    """Which sprite sets a project needs (OceanScene actors with render3d on)."""
    need: set[tuple[str, str]] = set()
    def walk(vs):
        for v in vs:
            yield v
            if isinstance(v, dict) and isinstance(v.get("fallback_visual"), dict):
                yield from walk([v["fallback_visual"]])

    for sc in project.scenes:
        for v in walk(sc.visuals):
            if isinstance(v, dict) and v.get("remotion") == "Anatomy":
                sp = (v.get("props") or {}).get("sprite") or {}
                if sp.get("creature") in SETS and sp.get("view") in SETS[sp["creature"]]:
                    need.add((sp["creature"], sp["view"]))
            if isinstance(v, dict) and v.get("remotion") == "OceanScene":
                for a in (v.get("props") or {}).get("actors", []) or []:
                    c = a.get("creature")
                    det = a.get("detail") or {}
                    key = "seaLionPup" if c in ("seaLion", "furSeal") and det.get("pup") else ("seaLion" if c == "furSeal" else c)
                    if c == "leopardSeal" and a.get("view") == "jaw":
                        key = "leopardSealHead"
                    if key in SETS:
                        view = "rest" if det.get("rest") else a.get("view", "side")
                        if view in SETS[key]:
                            need.add((key, view))
    return need

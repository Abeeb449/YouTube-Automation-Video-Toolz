"""Live 3D shots (the `Shot3D` template, remotion/src/stage): real 3D places, animals that swim by bending their own
bodies, a camera that moves, and graphics pinned to the picture.

A shot names its animals in `cast` (`model: greatWhite`). Each is a 3D file in remotion/public/models/, exported from
the hand-built Blender models (blender/export_glb.py) with its painted skin:

    python -m ytauto models3d                 # export every missing animal
    python -m ytauto models3d --force orca    # export again after changing the model

A shot only ever loads the animals it names, so nothing from another video can appear in it.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from .utils import REPO_ROOT, YtautoError, file_fingerprint, log, run, stable_hash, which

MODEL_DIR = REPO_ROOT / "remotion" / "public" / "models"
# the animals that can be exported (blender/sealife.py)
MODELS = ("greatWhite", "orca", "orcaMale", "orcaPort", "orcaStarboard", "sevengill", "bronzeWhaler", "fishBladder",
          # the same animals with fewer triangles, for shots with many of them at once
          "greatWhiteLo", "sevengillLo", "bronzeWhalerLo")


def model_files(name: str) -> tuple[Path, Path]:
    return MODEL_DIR / f"{name}.glb", MODEL_DIR / f"{name}.json"


def export_model(name: str, force: bool = False) -> Path:
    glb, meta = model_files(name)
    if glb.exists() and meta.exists() and not force:
        return glb
    if name not in MODELS:
        raise YtautoError(f"no 3D model called {name!r} (there are: {', '.join(MODELS)})")
    blender = os.environ.get("YTAUTO_BLENDER") or which("blender")
    if not blender:
        raise YtautoError(f"Blender is needed to export the 3D model {name!r}")
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    tmp = MODEL_DIR / f"{name}.new.glb"
    log(f"Exporting the 3D model {name} with Blender …")
    lo = name.endswith("Lo")
    run([blender, "-b", "--factory-startup", "-P", REPO_ROOT / "blender" / "export_glb.py", "--", "--creature", name[:-2] if lo else name,
         "--out", tmp, "--levels", "1" if lo else "2", "--tex", "1024" if lo else "2048"])
    if not tmp.exists() or not tmp.with_suffix(".json").exists():
        raise YtautoError(f"Blender did not export {name}")
    tmp.with_suffix(".json").replace(meta)       # put in place whole, so a half-written model is never used
    tmp.replace(glb)
    return glb


def export_all(force: list[str] | None = None) -> None:
    for name in MODELS:
        export_model(name, force=name in (force or []) or "all" in (force or []))


def cast_models(props: dict) -> list[str]:
    return sorted({str(a["model"]) for a in (props.get("cast") or []) if isinstance(a, dict) and a.get("model")})


def with_models(props: dict) -> dict:
    """The shot's props with the 3D files of the animals it names (and where their named points are)."""
    models = {}
    for name in cast_models(props):
        glb, meta = model_files(name)
        if not (glb.exists() and meta.exists()):
            export_model(name)
        models[name] = {"glb": f"models/{glb.name}", "meta": json.loads(meta.read_text())}
    return {**props, "models": models}


def stamp(spec: dict) -> str:
    """The 3D files a shot uses, by what is in them: a model that is exported again gives the shot a new name, so a
    clip drawn with the earlier model is never taken from the cache."""
    names = cast_models(spec.get("props") or {})
    return stable_hash([(n, file_fingerprint(model_files(n)[0])) for n in names if model_files(n)[0].exists()]) if names else ""

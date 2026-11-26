"""3D models for any topic: find a free-licence model of what the video is about, turn it into a lit, turning
3D shot, and let scenes move the camera around it.

  visual:  {model: "Apollo 11 command module", props: {title: …, callouts: […], shot: push}}
           {model: assets/my-model.glb}                       your own file (glb, gltf, stl, obj, ply, fbx)

Where the models come from (first that has one; only licences that allow commercial use):
  handmade      models built by hand for this channel in blender/handmade/ (made when no free model exists)
  smithsonian   Smithsonian Open Access 3D (CC0): spacecraft, aircraft, fossils, skulls, historic objects
  polyhaven     Poly Haven (CC0): everyday objects, tools, furniture, plants, rocks
  sketchfab     Sketchfab (CC0 / CC BY, the largest library) — only with a free account token in SKETCHFAB_TOKEN
  commons       Wikimedia Commons 3D files (CC0 / public domain / CC BY): scans and simple models, no colours

A model is accepted when its own title names the subject (every word of the search) and the test render shows
something solid. Blender renders it once as a seamless turning image set (blender/model3d.py), cached in
remotion/public/sprites/model-<id>/; the `Anatomy` template then shows it with pushes, callouts and titles.
The credit goes into the description like any stock item. If no model is found the scene's fallback is used.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import urllib.parse
from pathlib import Path

from . import stock
from .utils import REPO_ROOT, YtautoError, log, run, stable_hash, which

MODEL_EXT = (".glb", ".gltf", ".stl", ".obj", ".ply", ".fbx")
FRAMES, FPS, SIZE = 96, 12, "1280x720"       # an 8-second there-and-back swing; frames are blended on screen
MAX_MODEL_MB = 150.0
_STOP = {"a", "an", "the", "of", "in", "on", "at", "and", "or", "with", "to", "from", "3d", "model"}

stock.PROVIDER_NAMES.update({
    "smithsonian": "Smithsonian Open Access 3D (3d.si.edu, CC0)", "polyhaven": "Poly Haven (polyhaven.com, CC0)",
    "sketchfab": "Sketchfab (sketchfab.com)",
})


def _words(text: str) -> list[str]:
    return [re.sub(r"(?<!s)s$", "", w) for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in _STOP and len(w) > 1]


def _names(query: str, title: str) -> bool:
    """Every word of the search is in the model's own title/tags (plural or singular)."""
    t = set(_words(title))
    q = _words(query)
    return bool(q) and all(w in t for w in q)


# ------------------------------------------------------------------------------------------------ providers
def _smithsonian(query: str) -> list[dict]:
    if not stock._license_ok("cc0"):
        return []
    rows = []
    for start in range(0, 60, 10):      # the search gives 10 files a page; an object's whole-model file can be pages in
        q = urllib.parse.urlencode({"q": query, "file_type": "glb", "start": start})
        page = stock._retry_json(f"https://3d-api.si.edu/api/v1.0/content/file/search?{q}", tries=2).get("rows", [])
        rows += page
        if len(page) < 10:
            break
    packs: dict[str, list] = {}
    for r in rows:
        c = r.get("content") or {}
        if c.get("uri") and _names(query, r.get("title", "")):
            packs.setdefault(c.get("model_url") or c["uri"], []).append((r["title"], c))
    out = []
    order = {"Medium": 0, "Low": 1, "High": 2, "AR": 3, "Thumb": 5}
    for pid, files in packs.items():
        # the whole object seen from outside, rather than one part of it, at a sensible size
        def rank(tc):
            name = tc[1]["uri"].rsplit("/", 1)[-1].lower()
            inside = bool(re.search(r"interior|inside|seat|hatch|panel|graffiti|detail|fragment", name))
            piece = bool(re.search(r"shell|filler|[-_]top|[-_]bottom|[-_]part|section|engine|wheel|propeller|wing[-_]", name))
            whole = bool(re.search(r"exterior|full|complete|whole", name))
            kind = (0 if whole and not inside and not piece else 1 if not inside and not piece and "combined" not in name
                    else 2 if "combined" in name or "multi" in name else 3 if not inside else 4)
            flat = re.sub(r"[^a-z0-9]", "", name)
            named = any(w in flat for w in _words(query) if len(w) > 3)     # the file is named after the object itself
            return (kind, not named, order.get(tc[1].get("quality"), 4), name)
        best = sorted(files, key=rank)[0]
        title, c = best
        best_rank = rank(best)
        uid = pid.split(":")[-1]
        out.append((best_rank, {"cid": f"smithsonian-{uid[:13]}-{stable_hash(c['uri'])[:6]}", "provider": "smithsonian",
                                "title": title, "url": c["uri"], "ext": ".glb", "author": "Smithsonian Institution",
                                "code": "cc0", "license": "CC0 (Smithsonian Open Access)", "page": c["uri"]}))
    return [c for _r, c in sorted(out, key=lambda rc: rc[0])]


def _polyhaven(query: str) -> list[dict]:
    if not stock._license_ok("cc0"):
        return []
    assets = stock._retry_json("https://api.polyhaven.com/assets?t=models", tries=2)
    out = []
    for aid, a in assets.items():
        text = f"{a.get('name', '')} {' '.join(a.get('tags') or [])} {' '.join(a.get('categories') or [])}"
        if _names(query, text):
            exact = _names(query, a.get("name", ""))
            out.append((not exact, -int(a.get("download_count") or 0), aid, a))
    res = []
    for _e, _d, aid, a in sorted(out)[:6]:
        res.append({"cid": f"polyhaven-{aid}", "provider": "polyhaven", "title": a.get("name", aid), "polyhaven": aid,
                    "ext": ".gltf", "author": ", ".join((a.get("authors") or {}).keys()) or "Poly Haven", "code": "cc0",
                    "license": "CC0", "page": f"https://polyhaven.com/a/{aid}"})
    return res


def _commons(query: str) -> list[dict]:
    q = urllib.parse.urlencode({
        "action": "query", "format": "json", "generator": "search", "gsrnamespace": 6, "gsrlimit": 15,
        "gsrsearch": f"{query} filetype:3d", "prop": "imageinfo", "iiprop": "url|extmetadata|size",
        "iiextmetadatafilter": "LicenseShortName|LicenseUrl|Artist|ObjectName"})
    data = stock._retry_json(f"https://commons.wikimedia.org/w/api.php?{q}", tries=2)
    out = []
    for pg in (data.get("query") or {}).get("pages", {}).values():
        info = (pg.get("imageinfo") or [{}])[0]
        url = info.get("url") or ""
        if not url.lower().endswith(".stl") or (info.get("size") or 0) > MAX_MODEL_MB * 1e6:
            continue
        meta = info.get("extmetadata") or {}
        lic = (meta.get("LicenseShortName") or {}).get("value", "")
        code = stock.license_code(lic)
        title = pg.get("title", "").removeprefix("File:").rsplit(".", 1)[0]
        if not stock._license_ok(code) or not _names(query, title):
            continue
        out.append({"cid": f"commons-{pg['pageid']}", "provider": "commons", "title": title, "url": url, "ext": ".stl",
                    "author": (meta.get("Artist") or {}).get("value", "unknown"), "code": code, "license": lic,
                    "page": "https://commons.wikimedia.org/wiki/" + urllib.parse.quote(pg["title"].replace(" ", "_"))})
    return out


def _sketchfab_license(label: str) -> str | None:
    """Sketchfab's licence labels → cc0 | by | by-sa | None. Only the Creative Commons ones that allow commercial
    use and changes can pass; "NonCommercial", "NoDerivs", "Editorial", "Standard" and anything unknown cannot."""
    t = label.strip().lower()
    if not t.startswith("cc"):
        return None
    if "noncommercial" in t or "noderiv" in t:
        return None
    if t.startswith("cc0"):
        return "cc0"
    if "sharealike" in t:
        return "by-sa"
    return "by" if t in ("cc attribution", "cc-by", "cc by") else None


def _sketchfab(query: str) -> list[dict]:
    """Needs a free Sketchfab account token (SKETCHFAB_TOKEN): downloads are only given to signed-in users."""
    token = os.environ.get("SKETCHFAB_TOKEN", "").strip()
    if not token:
        return []
    q = urllib.parse.urlencode({"type": "models", "q": query, "downloadable": "true", "count": 24, "sort_by": "-likeCount"})
    data = stock._retry_json(f"https://api.sketchfab.com/v3/search?{q}", tries=2)
    out = []
    for r in data.get("results", []):
        lic = r.get("license") or {}
        label = lic.get("label") or lic.get("slug") or ""
        code = _sketchfab_license(label)
        if not stock._license_ok(code) or not _names(query, r.get("name", "")):
            continue
        out.append({"cid": f"sketchfab-{r['uid']}", "provider": "sketchfab", "title": r.get("name", ""), "sketchfab": r["uid"],
                    "ext": ".glb", "author": (r.get("user") or {}).get("displayName") or (r.get("user") or {}).get("username", "unknown"),
                    "code": code, "license": label or code, "page": r.get("viewerUrl") or f"https://sketchfab.com/3d-models/{r['uid']}"})
    return out[:6]


HANDMADE_DIR = REPO_ROOT / "blender" / "handmade"


def handmade_index() -> list[dict]:
    """The hand-built models in blender/handmade/: {slug, path, names, title} (read without starting Blender)."""
    import ast
    out = []
    for f in sorted(HANDMADE_DIR.glob("*.py")):
        names, title = [], f.stem.replace("_", " ").title()
        try:
            for node in ast.parse(f.read_text(encoding="utf-8")).body:
                if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                    if node.targets[0].id == "NAMES":
                        names = [str(x).lower() for x in ast.literal_eval(node.value)]
                    elif node.targets[0].id == "TITLE":
                        title = str(ast.literal_eval(node.value))
        except Exception:  # noqa: BLE001
            continue
        if names:
            out.append({"slug": f.stem, "path": f, "names": names, "title": title})
    return out


def _handmade(query: str) -> list[dict]:
    """A model built by hand for this subject (when no free model existed): matched by its listed names."""
    q = set(_words(query))
    out = []
    for m in handmade_index():
        for name in m["names"]:
            n = set(_words(name))
            if n and (n <= q or q <= n):          # the search names this model, or is one of its names in short
                out.append({"cid": f"handmade-{m['slug']}", "provider": "handmade", "title": m["title"], "build": m["path"],
                            "ext": ".py", "author": "built for this channel", "code": "own", "license": "own work",
                            "page": ""})
                break
    return out


PROVIDERS = {"handmade": _handmade, "smithsonian": _smithsonian, "polyhaven": _polyhaven, "sketchfab": _sketchfab,
             "commons": _commons}


def provider_order() -> list[str]:
    raw = os.environ.get("YTAUTO_MODEL_SOURCES") or "handmade,smithsonian,polyhaven,sketchfab,commons"
    return [p.strip() for p in raw.split(",") if p.strip() in PROVIDERS]


# ------------------------------------------------------------------------------------------------ download
def _download(c: dict, cache: Path) -> Path:
    if c.get("build"):
        return Path(c["build"])
    d = cache / "models" / c["cid"]
    d.mkdir(parents=True, exist_ok=True)
    if c.get("polyhaven"):
        main = d / "model.gltf"
        if main.exists():
            return main
        files = stock._retry_json(f"https://api.polyhaven.com/files/{c['polyhaven']}", tries=2)
        g = (files.get("gltf") or {})
        res = g.get("2k") or g.get("1k") or (list(g.values())[0] if g else None)
        if not res or "gltf" not in res:
            raise YtautoError("no glTF file for this Poly Haven model")
        entry = res["gltf"]
        for rel, inc in (entry.get("include") or {}).items():
            dst = d / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            stock.download(inc["url"], dst, max_mb=MAX_MODEL_MB)
        stock.download(entry["url"], main, max_mb=MAX_MODEL_MB)
        return main
    if c.get("sketchfab"):
        main = d / "model.glb"
        if main.exists():
            return main
        info = stock._get_json(f"https://api.sketchfab.com/v3/models/{c['sketchfab']}/download",
                               headers={"Authorization": f"Token {os.environ.get('SKETCHFAB_TOKEN', '').strip()}"})
        if (info.get("glb") or {}).get("url"):
            return stock.download(info["glb"]["url"], main, max_mb=MAX_MODEL_MB)
        if (info.get("gltf") or {}).get("url"):
            import zipfile
            z = stock.download(info["gltf"]["url"], d / "model.zip", max_mb=MAX_MODEL_MB)
            with zipfile.ZipFile(z) as zf:
                for name in zf.namelist():      # no paths that climb out of the folder
                    if not name.startswith(("/", "..")) and ".." not in Path(name).parts:
                        zf.extract(name, d)
            z.unlink(missing_ok=True)
            got = sorted(d.rglob("*.gltf"))
            if got:
                return got[0]
        raise YtautoError("Sketchfab gave no downloadable glTF for this model")
    return stock.download(c["url"], d / f"model{c['ext']}", max_mb=MAX_MODEL_MB)


# ------------------------------------------------------------------------------------------------ sprite set
def sprite_dir(key: str) -> Path:
    return REPO_ROOT / "remotion" / "public" / "sprites" / key / "orbit"


def _restore(key: str, cache: Path | None) -> None:
    """A set rendered in an earlier run lives in the project's cache (which CI keeps between runs): put it back."""
    if cache is None:
        return
    kept, pub = cache / "models" / "sprites" / key / "orbit", sprite_dir(key)
    if (kept / "meta.json").exists() and not (pub / "meta.json").exists():
        shutil.rmtree(pub, ignore_errors=True)
        shutil.copytree(kept, pub)


def _keep(key: str, cache: Path | None) -> None:
    if cache is None:
        return
    kept = cache / "models" / "sprites" / key / "orbit"
    if not (kept / "meta.json").exists():
        shutil.rmtree(kept, ignore_errors=True)
        shutil.copytree(sprite_dir(key), kept)


def sprite_meta(key: str, cache: Path | None = None) -> dict | None:
    _restore(key, cache)
    m = sprite_dir(key) / "meta.json"
    try:
        meta = json.loads(m.read_text())
        return meta if len(list(m.parent.glob("*.webp"))) >= meta["frames"] else None
    except Exception:  # noqa: BLE001
        return None


def render_model(model: Path, key: str, tint: str | None = None, front: float = 0.0, cache: Path | None = None) -> dict:
    """Blender → a seamless turning sprite set for this model (once; cached). Returns its meta."""
    meta = sprite_meta(key, cache)
    if meta:
        return meta
    blender = os.environ.get("YTAUTO_BLENDER") or which("blender")
    if not blender:
        raise YtautoError("Blender is needed to render 3D models")
    out = sprite_dir(key)
    tmp = out.with_name("orbit.tmp")
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    log(f"Rendering 3D model {model.name} ({FRAMES} frames) with Blender …")
    cmd = [blender, "-b", "--factory-startup", "-P", REPO_ROOT / "blender" / "model3d.py", "--",
           "--build" if model.suffix == ".py" else "--model", model,
           "--out", tmp, "--frames", str(FRAMES), "--size", SIZE, "--front", str(front)]
    if tint:
        cmd += ["--tint", tint]
    try:
        text = run(cmd)     # Blender exits 0 even when its script fails, so read what it printed
        if not list(tmp.glob("*.png")) and "draco" in text.lower() and model.suffix.lower() in (".glb", ".gltf"):
            # this Blender build has no Draco library (distribution packages often don't): decode the model first
            plain = model.with_name(model.stem + ".plain.glb")
            rdir = REPO_ROOT / "remotion"
            if not (rdir / "node_modules").exists() and os.environ.get("YTAUTO_REMOTION_DIR"):
                rdir = Path(os.environ["YTAUTO_REMOTION_DIR"])
            run(["node", "scripts/undraco.mjs", model.resolve(), plain.resolve()], cwd=rdir)
            cmd[cmd.index("--model") + 1] = plain
            text = run(cmd)
    except YtautoError:
        shutil.rmtree(tmp, ignore_errors=True)
        raise
    pngs = sorted(tmp.glob("*.png"))
    if not pngs:
        shutil.rmtree(tmp, ignore_errors=True)
        last = [ln for ln in text.strip().splitlines() if ln.strip() and not ln.startswith(("Fra:", "Saved", " Time"))][-3:]
        raise YtautoError(f"Blender could not render {model.name}: {' / '.join(last)[:200]}")
    from PIL import Image
    boxes, solid = [], 0.0
    for p in (pngs[0], pngs[len(pngs) // 4], pngs[len(pngs) // 2], pngs[3 * len(pngs) // 4]):
        im = Image.open(p)
        a = im.getchannel("A").point(lambda v: 255 if v > 24 else 0)
        boxes.append(a.getbbox() or (0, 0, im.width, im.height))
        solid = max(solid, sum(a.histogram()[255:]) / (im.width * im.height))
    if solid < 0.02:    # nothing really there: an empty or paper-thin model
        shutil.rmtree(tmp, ignore_errors=True)
        raise YtautoError("the model rendered empty (nothing solid to show)")
    shutil.rmtree(out, ignore_errors=True)
    out.mkdir(parents=True)
    for i, p in enumerate(pngs, 1):
        run(["ffmpeg", "-y", "-v", "error", "-i", p, "-c:v", "libwebp", "-lossless", "0", "-q:v", "88",
             "-compression_level", "6", out / f"{i:04d}.webp"])
    bbox = (min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes))
    meta = {"frames": len(pngs), "w": im.width, "h": im.height, "bbox": bbox, "fps": FPS, "loop": True, "blend": True}
    (out / "meta.json").write_text(json.dumps(meta))
    shutil.rmtree(tmp, ignore_errors=True)
    _keep(key, cache)
    return meta


# ------------------------------------------------------------------------------------------------ find + shot
def _memo(cache: Path) -> Path:
    return cache / "models" / "resolved.json"


def find_model(query: str, cache: Path) -> dict:
    """A rendered 3D model for these search words (alternatives with |): {key, meta, cid, credit}. Remembered, so
    the collection step finds it once and the render reuses it."""
    key_q = stable_hash("model-v1", query, sorted(stock.allowed_licenses()), provider_order(), bool(os.environ.get("SKETCHFAB_TOKEN")),
                        [(m["slug"], m["path"].stat().st_mtime_ns) for m in handmade_index()])
    memo = {}
    try:
        memo = json.loads(_memo(cache).read_text())
    except Exception:  # noqa: BLE001
        pass
    hit = memo.get(key_q)
    if hit and sprite_meta(hit["key"], cache):
        _register(hit)
        stock._requests.append({"query": query, "kind": "model", "wanted": None, "ok": True, "reused": True,
                                "path": str(sprite_dir(hit["key"]) / "0001.webp"), "cid": hit["cid"], "credit": hit["credit"]})
        return {**hit, "meta": sprite_meta(hit["key"])}
    if key_q in stock._missing:
        raise YtautoError(stock._missing[key_q])
    errors = []
    for alt in [a.strip() for a in query.split("|") if a.strip()]:
        for prov in provider_order():
            try:
                cands = PROVIDERS[prov](alt)
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{prov}: {str(exc)[:80]}")
                continue
            if not cands:
                errors.append(f"{prov}: no model named '{alt}'")
                continue
            for c in cands[:3]:
                try:
                    path = _download(c, cache)
                    # a hand-built model is rendered again whenever its script (or the kit) changes
                    stamp = (path.read_text(encoding="utf-8"), (REPO_ROOT / "blender" / "kit3d.py").read_text(encoding="utf-8")) \
                        if c.get("build") else ()
                    key = "model-" + stable_hash(c["cid"], *stamp)[:12]
                    meta = render_model(path, key, cache=cache)
                except Exception as exc:  # noqa: BLE001
                    errors.append(f"{prov}: {c['cid']} {str(exc)[:90]}")
                    continue
                from . import verify
                ok, why = (True, "hand-built and checked by eye") if c.get("build") else \
                    verify.check_model(sprite_dir(key) / f"{max(1, meta['frames'] // 8):04d}.webp", alt, cache)
                if not ok:
                    log(f"   skipped 3D model {c['cid']} for '{alt}': {why}")
                    errors.append(f"{prov}: {c['cid']} rejected by the model check")
                    continue
                rec = {"key": key, "cid": c["cid"], "query": alt, "credit": {
                    "id": c["cid"], "provider": c["provider"], "title": c["title"][:120], "author": re.sub(r"<[^>]+>", "", c["author"])[:80],
                    "code": c["code"], "license": c["license"], "license_url": "", "url": c["page"]}}
                memo[key_q] = rec
                _memo(cache).parent.mkdir(parents=True, exist_ok=True)
                _memo(cache).write_text(json.dumps(memo, indent=1))
                _register(rec)
                stock._requests.append({"query": query, "kind": "model", "wanted": None, "ok": True,
                                        "path": str(sprite_dir(key) / "0001.webp"), "cid": c["cid"], "credit": rec["credit"]})
                return {**rec, "meta": meta}
    msg = f"No free 3D model found for '{query}': " + "; ".join(errors[:6])
    stock._missing[key_q] = msg
    stock._requests.append({"query": query, "kind": "model", "wanted": None, "ok": False, "reason": msg})
    raise YtautoError(msg)


def _register(rec: dict) -> None:
    if rec["credit"].get("code") == "own":      # the channel's own model: nothing to credit
        return
    with stock._lock:
        stock._credits.setdefault(rec["cid"], rec["credit"])
        stock._used.add(rec["cid"])
    ids = getattr(stock._tl, "ids", None)
    if ids is not None:
        ids.append(rec["cid"])


SHOTS = {
    "turn": [],
    "push": [{"at": 0.4, "x": 0.5, "y": 0.45, "scale": 1.28}],
    "left": [{"at": 0.4, "x": 0.3, "y": 0.45, "scale": 1.6}],
    "right": [{"at": 0.4, "x": 0.7, "y": 0.45, "scale": 1.6}],
    "top": [{"at": 0.4, "x": 0.5, "y": 0.25, "scale": 1.6}],
    "base": [{"at": 0.4, "x": 0.5, "y": 0.75, "scale": 1.6}],
}


def model_shot(spec: dict, project, seq: int = 0) -> dict:
    """{model: …, props} → the Remotion visual that shows it (the `Anatomy` template with this model's sprite set).
    `props.shot`: turn | push | left | right | top | base (camera move; default varies from shot to shot)."""
    src = str(spec["model"]).strip()
    props = dict(spec.get("props") or {})
    local = project.resolve(src) if Path(src).suffix.lower() in MODEL_EXT else None
    if local is not None:
        if not local.exists():
            raise YtautoError(f"3D model file not found: {local}")
        key = "model-" + stable_hash(str(local), local.stat().st_size)[:12]
        meta = render_model(local, key, props.pop("tint", None), float(props.pop("front", 0) or 0), project.cache_dir)
    else:
        got = find_model(src, project.cache_dir)
        key, meta = got["key"], got["meta"]
        # the maker of every library model is named on screen (also public-domain ones); the channel's own
        # hand-built models carry no credit
        if got["credit"]["code"] != "own" and not props.get("source"):
            lic = {"cc0": "CC0 (public domain)", "pdm": "public domain", "by": "CC BY", "by-sa": "CC BY-SA"}.get(
                got["credit"]["code"], got["credit"]["license"])
            props["source"] = f"3D model: {got['credit']['author']} · {lic}"
    shot = props.pop("shot", None) or list(SHOTS)[seq % 2]        # turn / push by default
    zoom = props.pop("zoom", None) or SHOTS.get(shot, [])
    return {"remotion": "Anatomy",
            "props": {"backdrop": "dark", **props, "sprite": {"creature": key, "view": "orbit"},
                      "sprites": {key: {"orbit": meta}}, "zoom": zoom}}


def check_views(source: str, out: Path) -> Path:
    """Render a model from the front, both sides, the back and above into one labelled sheet, to compare with
    reference photos before it is used. `source`: a hand-built model's name, or a model file."""
    blender = os.environ.get("YTAUTO_BLENDER") or which("blender")
    if not blender:
        raise YtautoError("Blender is needed to render 3D models")
    hm = _handmade(source)
    path = Path(hm[0]["build"]) if hm else Path(source)
    if not path.exists():
        raise YtautoError(f"No hand-built model is named '{source}' and no such file exists. Hand-built models: "
                          + ", ".join(m["title"] for m in handmade_index()))
    tmp = out.parent / (out.stem + ".views")
    shutil.rmtree(tmp, ignore_errors=True)
    text = run([blender, "-b", "--factory-startup", "-P", REPO_ROOT / "blender" / "model3d.py", "--",
                "--build" if path.suffix == ".py" else "--model", path, "--out", tmp, "--views", "--size", "1280x720"])
    pngs = sorted(tmp.glob("*.png"))
    if len(pngs) < 5:
        last = [ln for ln in text.strip().splitlines() if ln.strip()][-4:]
        raise YtautoError("Blender could not render the model: " + " / ".join(last)[:300])
    from PIL import Image, ImageDraw
    labels = ["FRONT", "its RIGHT side (camera moved a quarter turn)", "BACK", "its LEFT side", "FROM ABOVE"]
    sheet = Image.new("RGB", (3 * 640, 2 * 360), (14, 22, 34))
    d = ImageDraw.Draw(sheet)
    for i, (p, lab) in enumerate(zip(pngs, labels)):
        im = Image.open(p).convert("RGBA").resize((640, 360))
        x, y = (i % 3) * 640, (i // 3) * 360
        sheet.paste(im, (x, y), im)
        d.text((x + 8, y + 8), lab, fill="yellow")
    sheet.save(out, quality=90)
    shutil.rmtree(tmp, ignore_errors=True)
    return out


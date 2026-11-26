"""Collect the b-roll before anything is edited.

Reads every scene for the stock video/photos it asks for (the creator's own search words, from the script), then
for each one: search → check that the picture really shows it (ytauto/verify.py) → download. Only then does the
render start, with every file already on disk; the render never searches again.

Writes into build/:
  broll_report.txt   each request: what was asked, what was found (source, author, licence) or why nothing passed
  broll_sheet.jpg    one thumbnail per item found, labelled with its scene and search words (review before rendering)
  broll.json         the same as data
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from .config import Project
from .utils import log, warn


def _asks_stock(spec) -> bool:
    return bool(re.search(r'"stock"\s*:|"model"\s*:|"(?:stock|pexels|pixabay|pexels-photo|photo):', json.dumps(spec, default=str))
                or (isinstance(spec, str) and spec.split(":")[0] in ("stock", "pexels", "pixabay")))


def _first_request(spec) -> tuple[str, str, str | None]:
    """(kind asked, search words, must-show) of a visual's main stock request, for the report."""
    if isinstance(spec, str):
        return "video", spec.split(":", 1)[-1], None
    if isinstance(spec, dict):
        if "model" in spec:
            return "3D model", str(spec["model"]), None
        if "stock" in spec:
            fb = spec.get("fallback_visual")
            either = isinstance(fb, dict) and fb.get("remotion") == "PhotoStory"
            kind = "photo" if spec.get("type") in ("photo", "image") else ("video or photo" if either else "video")
            return kind, str(spec["stock"]), spec.get("verify")
        for ph in (spec.get("props") or {}).get("photos") or []:
            v = str(ph.get("photo", ""))
            if v.lower().startswith(("stock:", "photo:", "pexels-photo:")):
                fb = spec.get("fallback_visual")
                both = isinstance(fb, dict) and "stock" in fb
                return ("photo or video" if both else "photo"), v.split(":", 1)[1].strip(), ph.get("verify")
        foot = (spec.get("props") or {}).get("footage")
        if isinstance(foot, str) and foot.lower().startswith(("stock:", "pexels:")):
            return "video", foot.split(":", 1)[1].strip(), (spec.get("props") or {}).get("footage_verify")
    return "b-roll", "", None


def collect_broll(project: Project, refresh: bool = False) -> dict:
    """Run the collection for a whole project. Returns the report data (also written to build/)."""
    from . import stock, verify
    from .visuals import ClipRenderer
    st = project.settings
    stock.species_photos = bool(st.get("species_photos", True))
    if refresh:
        stock.forget_resolved(project.cache_dir)
    renderer = ClipRenderer(project)
    items: list[dict] = []
    todo = [(sc, vi, spec, k) for k, (sc, vi, spec) in enumerate(
        (sc, vi, spec) for sc in project.scenes for vi, spec in enumerate(sc.visuals))]
    asked = [t for t in todo if _asks_stock(t[2])]
    if not asked:
        log("   no 3D models or b-roll requested in this script: nothing to collect")
        return {"requested": 0, "found": 0, "items": []}
    log(f"   {len(asked)} scene shot(s) need outside material (3D models, b-roll): finding, checking and "
        "preparing it now")
    for sc, vi, spec, seq in asked:
        mark = len(stock._requests)
        try:
            renderer.collect(spec, seq)
        except Exception as exc:  # noqa: BLE001 — a failed request is reported, never fatal here
            warn(f"scene {sc.index + 1}: b-roll could not be collected ({str(exc)[:160]})")
        new = stock._requests[mark:]
        kind, search, must = _first_request(spec)
        got_any = [r for r in new if r.get("ok")]
        # what was asked for, not what its fallback turned up (b-roll that isn't found may fall back to the 3D model)
        got = [r for r in got_any if (r.get("kind") == "model") == (kind == "3D model")]
        opening = sum(1 for x in project.scenes[:sc.index + 1] if x.raw.get("_intro"))   # the opening is not a script scene
        item = {"scene": "Opening" if sc.raw.get("_intro") else sc.index + 1 - opening, "shot": vi + 1,
                "text": (sc.text or "(opening: music and picture, no narration)")[:90],
                "asked": kind, "search": search, "must_show": must, "found": bool(got),
                "files": [{"path": g["path"], "kind": g.get("kind"), "id": g.get("cid"),
                           **{k: (g.get("credit") or {}).get(k) for k in ("title", "author", "license", "url", "provider")}}
                          for g in got],
                "fallback": "the 3D model" if got_any and not got else None,
                "tried": [r.get("reason", "")[:400] for r in new if not r.get("ok")]}
        items.append(item)
        log(f"   {'opening' if item['scene'] == 'Opening' else 'scene ' + str(item['scene'])}: "
            f"{'found' if item['found'] else 'NOT FOUND'}  [{kind}] {search[:70]}")
    verify.shutdown()     # free the picture-check model before the voice models load
    # the sheet shows each file once, even when several scenes use it
    data = {"title": project.title, "requested": len(items), "found": sum(1 for i in items if i["found"]), "items": items}
    build = project.build_dir
    build.mkdir(parents=True, exist_ok=True)
    (build / "broll.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
    (build / "broll_report.txt").write_text(_report(data), encoding="utf-8")
    try:
        _sheet(data, build / "broll_sheet.jpg")
    except Exception as exc:  # noqa: BLE001
        warn(f"b-roll sheet not written ({exc})")
    log(f"   b-roll collected: {data['found']} of {data['requested']} found and checked → {build / 'broll_report.txt'}")
    return data


def _report(data: dict) -> str:
    out = [f"B-roll for \"{data['title']}\": {data['requested']} requested, {data['found']} found and checked, "
           f"{data['requested'] - data['found']} not found", ""]
    for it in data["items"]:
        label = "Opening" if it["scene"] == "Opening" else f"Scene {it['scene']}"
        out.append(f"{label} (shot {it['shot']}): {it['text']}")
        out.append(f"  asked for: {it['asked']} — {it['search']}"
                   + (f"\n  must show: {it['must_show']}" if it["must_show"] else ""))
        if it["found"]:
            for f in it["files"]:
                who = " by ".join(x for x in ((f'"{f["title"]}"' if f.get("title") else ""), f.get("author") or "") if x)
                out.append(f"  FOUND ({f.get('kind') or 'file'}): {who or f.get('id') or Path(f['path']).name}"
                           + (f", {f['license']}" if f.get("license") else "") + (f"\n         {f['url']}" if f.get("url") else ""))
        else:
            out.append("  NOT FOUND: nothing usable passed the checks, so this scene uses its fallback shot"
                       + (f" ({it['fallback']})." if it.get("fallback") else "."))
            for t in it["tried"][:2]:
                out.append(f"    tried: {t}")
        out.append("")
    return "\n".join(out)


def _sheet(data: dict, out: Path, cols: int = 4) -> None:
    from PIL import Image, ImageDraw
    cells, shown = [], set()
    for it in data["items"]:
        for f in it["files"]:
            p = Path(f["path"])
            if not p.exists() or str(p) in shown:
                continue
            shown.add(str(p))
            if f.get("kind") == "model":
                rgba = Image.open(p).convert("RGBA")
                im = Image.new("RGB", rgba.size, (14, 22, 34))
                im.paste(rgba, (0, 0), rgba)
                tag = "3D MODEL"
            elif p.suffix.lower() in (".mp4", ".mov", ".webm"):
                frame = out.parent / ".sheet_broll.jpg"
                subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", "1", "-i", str(p), "-frames:v", "1", str(frame)], check=False)
                if not frame.exists():
                    continue
                im = Image.open(frame).convert("RGB")
                frame.unlink(missing_ok=True)
                tag = "VIDEO"
            else:
                im = Image.open(p).convert("RGB")
                tag = "PHOTO"
            cells.append((im, ("Opening" if it["scene"] == "Opening" else f"Scene {it['scene']}") + f" · {tag}", it["search"][:52]))
    if not cells:
        return
    W, H, pad = 480, 270, 44
    rows = -(-len(cells) // cols)
    sheet = Image.new("RGB", (cols * W, rows * (H + pad)), "white")
    d = ImageDraw.Draw(sheet)
    for k, (im, head, sub) in enumerate(cells):
        im.thumbnail((W - 8, H - 8))
        x, y = (k % cols) * W, (k // cols) * (H + pad)
        sheet.paste(im, (x + (W - im.width) // 2, y + (H - im.height) // 2))
        d.text((x + 6, y + H + 4), head, fill="black")
        d.text((x + 6, y + H + 20), sub, fill=(70, 70, 70))
    sheet.save(out, quality=85)

"""Free B-roll for commercial use, photos and video.

Keyless (always on):
  openverse  CC0 / public-domain / CC BY / CC BY-SA photos (Flickr, Wikimedia, museums) — api.openverse.org
  commons    Wikimedia Commons photos and video clips (same licence filter)
  nasa       NASA Image and Video Library — public domain (Earth, ice, oceans, expeditions)
With a free key (optional, used first):
  pexels     PEXELS_API_KEY        pixabay   PIXABAY_API_KEY

Every non-public-domain item is credited in the video description (`credits()`), as CC BY / BY-SA require.
ND (no-derivatives) and NC (non-commercial) licences are never used.
"""
from __future__ import annotations

import json
import os
import re
import threading
import urllib.parse
import urllib.request
from pathlib import Path

from .utils import YtautoError, log, stable_hash

UA = {"User-Agent": "ytauto/1.0"}
_lock = threading.Lock()
_used: set[str] = set()  # avoid repeating the same stock clip inside one render
_credits: dict[str, str] = {}  # id -> attribution line
_path_ids: dict[str, str] = {}  # downloaded file -> id
OK_LICENSES = {"cc0", "pdm", "by", "by-sa", "public domain", "cc-by", "cc-by-sa"}


def _get_json(url: str, headers: dict | None = None) -> dict:
    req = urllib.request.Request(url, headers={**UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def download(url: str, dst: Path, tries: int = 3) -> Path:
    import time
    import urllib.error
    if dst.exists() and dst.stat().st_size > 0:
        return dst
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_suffix(dst.suffix + ".part")
    for k in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "ytauto-documentary-tool/1.0 (open-source video tool)"})
            with urllib.request.urlopen(req, timeout=120) as r, open(tmp, "wb") as f:
                while chunk := r.read(1 << 20):
                    f.write(chunk)
            break
        except urllib.error.HTTPError as exc:
            if exc.code in (429, 500, 502, 503, 504) and k < tries - 1:
                time.sleep(4 * (k + 1) ** 2)
                continue
            raise
    tmp.rename(dst)
    return dst


_STOP = {"a", "an", "the", "of", "in", "on", "at", "and", "or", "with", "to", "from", "under", "underwater", "close", "up"}


def _relevant(query: str, text: str, need_all: bool = False) -> bool:
    """Keep results that actually mention the subject (NASA's search in particular is very loose)."""
    words = [w for w in re.findall(r"[a-z]+", query.lower()) if w not in _STOP and len(w) > 2]
    if not words:
        return True
    t = text.lower()
    hits = [w.rstrip("s") in t for w in words]
    return all(hits) if need_all else any(hits)


def providers_used() -> list[str]:
    """Stock sites that supplied footage in this render (for description credits)."""
    names = {"pexels": "Pexels (pexels.com)", "pixabay": "Pixabay (pixabay.com)", "openverse": "Openverse (openverse.org)",
             "commons": "Wikimedia Commons", "nasa": "NASA Image and Video Library (public domain)"}
    return [names[p] for p in sorted({cid.split("-")[0] for cid in _used}) if p in names]


def credits() -> list[str]:
    """One attribution line per credited photo/clip used in this render (CC BY / BY-SA need these)."""
    with _lock:
        return [_credits[c] for c in sorted(_used) if c in _credits]


def _retry_json(url: str, tries: int = 4) -> dict:
    import time
    import urllib.error
    for k in range(tries):
        try:
            return _get_json(url, {"User-Agent": "ytauto-documentary-tool/1.0 (open-source video tool)"})
        except urllib.error.HTTPError as exc:
            if exc.code in (429, 500, 502, 503, 504) and k < tries - 1:
                time.sleep(3 * (k + 1) ** 2)
                continue
            raise
    return {}


def _openverse_photo(query: str) -> list[tuple[str, str]]:
    q = urllib.parse.urlencode({"q": query, "license_type": "commercial", "page_size": 20})
    data = _retry_json(f"https://api.openverse.org/v1/images/?{q}")
    out = []
    for r in data.get("results", []):
        if (r.get("license") or "").lower() not in OK_LICENSES or not r.get("url") or (r.get("width") or 1200) < 1000:
            continue
        if not _relevant(query, f"{r.get('title')} {' '.join(t.get('name', '') for t in r.get('tags') or [])}"):
            continue
        cid = f"openverse-{r['id']}"
        lic = f"CC {r['license'].upper()} {r.get('license_version') or ''}".strip() if r["license"] not in ("cc0", "pdm") else (
            "public domain" if r["license"] == "pdm" else "CC0")
        _credits[cid] = f'"{r.get("title") or "Photo"}" by {r.get("creator") or "unknown"} ({lic}), {r.get("foreign_landing_url") or ""}'
        out.append((cid, r["url"]))
    return out


def _commons(query: str, kind: str, width: int) -> list[tuple[str, str]]:
    ft = "video" if kind == "video" else "bitmap"
    q = urllib.parse.urlencode({
        "action": "query", "format": "json", "generator": "search", "gsrnamespace": 6, "gsrlimit": 20,
        "gsrsearch": f"{query} filetype:{ft}", "prop": "imageinfo|videoinfo",
        "iiprop": "url|extmetadata|size", "iiurlwidth": min(width, 2560),
        "viprop": "url|derivatives|extmetadata|size",
        "iiextmetadatafilter": "LicenseShortName|Artist|ObjectName", "viextmetadatafilter": "LicenseShortName|Artist|ObjectName"})
    data = _retry_json(f"https://commons.wikimedia.org/w/api.php?{q}")
    import re as _re
    out = []
    for pg in (data.get("query") or {}).get("pages", {}).values():
        info = (pg.get("videoinfo") or pg.get("imageinfo") or [{}])[0]
        meta = info.get("extmetadata") or {}
        lic = (meta.get("LicenseShortName") or {}).get("value", "")
        norm = lic.lower().replace(" ", "-")
        if not (norm.startswith(("cc-by-", "cc0", "cc-by-sa-")) or "public-domain" in norm or norm == "pd"):
            continue
        if "nc" in norm.split("-") or "nd" in norm.split("-"):
            continue
        if kind == "video":
            ders = [d for d in info.get("derivatives", []) if "webm" in d.get("type", "") or "mp4" in d.get("type", "")]
            ders.sort(key=lambda d: abs(int(d.get("height") or 0) - 1080))
            url = ders[0]["src"] if ders else info.get("url")
            if not url or (info.get("height") or 0) < 480:
                continue
        else:
            if (info.get("width") or 0) < 1200 or (info.get("width") or 1) < (info.get("height") or 1):
                continue
            url = info.get("thumburl") or info.get("url")
        if not _relevant(query, pg.get("title", "") + " " + (meta.get("ObjectName") or {}).get("value", "")):
            continue
        cid = f"commons-{pg['pageid']}"
        artist = _re.sub(r"<[^>]+>", "", (meta.get("Artist") or {}).get("value", "unknown")).strip()[:80]
        _credits[cid] = f'"{pg["title"].removeprefix("File:")}" by {artist} ({lic}), Wikimedia Commons'
        out.append((cid, url))
    return out


def _nasa(query: str, kind: str) -> list[tuple[str, str]]:
    q = urllib.parse.urlencode({"q": query, "media_type": kind})
    data = _retry_json(f"https://images-api.nasa.gov/search?{q}")
    out = []
    for it in data.get("collection", {}).get("items", [])[:12]:
        d = (it.get("data") or [{}])[0]
        nid = d.get("nasa_id")
        if not nid or not _relevant(query, f"{d.get('title')} {d.get('description', '')[:400]} {' '.join(d.get('keywords') or [])}",
                                    need_all=True):
            continue
        try:
            files = _retry_json(it["href"], tries=2)
        except Exception:  # noqa: BLE001
            continue
        files = files if isinstance(files, list) else []
        if kind == "video":
            pick = [f for f in files if f.endswith(".mp4") and "~orig" not in f] or [f for f in files if f.endswith(".mp4")]
            pick.sort(key=lambda f: ("~large" not in f, "~medium" not in f))
        else:
            pick = [f for f in files if f.lower().endswith((".jpg", ".jpeg", ".png"))]
            pick.sort(key=lambda f: ("~large" not in f, "~orig" not in f))
        if pick:
            cid = f"nasa-{nid}"
            _credits[cid] = f'"{d.get("title", nid)}" — NASA (public domain)'
            out.append((cid, pick[0].replace("http://", "https://").replace(" ", "%20")))
    return out


def _pick(candidates: list[tuple[str, str]]) -> tuple[str, str]:
    """candidates: (id, url). Prefer one not used yet in this render."""
    with _lock:
        for cid, url in candidates:
            if cid not in _used:
                _used.add(cid)
                return cid, url
    return candidates[0]


def _pexels_video(query: str, width: int, nth: int) -> list[tuple[str, str]]:
    key = os.environ["PEXELS_API_KEY"]
    q = urllib.parse.urlencode({"query": query, "per_page": 15, "orientation": "landscape", "page": 1 + nth // 15})
    data = _get_json(f"https://api.pexels.com/videos/search?{q}", {"Authorization": key})
    out = []
    for v in data.get("videos", []):
        files = [f for f in v.get("video_files", []) if f.get("width") and f.get("file_type") == "video/mp4"]
        if not files:
            continue
        # Smallest file that is still at least the target width, else the largest available.
        big = sorted([f for f in files if f["width"] >= width], key=lambda f: f["width"])
        f = big[0] if big else max(files, key=lambda f: f["width"])
        out.append((f"pexels-v{v['id']}", f["link"]))
    return out


def _pexels_photo(query: str, nth: int) -> list[tuple[str, str]]:
    key = os.environ["PEXELS_API_KEY"]
    q = urllib.parse.urlencode({"query": query, "per_page": 15, "orientation": "landscape", "page": 1 + nth // 15})
    data = _get_json(f"https://api.pexels.com/v1/search?{q}", {"Authorization": key})
    return [(f"pexels-p{p['id']}", p["src"].get("large2x") or p["src"]["original"]) for p in data.get("photos", [])]


def _pixabay_video(query: str, width: int) -> list[tuple[str, str]]:
    key = os.environ["PIXABAY_API_KEY"]
    q = urllib.parse.urlencode({"key": key, "q": query, "per_page": 20, "safesearch": "true"})
    data = _get_json(f"https://pixabay.com/api/videos/?{q}")
    out = []
    for h in data.get("hits", []):
        vids = h.get("videos", {})
        for size in ("large", "medium", "small"):
            v = vids.get(size)
            if v and v.get("url") and (v.get("width", 0) >= min(width, 1280) or size == "small"):
                out.append((f"pixabay-v{h['id']}", v["url"]))
                break
    return out


def _pixabay_photo(query: str) -> list[tuple[str, str]]:
    key = os.environ["PIXABAY_API_KEY"]
    q = urllib.parse.urlencode({"key": key, "q": query, "per_page": 20, "image_type": "photo",
                                "orientation": "horizontal", "safesearch": "true"})
    data = _get_json(f"https://pixabay.com/api/?{q}")
    return [(f"pixabay-p{h['id']}", h.get("largeImageURL") or h["webformatURL"]) for h in data.get("hits", [])]


def credit_for(path: Path) -> str | None:
    """Short credit for a downloaded stock file ("Godot13 · CC BY-SA 4.0 · Wikimedia Commons"), if it needs one."""
    cid = _path_ids.get(str(path))
    line = _credits.get(cid or "")
    if not line:
        return None
    m = re.match(r'"(.*)" by (.*?) \((.*?)\)(?:, (.*))?$', line)
    if m:
        who, lic, where = m.group(2), m.group(3), m.group(4) or ""
        where = "Wikimedia Commons" if "Wikimedia" in where else ("Flickr" if "flickr" in where.lower() else where.split("/")[2] if where.startswith("http") else where)
        return " · ".join(x for x in (who, lic, where) if x)
    return line.split(" — ")[-1] if " — " in line else line[:80]


def _fetch(cid: str, url: str, kind: str, query: str, cache: Path) -> Path:
    ext = ".mp4" if kind == "video" else ".jpg"
    src_ext = Path(urllib.parse.urlparse(url).path).suffix.lower()
    dst = cache / "stock" / f"{cid}_{stable_hash(url)}{ext}"
    _path_ids[str(dst)] = cid
    if dst.exists():
        return dst
    log(f"Downloading stock {kind} for '{query}' ({cid})")
    if kind == "video" and src_ext not in (".mp4", ".mov"):
        from .utils import run
        raw = download(url, dst.with_suffix(src_ext or ".webm"))
        run(["ffmpeg", "-y", "-v", "error", "-i", raw, "-t", "90", "-an", "-c:v", "libx264", "-crf", "18",
             "-preset", "veryfast", "-pix_fmt", "yuv420p", dst])
        raw.unlink(missing_ok=True)
        return dst
    return download(url, dst)


def fetch_stock(query: str, kind: str, cache: Path, width: int, nth: int = 0) -> tuple[Path, str]:
    """Return (local_path, 'video'|'image') for a stock search. Providers are tried in order: keyed sites first
    (Pexels, Pixabay), then the keyless ones (Openverse/Commons for photos, Commons/NASA for video)."""
    providers = []
    if os.environ.get("PEXELS_API_KEY"):
        providers.append("pexels")
    if os.environ.get("PIXABAY_API_KEY"):
        providers.append("pixabay")
    order = os.environ.get("YTAUTO_STOCK_FREE", "openverse,commons,nasa" if kind == "image" else "commons,nasa")
    providers += [p.strip() for p in order.split(",") if p.strip()]

    errors = []
    for prov in providers:
        try:
            if prov == "pexels":
                cands = _pexels_video(query, width, nth) if kind == "video" else _pexels_photo(query, nth)
            elif prov == "pixabay":
                cands = _pixabay_video(query, width) if kind == "video" else _pixabay_photo(query)
            elif prov == "openverse":
                cands = _openverse_photo(query) if kind == "image" else []
            elif prov == "commons":
                cands = _commons(query, kind, width)
            elif prov == "nasa":
                cands = _nasa(query, kind)
            else:
                continue
            if not cands:
                errors.append(f"{prov}: no results")
                continue
            rot = cands[nth % len(cands):] + cands[:nth % len(cands)]
            for attempt in range(min(3, len(rot))):
                cid, url = _pick(rot[attempt:])
                try:
                    return _fetch(cid, url, kind, query, cache), kind
                except Exception as exc:  # noqa: BLE001 — try the next result
                    with _lock:
                        _used.discard(cid)
                    errors.append(f"{prov}: {cid} {str(exc)[:80]}")
            continue
        except YtautoError:
            raise
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{prov}: {str(exc)[:120]}")
    raise YtautoError(f"Stock search failed for '{query}': {'; '.join(errors)}")

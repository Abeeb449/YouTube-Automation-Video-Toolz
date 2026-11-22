"""Free stock footage/photos: Pexels (PEXELS_API_KEY) and Pixabay (PIXABAY_API_KEY)."""
from __future__ import annotations

import json
import os
import threading
import urllib.parse
import urllib.request
from pathlib import Path

from .utils import YtautoError, log, stable_hash

UA = {"User-Agent": "ytauto/1.0"}
_lock = threading.Lock()
_used: set[str] = set()  # avoid repeating the same stock clip inside one render


def _get_json(url: str, headers: dict | None = None) -> dict:
    req = urllib.request.Request(url, headers={**UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def download(url: str, dst: Path) -> Path:
    if dst.exists() and dst.stat().st_size > 0:
        return dst
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_suffix(dst.suffix + ".part")
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=120) as r, open(tmp, "wb") as f:
        while chunk := r.read(1 << 20):
            f.write(chunk)
    tmp.rename(dst)
    return dst


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


def fetch_stock(query: str, kind: str, cache: Path, width: int, nth: int = 0) -> tuple[Path, str]:
    """Return (local_path, 'video'|'image') for a stock search."""
    providers = []
    if os.environ.get("PEXELS_API_KEY"):
        providers.append("pexels")
    if os.environ.get("PIXABAY_API_KEY"):
        providers.append("pixabay")
    if not providers:
        raise YtautoError("No stock API key: set PEXELS_API_KEY (free at pexels.com/api) or PIXABAY_API_KEY")

    errors = []
    for prov in providers:
        try:
            if kind == "video":
                cands = _pexels_video(query, width, nth) if prov == "pexels" else _pixabay_video(query, width)
            else:
                cands = _pexels_photo(query, nth) if prov == "pexels" else _pixabay_photo(query)
            if not cands:
                errors.append(f"{prov}: no results")
                continue
            cid, url = _pick(cands)
            ext = ".mp4" if kind == "video" else ".jpg"
            dst = cache / "stock" / f"{cid}_{stable_hash(url)}{ext}"
            if not dst.exists():
                log(f"Downloading stock {kind} for '{query}' ({cid})")
            return download(url, dst), kind
        except YtautoError:
            raise
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{prov}: {exc}")
    raise YtautoError(f"Stock search failed for '{query}': {'; '.join(errors)}")

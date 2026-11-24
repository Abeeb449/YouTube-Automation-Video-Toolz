"""Free B-roll for commercial use, photos and video. Everything is found, licence-checked, downloaded and credited
automatically during a render; you never download pictures yourself.

Keyless (always on):
  inaturalist  wildlife photos of the exact species (research-grade observations), CC0 / CC BY only
  openverse    CC0 / public-domain / CC BY photos (Flickr, Wikimedia, museums), api.openverse.org
  commons      Wikimedia Commons photos and video clips (same licence filter)
  nasa         NASA Image and Video Library: public domain (Earth, ice, oceans, expeditions)
With a free key (optional):
  unsplash     UNSPLASH_ACCESS_KEY   (Unsplash License: free for commercial use)
  pexels       PEXELS_API_KEY        pixabay   PIXABAY_API_KEY

Licences (`YTAUTO_STOCK_LICENSES`, default "cc0,pdm,by"): every Creative Commons item must carry one of these.
Add "by-sa" to also accept CC BY-SA (share-alike: adapted versions of the photo must stay BY-SA).
NC (non-commercial) and ND (no-derivatives) items are never used, whatever the setting.

Credits: every item used is recorded (title, author, licence, source link). `credits()` gives the lines for the
video description, `write_credits()` saves build/credits.json as your record of what was used and under which
licence, and `credit_for()` gives the short on-screen chip ("Jane Doe · CC BY 4.0 · iNaturalist").
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

UA = {"User-Agent": "ytauto-documentary-tool/1.0 (open-source video tool)"}
_lock = threading.Lock()
_used: set[str] = set()          # avoid repeating the same stock clip inside one render
_credits: dict[str, dict] = {}   # id -> {title, author, license, license_url, url, provider}
_path_ids: dict[str, str] = {}   # downloaded file -> id
_inat_last = [0.0]               # iNaturalist asks for at most ~1 request per second

PROVIDER_NAMES = {
    "inaturalist": "iNaturalist (inaturalist.org)", "unsplash": "Unsplash (unsplash.com)",
    "pexels": "Pexels (pexels.com)", "pixabay": "Pixabay (pixabay.com)", "openverse": "Openverse (openverse.org)",
    "commons": "Wikimedia Commons", "nasa": "NASA Image and Video Library (public domain)",
}
# licences that need no credit by law (credited anyway when there is room in the description)
NO_CREDIT_NEEDED = {"cc0", "pdm", "unsplash", "pexels", "pixabay"}


def allowed_licenses() -> set[str]:
    raw = os.environ.get("YTAUTO_STOCK_LICENSES", "cc0,pdm,by")
    return {x.strip().lower() for x in raw.split(",") if x.strip()}


def license_code(text: str) -> str | None:
    """Normalise a licence name from any provider to cc0 | pdm | by | by-sa, or None (NC, ND, unknown → reject)."""
    t = (text or "").lower().replace("_", "-").replace(" ", "-")
    if not t:
        return None
    parts = set(re.split(r"[-/.]", t))
    if "nc" in parts or "nd" in parts or "noncommercial" in t or "noderiv" in t:
        return None
    if t.startswith("cc0") or t in ("cc-zero", "zero"):
        return "cc0"
    if t in ("pdm", "pd", "public-domain", "publicdomain") or t.startswith(("public-domain", "pd-")):
        return "pdm"
    if t.startswith(("cc-by-sa", "by-sa")):
        return "by-sa"
    if t.startswith(("cc-by", "by")) and ("sa" not in parts):
        return "by"
    return None


def _license_ok(code: str | None) -> bool:
    return code is not None and code in allowed_licenses()


def _label(code: str, version: str = "") -> str:
    return {"cc0": "CC0", "pdm": "public domain", "by": f"CC BY {version}".strip(),
            "by-sa": f"CC BY-SA {version}".strip()}.get(code, code)


def _cc_url(code: str, version: str = "4.0") -> str:
    version = version or "4.0"
    return {"cc0": "https://creativecommons.org/publicdomain/zero/1.0/",
            "pdm": "https://creativecommons.org/publicdomain/mark/1.0/",
            "by": f"https://creativecommons.org/licenses/by/{version}/",
            "by-sa": f"https://creativecommons.org/licenses/by-sa/{version}/"}.get(code, "")


def _credit(cid: str, provider: str, title: str, author: str, code: str, license: str, url: str, license_url: str = ""):
    with _lock:
        _credits[cid] = {"id": cid, "provider": provider, "title": (title or "").strip()[:120],
                         "author": re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", author or "unknown")).strip()[:80] or "unknown",
                         "code": code, "license": license, "license_url": license_url, "url": url}


# ------------------------------------------------------------------------------------------------ http helpers
def _get_json(url: str, headers: dict | None = None) -> dict:
    req = urllib.request.Request(url, headers={**UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def _retry_json(url: str, tries: int = 4, headers: dict | None = None) -> dict:
    import time
    import urllib.error
    for k in range(tries):
        try:
            return _get_json(url, headers)
        except urllib.error.HTTPError as exc:
            if exc.code in (429, 500, 502, 503, 504) and k < tries - 1:
                time.sleep(3 * (k + 1) ** 2)
                continue
            raise
    return {}


def download(url: str, dst: Path, tries: int = 3) -> Path:
    import time
    import urllib.error
    if dst.exists() and dst.stat().st_size > 0:
        return dst
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_suffix(dst.suffix + ".part")
    for k in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
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


def _words(text: str) -> list[str]:
    return [w for w in re.findall(r"[a-z]+", (text or "").lower()) if w not in _STOP and len(w) > 2]


def _relevant(query: str, text: str, need_all: bool = False) -> bool:
    """Keep results that actually mention the subject (NASA's and Unsplash's search in particular are loose)."""
    words = _words(query)
    if not words:
        return True
    t = text.lower()
    hits = [w.rstrip("s") in t for w in words]
    return all(hits) if need_all else any(hits)


# ------------------------------------------------------------------------------------------------ credits
def providers_used() -> list[str]:
    """Stock sites that supplied footage in this render (for description credits)."""
    return [PROVIDER_NAMES[p] for p in sorted({cid.split("-")[0] for cid in _used}) if p in PROVIDER_NAMES]


def credit_records() -> list[dict]:
    with _lock:
        return [_credits[c] for c in sorted(_used) if c in _credits]


def _line(r: dict) -> str:
    title = f'"{r["title"]}" ' if r.get("title") else ""
    return f'{title}by {r["author"]}, {r["license"]}, {r["url"]}'.strip()


def credits(required_only: bool = False) -> list[str]:
    """One attribution line per photo/clip used in this render: title, author, licence and source link (the
    source page states the licence, which is how CC BY 4.0 asks to be credited)."""
    return [_line(r) for r in credit_records() if not (required_only and r.get("code") in NO_CREDIT_NEEDED)]


def write_credits(path: Path) -> None:
    """Save the full licence record of every stock item used (keep it: it is your proof of licence)."""
    path.write_text(json.dumps(credit_records(), indent=2), encoding="utf-8")


def credit_for(path: Path) -> str | None:
    """Short on-screen credit for a downloaded stock file ("Jane Doe · CC BY 4.0 · iNaturalist"), if it needs one."""
    r = _credits.get(_path_ids.get(str(path)) or "")
    if not r:
        return None
    if r["provider"] == "nasa":
        return "NASA"
    where = {"inaturalist": "iNaturalist", "commons": "Wikimedia Commons", "unsplash": "Unsplash", "openverse": "",
             "pexels": "Pexels", "pixabay": "Pixabay", "nasa": "NASA"}.get(r["provider"], "")
    if r["provider"] == "openverse":
        host = urllib.parse.urlparse(r["url"]).netloc.replace("www.", "")
        where = {"flickr.com": "Flickr", "commons.wikimedia.org": "Wikimedia Commons"}.get(host, host)
    return " · ".join(x for x in (r["author"], r["license"] if r["provider"] not in ("unsplash", "pexels", "pixabay") else "", where) if x)


# ------------------------------------------------------------------------------------------------ providers
def _inat_get(url: str) -> dict:
    import time
    with _lock:
        wait = 1.05 - (time.time() - _inat_last[0])
        _inat_last[0] = time.time() + max(0.0, wait)
    if wait > 0:
        time.sleep(wait)
    return _retry_json(url, tries=3)


def _inat_taxon(query: str) -> tuple[dict | None, bool]:
    """Find the species named in the query: "leopard seal teeth" → Leopard Seal (exact=False, extra words left over)."""
    words = query.split()
    for n in range(len(words), 0, -1):
        sub = " ".join(words[:n])
        if not _words(sub):
            continue
        data = _inat_get("https://api.inaturalist.org/v1/taxa/autocomplete?" + urllib.parse.urlencode({"q": sub, "per_page": 5}))
        want = {w.rstrip("s") for w in _words(sub)}
        for tx in data.get("results", []):
            names = [tx.get("matched_term") or "", tx.get("preferred_common_name") or "", tx.get("name") or ""]
            if any({w.rstrip("s") for w in _words(nm)} == want for nm in names):
                return tx, n == len(words)
    return None, False


def _inaturalist(query: str) -> tuple[list[tuple[str, str]], bool]:
    """Research-grade observation photos of the exact species, most-faved first, CC0 / CC BY (per allowed list)."""
    tx, exact = _inat_taxon(query)
    if not tx:
        return [], False
    lic = ",".join(x for x in ("cc0", "cc-by", "cc-by-sa") if license_code(x) in allowed_licenses())
    q = urllib.parse.urlencode({"taxon_id": tx["id"], "photo_license": lic, "quality_grade": "research", "photos": "true",
                                "per_page": 40, "order_by": "votes", "order": "desc"})
    data = _inat_get(f"https://api.inaturalist.org/v1/observations?{q}")
    common = tx.get("preferred_common_name") or tx.get("name")
    out = []
    for ob in data.get("results", []):
        user = ob.get("user") or {}
        for ph in (ob.get("photos") or [])[:2]:
            code = license_code(ph.get("license_code") or "")
            if not _license_ok(code) or not ph.get("url"):
                continue
            dims = ph.get("original_dimensions") or {}
            w, h = dims.get("width") or 0, dims.get("height") or 1
            if w < 1400 or w / h < 1.2:    # landscape and sharp enough for a 1080p frame
                continue
            cid = f"inaturalist-{ph['id']}"
            _credit(cid, "inaturalist", f"{common} ({tx.get('name')})", user.get("name") or user.get("login") or "unknown",
                    code, _label(code, "4.0"), f"https://www.inaturalist.org/photos/{ph['id']}", _cc_url(code))
            out.append((cid, re.sub(r"/(square|small|medium|thumb)\.", "/original.", ph["url"])))
    return out, exact


def _unsplash(query: str) -> list[tuple[str, str]]:
    key = os.environ["UNSPLASH_ACCESS_KEY"]
    q = urllib.parse.urlencode({"query": query, "per_page": 20, "orientation": "landscape", "content_filter": "high"})
    data = _retry_json(f"https://api.unsplash.com/search/photos?{q}", tries=2, headers={"Authorization": f"Client-ID {key}",
                                                                                       "Accept-Version": "v1"})
    subject = " ".join(_words(query)[:2])
    out = []
    for p in data.get("results", []):
        text = " ".join([p.get("description") or "", p.get("alt_description") or "",
                         " ".join(t.get("title", "") for t in p.get("tags") or [])])
        if not _relevant(subject, text, need_all=True):
            continue
        cid = f"unsplash-{p['id']}"
        user = p.get("user") or {}
        prof = (user.get("links") or {}).get("html") or "https://unsplash.com"
        _credit(cid, "unsplash", p.get("alt_description") or "", user.get("name") or "unknown", "unsplash",
                "Unsplash License", f"{prof}?utm_source=ytauto&utm_medium=referral", "https://unsplash.com/license")
        _credits[cid]["download_location"] = (p.get("links") or {}).get("download_location")
        raw = (p.get("urls") or {}).get("raw")
        if raw:
            out.append((cid, f"{raw}&w=2400&q=85&fm=jpg"))
    return out


def _unsplash_track(cid: str) -> None:
    """Unsplash API rule: tell Unsplash when a photo is actually used (counts as a download for the photographer)."""
    loc = (_credits.get(cid) or {}).get("download_location")
    if loc and os.environ.get("UNSPLASH_ACCESS_KEY"):
        try:
            _get_json(loc, {"Authorization": f"Client-ID {os.environ['UNSPLASH_ACCESS_KEY']}"})
        except Exception:  # noqa: BLE001 — tracking only
            pass


def _openverse_photo(query: str) -> list[tuple[str, str]]:
    q = urllib.parse.urlencode({"q": query, "license_type": "commercial", "page_size": 20})
    data = _retry_json(f"https://api.openverse.org/v1/images/?{q}")
    out = []
    for r in data.get("results", []):
        code = license_code(r.get("license") or "")
        if not _license_ok(code) or not r.get("url") or (r.get("width") or 1200) < 1000:
            continue
        if not _relevant(query, f"{r.get('title')} {' '.join(t.get('name', '') for t in r.get('tags') or [])}"):
            continue
        cid = f"openverse-{r['id']}"
        _credit(cid, "openverse", r.get("title") or "Photo", r.get("creator") or "unknown", code,
                _label(code, r.get("license_version") or ""), r.get("foreign_landing_url") or r["url"],
                r.get("license_url") or _cc_url(code, r.get("license_version") or ""))
        out.append((cid, r["url"]))
    return out


def _commons(query: str, kind: str, width: int) -> list[tuple[str, str]]:
    ft = "video" if kind == "video" else "bitmap"
    meta_keys = "LicenseShortName|LicenseUrl|Artist|ObjectName"
    q = urllib.parse.urlencode({
        "action": "query", "format": "json", "generator": "search", "gsrnamespace": 6, "gsrlimit": 20,
        "gsrsearch": f"{query} filetype:{ft}", "prop": "imageinfo|videoinfo",
        "iiprop": "url|extmetadata|size", "iiurlwidth": min(width, 2560),
        "viprop": "url|derivatives|extmetadata|size",
        "iiextmetadatafilter": meta_keys, "viextmetadatafilter": meta_keys})
    data = _retry_json(f"https://commons.wikimedia.org/w/api.php?{q}")
    out = []
    for pg in (data.get("query") or {}).get("pages", {}).values():
        info = (pg.get("videoinfo") or pg.get("imageinfo") or [{}])[0]
        meta = info.get("extmetadata") or {}
        lic = (meta.get("LicenseShortName") or {}).get("value", "")
        code = license_code(lic)
        if not _license_ok(code):
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
        page = "https://commons.wikimedia.org/wiki/" + urllib.parse.quote(pg["title"].replace(" ", "_"))
        _credit(cid, "commons", pg["title"].removeprefix("File:").rsplit(".", 1)[0],
                (meta.get("Artist") or {}).get("value", "unknown"), code, lic, page,
                (meta.get("LicenseUrl") or {}).get("value", "") or _cc_url(code))
        out.append((cid, url))
    return out


_NASA_NOT_PD = re.compile(r"©|\(c\)\s|copyright|all rights reserved|courtesy of|used with permission", re.I)


def _nasa(query: str, kind: str) -> list[tuple[str, str]]:
    """NASA's own imagery is public domain; items marked as third-party (copyright, "courtesy of") are skipped."""
    if not _license_ok("pdm"):
        return []
    q = urllib.parse.urlencode({"q": query, "media_type": kind})
    data = _retry_json(f"https://images-api.nasa.gov/search?{q}")
    out = []
    for it in data.get("collection", {}).get("items", [])[:12]:
        d = (it.get("data") or [{}])[0]
        nid = d.get("nasa_id")
        blob = f"{d.get('title')} {d.get('description', '')[:400]} {' '.join(d.get('keywords') or [])}"
        if not nid or not _relevant(query, blob, need_all=True):
            continue
        if _NASA_NOT_PD.search(f"{d.get('description', '')} {d.get('photographer', '')} {d.get('secondary_creator', '')}"):
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
            _credit(cid, "nasa", d.get("title", nid), d.get("photographer") or d.get("center") or "NASA", "pdm",
                    "public domain (NASA)", f"https://images.nasa.gov/details/{urllib.parse.quote(nid)}")
            out.append((cid, pick[0].replace("http://", "https://").replace(" ", "%20")))
    return out


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
        cid = f"pexels-v{v['id']}"
        _credit(cid, "pexels", "", (v.get("user") or {}).get("name") or "Pexels", "pexels", "Pexels License", v.get("url") or "")
        out.append((cid, f["link"]))
    return out


def _pexels_photo(query: str, nth: int) -> list[tuple[str, str]]:
    key = os.environ["PEXELS_API_KEY"]
    q = urllib.parse.urlencode({"query": query, "per_page": 15, "orientation": "landscape", "page": 1 + nth // 15})
    data = _get_json(f"https://api.pexels.com/v1/search?{q}", {"Authorization": key})
    out = []
    for p in data.get("photos", []):
        cid = f"pexels-p{p['id']}"
        _credit(cid, "pexels", p.get("alt") or "", p.get("photographer") or "Pexels", "pexels", "Pexels License", p.get("url") or "")
        out.append((cid, p["src"].get("large2x") or p["src"]["original"]))
    return out


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
                cid = f"pixabay-v{h['id']}"
                _credit(cid, "pixabay", "", h.get("user") or "Pixabay", "pixabay", "Pixabay Content License", h.get("pageURL") or "")
                out.append((cid, v["url"]))
                break
    return out


def _pixabay_photo(query: str) -> list[tuple[str, str]]:
    key = os.environ["PIXABAY_API_KEY"]
    q = urllib.parse.urlencode({"key": key, "q": query, "per_page": 20, "image_type": "photo",
                                "orientation": "horizontal", "safesearch": "true"})
    data = _get_json(f"https://pixabay.com/api/?{q}")
    out = []
    for h in data.get("hits", []):
        cid = f"pixabay-p{h['id']}"
        _credit(cid, "pixabay", "", h.get("user") or "Pixabay", "pixabay", "Pixabay Content License", h.get("pageURL") or "")
        out.append((cid, h.get("largeImageURL") or h["webformatURL"]))
    return out


# ------------------------------------------------------------------------------------------------ fetching
def _pick(candidates: list[tuple[str, str]]) -> tuple[str, str]:
    """candidates: (id, url). Prefer one not used yet in this render."""
    with _lock:
        for cid, url in candidates:
            if cid not in _used:
                _used.add(cid)
                return cid, url
        _used.add(candidates[0][0])
    return candidates[0]


def _fetch(cid: str, url: str, kind: str, query: str, cache: Path) -> Path:
    ext = ".mp4" if kind == "video" else ".jpg"
    src_ext = Path(urllib.parse.urlparse(url).path).suffix.lower()
    dst = cache / "stock" / f"{cid}_{stable_hash(url)}{ext}"
    _path_ids[str(dst)] = cid
    if dst.exists():
        return dst
    log(f"Downloading stock {kind} for '{query}' ({cid})")
    if cid.startswith("unsplash-"):
        _unsplash_track(cid)
    if kind == "video" and src_ext not in (".mp4", ".mov"):
        from .utils import run
        raw = download(url, dst.with_suffix(src_ext or ".webm"))
        run(["ffmpeg", "-y", "-v", "error", "-i", raw, "-t", "90", "-an", "-c:v", "libx264", "-crf", "18",
             "-preset", "veryfast", "-pix_fmt", "yuv420p", dst])
        raw.unlink(missing_ok=True)
        return dst
    return download(url, dst)


def provider_order(kind: str) -> list[str]:
    """Providers to try, best first. Override with YTAUTO_STOCK_IMAGE / YTAUTO_STOCK_VIDEO (comma-separated)."""
    default = ("inaturalist,unsplash,pexels,pixabay,openverse,commons,nasa" if kind == "image"
               else "pexels,pixabay,commons,nasa")
    raw = os.environ.get(f"YTAUTO_STOCK_{kind.upper()}") or os.environ.get("YTAUTO_STOCK_FREE") and (
        "pexels,pixabay,unsplash," + os.environ["YTAUTO_STOCK_FREE"]) or default
    keyed = {"pexels": "PEXELS_API_KEY", "pixabay": "PIXABAY_API_KEY", "unsplash": "UNSPLASH_ACCESS_KEY"}
    return [p.strip() for p in raw.split(",") if p.strip() and (p.strip() not in keyed or os.environ.get(keyed[p.strip()]))]


def fetch_stock(query: str, kind: str, cache: Path, width: int, nth: int = 0) -> tuple[Path, str]:
    """Return (local_path, 'video'|'image') for a stock search: search each provider in order, keep only
    commercial-use licences, download the best unused result and record its credit."""
    errors = []
    later: list[tuple[str, list]] = []   # species photos when the query also asks for a detail ("seal teeth")

    def attempt(prov: str, cands: list) -> Path | None:
        rot = cands[nth % len(cands):] + cands[:nth % len(cands)]
        for k in range(min(3, len(rot))):
            cid, url = _pick(rot[k:])
            try:
                return _fetch(cid, url, kind, query, cache)
            except Exception as exc:  # noqa: BLE001 — try the next result
                with _lock:
                    _used.discard(cid)
                errors.append(f"{prov}: {cid} {str(exc)[:80]}")
        return None

    for prov in provider_order(kind):
        try:
            if prov == "inaturalist":
                if kind != "image":
                    continue
                cands, exact = _inaturalist(query)
                if cands and not exact:
                    later.append((prov, cands))   # right animal, but can't promise the detail: try text searches first
                    continue
            elif prov == "unsplash":
                cands = _unsplash(query) if kind == "image" else []
            elif prov == "pexels":
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
            got = attempt(prov, cands)
            if got:
                return got, kind
        except YtautoError:
            raise
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{prov}: {str(exc)[:120]}")
    for prov, cands in later:
        got = attempt(prov, cands)
        if got:
            return got, kind
    raise YtautoError(f"Stock search failed for '{query}': {'; '.join(errors)}")

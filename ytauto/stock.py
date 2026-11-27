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

import functools
import json
import os
import re
import threading
import urllib.parse
import urllib.request
from pathlib import Path

from .utils import YtautoError, log, stable_hash

# Wikimedia's robot policy asks automated tools to identify themselves with contact details (a URL or email);
# without them, downloads may be refused. Set YTAUTO_CONTACT (e.g. your channel URL or an email) to comply.
_CONTACT = os.environ.get("YTAUTO_CONTACT", "").strip()
UA = {"User-Agent": "ytauto-documentary-tool/1.0 (open-source video tool" + (f"; {_CONTACT}" if _CONTACT else "") + ")"}
_lock = threading.Lock()
_used: set[str] = set()          # avoid repeating the same stock clip inside one render
_reused: dict[str, int] = {}     # how often a clip had to be shown again
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
    # an unset GitHub variable arrives as an EMPTY string: that means "default", not "no licence allowed"
    raw = os.environ.get("YTAUTO_STOCK_LICENSES", "").strip() or "cc0,pdm,by"
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


_warned_contact: list[int] = []
_wm_lock = threading.Lock()   # Wikimedia asks bots for few concurrent requests: one download at a time


class TooLarge(Exception):
    pass


MAX_VIDEO_MB = float(os.environ.get("YTAUTO_MAX_VIDEO_MB", "400"))   # b-roll; NASA also lists hours-long streams
MAX_IMAGE_MB = 60.0


def download(url: str, dst: Path, tries: int = 3, max_mb: float | None = None) -> Path:
    import contextlib
    import time
    import urllib.error
    if dst.exists() and dst.stat().st_size > 0:
        return dst
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_suffix(dst.suffix + ".part")
    wikimedia = "upload.wikimedia.org" in url
    for k in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with (_wm_lock if wikimedia else contextlib.nullcontext()):
                with urllib.request.urlopen(req, timeout=120) as r:
                    size = int(r.headers.get("Content-Length") or 0)
                    if max_mb and size > max_mb * 1e6:
                        raise TooLarge(f"{size / 1e6:.0f} MB is over the {max_mb:.0f} MB limit")
                    got = 0
                    with open(tmp, "wb") as f:
                        while chunk := r.read(1 << 20):
                            got += len(chunk)
                            if max_mb and got > max_mb * 1e6:
                                raise TooLarge(f"over the {max_mb:.0f} MB limit")
                            f.write(chunk)
            break
        except TooLarge:
            tmp.unlink(missing_ok=True)
            raise
        except urllib.error.HTTPError as exc:
            if exc.code == 429 and wikimedia:
                if not _CONTACT and not _warned_contact:
                    _warned_contact.append(1)
                    warn("Wikimedia refused a download (robot policy). Set YTAUTO_CONTACT to your channel URL or an "
                         "email so the toolkit can identify itself as Wikimedia asks; other sources are used meanwhile.")
                raise   # rate-limited: move on to the next photo/source now instead of waiting
            if exc.code in (429, 500, 502, 503, 504) and k < tries - 1:
                time.sleep(4 * (k + 1) ** 2)
                continue
            raise
    tmp.rename(dst)
    return dst


_STOP = {"a", "an", "the", "of", "in", "on", "at", "and", "or", "with", "to", "from", "under", "underwater", "close", "up"}


def _words(text: str) -> list[str]:
    return [w for w in re.findall(r"[a-z]+", (text or "").lower()) if w not in _STOP and len(w) > 2]


@functools.lru_cache(maxsize=512)
def _subject(query: str) -> tuple[str, ...]:
    """Words that MUST all appear in a caption: the animal's full name if the query names one
    ("leopard seal underwater" → leopard, seal), else the first two content words."""
    try:
        tx, _ = _inat_taxon(query)
    except Exception:  # noqa: BLE001
        tx = None
    if tx:
        name = (tx.get("preferred_common_name") or "").lower()
        ws = tuple(w.rstrip("s") for w in _words(name))
        if ws and all(w in " ".join(_words(query)) for w in ws):
            return ws
    return tuple(w.rstrip("s") for w in _words(query)[:2])


def _on_subject(query: str, text: str) -> bool:
    t = (text or "").lower()
    return all(w in t for w in _subject(query))


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


# words that describe a detail of an animal (so "orca teeth" is still about the orca), not a place or thing
_DETAIL = {w.rstrip("s") for w in """teeth tooth jaw jaws mouth head eye eyes ear ears nose snout whisker whiskers skin fur
    feather feathers scale scales fin fins flipper flippers tail tails claw claws paw paws leg legs wing wings beak horn horns
    tusk tusks shell spine spines tentacle tentacles stinger venom body face closeup close portrait profile
    pup pups cub cubs calf calves chick chicks baby babies juvenile young mother mothers female females male males adult
    colony colonies herd herds pod pods flock flocks school schools swarm group pair family nest nests egg eggs
    pride prides pack packs troop troops den dens burrow mating courtship migration
    hunting hunt hunts attack attacking feeding eating swimming diving flying running sleeping resting sunbathing basking
    underwater surface water ice land beach shore rock rocks wild skeleton""".split()}


@functools.lru_cache(maxsize=512)
def _inat_taxon(query: str) -> tuple[dict | None, bool]:
    """Find the species named in the query: "leopard seal teeth" → Leopard Seal (exact=False, extra words left over)."""
    words = query.split()
    for n in range(len(words), 0, -1):
        sub = " ".join(words[:n])
        if not _words(sub):
            continue
        want = {w.rstrip("s") for w in _words(sub)}
        results = []
        for q in dict.fromkeys([sub, sub + "s" if not sub.endswith("s") else sub[:-1]]):   # "eagle" and "eagles"
            data = _inat_get("https://api.inaturalist.org/v1/taxa/autocomplete?" + urllib.parse.urlencode({"q": q, "per_page": 8}))
            results += data.get("results", [])
        for tx in results:
            names = [tx.get("matched_term") or "", tx.get("preferred_common_name") or "", tx.get("name") or ""]
            # group names list their members: "Hawks, Eagles, and Kites" matches "eagle"
            # ("Emperor, Royal, Moon, and Giant Silk Moths": 'Moon' only describes the moths)
            parts = [p for nm in names for p in re.split(r",\s*|\s+and\s+", nm)
                     if p.strip() and p.strip().split()[-1].lower().endswith("s")]
            if any({w.rstrip("s") for w in _words(nm)} == want for nm in names + parts):
                # words were dropped ("sahara desert" -> "sahara"): a one-word leftover only counts if it is a
                # well-known animal ("orca teeth" -> orca), not an obscure taxon that shares a place name
                dropped = {w.rstrip("s") for w in _words(" ".join(words[n:]))}
                if n < len(words) and len(want) < 2 and not dropped <= _DETAIL:
                    continue
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
            w, h = dims.get("width") or 0, dims.get("height") or 0
            if w and h and (w < 1400 or w / h < 1.2):    # landscape and sharp enough for a 1080p frame
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
        if not _on_subject(query, f"{r.get('title')} {' '.join(t.get('name', '') for t in r.get('tags') or [])}"):
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
        "iiprop": "url|extmetadata|size", "iiurlwidth": 1920,
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
            if not url or (info.get("height") or 0) < 720:   # sharp enough for a 1080p video
                continue
        else:
            w0 = info.get("width") or 0
            if w0 < 1200 or w0 < (info.get("height") or 1):
                continue
            url = _wm_thumb(info.get("url") or "", w0) or info.get("thumburl") or info.get("url")
        if not _on_subject(query, pg.get("title", "") + " " + (meta.get("ObjectName") or {}).get("value", "")):
            continue
        cid = f"commons-{pg['pageid']}"
        page = "https://commons.wikimedia.org/wiki/" + urllib.parse.quote(pg["title"].replace(" ", "_"))
        _credit(cid, "commons", pg["title"].removeprefix("File:").rsplit(".", 1)[0],
                (meta.get("Artist") or {}).get("value", "unknown"), code, lic, page,
                (meta.get("LicenseUrl") or {}).get("value", "") or _cc_url(code))
        out.append((cid, url))
    return out


def _wm_thumb(original: str, width: int) -> str | None:
    """A thumbnail in one of Wikimedia's standard widths (others are refused or rate-limited): 1920, else 1280."""
    m = re.match(r"(https://upload\.wikimedia\.org/wikipedia/commons)/(\w/\w\w)/([^/]+)$", original)
    if not m:
        return None
    step = 1920 if width > 1920 else 1280 if width > 1280 else None
    if not step:
        return original
    name = m.group(3)
    tail = name + (".jpg" if name.lower().endswith((".tif", ".tiff")) else ".png" if name.lower().endswith(".svg") else "")
    return f"{m.group(1)}/thumb/{m.group(2)}/{name}/{step}px-{tail}"


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
        if v.get("image"):
            _thumbs[cid] = v["image"]
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
                thumb = v.get("thumbnail") or next((x.get("thumbnail") for x in vids.values() if x and x.get("thumbnail")), None)
                if thumb:
                    _thumbs[cid] = thumb
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
_thumbs: dict[str, str] = {}      # video id -> its still preview picture (checked before the whole clip is downloaded)
# How many candidates one search phrase may turn down before the toolkit moves on. A phrase no library can answer
# (footage of one news event) otherwise costs dozens of downloads and checks, and an hour of a render.
MAX_REJECTS = {"video": 10, "image": 12}
DEADLINE: float | None = None     # set by the collection step: after this moment no new search is started


def _pick(candidates: list[tuple[str, str]]) -> tuple[str, str]:
    """candidates: (id, url). Prefer one not used yet in this render."""
    with _lock:
        for cid, url in candidates:
            if cid not in _used:
                _used.add(cid)
                return cid, url
        # all already shown: reuse the least-shown one, at most twice in a video (a third showing is worse than
        # moving on to the next search or the drawn shot)
        cid, url = min(candidates, key=lambda c: _reused.get(c[0], 0))
        if _reused.get(cid, 0) >= 1:
            raise YtautoError("every result is already in the video twice")
        _reused[cid] = _reused.get(cid, 0) + 1
    return cid, url


_tl = threading.local()


class track:
    """`with track() as ids:` collects the stock ids fetched in this thread (to cache credits with a clip)."""
    def __enter__(self) -> list[str]:
        self.prev = getattr(_tl, "ids", None)
        _tl.ids = []
        return _tl.ids

    def __exit__(self, *exc) -> None:
        if self.prev is not None:
            self.prev.extend(_tl.ids)
        _tl.ids = self.prev


def records_for(ids: list[str]) -> list[dict]:
    with _lock:
        return [{k: v for k, v in _credits[c].items() if k != "download_location"} for c in dict.fromkeys(ids) if c in _credits]


def register(records: list[dict]) -> None:
    """Re-register the credits of a clip taken from the cache (its photos were not searched again)."""
    with _lock:
        for r in records:
            if r.get("id"):
                _credits.setdefault(r["id"], r)
                _used.add(r["id"])


def _fetch(cid: str, url: str, kind: str, query: str, cache: Path) -> Path:
    path = _fetch_file(cid, url, kind, query, cache)
    if getattr(_tl, "ids", None) is not None:
        _tl.ids.append(cid)
    return path


def _good_part(path: Path) -> Path:
    """Only the stretch of a stock video that the picture check approved (verify.check_video), so a long
    clip is never shown from its title card, interview or end slate, even when the scene loops it."""
    import subprocess
    from .utils import ffprobe_duration
    from .verify import best_start
    start = best_start(path)
    try:
        span = float(json.loads(path.with_name(path.name + ".start.json").read_text())["span"])
    except Exception:  # noqa: BLE001
        return path
    d = ffprobe_duration(path)
    if start is None or (start < 0.5 and span >= d * 0.9):
        return path
    out = path.with_name(f"{path.stem}.good{int(start * 10)}.mp4")
    if not out.exists():
        tmp = out.with_suffix(".part.mp4")
        r = subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{start:.2f}", "-i", str(path), "-t", f"{span:.2f}",
                            "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "16", "-pix_fmt", "yuv420p",
                            str(tmp)], check=False)
        if r.returncode != 0 or not tmp.exists():
            return path
        tmp.replace(out)
    with _lock:
        if str(path) in _path_ids:
            _path_ids[str(out)] = _path_ids[str(path)]
    return out


def _fetch_file(cid: str, url: str, kind: str, query: str, cache: Path) -> Path:
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
        raw = download(url, dst.with_suffix(src_ext or ".webm"), max_mb=MAX_VIDEO_MB)
        run(["ffmpeg", "-y", "-v", "error", "-i", raw, "-t", "90", "-an", "-c:v", "libx264", "-crf", "18",
             "-preset", "veryfast", "-pix_fmt", "yuv420p", dst])
        raw.unlink(missing_ok=True)
        return dst
    return download(url, dst, max_mb=MAX_VIDEO_MB if kind == "video" else MAX_IMAGE_MB)


def provider_order(kind: str) -> list[str]:
    """Providers to try, best first. Override with YTAUTO_STOCK_IMAGE / YTAUTO_STOCK_VIDEO (comma-separated)."""
    default = ("inaturalist,unsplash,pexels,pixabay,openverse,commons,nasa" if kind == "image"
               else "pexels,pixabay,commons,nasa")
    raw = os.environ.get(f"YTAUTO_STOCK_{kind.upper()}") or os.environ.get("YTAUTO_STOCK_FREE") and (
        "pexels,pixabay,unsplash," + os.environ["YTAUTO_STOCK_FREE"]) or default
    keyed = {"pexels": "PEXELS_API_KEY", "pixabay": "PIXABAY_API_KEY", "unsplash": "UNSPLASH_ACCESS_KEY"}
    return [p.strip() for p in raw.split(",") if p.strip() and (p.strip() not in keyed or os.environ.get(keyed[p.strip()]))
            and not (p.strip() == "inaturalist" and not species_photos)]


species_photos = True   # set per project (settings.species_photos): only animal/nature videos use iNaturalist
# set per project (settings.stock_approved): the ids the creator approved on the review sheet. When given, nothing
# else is ever downloaded or used, so a render shows exactly the pictures and clips that were looked at.
APPROVED: set[str] | None = None


_rejected: set[str] = set()
_paused: dict[str, float] = {}   # provider -> time until which it is skipped (rate limits)   # candidates that failed the picture check (never retried in this render)


_requests: list[dict] = []        # every stock request of this run and how it ended (for the b-roll report)
_missing: dict[str, str] = {}     # requests already searched in this run with no usable result (not searched twice)
# Parallel rendering: the prepare step collects everything once; the machines that render the scenes and the one
# that builds the video then use exactly that material and never search (FROZEN). A request the prepare step
# never made is noted here, and the machine stops instead of quietly showing something else.
FROZEN = False
UNPREPARED: list[str] = []


def _missing_file(cache: Path) -> Path:
    return cache / "stock" / "missing.json"


def save_missing(cache: Path) -> None:
    """Remember which requests found nothing, for the other machines of a parallel render."""
    f = _missing_file(cache)
    f.parent.mkdir(parents=True, exist_ok=True)
    with _lock:
        f.write_text(json.dumps(_missing, indent=1))


def use_prepared(cache: Path) -> None:
    """Use only what the prepare step collected: what it found is found, what it missed stays missed."""
    global FROZEN
    try:
        _missing.update(json.loads(_missing_file(cache).read_text()))
    except Exception:  # noqa: BLE001
        pass
    FROZEN = True


def unprepared(what: str) -> YtautoError:
    msg = f"{what} was not collected in the prepare step"
    with _lock:
        UNPREPARED.append(msg)
    return YtautoError(msg)


def _resolved_file(cache: Path) -> Path:
    return cache / "stock" / "resolved.json"


def _resolved_load(cache: Path) -> dict:
    f = _resolved_file(cache)
    try:
        return json.loads(f.read_text()) if f.exists() else {}
    except Exception:  # noqa: BLE001
        return {}


def forget_resolved(cache: Path) -> None:
    """Search everything again next time (`ytauto broll --refresh`)."""
    _resolved_file(cache).unlink(missing_ok=True)
    (cache / "models" / "resolved.json").unlink(missing_ok=True)     # 3D models are looked for again too
    _missing.clear()


def fetch_stock(query: str, kind: str, cache: Path, width: int, nth: int = 0, wanted: str | None = None) -> tuple[Path, str]:
    """One stock request → a checked local file. The answer is remembered (cache/stock/resolved.json): the b-roll
    collection step that runs before anything is rendered finds and checks every item once, and the render then
    uses exactly those files without searching again."""
    key = stable_hash("resolved-v1", query, kind, nth, wanted, sorted(allowed_licenses()), species_photos)
    entry = {"query": query, "kind": kind, "wanted": wanted, "ok": False}
    with _lock:
        hit = _resolved_load(cache).get(key)
        gone = _missing.get(key)
    if hit and APPROVED is not None and hit.get("cid") not in APPROVED:
        hit = None                    # found in an earlier run, but not approved on the review sheet
    if hit and Path(hit["path"]).exists():
        path, cid, rec = Path(hit["path"]), hit.get("cid"), hit.get("credit")
        with _lock:
            if cid:
                _path_ids[str(path)] = cid
                _used.add(cid)
                if rec:
                    _credits.setdefault(cid, rec)
        if cid and getattr(_tl, "ids", None) is not None:
            _tl.ids.append(cid)
        with _lock:     # an answer found earlier still counts as found in this run's report
            _requests.append({**entry, "ok": True, "reused": True, "kind": hit.get("kind", kind), "path": str(path),
                              "cid": cid, "credit": rec})
        return path, hit.get("kind", kind)
    if gone:
        raise YtautoError(gone)
    if FROZEN:
        raise unprepared(f"the {kind} for '{query}'")
    try:
        path, got = _fetch_stock_alts(query, kind, cache, width, nth, wanted)
    except YtautoError as exc:
        with _lock:
            _missing[key] = str(exc)
            _requests.append({**entry, "reason": str(exc)})
        raise
    with _lock:
        cid = _path_ids.get(str(path))
        rec = _credits.get(cid) if cid else None
        memo = _resolved_load(cache)
        memo[key] = {"path": str(path), "kind": got, "cid": cid, "credit": rec, "query": query, "wanted": wanted}
        f = _resolved_file(cache)
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps(memo, indent=1))
        _requests.append({**entry, "ok": True, "kind": got, "path": str(path), "cid": cid, "credit": rec})
    return path, got


def _fetch_stock_alts(query: str, kind: str, cache: Path, width: int, nth: int = 0, wanted: str | None = None) -> tuple[Path, str]:
    """`query` may list alternatives, most specific first: "Great Pyramid of Giza|pharaoh Khufu|pyramid". Each is
    searched (and every result picture-checked against THAT alternative) until one gives a usable picture."""
    alts = [q.strip() for q in query.split("|") if q.strip()]
    if len(alts) <= 1:
        return _fetch_stock_one(query.strip(), kind, cache, width, nth, wanted)
    errors = []
    for q in alts:
        try:
            return _fetch_stock_one(q, kind, cache, width, nth, wanted)
        except YtautoError as exc:
            errors.append(f"[{q}] {str(exc)[:160]}")
    raise YtautoError("Stock search failed for every alternative: " + " ; ".join(errors))


def _fetch_stock_one(query: str, kind: str, cache: Path, width: int, nth: int = 0, wanted: str | None = None) -> tuple[Path, str]:
    """Return (local_path, 'video'|'image') for a stock search: search each provider in order, keep only
    commercial-use licences, download the best unused result, CHECK THAT IT SHOWS THE SUBJECT (ytauto/verify.py)
    and record its credit. `wanted` = a more exact description to check against ("sea lions on a rocky beach")."""
    from . import verify
    errors = []
    later: list[tuple[str, list]] = []   # species photos when the query also asks for a detail ("seal teeth")

    import time as _time
    if DEADLINE is not None and _time.time() > DEADLINE:
        raise YtautoError(f"Stock search for '{query}' not run: the time set aside for collecting was used up")
    budget = {"left": MAX_REJECTS.get(kind, 12)}

    def turn_down(cid: str, url: str, why: str, path: Path | None = None) -> None:
        log(f"   skipped {cid} for '{query}': {why}")
        if kind == "video":   # don't keep gigabytes of rejected footage; remember the verdict instead
            marker = cache / "stock" / f"{cid}_{stable_hash(url)}.mp4.rejected"
            marker.parent.mkdir(parents=True, exist_ok=True)
            marker.write_text(f"{query}\t{why}\n")
            if path is not None:
                path.unlink(missing_ok=True)
        with _lock:
            _used.discard(cid)
            _rejected.add(cid)
        ids = getattr(_tl, "ids", None)
        if ids is not None and cid in ids:
            ids.remove(cid)
        budget["left"] -= 1

    def attempt(prov: str, cands: list) -> Path | None:
        rot = cands[nth % len(cands):] + cands[:nth % len(cands)]
        rot = [c for c in rot if c[0] not in _rejected and (APPROVED is None or c[0] in APPROVED)]
        tries = 0
        while rot and tries < 8 and budget["left"] > 0 and not (DEADLINE is not None and _time.time() > DEADLINE):
            try:
                cid, url = _pick(rot)
            except YtautoError as exc:
                errors.append(f"{prov}: {exc}")
                break
            rot = [c for c in rot if c[0] != cid]
            tries += 1
            known = cache / "stock" / f"{cid}_{stable_hash(url)}{'.mp4' if kind == 'video' else '.jpg'}.rejected"
            if known.exists() and known.read_text().split("\t")[0] == query:
                with _lock:
                    _used.discard(cid)
                continue   # already checked and turned down for this exact search
            # a clip's still preview is checked first: a clip whose preview is clearly something else is never downloaded
            if kind == "video" and cid in _thumbs and verify.enabled():
                try:
                    thumb = download(_thumbs[cid], cache / "stock" / "previews" / f"{cid}.jpg", max_mb=8)
                    ok, why = verify.check(thumb, query, cache, wanted)
                except Exception:  # noqa: BLE001 — no preview: judge the clip itself
                    ok, why = True, ""
                if not ok:
                    turn_down(cid, url, f"preview: {why}")
                    errors.append(f"{prov}: {cid} rejected by its preview picture")
                    continue
            try:
                path = _fetch(cid, url, kind, query, cache)
            except Exception as exc:  # noqa: BLE001 — try the next result
                with _lock:
                    _used.discard(cid)
                errors.append(f"{prov}: {cid} {str(exc)[:80]}")
                continue
            ok, why = (verify.check_video(path, query, cache, wanted) if kind == "video"
                       else verify.check(path, query, cache, wanted, trusted=(prov == "inaturalist")))
            if ok:
                return _good_part(path) if kind == "video" else path
            turn_down(cid, url, why, path)
            errors.append(f"{prov}: {cid} rejected by picture check")
        if budget["left"] <= 0:
            errors.append(f"{prov}: stopped after {MAX_REJECTS.get(kind, 12)} results that did not show it")
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
                import time as _t
                if _t.time() < _paused.get("commons", 0):
                    errors.append("commons: paused (rate-limited)")
                    continue
                try:
                    cands = _commons(query, kind, width)
                except Exception as exc:  # noqa: BLE001
                    if "429" in str(exc):   # rate-limited: skip Wikimedia for a while instead of waiting on every search
                        _paused["commons"] = _t.time() + 600
                        log("   Wikimedia Commons is rate-limiting this machine: using the other sources for 10 minutes")
                    raise
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

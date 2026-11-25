"""Check that a stock photo or clip really shows what the narration says, before it is used.

Text search alone is not enough (a caption saying "seal" can sit on any seal, in a zoo pool, on a temperate
beach...). Every candidate is shown to CLIP, an open image-text model, together with the wanted description and
a set of look-alikes it must beat:

  animals   the most-observed OTHER species of the same family (iNaturalist): a "leopard seal" photo must look
            more like a leopard seal than a harbour, Weddell or crabeater seal
  always    a zoo or aquarium, a drawing/illustration, a map or text, a museum specimen, people
  places    contrasting landscapes (tropical beach, green coast, forest, desert, city, indoor room...)

A candidate is used only if the wanted description wins clearly; otherwise the next result is tried, and if no
result passes, the scene's fallback visual is used. Results are cached. YTAUTO_VERIFY=0 turns it off.
"""
from __future__ import annotations

import json
import os
import re
import threading
from functools import lru_cache
from pathlib import Path

from .utils import log, stable_hash, warn

_WORKERS = Path(__file__).resolve().parent / "tts_workers"
_lock = threading.Lock()
_worker = None
_disabled_reason: str | None = None

ALWAYS_NEG = [
    "an animal in a zoo enclosure or an aquarium tank",
    "a drawing, cartoon or illustration",
    "a map, chart, diagram or text",
    "a stuffed museum specimen, skeleton or skull",
    "people posing for a photo",
]
PLACE_NEG = [
    "a tropical beach with palm trees", "a green grassy coastline with trees", "a dense green forest",
    "a sandy desert", "a city street with buildings", "an indoor room", "a farm field",
]
ANIMAL_RANKS = ("family", "order")


def enabled() -> bool:
    return os.environ.get("YTAUTO_VERIFY", "1") != "0" and _disabled_reason is None


def _clip():
    global _worker
    from .tts import _Worker
    if _worker is None:
        _worker = _Worker("CLIP image check", os.environ.get("YTAUTO_CLIP_PYTHON", os.environ.get("YTAUTO_QWEN_PYTHON", "/opt/tts-qwen/bin/python")),
                          str(_WORKERS / "clip_worker.py"))
    return _worker


def shutdown() -> None:
    if _worker is not None:
        _worker.stop()


def _words(text: str) -> set[str]:
    return {w.rstrip("s") for w in re.findall(r"[a-z]+", (text or "").lower()) if len(w) > 2}


@lru_cache(maxsize=256)
def lookalikes(query: str) -> tuple[str, ...]:
    """Other species a photo of `query` could be confused with (same family on iNaturalist), most common first."""
    try:
        from .stock import _inat_get, _inat_taxon
        import urllib.parse
        tx, _ = _inat_taxon(query)
        if not tx:   # no exact species: a group whose whole name is in the query ("fur seal" in "fur seal mother")
            lo = _loose_animal(query)
            if lo and _names_fit(lo, query):
                tx = lo
        if not tx:
            return ()
        full = _inat_get(f"https://api.inaturalist.org/v1/taxa/{tx['id']}").get("results", [{}])[0]
        ancestors = full.get("ancestors") or []
        names: list[str] = []
        me = {(tx.get("preferred_common_name") or "").lower(), (tx.get("name") or "").lower()}
        # the same family, then the group just above it (e.g. all seals and sea lions), so a photo has to beat
        # close relatives AND cousins that look alike
        fam_i = next((i for i, a in enumerate(ancestors) if a.get("rank") == "family"), None)
        levels = []
        if fam_i is not None:
            levels.append(ancestors[fam_i])
            if fam_i > 0 and ancestors[fam_i - 1].get("rank") not in ("class", "phylum", "kingdom"):
                levels.append(ancestors[fam_i - 1])
        elif ancestors:
            levels.append(ancestors[-1])
        for a in levels:
            q = urllib.parse.urlencode({"taxon_id": a["id"], "per_page": 12, "quality_grade": "research"})
            for r in _inat_get(f"https://api.inaturalist.org/v1/observations/species_counts?{q}").get("results", []):
                t = r.get("taxon") or {}
                nm = (t.get("preferred_common_name") or t.get("name") or "").strip()
                if nm and nm.lower() not in me and nm.lower() not in (n.lower() for n in names) and t.get("id") != tx["id"]:
                    names.append(nm)
        return tuple(names[:16])
    except Exception as exc:  # noqa: BLE001 — offline: fall back to the generic look-alikes
        warn(f"look-alike species for '{query}' unavailable: {exc}")
        return ()


ANIMAL_ICONIC = {"Animalia", "Mammalia", "Aves", "Reptilia", "Amphibia", "Actinopterygii", "Mollusca", "Arachnida",
                 "Insecta"}


def _is_animal(query: str) -> bool:
    """Does the query name an animal? (an exact species/group, or a loose match whose whole name is in the query)"""
    from .stock import _inat_taxon
    try:
        tx, _ = _inat_taxon(query)
    except Exception:  # noqa: BLE001
        return False
    if tx and tx.get("iconic_taxon_name") in ANIMAL_ICONIC or lookalikes(query):
        return True
    lo = _loose_animal(query)
    return bool(lo and _names_fit(lo, query))


def _names_fit(tx: dict, query: str) -> bool:
    """The taxon's whole name is in the query, or the query's first two words are in the taxon's name
    ("fur seal mother" ~ "Fur Seals and Sea Lions"; but "antarctic sea ice" !~ "Antarctic Krill")."""
    from .stock import _DETAIL
    names = [tx.get("preferred_common_name") or "", tx.get("matched_term") or ""]
    qw = _words(query)
    for n in names:
        nw = _words(n)
        # a one-word name only counts if the rest of the query is detail words ("orca teeth"), not a place
        # ("Sahara desert", "Amazon rainforest" and "Roman empire" all have a fish or parrot alias)
        if nw and nw <= qw and (len(nw) >= 2 or (qw - nw) <= _DETAIL):
            return True
    # looser: a GROUP (family, genus…) whose name starts with the query's first words ("Fur Seals and Sea Lions")
    stem = lambda t: [w.rstrip("s") for w in re.findall(r"[a-z]+", t.lower())]
    head = stem(query)[:2]
    group = tx.get("rank") not in ("species", "subspecies", "variety", "form")
    return group and any(stem(n)[:len(head)] == head for n in names if n)


def _loose_animal(query: str) -> dict | None:
    """No exact species in the query ("fur seal mother"): the best animal match for its leading words
    (e.g. a fur seal genus), used only to find look-alikes."""
    import urllib.parse
    from .stock import _inat_get
    words = query.split()
    for n in range(len(words), 0, -1):
        sub = " ".join(words[:n])
        data = _inat_get("https://api.inaturalist.org/v1/taxa/autocomplete?" + urllib.parse.urlencode({"q": sub, "per_page": 3}))
        for tx in data.get("results", []):
            if tx.get("iconic_taxon_name") in ANIMAL_ICONIC and _words(sub) & _words(
                    f"{tx.get('matched_term')} {tx.get('preferred_common_name')}"):
                return tx
    return None


def prompts(query: str, wanted: str | None = None, trusted: bool = False) -> tuple[str, list[str]]:
    """(wanted description, look-alikes to beat) for a stock query. `trusted`: the species is already confirmed
    by experts (iNaturalist research grade), so only the kind of picture and the scene are checked: CLIP can't
    reliably tell close relatives apart (fur seal vs sea lion), experts can."""
    pos = wanted or f"a photo of {query}"
    qw = _words(pos)
    negs = [] if trusted else [f"a photo of a {n.lower()}" for n in lookalikes(query)]
    negs += ALWAYS_NEG
    if not lookalikes(query) or wanted:   # a place/scene, or a described setting: rule out the wrong setting
        negs += PLACE_NEG
    # never use a look-alike that is really the same thing as what we want, or a kind of it
    # ("California sea lion" is not a rival of "sea lion"; "harbor seal" IS a rival of "leopard seal")
    subj = _words(" ".join(re.findall(r"[a-z]+", query.lower())[:3])) & _words(" ".join(lookalikes(query)) + " " + query)
    from .stock import _subject
    core = {w for w in _subject(query)} or subj
    negs = [n for n in negs if not (_words(n) - {"photo"}) <= qw and not (core and core <= _words(n))]
    return pos, negs


def _memo_path(cache: Path) -> Path:
    return cache / "stock" / "verify.json"


def check(image: Path, query: str, cache: Path, wanted: str | None = None, trusted: bool = False) -> tuple[bool, str]:
    """Does `image` show `query` (or `wanted`)? Returns (ok, reason). `trusted` = species already confirmed by
    the source (iNaturalist research grade): only a clear look-alike or wrong scene rejects it."""
    global _disabled_reason
    if not enabled():
        return True, "check off"
    r = _judge(image, query, cache, wanted, trusted)
    return r["ok"], r["reason"]


# Question 1: is this a real camera photograph / footage at all?
# (two wordings, calibrated on known good/bad photos and clips: real photos score >= 0.23 on the better of the
#  two, data maps and cartoons 0.00)
KIND_A = ["a photograph", "a map or a chart with a colour legend", "a cartoon or animated illustration",
          "a screenshot of a computer screen or a presentation slide"]
KIND_B = ["a real-world photo of nature", "a scientific data map or graph", "a cartoon, drawing or computer animation",
          "a computer screenshot"]
KIND_MIN = 0.12
# Question 3 (animals only): wild, or kept by people? (wild photos >= 0.84, pool/aquarium shots <= 0.01)
WILD = ["an animal outdoors in nature, on rocks, ice, sand, grass or in the open sea",
        "an animal in a man-made tank or pool with smooth blue walls, or behind a zoo fence"]
WILD_MIN = 0.5
KIND = KIND_A


def _judge(image: Path, query: str, cache: Path, wanted: str | None, trusted: bool) -> dict:
    """All three questions for one image (cached): kind, subject, wild. Returns {ok, reason, kind, subject, wild}."""
    global _disabled_reason
    pos, negs = prompts(query, wanted, trusted)
    animal = _is_animal(query)
    key = stable_hash("verify-v6", str(image), image.stat().st_size, pos, negs, trusted, animal)
    memo_file = _memo_path(cache)
    with _lock:
        memo = json.loads(memo_file.read_text()) if memo_file.exists() else {}
    if key in memo:
        return memo[key]
    groups = [KIND_A, KIND_B, [pos, *negs]] + ([WILD] if animal else [])
    try:
        res = _clip().run({"images": [str(image)], "groups": groups})
    except Exception as exc:  # noqa: BLE001
        _disabled_reason = str(exc)
        warn(f"photo check unavailable ({exc}); using text matching only")
        return {"ok": True, "reason": "check unavailable", "kind": 1.0, "subject": 1.0, "wild": 1.0}
    kind = max(res["groups"][0][0][0], res["groups"][1][0][0])
    probs = res["groups"][2][0]
    wild = res["groups"][3][0][0] if animal else 1.0
    best = max(range(len(probs)), key=lambda i: probs[i])
    p = probs[0]
    need = 0.25 if trusted else 0.45
    subject_ok = best == 0 and p >= need or (trusted and p >= 0.5)
    if kind < KIND_MIN:
        k2 = max(range(1, len(KIND_B)), key=lambda i: res["groups"][1][0][i])
        reason = f"not a real photo: looks like {KIND_B[k2]} ({res['groups'][1][0][k2]:.0%})"
    elif animal and wild < WILD_MIN:
        reason = f"captive animal (zoo/aquarium/pool, {1 - wild:.0%})"
    elif not subject_ok:
        reason = (f"not sure enough it shows '{pos}' ({p:.0%})" if best == 0 else
                  f"looks more like '{([pos] + negs)[best]}' ({probs[best]:.0%}) than '{pos}' ({p:.0%})")
    else:
        reason = f"matches ({p:.0%}; real photo {kind:.0%}" + (f"; wild {wild:.0%})" if animal else ")")
    out = {"ok": kind >= KIND_MIN and (not animal or wild >= WILD_MIN) and subject_ok, "reason": reason,
           "kind": round(kind, 3), "subject": round(p, 3), "wild": round(wild, 3), "subject_ok": subject_ok}
    with _lock:
        memo = json.loads(memo_file.read_text()) if memo_file.exists() else {}
        memo[key] = out
        memo_file.parent.mkdir(parents=True, exist_ok=True)
        memo_file.write_text(json.dumps(memo))
    return out


def check_video(clip: Path, query: str, cache: Path, wanted: str | None = None) -> tuple[bool, str]:
    """A clip passes only if EVERY sampled frame (15/35/50/65/85 %) is real footage (no maps, charts, cartoons) and,
    for animals, wild; and the subject is shown in at least 4 of the 5 frames."""
    import subprocess
    from .utils import ffprobe_duration
    d = ffprobe_duration(clip)
    rs = []
    for k, f in enumerate((0.15, 0.35, 0.5, 0.65, 0.85)):
        frame = clip.with_name(f"{clip.stem}.v{k}.jpg")
        if not frame.exists():
            subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{d * f:.2f}", "-i", str(clip), "-frames:v", "1",
                            "-vf", "scale=640:-2", str(frame)], check=False)
        if frame.exists():
            rs.append(_judge(frame, query, cache, wanted, False))
    if not rs:
        return False, "no frames"
    bad = [r for r in rs if r["kind"] < KIND_MIN or r["wild"] < WILD_MIN]
    if bad:
        return False, bad[0]["reason"]
    hits = sum(1 for r in rs if r["subject_ok"])
    if hits < max(1, len(rs) - 1):
        return False, f"subject seen in only {hits} of {len(rs)} frames ({rs[0]['reason']})"
    return True, f"all {len(rs)} frames real footage, subject in {hits}"

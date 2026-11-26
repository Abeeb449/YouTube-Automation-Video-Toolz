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


# Question 4: the details the search words describe. A picture of the right subject in the wrong scene is still a
# mismatch ("a colony on rocks" must not be one animal on sand; "lying on ice" must not be swimming in the surf).
# Each group is a set of alternatives that exclude each other; when the description names one (or more) of them,
# the picture must look like those rather than the others. Calibrated on real wildlife photos: right scenes score
# >= 0.48 for the place and >= 0.8 for the count; wrong ones <= 0.2.
DETAILS: dict[str, list[tuple[str, str, str]]] = {
    "place": [
        ("ice", r"\b(ice|icy|icebergs?|floes?|snow\w*|glaciers?|frozen)\b", "a photo taken on ice or snow"),
        ("sand", r"\b(sand\w*|dunes?)\b", "a photo taken on a sandy beach"),
        ("rocks", r"\b(rock\w*|boulders?|cliffs?|pebbl\w*|stones?)\b", "a photo taken on rocks or a rocky shore"),
        ("underwater", r"\b(underwater|beneath the surface|below the surface|div(?:e|es|ing)|seabed|sea floor|reef)\b",
         "a photo taken underwater, below the surface"),
        ("water", r"\b(swim\w*|in (?:the )?(?:water|sea|ocean|river|lake|surf)|at the surface|waves?)\b",
         "a photo of something swimming in the water"),
        ("grass", r"\b(grass\w*|meadows?|savanna\w*|fields?)\b", "a photo taken on grass"),
        ("forest", r"\b(forests?|jungle|woods|rainforest|trees?)\b", "a photo taken among trees in a forest"),
        ("city", r"\b(city|cities|streets?|town|urban|buildings?|skyline|harbou?r|marina|port)\b",
         "a photo taken in a town or city with buildings"),
        ("indoors", r"\b(indoors?|inside|room|lab(?:oratory)?|museum|kitchen|office|factory)\b", "a photo taken indoors"),
        ("sky", r"\b(flying|in flight|soaring|in the sky|mid-air)\b", "a photo of something flying in the sky"),
        ("mountains", r"\b(mountains?|peaks?|alpine|summit)\b", "a photo taken in the mountains"),
        ("desert", r"\b(deserts?)\b", "a photo taken in a desert"),
    ],
    "count": [
        ("many", r"\b(colony|colonies|many|crowd\w*|hundreds|thousands|herds?|flocks?|packs?|schools?|swarms?|groups?|"
                 r"dozens|packed|gathering)\b", "a photo of a large group of many together"),
        ("single", r"\b(single|alone|lone|solitary)\b", "a photo of just a single one, alone"),
        ("pair", r"\b(two|pair|couple|mother and (?:her )?(?:pup|cub|calf|chick|baby|young))\b", "a photo of exactly two"),
    ],
    "time": [
        ("night", r"\b(night|at night|moonlit|starry|after dark)\b", "a photo taken at night in the dark"),
        ("day", r"\b(daylight|daytime|sunny|sunlit)\b", "a photo taken in daylight"),
    ],
    "view": [
        ("aerial", r"\b(aerial|from above|drone|bird'?s[- ]eye|satellite view)\b", "an aerial photo taken from high above"),
        ("closeup", r"\b(close[- ]?ups?|macro|portrait)\b", "a close-up photo"),
        ("wide", r"\b(wide (?:shot|view)|landscape|panoram\w*|vista)\b", "a wide landscape photo"),
    ],
}
DETAIL_MIN = {"place": 0.35, "count": 0.7, "time": 0.5, "view": 0.45}
# Question 5: nothing graphic. Wildlife sources hold kills, carcasses and skeletons; none of that goes in a video
# (calibrated on wildlife and on objects/places: ordinary pictures >= 0.67, kills / remains <= 0.02, borderline 0.5).
CLEAN = ["a pleasant wildlife photo", "an ordinary photo of an object, a machine, a vehicle, a building or a place",
         "a photo of people", "a gory photo of a predator eating bloody prey",
         "a photo of a dead animal, a carcass, a skeleton or animal remains"]
CLEAN_OK = 3      # the first three are fine; the rest are what is kept out
CLEAN_MIN = 0.6


def _details(text: str, drop: tuple[str, ...] = ()) -> dict[str, list[int]]:
    """Which alternatives of each DETAILS group the description names: {"place": [0], "count": [0]}."""
    t = " " + text.lower() + " "
    for w in drop:                       # the subject's own name is not a detail ("mountain lion", "rock hyrax")
        t = re.sub(rf"\b{re.escape(w)}s?\b", " ", t)
    out: dict[str, list[int]] = {}
    for group, members in DETAILS.items():
        hit = [i for i, (_k, pat, _p) in enumerate(members) if re.search(pat, t)]
        if group == "place" and not hit and re.search(r"\b(beach\w*|shore\w*|coast\w*)\b", t):
            hit = [1, 2, 4]              # a beach or shore: sand, rocks or the water's edge all fit
        if hit:
            out[group] = hit
    return out


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
    # needs two matching words: "fur seal" ~ "Fur Seals and Sea Lions", but "pyramid" !~ "Pyramid Snails"
    return group and len(head) >= 2 and any(stem(n)[:len(head)] == head for n in names if n)


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
# Question 2b (every topic but animals): baseline descriptions of "any picture at all"
BASE = ["a photo", "a photo of something", "a picture", "an image"]
MARGIN_MIN = 0.06
USE_S = 10.0          # seconds of a stock video that are checked closely and used
MAX_VIDEO_S = 1200.0  # longer than 20 min: a live stream or a full programme, not b-roll


def _judge(image: Path, query: str, cache: Path, wanted: str | None, trusted: bool) -> dict:
    """All three questions for one image (cached): kind, subject, wild. Returns {ok, reason, kind, subject, wild}."""
    global _disabled_reason
    pos, negs = prompts(query, wanted, trusted)
    animal = _is_animal(query)
    from .stock import _subject
    want_details = _details(wanted or query, _subject(query) if animal else ())
    key = stable_hash("verify-v10", str(image), image.stat().st_size, pos, negs, trusted, animal, want_details)
    memo_file = _memo_path(cache)
    with _lock:
        memo = json.loads(memo_file.read_text()) if memo_file.exists() else {}
    if key in memo:
        return memo[key]
    extra = [("clean", CLEAN)] + [(g, [m[2] for m in DETAILS[g]]) for g in want_details]
    groups = [KIND_A, KIND_B, [pos, *negs], BASE] + ([WILD] if animal else []) + [e[1] for e in extra]
    at = {name: 4 + (1 if animal else 0) + k for k, (name, _g) in enumerate(extra)}
    try:
        res = _clip().run({"images": [str(image)], "groups": groups})
    except Exception as exc:  # noqa: BLE001
        _disabled_reason = str(exc)
        warn(f"photo check unavailable ({exc}); using text matching only")
        return {"ok": True, "reason": "check unavailable", "kind": 1.0, "subject": 1.0, "wild": 1.0,
                "subject_ok": True, "margin": 1.0, "clean": 1.0, "detail_ok": True}
    kind = max(res["groups"][0][0][0], res["groups"][1][0][0])
    probs = res["groups"][2][0]
    wild = res["groups"][4][0][0] if animal else 1.0
    best = max(range(len(probs)), key=lambda i: probs[i])
    p = probs[0]
    need = 0.25 if trusted else 0.45
    subject_ok = best == 0 and p >= need or (trusted and p >= 0.5)
    # How much better does the line's description fit than a description of nothing in particular? A softmax
    # against unrelated scenes says 100% for almost anything; this margin is what separates "the telescope" from
    # "ships in the harbour it arrived at" or "a woman in a cleanroom" (calibrated: right pictures >= 0.06,
    # off-topic ones <= 0.055). Animals already face their look-alikes, so this guards every other topic.
    sims = res["sims"][0]
    i_pos = len(KIND_A) + len(KIND_B)
    i_base = i_pos + 1 + len(negs)
    margin = sims[i_pos] - max(sims[i_base:i_base + len(BASE)])
    general = not animal and not trusted
    if general and subject_ok and margin < MARGIN_MIN:
        subject_ok = False
    clean = sum(res["groups"][at["clean"]][0][:CLEAN_OK])
    detail_ok, detail_why, detail_note = True, "", []
    for g, wanted_idx in want_details.items():
        pr = res["groups"][at[g]][0]
        mass = sum(pr[i] for i in wanted_idx)
        names = " or ".join(DETAILS[g][i][0] for i in wanted_idx)
        if mass < DETAIL_MIN[g]:
            top = max(range(len(pr)), key=lambda i: pr[i])
            detail_ok = False
            detail_why = (f"wrong {g}: the search asks for '{names}', the picture looks like "
                          f"'{DETAILS[g][top][0]}' ({pr[top]:.0%})")
            break
        detail_note.append(f"{names} {mass:.0%}")
    if kind < KIND_MIN:
        k2 = max(range(1, len(KIND_B)), key=lambda i: res["groups"][1][0][i])
        reason = f"not a real photo: looks like {KIND_B[k2]} ({res['groups'][1][0][k2]:.0%})"
    elif clean < CLEAN_MIN:
        reason = f"graphic content (a kill, a carcass or remains): never used ({1 - clean:.0%})"
    elif subject_ok and not detail_ok:
        reason = detail_why
    elif animal and wild < WILD_MIN:
        reason = f"captive animal (zoo/aquarium/pool, {1 - wild:.0%})"
    elif not subject_ok and general and best == 0 and p >= need:
        reason = f"doesn't clearly show '{pos}' (fits it only {margin:+.3f} better than any picture)"
    elif not subject_ok:
        reason = (f"not sure enough it shows '{pos}' ({p:.0%})" if best == 0 else
                  f"looks more like '{([pos] + negs)[best]}' ({probs[best]:.0%}) than '{pos}' ({p:.0%})")
    else:
        reason = (f"matches ({p:.0%}; real photo {kind:.0%}" + (f"; wild {wild:.0%}" if animal else "")
                  + ("; " + ", ".join(detail_note) if detail_note else "") + ")")
    scene_ok = subject_ok and detail_ok and clean >= CLEAN_MIN     # the right thing, in the scene asked for, not graphic
    out = {"ok": kind >= KIND_MIN and (not animal or wild >= WILD_MIN) and scene_ok, "reason": reason,
           "kind": round(kind, 3), "subject": round(p, 3), "wild": round(wild, 3), "subject_ok": scene_ok,
           "margin": round(margin, 3), "clean": round(clean, 3), "detail_ok": detail_ok}
    with _lock:
        memo = json.loads(memo_file.read_text()) if memo_file.exists() else {}
        memo[key] = out
        memo_file.parent.mkdir(parents=True, exist_ok=True)
        memo_file.write_text(json.dumps(memo))
    return out


def best_start(clip: Path) -> float | None:
    """Where the checked good stretch of a stock clip begins (written by check_video), or None."""
    f = clip.with_name(clip.name + ".start.json")
    try:
        return float(json.loads(f.read_text())["start"])
    except Exception:  # noqa: BLE001
        return None


def check_video(clip: Path, query: str, cache: Path, wanted: str | None = None) -> tuple[bool, str]:
    """Stock videos are often long (briefings, explainers, live streams) and only part of them shows the subject.
    1) A coarse scan samples 5-12 frames across the clip. 2) Where the good frames are, a close check samples a
    frame every 2.5 s over the 10 s that will be used; every one must be real footage (no maps, charts,
    cartoons, screenshots), wild for animals, and show the subject. The approved stretch is saved so the video is
    cut from there, never from a title card, an interview or an end slate."""
    import subprocess
    from .utils import ffprobe_duration
    d = ffprobe_duration(clip)
    clip.with_name(clip.name + ".start.json").unlink(missing_ok=True)   # a fresh verdict, never a stale one
    if d > MAX_VIDEO_S:
        return False, f"too long to be b-roll ({d / 60:.0f} min: a stream or a full programme)"

    def frame_at(t: float, tag: str) -> dict | None:
        f = clip.with_name(f"{clip.stem}.{tag}.jpg")
        if not f.exists():
            subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{t:.2f}", "-i", str(clip), "-frames:v", "1",
                            "-vf", "scale=640:-2", str(f)], check=False)
        return _judge(f, query, cache, wanted, False) if f.exists() else None

    def good(r: dict | None) -> bool:
        return r is not None and r["kind"] >= KIND_MIN and r["wild"] >= WILD_MIN and r["subject_ok"]

    n = max(5, min(12, int(d / 4)))
    times = [d * (0.03 + 0.94 * (k + 0.5) / n) for k in range(n)]
    rs = [frame_at(t, f"w{k}of{n}") for k, t in enumerate(times)]
    if not any(rs):
        return False, "no frames"
    want = min(USE_S, d * 0.8)
    # candidate starts: each good coarse frame, best (longest run of good neighbours, then strongest match) first
    oks = [k for k, r in enumerate(rs) if good(r)]
    if not oks:
        bad = next((r for r in rs if r is not None), None)
        return False, f"no stretch shows the subject ({bad['reason']})" if bad else "no frames"
    def run_len(k: int) -> int:
        j = k
        while j + 1 < n and good(rs[j + 1]):
            j += 1
        return j - k
    cands = sorted(oks, key=lambda k: (-run_len(k), -(rs[k].get("margin") or 0), k))[:3]
    last = ""
    for k in cands:
        start = max(0.0, min(times[k] - 1.0, d - want))
        checks = [start + x for x in (0.5, 2.5, 5.0, 7.5, 9.5) if x < want]
        rr = [frame_at(t, f"c{int(t * 10)}") for t in checks]
        bad = next((r for r in rr if not good(r)), None)
        if bad is None:
            clip.with_name(clip.name + ".start.json").write_text(json.dumps({"start": round(start, 2), "span": round(want, 1)}))
            return True, f"{want:.0f}s of checked footage from {start:.0f}s ({len(oks)} of {n} scan frames good)"
        last = bad["reason"] if bad else "no frame"
    return False, f"no {want:.0f}s stretch shows the subject throughout ({last})"


MODEL_BASE = ["a 3D model", "a 3D render of an object", "an object", "a picture"]
MODEL_MIN = 0.04     # calibrated: the right model >= 0.07 over the baseline, a different object <= 0.03


def check_model(frame: Path, query: str, cache: Path) -> tuple[bool, str]:
    """Is this rendered 3D model the thing that was searched for? (A library title can match by accident:
    a "Moon boot" for "Moon".) The render must fit "a 3D model of <query>" clearly better than "a 3D model"."""
    if not enabled():
        return True, "check off"
    global _disabled_reason
    from PIL import Image
    try:
        im = Image.open(frame).convert("RGBA")
        box = im.getchannel("A").point(lambda v: 255 if v > 24 else 0).getbbox() or (0, 0, im.width, im.height)
        flat = Image.new("RGB", im.size, (120, 124, 130))
        flat.paste(im, (0, 0), im)
        flat = flat.crop((max(0, box[0] - 40), max(0, box[1] - 40), min(im.width, box[2] + 40), min(im.height, box[3] + 40)))
        tmp = cache / "models" / f"check_{stable_hash(str(frame), query)}.jpg"
        tmp.parent.mkdir(parents=True, exist_ok=True)
        flat.save(tmp, quality=90)
        res = _clip().run({"images": [str(tmp)], "texts": [f"a 3D model of {query}", *MODEL_BASE]})
    except Exception as exc:  # noqa: BLE001
        _disabled_reason = str(exc)
        warn(f"3D model check unavailable ({exc})")
        return True, "check unavailable"
    sims = res["sims"][0]
    margin = sims[0] - max(sims[1:])
    return margin >= MODEL_MIN, (f"matches ({margin:+.3f})" if margin >= MODEL_MIN else
                                 f"doesn't look like '{query}' (fits it only {margin:+.3f} better than any 3D model)")


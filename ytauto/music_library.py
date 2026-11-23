"""Real background music, picked automatically per scene mood.

Sources
-------
incompetech Kevin MacLeod's 1,400+ cinematic/ambient pieces (incompetech.com), CC BY 4.0, chosen by
            their "feel" tags (Dark, Mysterious, Suspenseful, Calming…). Widely used on YouTube and not
            registered with Content ID. Credit is added to description.txt automatically. (default)
openverse   Searches Openverse (WordPress.org's open media search: Jamendo, Freesound, Wikimedia…)
            for tracks licensed CC0 / Public Domain / CC BY only — all allowed in monetised videos.
            CC BY requires credit: ytauto appends a "Music:" credits block to description.txt.
library     A folder you fill once (e.g. from the YouTube Audio Library): one sub-folder per mood
            (wonder/ mystery/ danger/ tension/ calm/) with MP3/WAV files. Picked automatically.

Tracks are looped/trimmed to each mood section and crossfaded, then ducked under the narrator
exactly like the generated score.
"""
from __future__ import annotations

import json
import random
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path

from .stock import download
from .utils import YtautoError, log, run, stable_hash, warn

UA = {"User-Agent": "ytauto/1.0 (open-source video tool)"}
AUDIO_EXT = {".mp3", ".wav", ".m4a", ".ogg", ".flac", ".aac"}

MOOD_QUERIES = {
    "wonder": ["ambient cinematic", "ethereal ambient", "beautiful ambient", "atmospheric"],
    "mystery": ["mysterious ambient", "dark ambient", "deep ambient drone"],
    "danger": ["dark suspense", "horror ambient", "dark drone"],
    "tension": ["suspense", "tension cinematic", "thriller"],
    "calm": ["calm ambient", "peaceful ambient", "relaxing ambient piano"],
}
SAFE_LICENSES = {"cc0", "pdm", "by"}  # no NC (non-commercial), no ND, no SA (share-alike would bind the video)


@dataclass
class Track:
    path: str
    title: str
    creator: str
    license: str
    license_version: str
    source: str
    landing: str

    def credit(self) -> str:
        if self.source == "incompetech":
            return (f"♪ \"{self.title}\" Kevin MacLeod (incompetech.com)\n"
                    "   Licensed under Creative Commons: By Attribution 4.0 License — http://creativecommons.org/licenses/by/4.0/")
        lic = "Public Domain (CC0)" if self.license in ("cc0", "pdm") else f"CC BY {self.license_version}".strip()
        return f"♪ \"{self.title}\" by {self.creator} ({lic}) — {self.landing}"


def _get(url: str) -> dict:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def openverse_tracks(mood: str, cache: Path, want: int = 2, seed: int = 0, extra_query: str | None = None) -> list[Track]:
    """Find and download up to `want` commercially-usable tracks for a mood (cached in cache/music)."""
    index_file = cache / "music" / f"openverse_{mood}_{stable_hash(extra_query, want, seed)}.json"
    if index_file.exists():
        tracks = [Track(**t) for t in json.loads(index_file.read_text())]
        if all(Path(t.path).exists() for t in tracks):
            return tracks
    queries = ([extra_query] if extra_query else []) + MOOD_QUERIES.get(mood, MOOD_QUERIES["wonder"])
    candidates: list[dict] = []
    for q in queries:
        params = urllib.parse.urlencode({"q": q, "license": "cc0,by,pdm", "page_size": 20, "mature": "false"})
        try:
            data = _get(f"https://api.openverse.org/v1/audio/?{params}")
        except Exception as exc:  # noqa: BLE001
            raise YtautoError(f"Openverse search failed: {exc}") from exc
        for r in data.get("results", []):
            dur = (r.get("duration") or 0) / 1000
            # 45 s – 6 min: long enough to loop nicely, short enough to download quickly
            if r.get("license") not in SAFE_LICENSES or not (45 <= dur <= 360) or not r.get("url"):
                continue
            title = (r.get("title") or "").lower()
            if any(w in title for w in ("voice", "speech", "talk", "vocal", "scream", "podcast")):
                continue
            # prefer real music (Jamendo) and longer pieces
            r["_score"] = (2 if r.get("source") == "jamendo" else 1) + min(dur, 300) / 300
            candidates.append(r)
        if len(candidates) >= want * 4:
            break
    if not candidates:
        raise YtautoError(f"no commercially-usable tracks found for mood '{mood}'")
    seen, uniq = set(), []
    for c in sorted(candidates, key=lambda c: -c["_score"]):
        if c["id"] not in seen:
            seen.add(c["id"])
            uniq.append(c)
    rng = random.Random(seed + hash(mood) % 1000)
    pool = uniq[: max(want * 3, 6)]
    rng.shuffle(pool)
    tracks: list[Track] = []
    for r in pool:
        if len(tracks) >= want:
            break
        dst = cache / "music" / "openverse" / f"{r['source']}_{stable_hash(r['id'])}.mp3"
        try:
            if not dst.exists():
                log(f"   downloading music: \"{r.get('title')}\" by {r.get('creator')} ({r.get('license')}, {r.get('source')})")
            download(r["url"], dst)
            run(["ffprobe", "-v", "error", dst])  # make sure it's real audio
        except Exception as exc:  # noqa: BLE001
            warn(f"skipping track {r.get('title')!r}: {exc}")
            dst.unlink(missing_ok=True)
            continue
        tracks.append(Track(str(dst), r.get("title") or "Untitled", r.get("creator") or "Unknown", r["license"],
                            r.get("license_version") or "", r.get("source") or "", r.get("foreign_landing_url") or r["url"]))
    if not tracks:
        raise YtautoError(f"could not download any track for mood '{mood}'")
    index_file.parent.mkdir(parents=True, exist_ok=True)
    index_file.write_text(json.dumps([asdict(t) for t in tracks]))
    return tracks


def library_tracks(folder: Path, mood: str) -> list[Track]:
    """Tracks from a local folder: <folder>/<mood>/*.mp3, falling back to files directly in <folder>."""
    for d in (folder / mood, folder):
        if d.is_dir():
            files = sorted(p for p in d.iterdir() if p.suffix.lower() in AUDIO_EXT)
            if files:
                return [Track(str(p), p.stem, "", "own", "", "library", "") for p in files]
    return []


def _mean_db(path: Path) -> float:
    out = run(["ffmpeg", "-v", "info", "-i", path, "-af", "volumedetect", "-f", "null", "-"])
    for line in out.splitlines():
        if "mean_volume:" in line:
            return float(line.split("mean_volume:")[1].split("dB")[0])
    return -20.0


def assemble(total: float, segments: list[tuple[float, float, str]], pick, out: Path, xfade: float = 4.0) -> tuple[Path, list[Track]]:
    """Build one bed: each mood section gets a track (looped/trimmed), sections crossfade into each other.
    `pick(mood, occurrence)` returns a Track or None (→ silence for that section)."""
    work = out.parent / f".{out.stem}_parts"
    work.mkdir(parents=True, exist_ok=True)
    parts: list[Path] = []
    used: list[Track] = []
    counts: dict[str, int] = {}
    for i, (a, b, mood) in enumerate(segments):
        dur = (b - a) + (xfade if i < len(segments) - 1 else 0)
        part = work / f"part_{i:03d}.wav"
        tr = pick(mood, counts.get(mood, 0)) if mood != "none" else None
        counts[mood] = counts.get(mood, 0) + 1
        if tr is None:
            run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-t", f"{dur:.3f}", part])
        else:
            if tr not in used:
                used.append(tr)
            # Steady level per track: one static gain from the track's average loudness (a dynamic normaliser
            # "pumps" quiet intros and makes sudden loud entries), then soft fades so sections never jump in.
            tmp = part.with_suffix(".raw.wav")
            run(["ffmpeg", "-y", "-v", "error", "-stream_loop", "-1", "-ss", "2", "-i", tr.path, "-t", f"{dur:.3f}",
                 "-af", "aresample=48000,aformat=channel_layouts=stereo", "-ar", "48000", tmp])
            gain = max(-12.0, min(12.0, -22.0 - _mean_db(tmp)))
            run(["ffmpeg", "-y", "-v", "error", "-i", tmp, "-af",
                 f"volume={gain:.2f}dB,afade=t=in:d=2.5,afade=t=out:st={max(0.0, dur - 2.5):.3f}:d=2.5", part])
            tmp.unlink(missing_ok=True)
        parts.append(part)
    if len(parts) == 1:
        run(["ffmpeg", "-y", "-v", "error", "-i", parts[0], "-af",
             "acompressor=threshold=-26dB:ratio=3:attack=150:release=1200:makeup=1,alimiter=limit=0.35", out])
    else:
        inputs, chain = [], ""
        for p in parts:
            inputs += ["-i", p]
        prev = "[0:a]"
        for i in range(1, len(parts)):
            lab = f"[x{i}]"
            chain += f"{prev}[{i}:a]acrossfade=d={xfade}:c1=tri:c2=tri{lab};"
            prev = lab
        # glue: gentle compression + a limiter so no hit or swell ever jumps out from under the narration
        chain += f"{prev}acompressor=threshold=-26dB:ratio=3:attack=150:release=1200:makeup=1,alimiter=limit=0.35:attack=20:release=400[bed]"
        run(["ffmpeg", "-y", "-v", "error", *inputs, "-filter_complex", chain, "-map", "[bed]", "-t", f"{total + 1:.3f}", out])
    for p in parts:
        p.unlink(missing_ok=True)
    work.rmdir()
    return out, used


# ---------------------------------------------------------------- Incompetech (Kevin MacLeod, CC BY 4.0)
INCOMPETECH_INDEX = "https://incompetech.com/music/royalty-free/pieces.json"
INCOMPETECH_MP3 = "https://incompetech.com/music/royalty-free/mp3-royaltyfree/"
# mood → (feel tags to match, how many must match)
# mood → (feel tags to match, how many must match, feel tags that MUST be present (any of))
INCOMPETECH_RULES = {
    "wonder": ({"mystical", "uplifting", "calming", "somber", "mysterious"}, 2, {"mystical"}),
    "mystery": ({"mysterious", "eerie", "mystical", "dark", "somber"}, 2, {"mysterious"}),
    "danger": ({"dark", "unnerving", "eerie", "suspenseful", "intense"}, 2, {"dark"}),
    "tension": ({"suspenseful", "intense", "unnerving", "eerie"}, 2, {"suspenseful"}),
    "calm": ({"calming", "relaxed", "somber", "mystical"}, 2, {"mystical", "somber"}),
    "epic": ({"epic", "intense", "dark"}, 2, {"epic"}),
}
# Documentary beds shouldn't sound cheerful, folksy or comedic.
INCOMPETECH_AVOID = {"grooving", "bouncy", "humorous", "ren faire", "medieval", "aggressive", "bright", "driving", "action"}
# Beds sit under narration: no drum kits, booms or vocals that punch through the voice.
PERCUSSION = ("drum", "percussion", "timpani", "taiko", "cymbal", "snare", "kick", "vocal", "choir", "beat")
TITLE_AVOID = ("funeral", "porch", "sunny", "happy", "christmas", "party", "wedding", "comedy", "circus", "carnival",
               "dance", "disco", "jazz", "blues", "rock", "polka", "waltz", "march", "lullaby", "kids", "cartoon")


def _feels(p: dict) -> set[str]:
    return {f.strip().lower() for f in (p.get("feel") or "").split(",") if f.strip()}


def _secs(p: dict) -> int:
    try:
        h, m, sec = (p.get("length") or "0:0:0").split(":")
        return int(h) * 3600 + int(m) * 60 + int(sec)
    except ValueError:
        return 0


def incompetech_tracks(mood: str, cache: Path, want: int = 2, seed: int = 0, avoid: set[str] | None = None) -> list[Track]:
    idx = cache / "music" / "incompetech_pieces.json"
    idx.parent.mkdir(parents=True, exist_ok=True)
    if not idx.exists() or idx.stat().st_size < 1000:
        download(INCOMPETECH_INDEX, idx)
    pieces = json.loads(idx.read_text())
    want_feels, k, must = INCOMPETECH_RULES.get(mood, INCOMPETECH_RULES["wonder"])
    avoid_feels = INCOMPETECH_AVOID - ({"intense", "action", "driving"} & want_feels)
    cands = [p for p in pieces if len(_feels(p) & want_feels) >= k and _feels(p) & must and not _feels(p) & avoid_feels
             and not any(w in (p.get("title") or "").lower() for w in TITLE_AVOID)
             and 90 <= _secs(p) <= 600 and not any(w in (p.get("instruments") or "").lower() for w in PERCUSSION)
             and p.get("filename", "").lower().endswith(".mp3") and p.get("title") not in (avoid or set())]
    if not cands:
        raise YtautoError(f"no Incompetech pieces match mood '{mood}'")
    # strongest matches first, then a seeded shuffle so different videos get different music
    rng = random.Random(f"{mood}-{seed}")
    rng.shuffle(cands)
    cands.sort(key=lambda p: -len(_feels(p) & want_feels))
    pool = cands[: max(12, want * 4)]
    rng.shuffle(pool)
    out: list[Track] = []
    for p in pool:
        if len(out) >= want:
            break
        dst = cache / "music" / "incompetech" / f"{stable_hash(p['filename'])}.mp3"
        try:
            if not dst.exists():
                log(f"   downloading music: \"{p['title']}\" by Kevin MacLeod ({p.get('feel')})")
            download(INCOMPETECH_MP3 + urllib.parse.quote(p["filename"]), dst)
        except Exception as exc:  # noqa: BLE001
            warn(f"skipping {p['title']!r}: {exc}")
            dst.unlink(missing_ok=True)
            continue
        out.append(Track(str(dst), p["title"], "Kevin MacLeod", "by", "4.0", "incompetech",
                         "https://incompetech.com/music/royalty-free/"))
    if not out:
        raise YtautoError(f"could not download Incompetech music for mood '{mood}'")
    return out

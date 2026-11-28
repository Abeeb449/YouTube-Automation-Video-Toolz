"""A narration that sounds like one person reading the whole script in one sitting.

A neural voice records one piece of text at a time. Left to itself it gives every piece its own register, pace and
mood, and when every sentence is a separate recording the listener hears a stop and a fresh start at each one. Two
things here take that away (steady delivery, Qwen voice):

  the narrator's clip   One short clip of the narrator reading the opening of the script in the mood the script
                        calls for (sound_director.steady_mood). It is made once per project, checked, and kept in
                        <project>/voice/. Every later recording is made against it, so pitch, pace and mood stay
                        where the clip put them.
  passages              The scenes of one script paragraph are recorded together in one breath and then cut apart
                        at the sentence ends, in the short silences between sentences. The voice flows through a
                        paragraph the way a reader's does; the scenes still get their own audio and timings.
"""
from __future__ import annotations

import difflib
import json
import math
import re
import shutil
import wave
from pathlib import Path

from . import tts
from .utils import REPO_ROOT, YtautoError, log, stable_hash, warn

ANCHOR_DIR = "voice"
ANCHOR_TAKES = 6             # candidates recorded for the narrator's clip
PASSAGE_WORDS = 48           # a passage read in one breath is at most about this long (roughly 20 seconds)


# ---------------------------------------------------------------------------------------------------- helpers
def _norm(text: str) -> list[str]:
    return re.sub(r"[^a-z0-9 ]", "", text.lower().replace("-", " ")).split()


def _heard(path: Path, hint: str) -> list[dict]:
    """Words with times, as the recogniser hears the recording ([] when it is not available)."""
    wf = path.with_suffix(".words.json")
    wf.unlink(missing_ok=True)
    tts.align_words(hint, path, "auto")
    try:
        return json.loads(wf.read_text())
    except Exception:  # noqa: BLE001
        return []


def _says(heard: list[dict], text: str) -> float:
    """How closely the heard words match the text (1.0 = the same words)."""
    a, b = _norm(text), _norm(" ".join(w["text"] for w in heard))
    return difflib.SequenceMatcher(None, a, b).ratio() if a and b else 0.0


def _write(path: Path, y, sr: int) -> None:
    import numpy as np
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes((np.clip(y, -1.0, 1.0) * 32767.0).astype("<i2").tobytes())


# ------------------------------------------------------------------------------------------ the narrator's clip
def _anchor_text(texts: list[str]) -> str:
    """The opening of the script: whole sentences, about 20 to 32 words (8 to 12 seconds)."""
    sents = [s for t in texts for s in re.split(r"(?<=[.!?])\s+", tts.strip_directives(t).strip()) if s]
    out: list[str] = []
    for s in sents:
        if out and len(" ".join(out + [s]).split()) > 32:
            break
        out.append(s)
        if len(" ".join(out).split()) >= 20:
            break
    return " ".join(out)


def ensure_anchor(project) -> None:
    """Make (once) the clip this project's narration is recorded against, and point the voice at it."""
    st = project.settings
    voice = st.get("voice") or {}
    if (voice.get("engine") != "qwen" or str(voice.get("delivery", "steady")).lower() != "steady"
            or voice.get("reference") or voice.get("anchor") or str(st.get("narration", "natural")).lower() != "natural"):
        return
    folder = project.root / ANCHOR_DIR
    wav, meta = folder / "narrator.wav", folder / "narrator.json"
    try:
        rel = str(wav.resolve().relative_to(REPO_ROOT).with_suffix("")).replace("\\", "/")
    except ValueError:
        rel = str(wav.resolve().with_suffix(""))
    if wav.exists() and meta.exists():
        voice["anchor"] = rel
        st["voice"] = voice
        return
    text = _anchor_text([s.text or "" for s in project.scenes])
    if len(text.split()) < 8:
        return
    instruct = voice.get("instruct") or ""
    log(f"   the narrator's clip: recording {ANCHOR_TAKES} takes of the opening lines "
        f"({voice.get('mood') or 'steady'} mood) and keeping the most even one")
    work = project.cache_dir / "tts" / "anchor"
    work.mkdir(parents=True, exist_ok=True)
    exp = tts.expected_seconds(text)
    rows = []
    for k in range(ANCHOR_TAKES):
        take = work / f"take{k}_{stable_hash(text, instruct, voice.get('name'))[:8]}.wav"
        try:
            if not take.exists():
                tts.synthesize(text, {"engine": "qwen", "name": voice.get("name") or "ryan", "instruct": instruct,
                                      "fluent": False, "seed": 700 + 31 * k}, take)
                tts.level_take(take)
        except YtautoError as exc:
            warn(f"narrator's clip, take {k + 1}: {str(exc)[:120]}")
            continue
        tight = tts.tighten(take, 0.2)
        tone = tts.voice_tone(tight)
        if not tone:
            continue
        rows.append({"file": tight, "hz": tone[0], "swing": tone[1], "pace": tts.ffprobe_duration(tight) / exp,
                     "stall": tts.longest_pause(take), "says": _says(_heard(tight, text), text)})
    ok = [r for r in rows if r["says"] >= 0.9 and r["stall"] <= 0.6]
    if not ok:
        warn("the narrator's clip could not be made (no clean take); the general clip in voices/ is used")
        return
    med_hz = sorted(r["hz"] for r in ok)[len(ok) // 2]
    med_pace = sorted(r["pace"] for r in ok)[len(ok) // 2]

    def score(r: dict) -> float:      # the middle of the road: usual register, usual pace, an even tone
        return (abs(12 * math.log2(r["hz"] / med_hz)) + 4 * abs(math.log(r["pace"] / med_pace))
                + 0.35 * abs(r["swing"] - 5.0) + (1 - r["says"]) * 10)
    best = min(ok, key=score)
    folder.mkdir(parents=True, exist_ok=True)
    tts.run(["ffmpeg", "-y", "-v", "error", "-i", best["file"], "-ar", "24000", "-ac", "1", "-c:a", "pcm_s16le", wav])
    meta.write_text(json.dumps({
        "text": text, "pitch_hz": round(best["hz"], 1), "pace": round(best["pace"], 3),
        "mood": voice.get("mood"), "direction": instruct, "speaker": voice.get("name") or "ryan",
        "about": "The narrator's clip for this video. Every line of the narration is recorded against it, so the "
                 "voice keeps this pitch, pace and mood from start to finish. Delete this folder to make a new one."},
        indent=1), encoding="utf-8")
    log(f"   the narrator's clip: {best['hz']:.0f} Hz, tone moving {best['swing']:.1f} semitones, "
        f"{len(text.split()) / (tts.ffprobe_duration(best['file']) / 60):.0f} words a minute → {wav}")
    voice["anchor"] = rel
    st["voice"] = voice


# ---------------------------------------------------------------------------------------------------- passages
def groups_of(project, inputs: list[tuple]) -> list[list[int]]:
    """Which scenes are read together: consecutive scenes of one script paragraph (scene key `para`; without it,
    consecutive scenes up to the next chapter), never longer than PASSAGE_WORDS."""
    groups: list[list[int]] = []
    cur: list[int] = []
    words = 0
    for i, sc in enumerate(project.scenes):
        n = len((inputs[i][0] or "").split())
        prev = project.scenes[cur[-1]] if cur else None
        same = bool(cur) and (sc.raw.get("para") == prev.raw.get("para") if "para" in sc.raw or "para" in prev.raw
                              else not sc.raw.get("chapter"))
        if cur and same and words + n <= PASSAGE_WORDS and inputs[i][1] == inputs[cur[0]][1] and n and not sc.duration:
            cur.append(i)
            words += n
        else:
            if cur:
                groups.append(cur)
            cur, words = [i], n
    if cur:
        groups.append(cur)
    return groups


def _cuts(whole: Path, sents: list[str], heard: list[dict]) -> list[float] | None:
    """Where one recording of several sentences is cut apart: in the silence after each sentence's last word."""
    import numpy as np
    sr = 16000
    x = tts._decode(whole, sr)
    hop = 160
    n = len(x) // hop
    db = 20 * np.log10(np.sqrt((x[:n * hop].reshape(n, hop) ** 2).mean(axis=1)) + 1e-9)
    script = [w for s in sents for w in _norm(s)]
    got = [_norm(w["text"]) for w in heard]
    flat = [(t, k) for k, ws in enumerate(got) for t in ws]         # a heard word can be two script words ("7 gill")
    sm = difflib.SequenceMatcher(None, script, [t for t, _ in flat], autojunk=False)
    to_heard: dict[int, int] = {}
    for a, b, size in sm.get_matching_blocks():
        for j in range(size):
            to_heard[a + j] = flat[b + j][1]
    if len(to_heard) < 0.8 * len(script):
        return None
    cuts, pos = [], 0
    for s in sents[:-1]:
        pos += len(_norm(s))
        before = next((to_heard[i] for i in range(pos - 1, max(-1, pos - 4), -1) if i in to_heard), None)
        after = next((to_heard[i] for i in range(pos, min(len(script), pos + 3)) if i in to_heard), None)
        if before is None or after is None or after <= before:
            return None
        a, b = float(heard[before]["end"]), float(heard[after]["start"])
        lo, hi = max(0, int((a - 0.25) * 100)), min(n, int((b + 0.25) * 100) + 1)
        if hi - lo < 2:
            return None
        quiet = db[lo:hi] < -40.0
        best, i = None, 0
        while i < len(quiet):                     # the longest silence near the sentence end
            if quiet[i]:
                j = i
                while j < len(quiet) and quiet[j]:
                    j += 1
                if best is None or j - i > best[1] - best[0]:
                    best = (i, j)
                i = j
            else:
                i += 1
        if best is not None and best[1] - best[0] >= 3:
            cut = (lo + (best[0] + best[1]) / 2) / 100.0
        else:                                     # the sentences run together: cut at the quietest point between them
            k0, k1 = max(lo, int(a * 100) - 3), min(hi, int(b * 100) + 4)
            if k1 - k0 < 1:
                return None
            cut = (k0 + int(np.argmin(db[k0:k1])) + 0.5) / 100.0
        if cuts and cut <= cuts[-1] + 0.3:
            return None
        cuts.append(cut)
    return cuts


def record_passages(project, inputs: list[tuple], cache: Path) -> None:
    """Record the scenes of each paragraph in one breath and cut the recording into the scenes' own takes.
    inputs[i] = (text, voice, settings) of scene i, as `tts.narration_inputs` gives them. Scenes whose audio is
    already there (recorded ahead, or an earlier run) are left alone; a passage that cannot be cut cleanly is left
    to the ordinary scene-by-scene recording."""
    import numpy as np
    done_any = 0
    for group in groups_of(project, inputs):
        if len(group) < 2:
            continue
        takes = []
        for i in group:
            text, voice, sst = inputs[i]
            takes.append(tts.scene_take(text, voice, cache, sst, project.scenes[i].duration))
        if any(t is None for t in takes) or all(t[3] or tts._fresh(t[2]) for t in takes):
            continue
        v = takes[0][1]
        if v.get("engine") != "qwen" or not v.get("reference") or not v.get("max_pause") or any(t[1] != v for t in takes):
            continue
        sents = [t[0] for t in takes]
        text = " ".join(sents)
        whole = cache / f"pass_{tts._take_key(v, text)}.wav"
        try:
            if not tts._fresh(whole):
                tts.synthesize(text, v, whole)
                tts.guard_take(text, v, whole)
                if v.get("pitch_hz"):
                    tts.match_pitch(whole, float(v["pitch_hz"]))
                tts.level_take(whole)
        except YtautoError as exc:
            warn(f"passage not recorded in one breath ({str(exc)[:100]}): its scenes are recorded one by one")
            continue
        heard = _heard(whole, text)
        cuts = _cuts(whole, sents, heard) if heard and _says(heard, text) >= 0.85 else None
        if cuts is None:
            warn(f"passage could not be cut at its sentence ends; its scenes are recorded one by one: {text[:70]}")
            continue
        sr = tts.SAMPLE_RATE
        x = tts._decode(whole, sr).copy()
        fade = int(sr * 0.005)
        edges = [0.0] + cuts + [len(x) / sr]
        for (sent, _v, raw, _done), a, b in zip(takes, edges, edges[1:]):
            piece = x[int(a * sr):int(b * sr)].copy()
            if len(piece) > 2 * fade:
                piece[:fade] *= np.linspace(0.0, 1.0, fade)
                piece[-fade:] *= np.linspace(1.0, 0.0, fade)
            for old in raw.parent.glob(raw.stem + "*"):       # timings of an earlier take must not be reused
                old.unlink()
            _write(raw, piece, sr)
        done_any += 1
    if done_any:
        log(f"   {done_any} passage(s) recorded in one breath and cut into their scenes")

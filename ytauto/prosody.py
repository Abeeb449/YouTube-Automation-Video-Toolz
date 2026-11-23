"""Natural phrasing for neural narration.

Neural voices (Qwen3-TTS especially) sometimes hesitate in the middle of a phrase ("and the ... leopard seal")
or stretch a word. A person reading a documentary only pauses where the meaning allows it: after a full stop,
at a comma or dash, and occasionally before a big reveal. This module

  1. measures every silence in a take and decides which word boundary it belongs to (via faster-whisper words
     matched back onto the script tokens and their punctuation),
  2. scores the take (mid-phrase hesitations, misread words, speaking rate) so the caller can ask the model
     for another take when it's bad (`analyse` / `score`), and
  3. re-times the pauses of the chosen take (`retime`): mid-phrase gaps shrink to a normal word gap, commas get a
     short breath, sentence ends a full pause. Cuts are made only inside true silence, with short fades, so no
     syllable is ever clipped.

Target pause lengths come from measuring professional narrator samples (see PAUSES); everything is tunable
through `settings.voice_polish`.
"""
from __future__ import annotations

import difflib
import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .utils import run, stable_hash, warn

SR = 16000
FRAME = 0.01  # 10 ms analysis frames

# Pause targets (seconds) by boundary type: (min, max). Measured from studio narrator reads: word gaps inside a
# phrase are nearly always < 0.1 s, commas 0.15-0.35 s, sentence ends 0.35-0.7 s.
PAUSES = {"word": (0.0, 0.08), "inside": (0.0, 0.07), "clause": (0.0, 0.42), "sentence": (0.3, 0.65)}
STOP_CLOSURE = 0.14
_DROP = 21  # dB below the take's speech level that counts as a pause  # silences shorter than this are left alone (stop consonants like the p in "leopard")


@dataclass
class Gap:
    start: float
    end: float
    kind: str        # word | clause | sentence | edge | inside (a pause inside one word: "af ... ter")
    after: str       # the script token before the gap ("" at the start)
    idx: int = -1    # index of that token

    @property
    def dur(self) -> float:
        return self.end - self.start


def load(path: Path) -> "np.ndarray":  # noqa: F821
    import numpy as np
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.float32)


def silences(audio, min_len: float = 0.06) -> list[tuple[float, float]]:
    """Runs of low energy, relative to the take's own loudness (robust to quiet or loud takes)."""
    import numpy as np
    hop = int(SR * FRAME)
    n = len(audio) // hop
    if n == 0:
        return []
    fr = audio[: n * hop].reshape(n, hop)
    db = 20 * np.log10(np.sqrt((fr ** 2).mean(1)) + 1e-9)
    db = np.convolve(db, np.ones(3) / 3, mode="same")          # 30 ms smoothing: ignore single-frame blips
    loud = np.percentile(db, 95)
    # neural voices fill pauses with soft breath/room noise (-40..-55 dBFS), not digital silence
    thr = max(loud - float(_DROP), -52.0)
    quiet = db < thr
    out, i = [], 0
    while i < n:
        if quiet[i]:
            j = i
            while j < n and quiet[j]:
                j += 1
            if (j - i) * FRAME >= min_len:
                out.append((i * FRAME, j * FRAME))
            i = j
        else:
            i += 1
    return out


_NUMWORDS = set("""zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen
seventeen eighteen nineteen twenty thirty forty fifty sixty seventy eighty ninety hundred thousand million billion half
quarter percent per cent and a point""".split())
_UK = {"metres": "meters", "metre": "meter", "kilometres": "kilometers", "kilometre": "kilometer", "litres": "liters",
       "centre": "center", "colour": "color", "behaviour": "behavior", "favourite": "favorite", "grey": "gray"}


def _norm(w: str) -> str:
    w = re.sub(r"[^a-z0-9%]", "", w.lower())
    return _UK.get(w, w)


def _words_only(tokens: list[str]) -> list[str]:
    """Drop numbers in any spelling ("three and a half" vs "3.5") so they never count as misreads."""
    out = []
    for t in tokens:
        for part in re.split(r"-", t):
            n = _norm(part)
            if n and not re.search(r"\d", n) and n not in _NUMWORDS and n != "%":
                out.append(n)
    return out


def _boundary(tok: str) -> str:
    t = tok.rstrip("\"'”’)")
    if re.search(r"[.!?]$", t):
        return "sentence"
    if re.search(r"[,;:—–-]$", t) or t.endswith("..."):
        return "clause"
    return "word"


_model = None


def _whisper():
    global _model
    if _model is None:
        import os
        from faster_whisper import WhisperModel
        _model = WhisperModel(os.environ.get("YTAUTO_WHISPER_MODEL", "base.en"), device="cpu", compute_type="int8",
                              download_root=os.environ.get("YTAUTO_WHISPER_DIR"))
    return _model


def transcribe(audio, prompt: str | None = None):
    segs, _ = _whisper().transcribe(audio, language="en", word_timestamps=True, beam_size=1, vad_filter=False,
                                    initial_prompt=None, condition_on_previous_text=False)
    return [(w.start, w.end, w.word.strip()) for s in segs for w in (s.words or [])]


@dataclass
class Analysis:
    duration: float
    speech: float            # seconds of actual speech (edges excluded)
    gaps: list[Gap]
    wer: float               # word error rate of the take against the script
    words: int
    heard: str

    @property
    def wpm(self) -> float:
        return 60 * self.words / max(self.speech, 0.5)

    def hesitations(self, limit: float = 0.2) -> list[Gap]:
        return [g for g in self.gaps if g.kind in ("word", "inside") and g.dur > limit]

    def score(self) -> float:
        """Lower is better. Mid-phrase pauses dominate, then misreads, then a pace far from ~155 wpm."""
        s = sum(max(0.0, g.dur - 0.12) * 4 for g in self.gaps if g.kind in ("word", "inside"))
        s += sum(max(0.0, g.dur - 0.9) for g in self.gaps if g.kind in ("clause", "sentence"))
        s += self.wer * 6
        s += max(0.0, 130 - self.wpm) / 40 + max(0.0, self.wpm - 185) / 40
        return round(s, 3)

    def ok(self) -> bool:
        """Good enough to keep: no word broken in the middle ("af ... ter") and no misread words. Pauses
        between words are fine here — retime() closes them without touching any sound."""
        broken = [g for g in self.gaps if g.kind == "inside" and g.dur > 0.3]
        return not broken and self.wer <= 0.12

    def summary(self) -> str:
        h = ", ".join(f"{g.after or '^'}·{g.dur:.2f}s" for g in self.hesitations())
        return f"{self.wpm:.0f} wpm, wer {self.wer:.2f}" + (f", mid-phrase pauses: {h}" if h else "")


def analyse(path: Path, text: str) -> Analysis:
    audio = load(path)
    dur = len(audio) / SR
    heard = transcribe(audio)
    toks = text.split()
    nt = [_norm(t) for t in toks]
    nh = [_norm(w) for _, _, w in heard]
    sm = difflib.SequenceMatcher(a=nt, b=nh, autojunk=False)
    wa, wb = _words_only(toks), _words_only([w for _, _, w in heard])
    sw = difflib.SequenceMatcher(a=wa, b=wb, autojunk=False)
    wer = 1 - sum(b.size for b in sw.get_matching_blocks()) / max(1, len(wa))
    # heard word index -> script token index (for punctuation)
    h2t: dict[int, int] = {}
    for op, a0, a1, b0, b1 in sm.get_opcodes():
        if op in ("equal", "replace"):
            for k in range(b1 - b0):
                h2t[b0 + k] = min(a0 + k, a1 - 1) if a1 > a0 else a0
    sil = silences(audio)
    gaps: list[Gap] = []
    for s0, s1 in sil:
        if s0 <= 0.02:
            gaps.append(Gap(s0, s1, "edge", ""))
            continue
        if s1 >= dur - 0.02:
            gaps.append(Gap(s0, s1, "edge", toks[-1] if toks else ""))
            continue
        # the word before the gap: the last heard word that started before the silence did
        prev = None
        for i, (w0, _w1, _w) in enumerate(heard):
            if w0 < s0 + 0.02:
                prev = i
        if prev is None:
            gaps.append(Gap(s0, s1, "word", ""))
            continue
        ti = h2t.get(prev)
        tok = toks[ti] if ti is not None and ti < len(toks) else heard[prev][2]
        gaps.append(Gap(s0, s1, _boundary(tok), tok, ti if ti is not None else -1000 - prev))
    # Several gaps after the same word: only the last one is the real boundary pause, the others are inside it.
    last: dict[int, int] = {}
    for i, g in enumerate(gaps):
        if g.kind != "edge":
            last[g.idx] = i
    for i, g in enumerate(gaps):
        if g.kind != "edge" and last.get(g.idx) != i:
            g.kind = "inside"
    lead = next((g.dur for g in gaps if g.kind == "edge" and g.start <= 0.02), 0.0)
    tail = next((g.dur for g in gaps if g.kind == "edge" and g.start > 0.02), 0.0)
    return Analysis(dur, max(0.1, dur - lead - tail), gaps, round(wer, 3), len(toks),
                    " ".join(w for _, _, w in heard))


def retime(raw: Path, text: str, cfg: dict, out: Path | None = None) -> Path:
    """Re-time the pauses of a take so it only breathes where the meaning allows (see module doc)."""
    pauses = {**PAUSES, **{k: tuple(v) for k, v in (cfg.get("pauses") or {}).items()}}
    tempo = float(cfg.get("tempo", 1.0))
    out = out or raw.with_name(f"{raw.stem}.n{stable_hash('retime-v3', pauses, tempo, cfg.get('target_wpm'), cfg.get('max_tempo'))[:6]}.wav")
    if out.exists():
        return out
    import numpy as np
    try:
        an = analyse(raw, text)
    except Exception as exc:  # noqa: BLE001 — never fail a render over phrasing
        warn(f"phrasing analysis failed ({str(exc)[:120]}); using the take as is")
        an = None
    sr = 24000
    pcm = subprocess.run(["ffmpeg", "-v", "error", "-i", str(raw), "-ac", "1", "-ar", str(sr), "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    a = np.frombuffer(pcm, dtype=np.float32).copy()
    pieces, pos = [], 0
    fade = int(0.008 * sr)
    gaps = an.gaps if an else []
    for g in gaps:
        s0, s1 = int(g.start * sr), int(g.end * sr)
        if g.kind == "edge":
            keep = 0.04 if g.start <= 0.02 else 0.06
            if g.start <= 0.02:
                cut0, cut1 = 0, max(0, s1 - int(keep * sr))
            else:
                cut0, cut1 = min(len(a), s0 + int(keep * sr)), len(a)
        else:
            if g.dur < STOP_CLOSURE and g.kind in ("word", "inside"):
                continue
            lo, hi = pauses[g.kind]
            target = min(max(g.dur, lo), hi)
            if target >= g.dur - 0.01:
                if target > g.dur + 0.01:   # lengthen a too-short comma/full stop with real silence
                    mid = (s0 + s1) // 2
                    pieces.append(a[pos:mid])
                    pieces.append(np.zeros(int((target - g.dur) * sr), dtype=np.float32))
                    pos = mid
                continue
            # keep the first and last part of the silence (natural decay and in-breath), drop the middle
            keep = int(target * sr)
            cut0 = s0 + keep // 2
            cut1 = s1 - (keep - keep // 2)
        if cut1 <= cut0 or cut0 < pos:
            continue
        seg = a[pos:cut0].copy()
        if len(seg) > fade:
            seg[-fade:] *= np.linspace(1, 0, fade, dtype=np.float32)
        pieces.append(seg)
        pos = cut1
        if pos < len(a) and len(a) - pos > fade:
            a[pos:pos + fade] *= np.linspace(0, 1, fade, dtype=np.float32)
    pieces.append(a[pos:])
    y = np.concatenate(pieces) if pieces else a
    tmp = out.with_suffix(".f32")
    tmp.write_bytes(y.astype(np.float32).tobytes())
    # Pace: if the re-timed take is still slower than a studio narrator, nudge it (never more than max_tempo).
    target = float(cfg.get("target_wpm", 0) or 0)
    if target and tempo == 1.0 and an:
        wpm = 60 * an.words / max(0.5, len(y) / sr)
        tempo = min(float(cfg.get("max_tempo", 1.08)), max(1.0, target / wpm))
    af = ["-af", f"atempo={tempo:.3f}"] if abs(tempo - 1) > 0.005 else []
    run(["ffmpeg", "-y", "-v", "error", "-f", "f32le", "-ar", str(sr), "-ac", "1", "-i", tmp, *af,
         "-ar", "24000", "-ac", "1", "-sample_fmt", "s16", out])
    tmp.unlink(missing_ok=True)
    if an:
        out.with_suffix(".phrasing.json").write_text(json.dumps({"before": an.summary(), "score": an.score()}))
    return out

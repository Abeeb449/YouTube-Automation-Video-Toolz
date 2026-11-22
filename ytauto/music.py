"""Generative background score + voice-aware ducking.

The score is synthesized (no samples, no licences): slow evolving pad chords, plus mood-specific
layers, crossfading whenever a scene's `mood` changes.

  wonder   bright major-7/9 pads + soft high bells            (discoveries, scale, beauty)
  mystery  suspended/minor-9 pads + sparse low bells           (the unknown, the deep)
  danger   low minor pads + heartbeat pulse + dissonant swell  (threat, the hunt)
  tension  low cluster + rising tone + fast pulse              (build-ups before reveals)
  calm     soft open pads only                                 (intros, outros)
  none     silence

Mixing: ytauto knows exactly when the narrator speaks (word timings), so instead of a compressor
reacting late, a gain envelope dips the music *before* each sentence and lets it swell into pauses.
"""
from __future__ import annotations

import wave
from pathlib import Path

import numpy as np

SR = 24000  # the bed is low-bandwidth; resampled to 48 kHz in the mix

MOODS = ("wonder", "mystery", "danger", "tension", "calm", "epic", "none")

# Chord progressions as MIDI notes (bass first). 4 chords, looped.
PROGRESSIONS = {
    "wonder": ([38, 50, 57, 64, 66, 69], [35, 47, 54, 61, 62, 66], [31, 43, 50, 54, 57, 61], [33, 45, 52, 57, 59, 64]),
    "mystery": ([28, 40, 47, 54, 55], [24, 36, 43, 47, 54], [33, 45, 52, 59, 60], [35, 47, 52, 54, 59]),
    "danger": ([26, 38, 45, 50, 53], [22, 34, 41, 46, 50], [31, 43, 50, 55, 58], [33, 45, 52, 55, 58]),
    "tension": ([24, 36, 43, 48, 49], [24, 36, 42, 48, 51], [23, 35, 42, 47, 48], [24, 36, 43, 48, 54]),
    "calm": ([29, 41, 48, 52, 57], [24, 36, 43, 50, 52], [26, 38, 45, 52, 53], [22, 34, 41, 45, 50]),
}
CHORD_LEN = {"wonder": 8.0, "mystery": 9.0, "danger": 6.0, "tension": 4.0, "calm": 10.0}
XFADE = 2.5  # seconds between chords
MOOD_XFADE = 2.5  # seconds between moods


def _hz(m: float) -> float:
    return 440.0 * 2 ** ((m - 69) / 12)


def _pad(t: np.ndarray, notes: list[int], bright: float) -> np.ndarray:
    out = np.zeros_like(t)
    for j, m in enumerate(notes):
        f = _hz(m)
        amp = 0.9 if j == 0 else 0.55 / (1 + 0.15 * j)
        for det in (-0.0012, 0.0012):
            for h, ha in ((1, 1.0), (2, 0.35 * bright), (3, 0.14 * bright)):
                out += amp * ha * np.sin(2 * np.pi * f * (1 + det) * h * t + j * 1.7 + h)
    # slow breathing
    return out * (0.8 + 0.2 * np.sin(2 * np.pi * t / 11.0))


def _chord_layer(t: np.ndarray, mood: str) -> np.ndarray:
    prog = PROGRESSIONS[mood]
    L = CHORD_LEN[mood]
    bright = {"wonder": 1.0, "calm": 0.7, "mystery": 0.6, "danger": 0.5, "tension": 0.8}[mood]
    out = np.zeros_like(t)
    k0 = int(np.floor(t[0] / L)) - 1
    k1 = int(np.floor(t[-1] / L)) + 1
    for k in range(k0, k1 + 1):
        a, b = k * L, (k + 1) * L
        # raised-cosine window covering [a - XFADE/2, b + XFADE/2]
        w = np.clip(np.minimum((t - (a - XFADE / 2)) / XFADE, ((b + XFADE / 2) - t) / XFADE), 0, 1)
        if not w.any():
            continue
        w = np.sin(w * np.pi / 2) ** 2
        out += w * _pad(t, prog[k % len(prog)], bright)
    return out


def _events(t0: float, t1: float, rng_seed: int, mean_gap: float) -> list[float]:
    rng = np.random.default_rng(rng_seed)
    ev, x = [], 0.0
    while x < t1:
        x += rng.uniform(mean_gap * 0.5, mean_gap * 1.5)
        if x >= t0 - 3 and x < t1:
            ev.append(x)
    return ev


def _bells(t: np.ndarray, mood: str, seed: int, gap: float, octave: int) -> np.ndarray:
    out = np.zeros_like(t)
    prog = PROGRESSIONS[mood]
    L = CHORD_LEN[mood]
    rng = np.random.default_rng(seed)
    for e in _events(t[0], t[-1], seed, gap):
        notes = prog[int(e // L) % len(prog)][1:]
        f = _hz(notes[int(rng.integers(len(notes)))] + octave)
        d = t - e
        m = d >= 0
        if not m.any():
            continue
        env = np.where(m, np.exp(-np.maximum(d, 0) / 2.2) * np.minimum(1, np.maximum(d, 0) / 0.01), 0)
        out += env * (np.sin(2 * np.pi * f * d) + 0.25 * np.sin(2 * np.pi * f * 2.76 * d))
    return out


def _heartbeat(t: np.ndarray, bpm: float) -> np.ndarray:
    period = 60.0 / bpm
    out = np.zeros_like(t)
    for off, a in ((0.0, 1.0), (0.28, 0.6)):
        d = (t - off) % period
        out += a * np.sin(2 * np.pi * 52 * d) * np.exp(-d / 0.09)
    return out


def _mood_signal(t: np.ndarray, mood: str) -> np.ndarray:
    if mood == "none":
        return np.zeros_like(t)
    y = _chord_layer(t, mood)
    if mood == "wonder":
        y += 0.5 * _bells(t, mood, 11, 2.2, 24)
    elif mood == "mystery":
        y += 0.45 * _bells(t, mood, 23, 4.0, 12)
    elif mood == "danger":
        y += 0.9 * _heartbeat(t, 62)
        y += 0.25 * np.sin(2 * np.pi * _hz(74) * t) * np.sin(2 * np.pi * _hz(75) * t) * (0.5 + 0.5 * np.sin(2 * np.pi * t / 13))
    elif mood == "tension":
        y += 0.8 * _heartbeat(t, 84)
        y += 0.22 * np.sin(2 * np.pi * (_hz(81) * (1 + 0.02 * ((t % 16) / 16))) * t)
    return y


def build_score(total: float, segments: list[tuple[float, float, str]], out: Path, seed: int = 0) -> Path:
    """segments: (start, end, mood) covering the video. Writes a normalised mono WAV at 24 kHz."""
    n = int((total + 1) * SR)
    y = np.zeros(n, dtype=np.float32)
    chunk = SR * 10
    segments = [(a, b, "tension" if m == "epic" else m) for a, b, m in segments]  # the synth has no epic layer
    moods = sorted({m for _, _, m in segments if m != "none"})
    for i0 in range(0, n, chunk):
        t = np.arange(i0, min(n, i0 + chunk)) / SR
        acc = np.zeros_like(t)
        for mood in moods:
            w = np.zeros_like(t)
            for a, b, m in segments:
                if m != mood:
                    continue
                w = np.maximum(w, np.clip(np.minimum((t - a) / MOOD_XFADE + 0.5, (b - t) / MOOD_XFADE + 0.5), 0, 1))
            if w.any():
                acc += w * _mood_signal(t + seed * 37.0, mood)
        y[i0:i0 + len(t)] = acc
    # gentle fades + normalise to a consistent RMS (≈ -20 dBFS) so `volume` means the same for every video
    t_all = np.arange(n) / SR
    y *= np.minimum(1, t_all / 3) * np.minimum(1, np.maximum(0, total - t_all) / 4)
    rms = float(np.sqrt(np.mean(y.astype(np.float64) ** 2))) + 1e-9
    y = np.clip(y * (0.1 / rms), -0.98, 0.98)
    _write(out, y, SR)
    return out


def speech_segments(word_spans: list[tuple[float, float]], merge_gap: float = 0.35) -> list[tuple[float, float]]:
    """Merge word spans into speaking segments; gaps shorter than merge_gap don't count as pauses."""
    segs: list[list[float]] = []
    for a, b in sorted(word_spans):
        if segs and a - segs[-1][1] < merge_gap:
            segs[-1][1] = max(segs[-1][1], b)
        else:
            segs.append([a, b])
    return [(a, b) for a, b in segs]


def speech_from_audio(path: Path, threshold_db: float = -32.0, min_gap: float = 0.08) -> list[tuple[float, float]]:
    """Voice-activity detection on the narration itself: (start, end) of every stretch of speech.
    Exact for any TTS engine, unlike estimated word timings."""
    with wave.open(str(path), "rb") as w:
        sr, ch = w.getframerate(), w.getnchannels()
        a = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
    if ch > 1:
        a = a.reshape(-1, ch).mean(axis=1)
    hop = int(sr * 0.01)
    frames = len(a) // hop
    if frames == 0:
        return []
    rms = np.sqrt(np.mean(a[: frames * hop].reshape(frames, hop) ** 2, axis=1)) + 1e-9
    db = 20 * np.log10(rms)
    ref = np.percentile(db, 95)  # relative to the voice's own loud parts
    active = db > ref + threshold_db
    segs, start = [], None
    for i, on in enumerate(active):
        if on and start is None:
            start = i
        elif not on and start is not None:
            segs.append([start / 100, i / 100])
            start = None
    if start is not None:
        segs.append([start / 100, frames / 100])
    merged: list[list[float]] = []
    for a0, b0 in segs:
        if merged and a0 - merged[-1][1] < min_gap:
            merged[-1][1] = b0
        else:
            merged.append([a0, b0])
    return [(a0, b0) for a0, b0 in merged if b0 - a0 > 0.05]


def build_duck_envelope(total: float, speech: list[tuple[float, float]], duck: float, out: Path,
                        lead: float = 0.12, attack: float = 0.1, release: float = 0.35, breath: float = 0.6,
                        sr: int = 48000) -> Path:
    """Gain curve for the music: 1.0 in pauses, `duck` while words are spoken, and halfway back up
    (`breath`) in the short breaths between words/sentences, so the bed never "holes" like a gate.
    Dips `lead` s before speech starts so the first syllable is never masked."""
    fr = 100  # control rate
    n = int((total + 1) * fr)
    target = np.ones(n)
    spans = sorted(speech)
    for i, (a, b) in enumerate(spans):
        target[max(0, int((a - lead) * fr)):min(n, int((b + 0.04) * fr))] = duck
        if i + 1 < len(spans):
            gap_a, gap_b = b + 0.04, spans[i + 1][0] - lead
            if 0 < gap_b - gap_a < 0.6:  # short breath: partial lift
                target[int(gap_a * fr):int(gap_b * fr)] = duck + (1 - duck) * breath * min(1.0, (gap_b - gap_a) / 0.3)
    env = np.empty(n)
    g = target[0]
    ka, kr = 1 - np.exp(-1 / (attack * fr)), 1 - np.exp(-1 / (release * fr))
    for i in range(n):
        g += (target[i] - g) * (ka if target[i] < g else kr)
        env[i] = g
    samples = np.interp(np.arange(int((total + 1) * sr)) / sr, np.arange(n) / fr, env).astype(np.float32)
    _write(out, samples * 0.98, sr)
    return out


def _write(path: Path, y: np.ndarray, sr: int) -> None:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes((np.clip(y, -1, 1) * 32767).astype(np.int16).tobytes())

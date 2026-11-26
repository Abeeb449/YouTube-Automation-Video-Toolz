"""Synthesized sound design — no downloads, no licences to worry about.

Builds one stereo-compatible WAV track with:
  - an optional low ambient drone bed (dark documentary tension)
  - a soft whoosh on every scene change
  - per-scene effects by name: whoosh, swell, riser, hit, boom, thud, tick, ticks, typing, glitch, beep, alarm

Effects can be placed on a spoken word (see cues.py), e.g.
  sfx: [{sound: boom, at: "detonation"}, {sound: typing, at: 0.5, dur: 1.2}]
"""
from __future__ import annotations

import wave
from pathlib import Path

import numpy as np

SR = 48000
BUILTIN = {"whoosh", "swell", "riser", "hit", "boom", "thud", "tick", "ticks", "typing", "glitch", "beep", "alarm"}
# Transition-style sounds (noise sweeps between shots, rising sweeps into a moment, glitch bursts). The channel's
# rule: NEVER in any video. They are still recognised by name so old scripts load, but the mix drops every one,
# wherever it was asked for (a scene's sfx list, a preset, the sound director).
TRANSITION = {"whoosh", "swell", "riser", "glitch"}
ALLOWED = BUILTIN - TRANSITION


def _env(n: int, attack: float, decay: float) -> np.ndarray:
    t = np.arange(n) / SR
    return np.minimum(1.0, t / max(attack, 1e-4)) * np.exp(-t / max(decay, 1e-4))


def _lowpass(x: np.ndarray, a: np.ndarray | float) -> np.ndarray:
    """One-pole low-pass with a (possibly time-varying) coefficient 0..1."""
    a = np.broadcast_to(a, x.shape)
    y = np.empty_like(x)
    acc = 0.0
    for i in range(len(x)):
        acc += a[i] * (x[i] - acc)
        y[i] = acc
    return y


def synth(name: str, rng: np.random.Generator, dur: float | None = None) -> np.ndarray:
    if name == "whoosh":
        n = int((dur or 0.7) * SR)
        shape = np.sin(np.linspace(0, np.pi, n)) ** 2
        y = _lowpass(rng.normal(0, 1, n), 0.01 + 0.22 * shape) * shape
        return y / (np.abs(y).max() + 1e-9) * 0.6
    if name in ("swell", "riser"):
        n = int((dur or (1.6 if name == "swell" else 2.5)) * SR)
        t = np.arange(n) / SR
        ramp = (t / t[-1]) ** 2
        noise = _lowpass(rng.normal(0, 1, n), 0.02 + 0.3 * ramp)
        tone = np.sin(2 * np.pi * (80 + 220 * ramp) * t) * 0.3 if name == "riser" else 0
        y = (noise + tone) * ramp * np.minimum(1, (t[-1] - t) / 0.08)
        return y / (np.abs(y).max() + 1e-9) * 0.5
    if name in ("hit", "thud", "boom"):
        # Soft cinematic accents that sit UNDER a narrator: a deep sine swell that blooms in over 40-90 ms and
        # fades slowly, with a little airy shimmer. No noise "crack" and no hard attack, so nothing ever
        # snaps out over the voice (the old percussive hits did).
        L = {"hit": 1.6, "thud": 1.2, "boom": 3.0}[name]
        n = int(L * SR)
        t = np.arange(n) / SR
        f0 = {"hit": 62, "thud": 52, "boom": 42}[name]
        atk = {"hit": 0.06, "thud": 0.04, "boom": 0.09}[name]
        env = np.minimum(1.0, t / atk) ** 2 * np.exp(-t * {"hit": 2.2, "thud": 3.0, "boom": 1.1}[name])
        body = np.sin(2 * np.pi * (f0 * (1 + 0.25 * np.exp(-t * 4))) * t)
        warm = 0.35 * np.sin(2 * np.pi * 2 * f0 * t + 0.6)
        air = _lowpass(rng.normal(0, 1, n), 0.02) * 0.6 * np.minimum(1.0, t / 0.12) * np.exp(-t * 2.5)
        y = (body + warm) * env + air
        return y / (np.abs(y).max() + 1e-9) * 0.35
    if name in ("tick", "beep"):
        n = int((0.04 if name == "tick" else 0.18) * SR)
        t = np.arange(n) / SR
        f = 2200 if name == "tick" else 1000
        return np.sin(2 * np.pi * f * t) * _env(n, 0.001, 0.012 if name == "tick" else 0.06) * 0.35
    if name == "ticks":  # clock ticking, 1 per second
        d = dur or 3.0
        out = np.zeros(int(d * SR))
        one = synth("tick", rng)
        for k in range(int(d)):
            i = int(k * SR)
            out[i:i + len(one)] += one
        return out
    if name == "typing":
        d = dur or 1.0
        out = np.zeros(int(d * SR))
        k = 0.0
        while k < d - 0.05:
            n = int(0.025 * SR)
            click = rng.normal(0, 1, n) * _env(n, 0.0005, 0.004) * 0.25
            i = int(k * SR)
            out[i:i + n] += click[: len(out) - i]
            k += rng.uniform(0.045, 0.11)
        return out
    if name == "glitch":
        n = int((dur or 0.4) * SR)
        y = rng.normal(0, 1, n) * (rng.random(n // 400 + 1).repeat(400)[:n] > 0.5) * 0.3
        return y * _env(n, 0.001, 0.25)
    if name == "alarm":
        d = dur or 2.0
        n = int(d * SR)
        t = np.arange(n) / SR
        f = 600 + 250 * (np.sin(2 * np.pi * 0.8 * t) > 0)
        return np.sin(2 * np.pi * f * t) * 0.18 * np.minimum(1, t / 0.05) * np.minimum(1, (d - t) / 0.2)
    raise ValueError(f"unknown built-in sound {name!r}; choose from {', '.join(sorted(BUILTIN))}")


def drone(total: float, rng: np.random.Generator, level: float) -> np.ndarray:
    """Low ambient bed, generated in chunks so 15-minute videos stay light on memory."""
    n = int(total * SR)
    out = np.empty(n, dtype=np.float32)
    # slow "air" texture: low-passed noise at 400 Hz, then interpolated up
    lo_sr = 400
    lo = _lowpass(rng.normal(0, 1, int(total * lo_sr) + 2), 0.05)
    chunk = SR * 10
    for i0 in range(0, n, chunk):
        t = np.arange(i0, min(n, i0 + chunk)) / SR
        pad = sum(a * np.sin(2 * np.pi * f * t + 2 * np.sin(2 * np.pi * 0.05 * t + f)) for f, a in
                  [(55, 1.0), (82.4, 0.5), (110, 0.3), (164.8, 0.12)])
        pad *= 0.6 + 0.4 * np.sin(2 * np.pi * t / 19) ** 2
        air = np.interp(t * lo_sr, np.arange(len(lo)), lo) * 6
        y = (pad + air) * np.minimum(1, t / 4) * np.minimum(1, (total - t) / 3)
        out[i0:i0 + len(t)] = y
    return out / (np.abs(out).max() + 1e-9) * level


def build_track(total: float, events: list[tuple[float, str, float, float | None]], drone_level: float, out: Path) -> Path:
    """events: (time, sound_name, volume, duration_or_None)."""
    rng = np.random.default_rng(7)
    n = int(total * SR) + SR
    x = drone(total + 1, rng, drone_level).astype(np.float64) if drone_level > 0 else np.zeros(n)
    x = x[:n] if len(x) >= n else np.pad(x, (0, n - len(x)))
    for at, name, vol, dur in events:
        y = synth(name, rng, dur) * vol
        if name in ("whoosh", "swell", "riser"):
            at = at - len(y) / SR * (0.5 if name == "whoosh" else 1.0)  # peak lands on the cut
        i = max(0, int(at * SR))
        e = min(n, i + len(y))
        if e > i:
            x[i:e] += y[: e - i]
    x = np.clip(x, -1, 1)
    with wave.open(str(out), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((x * 32767).astype(np.int16).tobytes())
    return out

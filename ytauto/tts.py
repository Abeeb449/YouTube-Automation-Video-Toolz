"""Text-to-speech engines and per-scene voiceover assembly.

Engines
-------
edge        Microsoft Edge neural voices via the free `edge-tts` package. Best free
            quality, needs internet. Voice ids like "en-US-AndrewNeural".
piper       Fully offline neural TTS (https://github.com/rhasspy/piper). Voice ids
            like "en_US-lessac-medium"; models are downloaded once and cached.
kokoro      Kokoro-82M (Apache 2.0 — free for commercial use). Excellent offline neural voices,
            ~4x faster than real time on CPU. Voices: bm_george, bm_lewis, am_onyx, am_michael…
            Blend voices with "bm_george:0.6,am_onyx:0.4".
qwen        Qwen3-TTS (Apache 2.0) — very natural; direct it in plain English per sentence ("hushed, awed"),
            invent a voice from a description, or clone one. Runs on CPU (slower than real time).
chatterbox  Chatterbox (MIT) — expressive, emotion exaggeration, voice cloning from a 5-10 s clip.
elevenlabs  Premium voices. Needs ELEVENLABS_API_KEY. Voice = ElevenLabs voice id.
espeak      Robotic but always-available offline fallback (espeak-ng).
"""
from __future__ import annotations

import asyncio
import json
import threading
import os
import re
import urllib.request
import wave
from dataclasses import dataclass, field
from pathlib import Path

from .utils import YtautoError, ffprobe_duration, log, run, stable_hash, warn, which

SAMPLE_RATE = 48000

_failed_engines: set[str] = set()


@dataclass
class Cue:
    start: float
    end: float
    text: str


@dataclass
class SceneAudio:
    path: Path
    duration: float          # narration length (without trailing padding)
    cues: list[Cue]          # caption cues relative to the scene start
    words: list[Cue] = field(default_factory=list)  # per-word timings relative to the scene start


# --------------------------------------------------------------------------- text

_SENT_RE = re.compile(r"(?<=[.!?…])[\"')\]]*\s+")


def split_sentences(text: str) -> list[str]:
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []
    parts = [p.strip() for p in _SENT_RE.split(text) if p.strip()]
    # Very long sentences sound fine but make huge captions; split them on commas/semicolons.
    out: list[str] = []
    for p in parts:
        if len(p) > 280:
            out.extend(x.strip() for x in re.split(r"(?<=[,;:])\s+", p) if x.strip())
        else:
            out.append(p)
    return out


_TAG_RE = re.compile(r"\[(pause|speed|emotion|voice|tone|reset)(?:\s+([^\]]+))?\]", re.I)


def strip_directives(text: str) -> str:
    """Narration text without [pause]/[speed …] tags (for captions, kinetic text, cue matching)."""
    return re.sub(r"\s+", " ", _TAG_RE.sub(" ", text)).strip()


def narration_inputs(text: str, voice: dict, st: dict) -> tuple[str, dict, dict]:
    """Apply the project's narration style before voicing a scene.

    settings.narration:
      natural  (default) the voice reads the script as written, the way it naturally speaks: [tone]/[pause] tags
               are dropped, no retakes, no pause editing, default model sampling.
      polished each sentence is listened back, re-voiced when a word breaks, pauses moved to punctuation
               (voice_polish mode "phrasing", ytauto/prosody.py), and [tone …] / [pause] tags are performed.
    """
    if str(st.get("narration", "natural")).lower() != "natural":
        return text, voice, st
    st = {**st, "voice_polish": {"enabled": False}, "sentence_gap": 0.0}
    voice = {k: v for k, v in voice.items() if k != "sampling"}
    voice["fluent"] = False
    return strip_directives(text), voice, st


def parse_directives(text: str) -> list[tuple]:
    """Split narration into ("say", sentence, voice_overrides) and ("pause", seconds) items.

    Voice-direction tags, written inline in the script:
      [pause] / [pause 1.2]   silence (default 0.7 s) — dramatic beats
      [speed 0.85]            slower (or faster) delivery from here on
      [emotion 0.8]           Chatterbox exaggeration 0.25–1.0 (calm → intense); Kokoro: slight slow-down when > 0.6
      [voice bm_lewis]        switch voice from here on
      [tone hushed, awed]     Qwen3-TTS: describe how to say it, in plain English
      [reset]                 back to the scene's default voice settings
    Tags stay in effect until the end of the scene (or [reset]).
    """
    items: list[tuple] = []
    over: dict = {}
    pos = 0
    for m in list(_TAG_RE.finditer(text)) + [None]:
        chunk = text[pos:m.start()] if m else text[pos:]
        for sent in split_sentences(chunk):
            items.append(("say", sent, dict(over)))
        if not m:
            break
        pos = m.end()
        tag, arg = m.group(1).lower(), (m.group(2) or "").strip()
        try:
            if tag == "pause":
                items.append(("pause", float(arg) if arg else 0.7))
            elif tag == "speed":
                over["speed"] = float(arg)
            elif tag == "emotion":
                e = float(arg)
                over["exaggeration"] = e
                if "speed" not in over and e > 0.6:
                    over["speed_hint"] = round(1.0 - (e - 0.6) * 0.25, 3)
            elif tag == "voice":
                over["name"] = arg
            elif tag == "tone":  # Qwen3-TTS: plain-English direction, e.g. [tone whispered and tense]
                over["tone"] = arg
            elif tag == "reset":
                over = {}
        except ValueError:
            warn(f"ignoring malformed voice tag {m.group(0)!r}")
    # Kokoro/Edge have no emotion knob: map intensity to a slightly more deliberate pace.
    for it in items:
        if it[0] == "say" and "speed_hint" in it[2]:
            hint = it[2].pop("speed_hint")
            it[2].setdefault("speed", hint)
    return items


def polish(raw: Path, cfg: dict) -> Path:
    """Make generated speech flow like a person talking: trim the silence neural voices leave at the start/end,
    shorten long gaps inside a line (models often pause 0.8-1.3 s mid-sentence) to a natural breath, and
    optionally nudge the tempo. Cached next to the raw take, so re-tuning never re-voices anything."""
    if cfg.get("enabled") is False:
        return raw
    keep = float(cfg.get("keep_gap", 0.12))     # silence kept when a long gap is shortened
    longest = float(cfg.get("max_gap", 0.25))   # gaps longer than this get shortened
    tempo = float(cfg.get("tempo", 1.0))
    out = raw.with_name(f"{raw.stem}.p{stable_hash(keep, longest, tempo)[:6]}.wav")
    if out.exists():
        return out
    af = ("silenceremove=start_periods=1:start_threshold=-50dB:start_silence=0.03,areverse,"
          "silenceremove=start_periods=1:start_threshold=-50dB:start_silence=0.08,areverse,"
          f"silenceremove=stop_periods=-1:stop_threshold=-40dB:stop_duration={longest}:stop_silence={keep}")
    if abs(tempo - 1.0) > 0.005:
        af += f",atempo={tempo}"
    run(["ffmpeg", "-y", "-v", "error", "-i", raw, "-af", af, "-ar", str(SAMPLE_RATE), "-ac", "1", "-sample_fmt", "s16", out])
    return out


_take_lock = threading.Lock()


def best_take(sent: str, voice: dict, raw: Path, pol: dict) -> Path:
    """Voice a sentence, listen back (prosody.analyse) and ask for another take while it hesitates mid-phrase or
    misreads words; keep the best take, then re-time its pauses so it only breathes at punctuation."""
    from . import prosody
    choice = raw.with_suffix(".take.json")
    best: Path | None = None
    if choice.exists():
        try:
            best = raw.with_name(json.loads(choice.read_text())["file"])
        except (ValueError, KeyError):
            best = None
    if best is None or not _fresh(best) or any(raw.parent.glob(f"{raw.stem}*.fallback")):
        retakes = int(pol.get("retakes", 2))
        prior = sorted(raw.parent.glob(f"{raw.stem}.t*.wav"))   # takes already made by an earlier run
        base = int(voice.get("seed") or pol.get("seed", 1234))
        cands = []
        for k in range(max(retakes, len(prior)) + 1):
            f = raw if k == 0 else raw.with_name(f"{raw.stem}.t{k}.wav")
            if not _fresh(f):
                if k > retakes:
                    break
                synthesize(sent, {**voice, "seed": base + 101 * k}, f)
            try:
                with _take_lock:
                    an = prosody.analyse(f, sent)
            except Exception as exc:  # noqa: BLE001 — no whisper: keep the first take
                warn(f"take check unavailable ({str(exc)[:100]})")
                cands.append((0.0, k, f, None))
                break
            cands.append((an.score(), k, f, an))
            if an.ok():
                break
        sc, k, best, an = min(cands, key=lambda c: (c[0], c[1]))
        if an is not None and not an.ok():
            warn(f"best of {len(cands)} takes still imperfect ({an.summary()}): {sent[:60]}")
        log(f"   voiced ({len(cands)} take{'s' if len(cands) > 1 else ''}): {sent[:70]}")
        choice.write_text(json.dumps({"file": best.name, "score": sc, "takes": len(cands),
                                      "summary": an.summary() if an else ""}))
    with _take_lock:
        return prosody.retime(best, sent, pol)


def merge_passages(items: list[tuple], max_chars: int = 320) -> list[tuple]:
    """Join consecutive sentences that share the same voice direction into one passage.
    Neural engines sound more natural across sentence boundaries, and each call has a fixed cost,
    so fewer, longer calls are both better-sounding and much faster. Pauses still split passages."""
    out: list[tuple] = []
    for it in items:
        if (it[0] == "say" and out and out[-1][0] == "say" and out[-1][2] == it[2]
                and len(out[-1][1]) + 1 + len(it[1]) <= max_chars):
            out[-1] = ("say", f"{out[-1][1]} {it[1]}", out[-1][2])
        else:
            out.append(it)
    return out


_whisper_model = None
_whisper_lock = threading.Lock()
_whisper_failed = False


def align_words(sentence: str, wav: Path, mode: str = "auto") -> None:
    """Exact word timings for engines that don't report them (Kokoro, Piper, Chatterbox, ElevenLabs):
    run faster-whisper (MIT) over our own audio and save <wav>.words.json. Skipped when the file exists,
    faster-whisper isn't installed, or the model can't be loaded (timings are then estimated)."""
    global _whisper_model, _whisper_failed
    wf = wav.with_suffix(".words.json")
    if wf.exists() or _whisper_failed:
        return
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        if mode == "on":
            warn("align: on, but faster-whisper isn't installed (pip install faster-whisper)")
        _whisper_failed = True
        return
    with _whisper_lock:
        if _whisper_failed:
            return
        if _whisper_model is None:
            try:
                name = os.environ.get("YTAUTO_WHISPER_MODEL", "base.en")
                _whisper_model = WhisperModel(name, device="cpu", compute_type="int8",
                                              download_root=os.environ.get("YTAUTO_WHISPER_DIR"))
            except Exception as exc:  # noqa: BLE001 — no network for the model etc.
                warn(f"word alignment unavailable ({str(exc).splitlines()[0][:120]}); estimating word timings")
                _whisper_failed = True
                return
        try:
            import subprocess

            import numpy as np
            # decode with ffmpeg ourselves (16 kHz mono float) — avoids PyAV version clashes
            raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(wav), "-ac", "1", "-ar", "16000", "-f", "f32le", "-"],
                                 capture_output=True, check=True).stdout
            audio = np.frombuffer(raw, dtype=np.float32)
            segs, _ = _whisper_model.transcribe(audio, language="en", word_timestamps=True, initial_prompt=sentence,
                                                beam_size=1, vad_filter=False)
            got = [w for seg in segs for w in (seg.words or [])]
        except Exception as exc:  # noqa: BLE001 — alignment is a nice-to-have; never fail the render
            warn(f"word alignment failed ({str(exc).splitlines()[0][:120]}); estimating word timings")
            _whisper_failed = True
            return
    toks = sentence.split()
    if not got:
        return
    if len(got) == len(toks):
        data = [{"start": round(w.start, 3), "end": round(w.end, 3), "text": tok} for w, tok in zip(got, toks)]
    else:  # different tokenisation: keep whisper's words (cue matching ignores punctuation)
        data = [{"start": round(w.start, 3), "end": round(w.end, 3), "text": w.word.strip()} for w in got]
    wf.write_text(json.dumps(data))


def caption_chunks(sentence: str, max_chars: int) -> list[str]:
    """Split a sentence into evenly sized caption chunks of at most two lines of `max_chars`."""
    limit = max_chars * 2
    words = sentence.split()
    if len(sentence) <= limit:
        return [sentence]
    n = -(-len(sentence) // limit)  # ceil
    while True:
        target = len(sentence) / n
        chunks, cur = [], ""
        for w in words:
            if cur and (len(cur) + 1 + len(w) > limit or (len(cur) >= target and len(chunks) < n - 1)):
                chunks.append(cur)
                cur = w
            else:
                cur = f"{cur} {w}".strip()
        chunks.append(cur)
        if all(len(c) <= limit for c in chunks):
            return chunks
        n += 1


def wrap_two_lines(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    words = text.split()
    best, best_diff = text, 10**9
    for i in range(1, len(words)):
        a, b = " ".join(words[:i]), " ".join(words[i:])
        diff = abs(len(a) - len(b))
        if diff < best_diff:
            best, best_diff = f"{a}\n{b}", diff
    return best


# --------------------------------------------------------------------------- engines

def _to_wav(src: Path, dst: Path) -> None:
    run(["ffmpeg", "-y", "-v", "error", "-i", src, "-ac", "1", "-ar", str(SAMPLE_RATE), "-sample_fmt", "s16", dst])


def _edge(text: str, voice: dict, out: Path) -> None:
    try:
        import edge_tts
    except ImportError as exc:
        raise YtautoError("edge-tts not installed (pip install edge-tts)") from exc
    tmp = out.with_suffix(".mp3")
    rate = voice.get("rate", "+0%")
    if voice.get("speed"):
        rate = f"{round((float(voice['speed']) - 1) * 100):+d}%"
    kwargs = {"rate": rate, "pitch": voice.get("pitch", "+0Hz")}
    proxy = os.environ.get("YTAUTO_EDGE_PROXY")
    if proxy:
        kwargs["proxy"] = proxy
    try:  # word timings let graphics land exactly on spoken words
        comm = edge_tts.Communicate(text, voice.get("name") or "en-US-AndrewNeural", boundary="WordBoundary", **kwargs)
    except TypeError:  # older edge-tts
        comm = edge_tts.Communicate(text, voice.get("name") or "en-US-AndrewNeural", **kwargs)
    words: list[dict] = []

    async def go():
        with open(tmp, "wb") as f:
            async for chunk in comm.stream():
                if chunk["type"] == "audio":
                    f.write(chunk["data"])
                elif chunk["type"] == "WordBoundary":
                    st = chunk["offset"] / 1e7
                    words.append({"start": round(st, 3), "end": round(st + chunk["duration"] / 1e7, 3), "text": chunk["text"]})

    asyncio.run(asyncio.wait_for(go(), timeout=90))
    if not tmp.exists() or tmp.stat().st_size == 0:
        raise YtautoError("edge-tts returned no audio")
    _to_wav(tmp, out)
    tmp.unlink(missing_ok=True)
    if words:
        out.with_suffix(".words.json").write_text(json.dumps(words))


def piper_model_dir() -> Path:
    return Path(os.environ.get("YTAUTO_PIPER_DIR", Path.home() / ".cache" / "ytauto" / "piper"))


def ensure_piper_voice(name: str) -> Path:
    """Download a Piper voice from Hugging Face (rhasspy/piper-voices) if missing."""
    d = piper_model_dir()
    d.mkdir(parents=True, exist_ok=True)
    onnx = d / f"{name}.onnx"
    cfg = d / f"{name}.onnx.json"
    if onnx.exists() and cfg.exists():
        return onnx
    try:
        lang_code, speaker, quality = name.split("-", 2)
    except ValueError as exc:
        raise YtautoError(f"Piper voice must look like 'en_US-lessac-medium', got {name!r}") from exc
    family = lang_code.split("_")[0]
    base = f"https://huggingface.co/rhasspy/piper-voices/resolve/main/{family}/{lang_code}/{speaker}/{quality}/{name}"
    log(f"Downloading Piper voice {name} …")
    for url, dst in ((base + ".onnx", onnx), (base + ".onnx.json", cfg)):
        urllib.request.urlretrieve(url, dst)
    return onnx


def _piper(text: str, voice: dict, out: Path) -> None:
    name = voice.get("name") or "en_US-lessac-medium"
    if "Neural" in name:  # an edge voice id leaked in through the fallback chain
        name = "en_US-lessac-medium"
    model = ensure_piper_voice(name)
    try:
        from piper import PiperVoice
    except ImportError as exc:
        raise YtautoError("piper-tts not installed (pip install piper-tts)") from exc
    pv = PiperVoice.load(str(model))
    tmp = out.with_suffix(".raw.wav")
    with wave.open(str(tmp), "wb") as wf:
        if hasattr(pv, "synthesize_wav"):          # piper-tts >= 1.3
            syn_config = None
            length_scale = voice.get("length_scale") or (1 / float(voice["speed"]) if voice.get("speed") else None)
            if length_scale:
                from piper import SynthesisConfig
                syn_config = SynthesisConfig(length_scale=float(length_scale))
            pv.synthesize_wav(text, wf, syn_config=syn_config)
        else:                                      # older piper-tts
            pv.synthesize(text, wf)
    _to_wav(tmp, out)
    tmp.unlink(missing_ok=True)


def _elevenlabs(text: str, voice: dict, out: Path) -> None:
    key = os.environ.get("ELEVENLABS_API_KEY")
    if not key:
        raise YtautoError("ELEVENLABS_API_KEY is not set")
    voice_id = voice.get("name") or "21m00Tcm4TlvDq8ikWAM"
    body = json.dumps({
        "text": text,
        "model_id": voice.get("model", "eleven_multilingual_v2"),
        "voice_settings": {"stability": voice.get("stability", 0.5), "similarity_boost": voice.get("similarity", 0.75)},
    }).encode()
    req = urllib.request.Request(
        f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}?output_format=mp3_44100_128",
        data=body,
        headers={"xi-api-key": key, "Content-Type": "application/json", "Accept": "audio/mpeg"},
    )
    tmp = out.with_suffix(".mp3")
    with urllib.request.urlopen(req, timeout=120) as resp:
        tmp.write_bytes(resp.read())
    _to_wav(tmp, out)
    tmp.unlink(missing_ok=True)


def _espeak(text: str, voice: dict, out: Path) -> None:
    exe = which("espeak-ng") or which("espeak")
    if not exe:
        raise YtautoError("espeak-ng not installed")
    tmp = out.with_suffix(".raw.wav")
    name = voice.get("name") or "en-us"
    if "Neural" in name or "_" in name:
        name = "en-us"
    run([exe, "-v", name, "-s", str(voice.get("speed", 165)), "-w", tmp, text])
    _to_wav(tmp, out)
    tmp.unlink(missing_ok=True)


def _speed(voice: dict) -> float:
    """Engine-neutral speed: `speed: 0.9`, or an Edge-style `rate: "-10%"`."""
    if voice.get("speed"):
        return float(voice["speed"])
    m = re.match(r"^([+-]?\d+(?:\.\d+)?)%$", str(voice.get("rate", "")).strip())
    return 1.0 + float(m.group(1)) / 100 if m else 1.0


KOKORO_FILES = {
    "kokoro-v1.0.onnx": "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx",
    "voices-v1.0.bin": "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin",
}
_kokoro_lock = threading.Lock()
_kokoro_model = None


def kokoro_dir() -> Path:
    return Path(os.environ.get("YTAUTO_KOKORO_DIR", Path.home() / ".cache" / "ytauto" / "kokoro"))


def ensure_kokoro() -> tuple[Path, Path]:
    d = kokoro_dir()
    d.mkdir(parents=True, exist_ok=True)
    for name, url in KOKORO_FILES.items():
        dst = d / name
        if not dst.exists() or dst.stat().st_size == 0:
            log(f"Downloading Kokoro {name} (one time) …")
            urllib.request.urlretrieve(url, dst.with_suffix(".part"))
            dst.with_suffix(".part").rename(dst)
    return d / "kokoro-v1.0.onnx", d / "voices-v1.0.bin"


def _kokoro(text: str, voice: dict, out: Path) -> None:
    global _kokoro_model
    try:
        from kokoro_onnx import Kokoro
        import soundfile as sf
    except ImportError as exc:
        raise YtautoError("kokoro-onnx not installed (pip install kokoro-onnx soundfile)") from exc
    with _kokoro_lock:
        if _kokoro_model is None:
            model, voices = ensure_kokoro()
            _kokoro_model = Kokoro(str(model), str(voices))
    k = _kokoro_model
    name = voice.get("name") or "bm_george"
    if "Neural" in name or "-" in name or ("," not in name and ":" not in name and name not in k.get_voices()):
        name = "bm_george"  # an id from another engine leaked in through a fallback chain
    if "," in name or ":" in name:  # blend, e.g. "bm_george:0.6,am_onyx:0.4"
        style, first = None, None
        for part in name.split(","):
            vid, _, w = part.strip().partition(":")
            first = first or vid
            v = k.get_voice_style(vid) * float(w or 1)
            style = v if style is None else style + v
        speaker, lang_src = style, first
    else:
        speaker, lang_src = name, name
    lang = voice.get("lang") or ("en-gb" if str(lang_src).startswith("b") else "en-us")
    samples, sr = k.create(text, voice=speaker, speed=max(0.5, min(2.0, _speed(voice))), lang=lang)
    tmp = out.with_suffix(".raw.wav")
    sf.write(str(tmp), samples, sr)
    _to_wav(tmp, out)
    tmp.unlink(missing_ok=True)


class _Worker:
    """A long-running TTS worker in its own Python environment (see ytauto/tts_workers/)."""

    def __init__(self, name: str, python: str, script: str):
        self.name, self.python, self.script = name, python, script
        self.proc = None
        self.lock = threading.Lock()

    def _start(self):
        import subprocess

        if not Path(self.python).exists():
            raise YtautoError(f"{self.name} is not installed (expected {self.python}); see README → Voices")
        log(f"Starting {self.name}{'' if 'check' in self.name else ' voice engine'} (first use loads the model, this can take a minute) …")
        self.proc = subprocess.Popen([self.python, "-u", self.script], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     stderr=subprocess.DEVNULL, text=True, bufsize=1)
        if self._read() is None:
            raise YtautoError(f"{self.name} worker failed to start")

    def _read(self) -> dict | None:
        """Next JSON line from the worker, skipping anything libraries print to stdout."""
        while True:
            line = self.proc.stdout.readline()
            if not line:
                return None
            line = line.strip()
            if line.startswith("{"):
                try:
                    return json.loads(line)
                except ValueError:
                    pass

    def run(self, job: dict) -> dict:
        with self.lock:
            if self.proc is None or self.proc.poll() is not None:
                self._start()
            try:
                self.proc.stdin.write(json.dumps(job) + "\n")
                self.proc.stdin.flush()
                res = self._read()
            except (BrokenPipeError, OSError):
                res = None
            if res is None:   # crashed: drop the process so the next call starts a fresh one
                try:
                    self.proc.kill()
                except Exception:  # noqa: BLE001
                    pass
                self.proc = None
        if res is None:
            raise YtautoError(f"{self.name} worker crashed")
        if not res.get("ok"):
            raise YtautoError(f"{self.name}: {res.get('error')}")
        return res


    def stop(self):
        with self.lock:
            if self.proc is not None and self.proc.poll() is None:
                try:
                    self.proc.stdin.close()
                    self.proc.wait(timeout=20)
                except Exception:  # noqa: BLE001
                    self.proc.kill()
            self.proc = None


def shutdown_workers() -> None:
    """Free the big voice models (several GB of RAM) before the video rendering starts."""
    for w in (_qwen, _cbox):
        w.stop()


_WORKERS_DIR = Path(__file__).resolve().parent / "tts_workers"
_qwen = _Worker("Qwen3-TTS", os.environ.get("YTAUTO_QWEN_PYTHON", "/opt/tts-qwen/bin/python"), str(_WORKERS_DIR / "qwen_worker.py"))
_cbox = _Worker("Chatterbox", os.environ.get("YTAUTO_CHATTERBOX_PYTHON", "/opt/tts-chatterbox/bin/python"),
                str(_WORKERS_DIR / "chatterbox_worker.py"))

EMOTION_WORDS = [(0.85, "very intense, urgent and dramatic"), (0.7, "tense and gripping"), (0.55, "engaged and expressive"),
                 (0.4, "calm and measured"), (0.0, "soft, quiet and gentle")]


def _qwen_tts(text: str, voice: dict, out: Path) -> None:
    """Qwen3-TTS (Apache 2.0). voice: name = speaker (ryan, aiden, eric, dylan, serena, vivian…) or "design";
    description = the voice to invent for "design"; instruct / [tone …] = how to say it; reference = clone a voice."""
    name = (voice.get("name") or "ryan").lower()
    if "neural" in name or "_" in name and name not in ("uncle_fu", "ono_anna"):
        name = "ryan"
    style = [voice.get("instruct") or "", voice.get("tone") or ""]
    if voice.get("exaggeration") is not None:
        e = float(voice["exaggeration"])
        style.append(next(w for lvl, w in EMOTION_WORDS if e >= lvl))
    sp = voice.get("speed")
    if sp and float(sp) < 0.95:
        style.append("slow, deliberate pace")
    elif sp and float(sp) > 1.05:
        style.append("brisk pace")
    if voice.get("fluent", True):  # neural voices hesitate mid-phrase unless told not to
        style.append("Speak each phrase in one smooth, continuous flow, never hesitating inside a phrase; "
                     "pause only at commas and full stops")
    instruct = ". ".join(x.strip().rstrip(".") for x in style if x and x.strip())
    job = {"text": text, "out": str(out.with_suffix(".raw.wav")), "language": voice.get("language", "English"),
           "sampling": voice.get("sampling"), "seed": voice.get("seed")}
    if voice.get("reference"):
        job.update(model="Base", reference=str(voice["reference"]), ref_text=voice.get("ref_text"))
    elif name == "design" or voice.get("description"):
        desc = voice.get("description") or "A deep, warm, mature male narrator voice, like a nature documentary"
        job.update(model="VoiceDesign", instruct=f"{desc}. {instruct}".strip(". "))
    else:
        job.update(model="CustomVoice", speaker=name, instruct=instruct or None)
    _qwen.run(job)
    _to_wav(Path(job["out"]), out)
    Path(job["out"]).unlink(missing_ok=True)


def _chatterbox(text: str, voice: dict, out: Path) -> None:
    """Chatterbox (MIT). model: turbo (faster) | standard (honours exaggeration = emotion);
    reference: a 5-10 s WAV of a voice you own to clone."""
    job = {"text": text, "out": str(out.with_suffix(".raw.wav")), "model": voice.get("model", "turbo"),
           "exaggeration": voice.get("exaggeration", 0.55), "cfg_weight": voice.get("cfg_weight", 0.45)}
    if voice.get("reference"):
        job["reference"] = str(voice["reference"])
    _cbox.run(job)
    _to_wav(Path(job["out"]), out)
    Path(job["out"]).unlink(missing_ok=True)


ENGINES = {"edge": _edge, "kokoro": _kokoro, "qwen": _qwen_tts, "chatterbox": _chatterbox, "piper": _piper,
           "elevenlabs": _elevenlabs, "espeak": _espeak}


_worked_engines: set[str] = set()   # engines that have voiced at least one line in this run


def _fresh(path: Path) -> bool:
    """A cached voice file that the requested engine really made (not a fallback stand-in)."""
    return path.exists() and not path.with_suffix(".fallback").exists()


def synthesize(text: str, voice: dict, out: Path) -> str:
    """Synthesize `text` into `out` (wav). Returns the engine actually used."""
    engine = voice.get("engine", "edge")
    chain = [engine]
    fb = voice.get("fallback")
    if fb and fb != engine:
        chain.append(fb)
    last: Exception | None = None
    for eng in chain:
        if eng in _failed_engines and eng != chain[-1]:
            continue
        if eng != engine and engine in _worked_engines:
            # The narrator already voiced part of this video: never switch to another voice mid-video.
            raise YtautoError(f"{engine} failed on: {text[:80]!r} ({last}); stopping rather than mixing voices")
        fn = ENGINES.get(eng)
        if not fn:
            raise YtautoError(f"Unknown TTS engine {eng!r}. Choose from {', '.join(ENGINES)}")
        try:
            v = voice if eng == engine else {**voice, "name": voice.get("fallback_name")}
            # model workers (Qwen, Chatterbox) can crash on a long run: restart and retry the same line
            tries = 5 if eng in ("qwen", "chatterbox") else 1
            for k in range(tries):
                try:
                    fn(text, v, out)
                    break
                except YtautoError as exc:
                    if k == tries - 1 or not re.search(r"crashed|failed to start|Broken pipe", str(exc)):
                        raise
                    warn(f"{eng} worker stopped ({exc}); restarting it and retrying this line ({k + 2}/{tries})")
                    import time as _t
                    _t.sleep(5)
            _worked_engines.add(eng)
            marker = out.with_suffix(".fallback")
            if eng != engine:   # cached under the primary engine's key: mark it so a later run retries the real engine
                marker.write_text(eng)
            else:
                marker.unlink(missing_ok=True)
            return eng
        except Exception as exc:  # noqa: BLE001 — fall through to the fallback engine
            last = exc
            if eng not in _failed_engines:
                warn(f"TTS engine '{eng}' failed ({str(exc).splitlines()[0][:200]})"
                     + (f"; falling back to '{chain[-1]}'" if eng != chain[-1] else ""))
            _failed_engines.add(eng)
    raise YtautoError(f"All TTS engines failed: {last}")


def _silence(path: Path, seconds: float) -> None:
    run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", f"anullsrc=r={SAMPLE_RATE}:cl=mono",
         "-t", f"{max(seconds, 0.01):.3f}", "-sample_fmt", "s16", path])


def build_scene_audio(text: str, voice: dict, cache: Path, settings: dict, fixed_duration: float | None) -> SceneAudio:
    """Voice every sentence of a scene, join them, and compute caption cues."""
    cache.mkdir(parents=True, exist_ok=True)
    sub = settings["subtitles"]
    gap = float(settings["sentence_gap"])
    items = parse_directives(text)
    pol = settings.get("voice_polish") or {}
    phrasing = pol.get("mode") == "phrasing" and pol.get("enabled", True) is not False
    if voice.get("engine") in ("qwen", "chatterbox", "elevenlabs") and (not phrasing or pol.get("merge")):
        items = merge_passages(items)
    key = stable_hash("scene-audio-v7", voice, items, gap, fixed_duration, sub["max_chars"], settings.get("align"),
                      settings.get("voice_polish"), settings.get("pause_scale"),
                      *(["cbox-v2"] if voice.get("engine") == "chatterbox" else []))
    out = cache / f"scene_{key}.wav"
    meta = cache / f"scene_{key}.json"
    m = json.loads(meta.read_text()) if out.exists() and meta.exists() else {}
    if m and not m.get("fallback"):
        return SceneAudio(out, m["duration"], [Cue(**c) for c in m["cues"]], [Cue(**w) for w in m.get("words", [])])

    pieces: list[Path] = []
    cues: list[Cue] = []
    words: list[Cue] = []
    t = 0.0

    def silence(sec: float) -> Path:
        f = cache / f"gap_{int(round(sec * 1000))}.wav"
        if not f.exists():
            _silence(f, sec)
        return f

    pause_scale = float(settings.get("pause_scale", 1.0))
    used_fallback = False
    for i, item in enumerate(items):
        if item[0] == "pause":
            prev = items[i - 1] if i else None
            ends = bool(prev and prev[0] == "say" and re.search(r"[.!?][\"'”’)]*$", prev[1].strip()))
            dur = max(0.12, item[1] * pause_scale, gap if (phrasing and ends) else 0.0)
            pieces.append(silence(dur))
            t += dur
            continue
        _, sent, over = item
        v = {**voice, **over}
        parts = [v.get("engine"), v.get("name"), v.get("rate"),
                 v.get("pitch"), v.get("length_scale"), v.get("speed"), v.get("lang"),
                 v.get("exaggeration"), v.get("cfg_weight"), v.get("reference"), v.get("tone"),
                 v.get("instruct"), v.get("description"), v.get("model"), sent]
        if v.get("sampling") or v.get("fluent") is not None or v.get("engine") == "qwen":
            parts += [v.get("sampling"), v.get("fluent", True), "sent-v2"]
        if v.get("engine") == "chatterbox":
            parts.append("cbox-v2")   # earlier Chatterbox clone takes were silently Kokoro fallbacks
        sk = stable_hash("sent-v1", *parts)
        raw = cache / f"sent_{sk}.wav"
        if phrasing:
            wav = best_take(sent, v, raw, pol)
        else:
            if not _fresh(raw):
                synthesize(sent, v, raw)
            wav = polish(raw, pol)
        used_fallback = used_fallback or any(raw.parent.glob(f"{raw.stem}*.fallback"))
        d = ffprobe_duration(wav)
        if settings.get("align", "auto") != "off":
            align_words(sent, wav, settings.get("align", "auto"))
        sw = sentence_words(sent, d, wav.with_suffix(".words.json"))
        words.extend(Cue(round(t + w.start, 3), round(t + w.end, 3), w.text) for w in sw)
        chunks = caption_chunks(sent, int(sub["max_chars"]))
        total_chars = sum(len(c) for c in chunks) or 1
        ct = t
        exact = len(sw) == len(sent.split())  # word timings line up with our tokens
        wi = 0
        for ci, c in enumerate(chunks):
            n = len(c.split())
            if exact:
                c0 = t + sw[wi].start if ci else t
                c1 = t + (sw[wi + n].start if wi + n < len(sw) else d)
                cues.append(Cue(round(c0, 3), round(c1, 3), wrap_two_lines(c, int(sub["max_chars"]))))
                wi += n
            else:
                cd = d * len(c) / total_chars
                cues.append(Cue(round(ct, 3), round(ct + cd, 3), wrap_two_lines(c, int(sub["max_chars"]))))
                ct += cd
        pieces.append(wav)
        t += d
        nxt = items[i + 1] if i + 1 < len(items) else None
        if gap > 0 and nxt is not None and nxt[0] == "say":
            pieces.append(silence(gap))
            t += gap

    if fixed_duration and fixed_duration > t:
        pad = cache / f"pad_{key}.wav"
        _silence(pad, fixed_duration - t)
        pieces.append(pad)
        t = fixed_duration
    if not pieces:
        _silence(out, fixed_duration or 1.0)
        t = fixed_duration or 1.0
    else:
        lst = cache / f"list_{key}.txt"
        lst.write_text("".join(f"file '{p.resolve()}'\n" for p in pieces))
        run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", out])
        lst.unlink(missing_ok=True)
        t = ffprobe_duration(out)

    meta.write_text(json.dumps({"duration": t, "cues": [c.__dict__ for c in cues], "words": [w.__dict__ for w in words],
                                "fallback": used_fallback}))
    return SceneAudio(out, t, cues, words)


def sentence_words(sentence: str, duration: float, words_file: Path) -> list[Cue]:
    """Word timings for one voiced sentence: exact from Edge TTS, otherwise estimated by length."""
    if words_file.exists():
        try:
            data = json.loads(words_file.read_text())
            # Edge reports words without punctuation; map back onto our tokens when counts match.
            toks = sentence.split()
            if len(data) == len(toks):
                return [Cue(w["start"], w["end"], tok) for w, tok in zip(data, toks)]
            return [Cue(w["start"], w["end"], w["text"]) for w in data]
        except (ValueError, KeyError):
            pass
    toks = sentence.split()
    weights = [len(re.sub(r"\W", "", w)) + 2 for w in toks]
    total = sum(weights) or 1
    out, acc = [], 0.0
    for tok, wgt in zip(toks, weights):
        d = duration * wgt / total
        out.append(Cue(round(acc, 3), round(acc + d * 0.9, 3), tok))
        acc += d
    return out


def list_voices(engine: str, locale: str | None = None) -> list[str]:
    if engine == "edge":
        import edge_tts

        voices = asyncio.run(edge_tts.list_voices())
        rows = [f"{v['ShortName']:<34} {v['Gender']:<7} {v['Locale']}" for v in voices
                if not locale or v["Locale"].lower().startswith(locale.lower())]
        return sorted(rows)
    if engine == "piper":
        url = "https://huggingface.co/rhasspy/piper-voices/resolve/main/voices.json"
        with urllib.request.urlopen(url, timeout=60) as r:
            data = json.loads(r.read())
        return sorted(k for k in data if not locale or k.lower().startswith(locale.lower().replace("-", "_")))
    if engine == "kokoro":
        from kokoro_onnx import Kokoro

        model, voices = ensure_kokoro()
        names = sorted(Kokoro(str(model), str(voices)).get_voices())
        hint = {"a": "US English", "b": "UK English"}
        return [f"{n:<16} {'female' if n[1] == 'f' else 'male':<7} {hint.get(n[0], n[0])}" for n in names
                if not locale or (locale.lower().startswith("en-gb") and n[0] == "b") or (locale.lower().startswith("en-us") and n[0] == "a")
                or locale.lower() == "en" and n[0] in "ab"]
    if engine == "espeak":
        return run([which("espeak-ng") or "espeak", "--voices"]).splitlines()
    return ["ElevenLabs: see https://elevenlabs.io/app/voice-library (use the voice id)"]

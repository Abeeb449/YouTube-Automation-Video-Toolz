"""Text-to-speech engines and per-scene voiceover assembly.

Engines
-------
edge        Microsoft Edge neural voices via the free `edge-tts` package. Best free
            quality, needs internet. Voice ids like "en-US-AndrewNeural".
piper       Fully offline neural TTS (https://github.com/rhasspy/piper). Voice ids
            like "en_US-lessac-medium"; models are downloaded once and cached.
elevenlabs  Premium voices. Needs ELEVENLABS_API_KEY. Voice = ElevenLabs voice id.
espeak      Robotic but always-available offline fallback (espeak-ng).
"""
from __future__ import annotations

import asyncio
import json
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
    kwargs = {"rate": voice.get("rate", "+0%"), "pitch": voice.get("pitch", "+0Hz")}
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
            length_scale = voice.get("length_scale")
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


ENGINES = {"edge": _edge, "piper": _piper, "elevenlabs": _elevenlabs, "espeak": _espeak}


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
        fn = ENGINES.get(eng)
        if not fn:
            raise YtautoError(f"Unknown TTS engine {eng!r}. Choose from {', '.join(ENGINES)}")
        try:
            fn(text, voice, out)
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
    sentences = split_sentences(text)
    key = stable_hash("scene-audio-v4", voice, sentences, gap, fixed_duration, sub["max_chars"])
    out = cache / f"scene_{key}.wav"
    meta = cache / f"scene_{key}.json"
    if out.exists() and meta.exists():
        m = json.loads(meta.read_text())
        return SceneAudio(out, m["duration"], [Cue(**c) for c in m["cues"]], [Cue(**w) for w in m.get("words", [])])

    pieces: list[Path] = []
    cues: list[Cue] = []
    words: list[Cue] = []
    t = 0.0
    gap_file = cache / f"gap_{int(gap * 1000)}.wav"
    if gap > 0 and not gap_file.exists():
        _silence(gap_file, gap)
    for i, sent in enumerate(sentences):
        sk = stable_hash("sent-v1", voice.get("engine"), voice.get("name"), voice.get("rate"),
                         voice.get("pitch"), voice.get("length_scale"), sent)
        wav = cache / f"sent_{sk}.wav"
        if not wav.exists():
            synthesize(sent, voice, wav)
        d = ffprobe_duration(wav)
        sw = sentence_words(sent, d, wav.with_suffix(".words.json"))
        words.extend(Cue(round(t + w.start, 3), round(t + w.end, 3), w.text) for w in sw)
        chunks = caption_chunks(sent, int(sub["max_chars"]))
        total_chars = sum(len(c) for c in chunks) or 1
        ct = t
        exact = len(sw) == len(sent.split())  # engine word timings line up with our tokens
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
        if gap > 0 and i < len(sentences) - 1:
            pieces.append(gap_file)
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

    meta.write_text(json.dumps({"duration": t, "cues": [c.__dict__ for c in cues], "words": [w.__dict__ for w in words]}))
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
    if engine == "espeak":
        return run([which("espeak-ng") or "espeak", "--voices"]).splitlines()
    return ["ElevenLabs: see https://elevenlabs.io/app/voice-library (use the voice id)"]

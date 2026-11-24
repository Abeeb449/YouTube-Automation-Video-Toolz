"""Chatterbox worker (MIT). Run with the chatterbox venv's python; reads JSON jobs on stdin:
{"text": ..., "out": "/path.wav", "model": "turbo"|"standard", "reference": "/voice.wav",
 "exaggeration": 0.5, "cfg_weight": 0.5}
Turbo is faster; "standard" honours exaggeration (emotion intensity)."""
import json
import os
import sys
import time

import torch
import torchaudio as ta

torch.set_num_threads(int(os.environ.get("YTAUTO_TTS_THREADS", os.cpu_count() or 4)))
_models = {}


def model(kind: str):
    if kind not in _models:
        dev = "cuda" if torch.cuda.is_available() else "cpu"
        if kind == "standard":
            from chatterbox.tts import ChatterboxTTS
            _models[kind] = ChatterboxTTS.from_pretrained(device=dev)
        else:
            from chatterbox.tts_turbo import ChatterboxTurboTTS
            _models[kind] = ChatterboxTurboTTS.from_pretrained(device=dev)
        m = _models[kind]
        if hasattr(m, "norm_loudness"):
            # upstream bug: loudness normalisation returns float64, which breaks voice cloning
            # ("expected scalar type Double but found Float"); keep the reference clip float32
            orig = m.norm_loudness
            m.norm_loudness = lambda wav, sr, *a, **k: orig(wav, sr, *a, **k).astype("float32")
    return _models[kind]


def main():
    print(json.dumps({"ready": True}), flush=True)
    for line in sys.stdin:
        if not line.strip():
            continue
        job = json.loads(line)
        try:
            t = time.time()
            kind = job.get("model") or "turbo"
            m = model(kind)
            kw = {}
            if job.get("reference"):
                kw["audio_prompt_path"] = job["reference"]
            if kind == "standard":
                kw["exaggeration"] = float(job.get("exaggeration", 0.5))
                kw["cfg_weight"] = float(job.get("cfg_weight", 0.5))
            wav = m.generate(job["text"], **kw)
            ta.save(job["out"], wav, m.sr)
            print(json.dumps({"ok": True, "seconds": round(wav.shape[-1] / m.sr, 3), "took": round(time.time() - t, 2)}), flush=True)
        except Exception as exc:  # noqa: BLE001
            print(json.dumps({"ok": False, "error": f"{type(exc).__name__}: {exc}"}), flush=True)


if __name__ == "__main__":
    main()

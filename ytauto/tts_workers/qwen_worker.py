"""Qwen3-TTS worker (Apache 2.0). Run with the qwen venv's python; reads JSON jobs on stdin:
{"text": ..., "out": "/path.wav", "model": "CustomVoice"|"VoiceDesign"|"Base", "speaker": "ryan",
 "instruct": "how to say it", "language": "English", "reference": "/ref.wav", "ref_text": "...",
 "sampling": {"temperature": 0.8, "top_p": 0.95, ...}, "seed": 7}
and answers {"ok": true, "seconds": d} or {"ok": false, "error": "..."} per line."""
import json
import os
import sys
import time

from pathlib import Path

# A model that is already on this machine is loaded straight from its folder, without asking the model host: the host
# limits how often it may be asked, and a refusal must never stop (or change the voice of) a narration.
# YTAUTO_HF_ONLINE=1 asks the host again (to fetch a newer copy).
_hub = Path(os.environ.get("HF_HOME") or Path.home() / ".cache" / "huggingface") / "hub"

import soundfile as sf  # noqa: E402
import torch  # noqa: E402

torch.set_num_threads(int(os.environ.get("YTAUTO_TTS_THREADS", os.cpu_count() or 4)))
from qwen_tts import Qwen3TTSModel  # noqa: E402

_models = {}


def model(kind: str):
    if kind not in _models:
        # one 1.7B model at a time: two in float32 don't fit in 16 GB of RAM
        _models.clear()
        import gc
        gc.collect()
        size = os.environ.get("YTAUTO_QWEN_SIZE", "1.7B")
        repo = os.environ.get(f"YTAUTO_QWEN_{kind.upper()}_REPO", f"Qwen/Qwen3-TTS-12Hz-{size}-{kind}")
        dev = "cuda:0" if torch.cuda.is_available() else "cpu"
        dtype = torch.bfloat16 if dev != "cpu" else torch.float32
        local = None
        if not os.environ.get("YTAUTO_HF_ONLINE"):
            snaps = sorted((_hub / f"models--{repo.replace('/', '--')}" / "snapshots").glob("*"), key=lambda p: p.stat().st_mtime)
            if snaps and (snaps[-1] / "config.json").exists():
                local = str(snaps[-1])
        _models[kind] = Qwen3TTSModel.from_pretrained(local or repo, device_map=dev, dtype=dtype)
    return _models[kind]


def main():
    print(json.dumps({"ready": True}), flush=True)
    for line in sys.stdin:
        if not line.strip():
            continue
        job = json.loads(line)
        try:
            t = time.time()
            kind = job.get("model") or ("Base" if job.get("reference") else "CustomVoice")
            m = model(kind)
            lang = job.get("language", "English")
            gen = {k: v for k, v in (job.get("sampling") or {}).items() if v is not None}
            # 12 codec frames per second of audio; ~14 characters per spoken second. A generous cap stops the rare
            # runaway take (no end token) from generating minutes of audio.
            gen.setdefault("max_new_tokens", int(12 * (len(job["text"]) / 9 + 6)))
            if job.get("seed") is not None:
                torch.manual_seed(int(job["seed"]))
            if kind == "VoiceDesign":
                wavs, sr = m.generate_voice_design(text=job["text"], language=lang, instruct=job.get("instruct") or "", **gen)
            elif kind == "Base":
                wavs, sr = m.generate_voice_clone(text=job["text"], language=lang, ref_audio=job["reference"],
                                                  ref_text=job.get("ref_text"), x_vector_only_mode=not job.get("ref_text"), **gen)
            else:
                wavs, sr = m.generate_custom_voice(text=job["text"], speaker=job.get("speaker") or "ryan",
                                                   language=lang, instruct=job.get("instruct") or None, **gen)
            sf.write(job["out"], wavs[0], sr)
            print(json.dumps({"ok": True, "seconds": round(len(wavs[0]) / sr, 3), "took": round(time.time() - t, 2)}), flush=True)
        except Exception as exc:  # noqa: BLE001
            print(json.dumps({"ok": False, "error": f"{type(exc).__name__}: {exc}"}), flush=True)


if __name__ == "__main__":
    main()

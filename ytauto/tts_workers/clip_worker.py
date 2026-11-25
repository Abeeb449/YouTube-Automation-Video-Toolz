"""CLIP worker: scores how well images match text (used to check that every stock photo/clip really shows
what the narration says). Run with a Python that has torch + transformers (the Qwen-TTS venv has both).

Reads JSON jobs on stdin: {"images": ["/a.jpg", ...], "texts": ["a photo of a leopard seal", ...]}
Answers: {"ok": true, "probs": [[p_text0, p_text1, ...] per image], "sims": [[cosine ...] per image]}
Model: env YTAUTO_CLIP_MODEL (default openai/clip-vit-large-patch14, MIT licence).
"""
import json
import os
import sys

import torch
from PIL import Image
from transformers import CLIPModel, CLIPProcessor

torch.set_num_threads(int(os.environ.get("YTAUTO_TTS_THREADS", os.cpu_count() or 4)))
NAME = os.environ.get("YTAUTO_CLIP_MODEL", "openai/clip-vit-large-patch14")
model = CLIPModel.from_pretrained(NAME).eval()
proc = CLIPProcessor.from_pretrained(NAME)


def main():
    print(json.dumps({"ready": True, "model": NAME}), flush=True)
    for line in sys.stdin:
        if not line.strip():
            continue
        job = json.loads(line)
        try:
            imgs = [Image.open(p).convert("RGB") for p in job["images"]]
            groups = job.get("groups") or [job["texts"]]   # several separate questions, one softmax each
            flat = [t for g in groups for t in g]
            with torch.no_grad():
                inp = proc(text=flat, images=imgs, return_tensors="pt", padding=True)
                out = model(**inp)
                ie = out.image_embeds / out.image_embeds.norm(dim=-1, keepdim=True)
                te = out.text_embeds / out.text_embeds.norm(dim=-1, keepdim=True)
                sims = ie @ te.T
                scale = model.logit_scale.exp()
                res, i = [], 0
                for g in groups:
                    res.append((sims[:, i:i + len(g)] * scale).softmax(dim=-1).tolist())
                    i += len(g)
            print(json.dumps({"ok": True, "probs": res[0], "groups": res, "sims": sims.tolist()}), flush=True)
        except Exception as exc:  # noqa: BLE001
            print(json.dumps({"ok": False, "error": f"{type(exc).__name__}: {exc}"}), flush=True)


if __name__ == "__main__":
    main()

"""Command line interface: python -m ytauto <command> …"""
from __future__ import annotations

import argparse
import re
import shutil
import sys
from collections import Counter
from pathlib import Path

import yaml

from .utils import REPO_ROOT, YtautoError, find_font, log, run, which

STOPWORDS = set("""a about above after again against all am an and any are as at be because been before being below
between both but by can could did do does doing down during each few for from further had has have having he her here
hers herself him himself his how i if in into is it its itself just let me more most my myself no nor not now of off on
once only or other our ours ourselves out over own same she should so some such than that the their theirs them
themselves then there these they this those through to too under until up very was we were what when where which while
who whom why will with would you your yours yourself yourselves also like one two three many much get got make made
even still really thing things way ways something every yet well may might must us lot lots dont doesnt isnt youre
its thats theres whats let lets going go use used using know need want see look""".split())

TEMPLATE = """\
# ytauto project — edit me, then: python -m ytauto render {path}
title: "{title}"
description: |
  Write your YouTube description here. Chapters are appended automatically.
tags: [automation, tutorial]

settings:
  voice:
    engine: kokoro               # kokoro (free, offline, commercial OK) | edge | chatterbox | piper | elevenlabs | espeak
    name: bm_george              # list voices: python -m ytauto voices --engine kokoro
    rate: "+0%"
  # music: {{file: assets/music.mp3, volume: 0.12, duck: true}}
  # watermark: {{file: assets/logo.png, position: top-right}}
  subtitles: {{burn: true}}

thumbnail:
  text: "{title}"

youtube:
  privacy: private
  category_id: 27               # 27 = Education, 22 = People & Blogs, 28 = Science & Tech

scenes:
  - chapter: Intro
    text: "Welcome back to the channel. Today we are going to learn something new."
    visual: {{remotion: TitleCard, props: {{title: "{title}", subtitle: "Let's get started"}}}}

  - text: "Every scene has narration text and a visual. The visual stretches to match the voiceover."
    visual: {{remotion: KineticText, props: {{highlight: [narration, visual]}}}}

  - chapter: Main idea
    text: "You can use your own images and videos, stock footage, colour cards, Remotion animations or Blender 3D."
    visual: {{color: "#1e293b", text: "Main idea", subtext: "Use any visual you like"}}
"""


def cmd_new(a) -> int:
    dest = Path(a.path)
    if (dest / "script.yaml").exists() and not a.force:
        raise YtautoError(f"{dest}/script.yaml already exists (use --force to overwrite)")
    (dest / "assets").mkdir(parents=True, exist_ok=True)
    title = a.title or dest.name.replace("-", " ").replace("_", " ").title()
    if a.from_text:
        data = script_from_text(Path(a.from_text).read_text(encoding="utf-8"), title, a.visuals, a.voice)
        (dest / "script.yaml").write_text(
            "# Generated from text. Tweak visuals per scene, then render.\n"
            + yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=110), encoding="utf-8")
        log(f"Created {dest}/script.yaml with {len(data['scenes'])} scenes")
    else:
        (dest / "script.yaml").write_text(TEMPLATE.format(title=title, path=dest), encoding="utf-8")
        log(f"Created {dest}/script.yaml")
    return 0


def keywords(text: str, n: int = 3) -> str:
    words = [w.lower() for w in re.findall(r"[A-Za-z][A-Za-z'-]{2,}", text)]
    words = [w.strip("'") for w in words if w.strip("'") not in STOPWORDS]
    common = [w for w, _ in Counter(words).most_common(n)]
    return " ".join(common) or "abstract background"


def script_from_text(text: str, title: str, visuals: str, voice: str | None) -> dict:
    """Plain text → scenes.

    - Blank lines separate scenes.
    - "# Heading" lines start a new chapter (and add a title card).
    - "[visual: pexels:ocean]" inside a paragraph sets that scene's visual explicitly.
    - Long paragraphs get one visual per ~35 words so 10-15 minute videos stay dynamic.
    """
    scenes = []
    blocks = re.split(r"\n\s*\n", text.strip())
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        if block.startswith("#"):
            first, _, rest = block.partition("\n")
            chapter = first.lstrip("#").strip()
            scenes.append({"chapter": chapter, "duration": 2.5,
                           "visual": {"remotion": "TitleCard", "props": {"title": chapter}}})
            block = rest.strip()
            if not block:
                continue
        explicit = re.findall(r"\[visual:\s*([^\]]+)\]", block)
        body = re.sub(r"\[visual:[^\]]+\]", "", block)
        body = re.sub(r"\s+", " ", body).strip()
        if not body:
            continue
        scene: dict = {"text": body}
        if explicit:
            scene["visual"] = [v.strip() for v in explicit] if len(explicit) > 1 else explicit[0].strip()
        else:
            words = body.split()
            n = max(1, round(len(words) / 35))
            chunks = [" ".join(words[i * len(words) // n:(i + 1) * len(words) // n]) for i in range(n)]
            if visuals == "stock":
                vs = [f"pexels:{keywords(c)}" for c in chunks]
            elif visuals == "photo":
                vs = [f"pexels-photo:{keywords(c)}" for c in chunks]
            else:
                vs = [{"remotion": "KineticText", "props": {"text": c}} for c in chunks]
            scene["visual"] = vs if len(vs) > 1 else vs[0]
        scenes.append(scene)
    # The first title card should carry the video title.
    scenes.insert(0, {"chapter": "Intro", "duration": 3,
                      "visual": {"remotion": "TitleCard", "props": {"title": title}}})
    settings: dict = {"voice": {"engine": "edge", "name": voice or "en-US-AndrewNeural"}}
    return {"title": title, "description": "", "tags": [], "settings": settings,
            "thumbnail": {"text": title}, "youtube": {"privacy": "private"}, "scenes": scenes}


def cmd_render(a) -> int:
    from .config import load_project
    from .pipeline import render_project

    overrides = {}
    if a.preview:
        overrides = {"width": 960, "height": 540, "preset": "ultrafast", "crf": 26}
    if a.voice_engine:
        overrides.setdefault("voice", {})["engine"] = a.voice_engine
    if a.music:
        overrides["music"] = {"none": None, "generate": {"generate": True, "source": None}}.get(a.music, {"source": a.music})
    project = load_project(a.project, overrides)
    if a.clean:
        shutil.rmtree(project.cache_dir, ignore_errors=True)
        shutil.rmtree(project.build_dir, ignore_errors=True)
    render_project(project, preview=a.preview)
    return 0


def cmd_plan(a) -> int:
    from .planner import write_plan

    script = Path(a.script)
    out = Path(a.out) if a.out else (script.parent if script.parent.name not in ("", ".") else Path("projects") / script.stem)
    write_plan(script, out, a.style, a.title, a.director, a.model)
    return 0


def cmd_make(a) -> int:
    """Plain script → planned scenes → rendered video, in one go."""
    from .config import load_project
    from .pipeline import render_project
    from .planner import write_plan

    script = Path(a.script)
    out = Path(a.out) if a.out else script.parent
    if not (out / "script.yaml").exists() or a.replan:
        write_plan(script, out, a.style, a.title, a.director, a.model)
    overrides = {"width": 960, "height": 540, "preset": "ultrafast", "crf": 26} if a.preview else {}
    render_project(load_project(out, overrides), preview=a.preview)
    return 0


def cmd_voices(a) -> int:
    from .tts import list_voices

    for row in list_voices(a.engine, a.locale):
        print(row)
    return 0


def cmd_doctor(_a) -> int:
    ok = True

    def check(name, good, hint=""):
        nonlocal ok
        print(f"  {'✔' if good else '✘'} {name}" + ("" if good else f"   → {hint}"))
        ok &= bool(good) or not hint.startswith("REQUIRED")

    print("ytauto environment check")
    check("ffmpeg", which("ffmpeg"), "REQUIRED: install ffmpeg")
    if which("ffmpeg"):
        filters = run(["ffmpeg", "-hide_banner", "-filters"])
        check("ffmpeg subtitles filter (libass)", " subtitles " in filters, "needed to burn captions")
    check("font for text cards", find_font(), "install fonts-dejavu or set YTAUTO_FONT")
    for mod, hint in (("kokoro_onnx", "pip install kokoro-onnx soundfile (best free voice)"), ("edge_tts", "pip install edge-tts"),
                      ("piper", "pip install piper-tts"), ("chatterbox", "optional: pip install chatterbox-tts (GPU recommended)"),
                      ("googleapiclient", "pip install google-api-python-client (YouTube upload)")):
        try:
            __import__(mod)
            check(f"python: {mod}", True)
        except ImportError:
            check(f"python: {mod}", False, hint)
    check("espeak-ng (offline fallback voice)", which("espeak-ng") or which("espeak"), "apt install espeak-ng")
    check("node / npx (Remotion)", which("npx"), "install Node.js 18+")
    check("remotion installed", (REPO_ROOT / "remotion" / "node_modules").exists(), "cd remotion && npm install")
    check("blender", which("blender"), "optional: needed only for blender: visuals")
    for tool, hint in (("inkscape", "SVG drawing/conversion"), ("convert", "ImageMagick"), ("potrace", "bitmap → vector"),
                       ("rsvg-convert", "librsvg"), ("sox", "audio tools")):
        check(tool, which(tool), f"optional: {hint}")
    for mod, hint in (("rembg", 'pip install "rembg[cpu]" (ytauto cutout)'), ("faster_whisper", "pip install faster-whisper (exact word timing)")):
        try:
            __import__(mod)
            check(f"python: {mod}", True)
        except ImportError:
            check(f"python: {mod}", False, f"optional: {hint}")
    import os
    for key in ("PEXELS_API_KEY", "PIXABAY_API_KEY", "ELEVENLABS_API_KEY", "YT_REFRESH_TOKEN"):
        check(f"env {key}", os.environ.get(key), "optional")
    return 0 if ok else 1


def cmd_cutout(a) -> int:
    """Remove the background from photos/AI images so they can be animated as `image:` actors."""
    try:
        from PIL import Image, ImageFilter
        from rembg import new_session, remove
    except ImportError as exc:
        raise YtautoError('pip install "rembg[cpu]" (background removal)') from exc
    session = new_session(a.model)
    for src in a.images:
        src = Path(src)
        out = Path(a.out) / f"{src.stem}.png" if a.out else src.with_name(f"{src.stem}-cutout.png")
        out.parent.mkdir(parents=True, exist_ok=True)
        im = remove(Image.open(src).convert("RGB"), session=session)
        bbox = im.getchannel("A").point(lambda v: 255 if v > 20 else 0).getbbox()
        if bbox:  # trim empty space so `scale` in scripts behaves predictably
            im = im.crop(bbox)
        if a.outline:  # sticker-style outline, reads well on dark water
            alpha = im.getchannel("A").filter(ImageFilter.MaxFilter(a.outline * 2 + 1))
            border = Image.new("RGBA", im.size, (255, 255, 255, 0))
            border.putalpha(alpha)
            pad = Image.new("RGBA", im.size, (0, 0, 0, 0))
            pad.alpha_composite(Image.new("RGBA", im.size, (240, 244, 246, 255)), (0, 0))
            pad.putalpha(alpha)
            pad.alpha_composite(im)
            im = pad
        if a.flip:
            im = im.transpose(Image.FLIP_LEFT_RIGHT)
        im.save(out)
        log(f"cut-out → {out}")
    return 0


def cmd_upload(a) -> int:
    from .config import load_project
    from .youtube import upload

    project = load_project(a.project)
    upload(project.build_dir, a.privacy)
    return 0


def cmd_auth(a) -> int:
    from .youtube import authorize

    authorize(a.client_secrets)
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="ytauto", description="Script → narrated, captioned YouTube video.")
    sp = ap.add_subparsers(dest="cmd", required=True)

    p = sp.add_parser("new", help="create a project (optionally from a plain-text script)")
    p.add_argument("path")
    p.add_argument("--title")
    p.add_argument("--from-text", help="plain text/markdown file: blank lines separate scenes, '# ' = chapter")
    p.add_argument("--visuals", choices=["kinetic", "stock", "photo"], default="kinetic",
                   help="auto visuals for --from-text (stock/photo need PEXELS_API_KEY or PIXABAY_API_KEY)")
    p.add_argument("--voice", help="voice name for the generated script")
    p.add_argument("--force", action="store_true")
    p.set_defaults(fn=cmd_new)

    p = sp.add_parser("render", help="render a project to build/<title>.mp4")
    p.add_argument("project")
    p.add_argument("--preview", action="store_true", help="fast low-res render (480p) for checking timing")
    p.add_argument("--clean", action="store_true", help="drop caches and re-render everything")
    p.add_argument("--voice-engine", help="override the TTS engine (kokoro, edge, chatterbox, piper, elevenlabs, espeak)")
    p.add_argument("--music", choices=["incompetech", "openverse", "library", "generate", "none"], help="override the background music source")
    p.set_defaults(fn=cmd_render)

    for name, fn, hlp in (("plan", cmd_plan, "turn a plain narration script (.txt) into script.yaml scenes"),
                          ("make", cmd_make, "plain script → planned scenes → finished video, in one step")):
        p = sp.add_parser(name, help=hlp)
        p.add_argument("script", help="plain text narration; blank lines between paragraphs, optional '# Chapter' lines")
        p.add_argument("--style", choices=["ocean", "documentary"], default="ocean")
        p.add_argument("--title")
        p.add_argument("--out", help="project folder (default: the script's folder)")
        p.add_argument("--director", choices=["auto", "claude", "rules"], default="auto",
                       help="claude = Claude API (needs ANTHROPIC_API_KEY, best); rules = free offline; auto = claude if a key is set")
        p.add_argument("--model", help="Claude model for the director (default claude-opus-5-5)")
        if name == "make":
            p.add_argument("--preview", action="store_true")
            p.add_argument("--replan", action="store_true", help="re-plan even if script.yaml exists")
        p.set_defaults(fn=fn)

    p = sp.add_parser("voices", help="list available voices")
    p.add_argument("--engine", default="kokoro", choices=["kokoro", "edge", "piper", "espeak", "elevenlabs"])
    p.add_argument("--locale", help="e.g. en, en-GB, es")
    p.set_defaults(fn=cmd_voices)

    p = sp.add_parser("doctor", help="check installed tools")
    p.set_defaults(fn=cmd_doctor)

    p = sp.add_parser("cutout", help="remove backgrounds from images (animals for image: actors)")
    p.add_argument("images", nargs="+")
    p.add_argument("--out", help="output folder (default: next to each image, *-cutout.png)")
    p.add_argument("--model", default="isnet-general-use", help="rembg model (isnet-general-use, u2net, birefnet-general…)")
    p.add_argument("--outline", type=int, default=0, help="add a light sticker outline N px wide")
    p.add_argument("--flip", action="store_true", help="mirror horizontally (creatures should face right)")
    p.set_defaults(fn=cmd_cutout)

    p = sp.add_parser("upload", help="upload a rendered project to YouTube")
    p.add_argument("project")
    p.add_argument("--privacy", choices=["private", "unlisted", "public"])
    p.set_defaults(fn=cmd_upload)

    p = sp.add_parser("youtube-auth", help="one-time OAuth to get a YouTube refresh token")
    p.add_argument("--client-secrets", required=True)
    p.set_defaults(fn=cmd_auth)

    a = ap.parse_args(argv)
    try:
        return a.fn(a)
    except YtautoError as exc:
        print(f"\nERROR: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130

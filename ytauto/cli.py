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
        overrides = {"_preview_half": True, "preset": "ultrafast", "crf": 26}
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


def cmd_voiceover(a) -> int:
    """Narration only, as an MP3 (no video): to review the voice before rendering."""
    from concurrent.futures import ThreadPoolExecutor

    from .config import load_project
    from .tts import build_scene_audio, narration_inputs, shutdown_workers
    from .utils import log, run

    project = load_project(a.project, {})
    from .sound_director import direct_narration
    direct_narration(project)   # narrator direction from the script's content (unless the project sets one)
    st = dict(project.settings)
    if a.plain:
        st["narration"] = "natural"
    elif a.polished:
        st["narration"] = "polished"
    voice = dict(st["voice"])
    over = {}
    if a.engine:  # e.g. --engine chatterbox; no silent fallback to another voice when you asked for this one
        over.update(engine=a.engine, fallback=None)
    from .config import VOICE_PROFILES, resolve_voice
    if a.voice in VOICE_PROFILES:  # a named narrator, e.g. --voice deep-british
        over.update(resolve_voice(a.voice))
    elif a.voice:  # try another speaker, e.g. --voice aiden (Qwen: ryan aiden eric dylan serena vivian uncle_fu ono_anna sohee)
        over["name"] = a.voice
    if a.reference:  # clone the voice in this 5-10 s clip (Chatterbox / Qwen Base); use only voices you have rights to
        over["reference"] = str(Path(a.reference).resolve())
    voice.update(over)
    cache = project.cache_dir / "tts"
    scenes = project.scenes[: a.scenes] if a.scenes else project.scenes

    def one(scene):
        text, v, sst = narration_inputs(scene.text, {**voice, **(scene.voice or {}), **over}, st)
        return build_scene_audio(text, v, cache, sst, None) if text.strip() else None

    with ThreadPoolExecutor(max_workers=2) as ex:
        audios = [x for x in ex.map(one, scenes) if x]
    shutdown_workers()
    gap = cache / "scene_gap.wav"
    from .tts import _silence
    _silence(gap, float(st.get("padding", 0.3)))
    lst = cache / "voiceover_list.txt"
    lst.write_text("".join(f"file '{p.resolve()}'\n" for au in audios for p in (au.path, gap)))
    out = Path(a.out) if a.out else project.build_dir / f"voiceover{'-' + a.voice if a.voice else ''}.mp3"
    out.parent.mkdir(parents=True, exist_ok=True)
    run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", lst,
         "-af", f"loudnorm=I={st.get('loudness', -16)}:TP=-1.5:LRA=11", "-ar", "44100", "-c:a", "libmp3lame", "-b:a", "192k", out])
    log(f"Voiceover → {out}")
    return 0


def cmd_check(a) -> int:
    """Pre-render review: originality vs your other projects, sourced facts, shot variety, YouTube readiness."""
    from .check import check
    rep = check(Path(a.project), [Path(x) for x in a.against or []])
    print(f"Checking {a.project}")
    print(rep.render())
    if rep.fails or (a.strict and rep.warns):
        return 1
    return 0


def cmd_broll(a) -> int:
    """Collect the b-roll only: search, check and download everything the script asks for, and write the report
    and picture sheet to build/ so it can be reviewed before any rendering."""
    from .broll import collect_broll
    from .config import load_project
    project = load_project(a.project)
    data = collect_broll(project, refresh=a.refresh, minutes=a.minutes)
    print((project.build_dir / "broll_report.txt").read_text() if data["requested"] else "No b-roll requested in this script.")
    return 0


def cmd_model(a) -> int:
    """3D models: list the hand-built ones, or render one (or any model file) from every side to check it."""
    from .models3d import check_views, handmade_index
    if not a.name:
        for m in handmade_index():
            print(f"{m['title']}  (blender/handmade/{m['slug']}.py; found by: {', '.join(m['names'][:4])})")
        return 0
    out = Path(a.out or f"{re.sub(r'[^a-z0-9]+', '-', a.name.lower()).strip('-')}-views.jpg")
    print(f"Check sheet written → {check_views(a.name, out)}")
    return 0


def cmd_plan(a) -> int:
    from .planner import write_plan

    script = Path(a.script)
    out = Path(a.out) if a.out else (script.parent if script.parent.name not in ("", ".") else Path("projects") / script.stem)
    write_plan(script, out, a.style, a.title, fmt=a.format, broll=a.broll)
    return 0


def cmd_make(a) -> int:
    """Plain script → planned scenes → rendered video, in one go."""
    from .config import load_project
    from .pipeline import render_project
    from .planner import write_plan

    script = Path(a.script)
    out = Path(a.out) if a.out else script.parent
    if not (out / "script.yaml").exists() or a.replan:
        write_plan(script, out, a.style, a.title, fmt=a.format, broll=a.broll)
    overrides = {"_preview_half": True, "preset": "ultrafast", "crf": 26} if a.preview else {}
    render_project(load_project(out, overrides), preview=a.preview)
    return 0


def cmd_narrate(a) -> int:
    """Record the narration of a project exactly as a render would, and keep it with the project (narration/).
    The Ryan voice engine needs about 12 GB of memory, more than a standard GitHub runner has: record here, commit
    the folder, and the render reuses the recordings."""
    from .config import load_project
    from .pipeline import narrate
    from .utils import log, run
    project = load_project(a.project, {})
    audios = narrate(project, pack=True)
    total = sum(au.duration for au in audios)
    lst = project.cache_dir / "tts" / "narrate_list.txt"
    lst.write_text("".join(f"file '{au.path.resolve()}'\n" for au in audios if au.duration > 0))
    out = project.build_dir / "narration.mp3"
    out.parent.mkdir(parents=True, exist_ok=True)
    run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", lst, "-c:a", "libmp3lame", "-b:a", "128k", out])
    log(f"Narration: {total / 60:.1f} min in {len(audios)} scenes → {out} (to listen to)")
    return 0


def cmd_sprites(a) -> int:
    from .sprites import ensure_all

    ensure_all(force=a.force)
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
    for key in ("UNSPLASH_ACCESS_KEY", "PEXELS_API_KEY", "PIXABAY_API_KEY", "ELEVENLABS_API_KEY", "YT_REFRESH_TOKEN"):
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
        p.add_argument("--style", choices=["auto", "nature", "ocean", "documentary"], default="auto",
                       help="nature = any animal (real photos/video + 3D close-ups); ocean = drawn deep-sea look; documentary = what-if infographics")
        p.add_argument("--title")
        p.add_argument("--format", choices=["video", "shorts"], default="video",
                       help="video = 16:9 1080p (default); shorts = vertical 1080x1920 with burned-in captions")
        p.add_argument("--broll", choices=["script", "auto"], default="script",
                       help="script (default) = stock video/photos only where the script has 'B-roll:' / 'Video:' / "
                            "'Photo:' lines, with those search words; auto = the toolkit also picks search words itself")
        p.add_argument("--out", help="project folder (default: the script's folder)")
        if name == "make":
            p.add_argument("--preview", action="store_true")
            p.add_argument("--replan", action="store_true", help="re-plan even if script.yaml exists")
        p.set_defaults(fn=fn)

    p = sp.add_parser("voiceover", help="export only the narration as an MP3 (no video)")
    p.add_argument("project")
    p.add_argument("--plain", action="store_true", help="force the natural read (settings.narration: natural)")
    p.add_argument("--polished", action="store_true", help="force retakes + pause editing (settings.narration: polished)")
    p.add_argument("--voice", help="voice profile (ryan, deep-british, american-baritone, female-british) or a Qwen speaker, e.g. aiden")
    p.add_argument("--engine", help="TTS engine instead of the project's: qwen | chatterbox | kokoro | piper | edge")
    p.add_argument("--reference", help="5-10 s WAV of a voice to clone (chatterbox, qwen)")
    p.add_argument("--scenes", type=int, help="only the first N scenes (quick voice samples)")
    p.add_argument("--out")
    p.set_defaults(fn=cmd_voiceover)

    p = sp.add_parser("narrate", help="record the narration ahead of the render and keep it with the project (narration/)")
    p.add_argument("project")
    p.set_defaults(fn=cmd_narrate)

    p = sp.add_parser("sprites", help="render the 3D creature sprite library with Blender")
    p.add_argument("--force", nargs="*", default=[], help="re-render, e.g. leopardSeal or leopardSeal:side")
    p.set_defaults(fn=cmd_sprites)

    p = sp.add_parser("voices", help="list available voices")
    p.add_argument("--engine", default="kokoro", choices=["kokoro", "edge", "piper", "espeak", "elevenlabs"])
    p.add_argument("--locale", help="e.g. en, en-GB, es")
    p.set_defaults(fn=cmd_voices)

    p = sp.add_parser("check", help="review a script before rendering: originality, sources, variety, YouTube readiness")
    p.add_argument("project", help="project folder (script.yaml or script.txt)")
    p.add_argument("--against", nargs="*", help="more folders of past projects to compare with (default: projects/)")
    p.add_argument("--strict", action="store_true", help="also fail on warnings")
    p.set_defaults(fn=cmd_check)

    p = sp.add_parser("broll", help="collect the b-roll only (search, check, download) and write build/broll_report.txt "
                                    "+ broll_sheet.jpg to review before rendering")
    p.add_argument("project", help="project folder with script.yaml")
    p.add_argument("--refresh", action="store_true", help="search everything again instead of reusing earlier answers")
    p.add_argument("--minutes", type=float, default=None,
                   help="stop starting new searches after this many minutes (the rest is reported as not searched)")
    p.set_defaults(fn=cmd_broll)

    p = sp.add_parser("model", help="hand-built 3D models: list them, or render one from every side to check it")
    p.add_argument("name", nargs="?", help="a hand-built model's name (e.g. 'great pyramid') or a model file (.glb, .stl …)")
    p.add_argument("--out", help="where to write the check sheet (default: <name>-views.jpg)")
    p.set_defaults(fn=cmd_model)

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

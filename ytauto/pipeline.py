"""Render a project end-to-end: voiceover → clips → concat → mix → captions → final MP4."""
from __future__ import annotations

import json
import os
import shutil
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

from .config import Project
from .cues import find_word_time, resolve_cues
from .music import MOODS, build_duck_envelope, build_score, speech_from_audio
from .sound import BUILTIN, build_track
from .tts import Cue, SceneAudio, build_scene_audio, shutdown_workers, strip_directives
from .utils import YtautoError, find_font, fmt_ts, log, run, stable_hash, warn
from .visuals import ClipRenderer


@dataclass
class ScenePlan:
    scene_index: int
    start: float
    duration: float
    audio: SceneAudio
    clip_frames: list[int]


def _workers(settings: dict) -> int:
    w = int(settings.get("workers") or 0)
    return w if w > 0 else max(1, (os.cpu_count() or 2) // 2)


def _srt_time(t: float) -> str:
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _ass_time(t: float) -> str:
    cs = int(round(t * 100))
    h, cs = divmod(cs, 360_000)
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def write_captions(cues: list[Cue], build: Path, settings: dict) -> tuple[Path, Path]:
    srt = build / "captions.srt"
    srt.write_text("".join(f"{i}\n{_srt_time(c.start)} --> {_srt_time(c.end)}\n{c.text}\n\n"
                           for i, c in enumerate(cues, 1)), encoding="utf-8")
    sub = settings["subtitles"]
    W, H = settings["width"], settings["height"]
    scale = H / 1080
    box = bool(sub.get("box"))
    style = ",".join(str(x) for x in [
        "Default", sub["font"], int(sub["font_size"] * scale), sub["primary_color"], "&H000000FF",
        sub["outline_color"], "&H80000000", -1, 0, 0, 0, 100, 100, 0, 0, 3 if box else 1,
        sub["outline"], 0 if box else 1, 2, 60, 60, int(sub["margin_v"] * scale), 1])
    ass = build / "captions.ass"
    ass.write_text(
        "[Script Info]\nScriptType: v4.00+\nWrapStyle: 0\nScaledBorderAndShadow: yes\n"
        f"PlayResX: {W}\nPlayResY: {H}\n\n[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, "
        "Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, "
        "MarginR, MarginV, Encoding\n"
        f"Style: {style}\n\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
        + "".join(f"Dialogue: 0,{_ass_time(c.start)},{_ass_time(c.end)},Default,,0,0,0,,{c.text.replace(chr(10), chr(92) + 'N')}\n"
                  for c in cues),
        encoding="utf-8")
    return srt, ass


def chapters(project: Project, plans: list[ScenePlan]) -> list[tuple[float, str]]:
    marks = [(p.start, project.scenes[p.scene_index].chapter) for p in plans if project.scenes[p.scene_index].chapter]
    # YouTube needs the first chapter at 0:00 — the first chapter absorbs any leading scenes.
    if marks:
        marks[0] = (0.0, marks[0][1])
    return marks


def render_project(project: Project, preview: bool = False, keep_cache: bool = True) -> Path:
    t0 = time.time()
    st = project.settings
    fps = int(st["fps"])
    build = project.build_dir
    build.mkdir(parents=True, exist_ok=True)
    cache = project.cache_dir
    log(f"Project: {project.title} — {len(project.scenes)} scenes, {st['width']}x{st['height']}@{fps}"
        + (" (PREVIEW)" if preview else ""))

    # 1) Voiceover --------------------------------------------------------------------------
    log("Step 1/5: generating voiceover")
    voice_cache = cache / "tts"

    def do_audio(scene):
        voice = {**st["voice"], **(scene.voice or {})}
        return build_scene_audio(scene.text, voice, voice_cache, st, scene.duration)

    with ThreadPoolExecutor(max_workers=4) as ex:
        audios = list(ex.map(do_audio, project.scenes))
    shutdown_workers()  # release voice-model memory before rendering

    plans: list[ScenePlan] = []
    t = 0.0
    for scene, audio in zip(project.scenes, audios):
        dur = audio.duration + (float(st["padding"]) if scene.text else 0.0)
        if scene.duration:
            dur = max(dur, scene.duration)
        total_frames = max(len(scene.visuals), round(dur * fps))
        n = len(scene.visuals)
        base, extra = divmod(total_frames, n)
        frames = [base + (1 if i < extra else 0) for i in range(n)]
        dur = total_frames / fps  # snap to whole frames so audio and video never drift
        plans.append(ScenePlan(scene.index, t, dur, audio, frames))
        t += dur
    total = t
    log(f"   narration ready — video length will be {fmt_ts(total)} ({total:.1f}s)")

    # 2) Visual clips -----------------------------------------------------------------------
    log("Step 2/5: rendering visuals")
    renderer = ClipRenderer(project)
    jobs = []
    seq = 0
    for plan in plans:
        scene = project.scenes[plan.scene_index]
        offset_frames = 0
        for vi, (spec, fr) in enumerate(zip(scene.visuals, plan.clip_frames)):
            # Remotion KineticText with no explicit text uses the narration.
            if isinstance(spec, dict) and spec.get("remotion") == "KineticText":
                spec = {**spec, "props": {"text": strip_directives(scene.text), **(spec.get("props") or {})}}
            # Word cues (at: "Hiroshima") → seconds within this clip.
            if isinstance(spec, dict) and spec.get("props"):
                spec = {**spec, "props": resolve_cues(spec["props"], plan.audio.words, offset_frames / fps, fr / fps,
                                                      where=f"scene {plan.scene_index + 1}")}
            jobs.append((seq, spec, fr / fps, vi == 0, vi == len(scene.visuals) - 1))
            offset_frames += fr
            seq += 1

    done = [0]

    def do_clip(job):
        s, spec, d, fi, fo = job
        try:
            path = renderer.render(spec, d, s, fi, fo)
        except YtautoError as exc:
            raise YtautoError(f"Visual #{s + 1} ({spec!r}): {exc}") from exc
        done[0] += 1
        if done[0] % 10 == 0 or done[0] == len(jobs):
            log(f"   clips {done[0]}/{len(jobs)}")
        return path

    with ThreadPoolExecutor(max_workers=_workers(st)) as ex:
        clips = list(ex.map(do_clip, jobs))

    # 3) Join video + narration ------------------------------------------------------------
    log("Step 3/5: joining clips and narration")
    work = cache / "work"
    work.mkdir(parents=True, exist_ok=True)
    vlist = work / "video_list.txt"
    vlist.write_text("".join(f"file '{c.resolve()}'\n" for c in clips))
    video = work / "video.mp4"
    run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", vlist, "-c", "copy", video])

    padded = []
    for plan in plans:
        pth = work / f"vo_{plan.scene_index:04d}.wav"
        run(["ffmpeg", "-y", "-v", "error", "-i", plan.audio.path, "-af", f"apad=whole_dur={plan.duration:.4f}",
             "-t", f"{plan.duration:.4f}", "-ar", "48000", "-ac", "1", pth])
        padded.append(pth)
    alist = work / "audio_list.txt"
    alist.write_text("".join(f"file '{p.resolve()}'\n" for p in padded))
    narration = work / "narration.wav"
    run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", alist, "-c", "copy", narration])

    # 4) Audio mix: narration + sfx + ducked music + loudness normalisation -----------------
    log("Step 4/5: mixing audio")
    inputs = ["-i", narration]
    filters = ["[0:a]aresample=48000,aformat=channel_layouts=stereo[vo]"]
    mix = ["[vo]"]
    idx = 1
    synth_events, file_events = collect_sfx(project, plans)
    snd = st.get("sound") or {}
    if synth_events or float(snd.get("drone", 0) or 0) > 0:
        track = build_track(total, synth_events, float(snd.get("drone", 0) or 0), work / "sound_design.wav")
        inputs += ["-i", track]
        filters.append(f"[{idx}:a]aresample=48000,aformat=channel_layouts=stereo,volume={float(snd.get('volume', 1.0))}[sd]")
        mix.append("[sd]")
        idx += 1
    for at, path, vol in file_events:
        inputs += ["-i", path]
        ms = int(max(0, at) * 1000)
        filters.append(f"[{idx}:a]aresample=48000,aformat=channel_layouts=stereo,volume={vol},adelay={ms}|{ms}[s{idx}]")
        mix.append(f"[s{idx}]")
        idx += 1
    music = st.get("music")
    if isinstance(music, str):
        music = {"file": music}
    music_credits: list[str] = []
    if music and (music.get("file") or music.get("generate") or music.get("source") or music.get("library")):
        mfile, generated = None, False
        source = music.get("source") or ("library" if music.get("library") else None)
        if source in ("incompetech", "openverse", "library") and not music.get("file"):
            segs = mood_segments(project, plans, music.get("mood", "wonder"))
            try:
                mfile, used = real_music_bed(project, segs, total, music, source)
                music_credits = [t.credit() for t in used if t.license != "own"]
            except Exception as exc:  # noqa: BLE001 — offline, site down… never fail the render over music
                warn(f"music {source}: {exc} — using the generated score instead")
                mfile = None
                music = {**music, "generate": True}
        if music.get("file"):
            mfile = project.resolve(music["file"])
            if not mfile.exists():
                warn(f"music file not found: {mfile} — " + ("using the generated score" if music.get("generate") else "rendering without music"))
                mfile = None
        if mfile is None and music.get("generate"):
            segs = mood_segments(project, plans, music.get("mood", "wonder"))
            key = stable_hash("score-v1", segs, round(total, 2), music.get("seed", 0))
            mfile = cache / "music" / f"score_{key}.wav"
            if not mfile.exists():
                mfile.parent.mkdir(parents=True, exist_ok=True)
                log("   composing background score (" + ", ".join(sorted({m for _, _, m in segs})) + ")")
                build_score(total, segs, mfile, seed=int(music.get("seed", 0)))
            generated = True
        if mfile is not None:
            inputs += ["-stream_loop", "-1", "-i", mfile]
            vol = float(music.get("volume", 0.8))
            space = ",aecho=0.8:0.55:90|170|290:0.32|0.22|0.14" if generated else ""
            # Normalise any track to the same loudness first, so `volume` means the same for every song.
            filters.append(f"[{idx}:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,loudnorm=I=-20:TP=-2{space},"
                           f"volume={vol},atrim=0:{total:.3f},afade=t=in:d=2,afade=t=out:st={max(0, total - 4):.3f}:d=4[mus]")
            idx += 1
            duck = music.get("duck", 0.45)
            if duck is True:
                duck = 0.45
            if duck:
                speech = speech_from_audio(narration)  # exact for every voice engine
                env = build_duck_envelope(total, speech, float(duck), work / "duck_envelope.wav")
                inputs += ["-i", env]
                filters.append(f"[{idx}:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo[env]")
                filters.append("[mus][env]amultiply[musd]")
                mix.append("[musd]")
                idx += 1
            else:
                mix.append("[mus]")
    lufs = st.get("loudness", -14)
    filters.append(f"{''.join(mix)}amix=inputs={len(mix)}:duration=first:normalize=0,"
                   f"loudnorm=I={lufs}:TP=-1.5:LRA=11,aresample=48000[aout]")
    mixed = work / "mix.m4a"
    run(["ffmpeg", "-y", "-v", "error", *inputs, "-filter_complex", ";".join(filters), "-map", "[aout]",
         "-t", f"{total:.3f}", "-c:a", "aac", "-b:a", "192k", mixed])

    # 5) Captions, watermark, chapters, final mux -----------------------------------------
    log("Step 5/5: captions + final encode")
    all_cues = [Cue(round(p.start + c.start, 3), round(p.start + c.end, 3), c.text) for p in plans for c in p.audio.cues]
    srt, ass = write_captions(all_cues, build, st)

    marks = chapters(project, plans)
    meta = work / "chapters.txt"
    meta_lines = [";FFMETADATA1", f"title={project.title}"]
    for i, (start, name) in enumerate(marks):
        end = marks[i + 1][0] if i + 1 < len(marks) else total
        meta_lines += ["[CHAPTER]", "TIMEBASE=1/1000", f"START={int(start * 1000)}", f"END={int(end * 1000)}", f"title={name}"]
    meta.write_text("\n".join(meta_lines) + "\n", encoding="utf-8")

    sub = st["subtitles"]
    burn = sub.get("enabled", True) and sub.get("burn", True) and all_cues
    wm = st.get("watermark")
    wm_path = project.resolve(wm["file"] if isinstance(wm, dict) else wm) if wm else None
    if wm_path and not wm_path.exists():
        warn(f"watermark not found: {wm_path}")
        wm_path = None

    final = build / f"{_slug(project.title)}.mp4"
    cmd = ["ffmpeg", "-y", "-v", "error", "-stats", "-i", video, "-i", mixed, "-i", meta]
    vchain = "[0:v]"
    fparts = []
    if wm_path:
        cfg = wm if isinstance(wm, dict) else {}
        cmd += ["-i", wm_path]
        w = int(st["width"] * float(cfg.get("scale", 0.08)))
        m = int(st["width"] * 0.025)
        pos = {"top-right": f"W-w-{m}:{m}", "top-left": f"{m}:{m}", "bottom-right": f"W-w-{m}:H-h-{m}",
               "bottom-left": f"{m}:H-h-{m}"}.get(cfg.get("position", "top-right"), f"W-w-{m}:{m}")
        fparts.append(f"[3:v]scale={w}:-1,format=rgba,colorchannelmixer=aa={float(cfg.get('opacity', 0.8))}[wm]")
        fparts.append(f"{vchain}[wm]overlay={pos}[v1]")
        vchain = "[v1]"
    if burn:
        fparts.append(f"{vchain}subtitles=captions.ass[v2]")
        vchain = "[v2]"
    if fparts:
        cmd += ["-filter_complex", ";".join(fparts), "-map", vchain,
                "-c:v", "libx264", "-preset", st["preset"], "-crf", str(st["crf"]),
                *(["-tune", st["tune"]] if st.get("tune") else []), "-pix_fmt", "yuv420p",
                "-g", str(fps * 2)]
    else:
        cmd += ["-map", "0:v", "-c:v", "copy"]
    cmd += ["-map", "1:a", "-c:a", "copy", "-map_metadata", "2", "-map_chapters", "2",
            "-movflags", "+faststart", "-shortest", str(final.resolve())]
    run(cmd, cwd=build)

    # Description with chapters + metadata for upload ------------------------------------
    desc = project.description.strip()
    short = [n for i, (s, n) in enumerate(marks) if (marks[i + 1][0] if i + 1 < len(marks) else total) - s < 10]
    if short:
        warn(f"YouTube ignores chapters when any is under 10s: {', '.join(short)}")
    if music_credits:
        desc += "\n\nMusic:\n" + "\n".join(music_credits)
    from .stock import providers_used
    if providers_used():
        desc += "\n\nStock footage: " + ", ".join(providers_used())
    if len(marks) >= 3:
        desc += "\n\nChapters:\n" + "\n".join(f"{fmt_ts(s)} {n}" for s, n in marks)
    (build / "description.txt").write_text(desc + "\n", encoding="utf-8")
    thumb = make_thumbnail(project, clips, build)
    try:
        contact_sheet(final, plans, build / "contact_sheet.jpg")
    except YtautoError as exc:
        warn(f"contact sheet failed: {exc}")
    manifest = {
        "title": project.title, "description": desc, "tags": project.tags,
        "video": final.name, "captions": srt.name, "thumbnail": thumb.name if thumb else None,
        "duration_seconds": round(total, 2), "chapters": [{"start": s, "title": n} for s, n in marks],
        "youtube": project.youtube,
    }
    (build / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    if not keep_cache:
        shutil.rmtree(work, ignore_errors=True)
    size = final.stat().st_size / 1e6
    log(f"Done in {time.time() - t0:.0f}s → {final} ({fmt_ts(total)}, {size:.1f} MB)")
    return final


def stable_seed(text: str) -> int:
    return int(stable_hash(text), 16) % 100000


def real_music_bed(project: Project, segs, total: float, music: dict, source: str):
    """Assemble real tracks (Openverse or a local library folder) following the scene moods."""
    from .music_library import assemble, incompetech_tracks, library_tracks, openverse_tracks

    cache = project.cache_dir
    seed = int(music.get("seed", 0))
    queries = music.get("queries") or {}
    found: dict[str, list] = {}

    def pick(mood: str, occurrence: int):
        if mood not in found:
            if source == "library":
                folder = project.resolve(music.get("library", "assets/music"))
                found[mood] = library_tracks(folder, mood) if folder.exists() else []
                if not found[mood]:
                    warn(f"music library: no tracks for mood '{mood}' in {folder}")
            elif source == "incompetech":
                used_titles = {t.title for lst in found.values() for t in lst}
                found[mood] = incompetech_tracks(mood, cache, want=1 + int(total // 420), seed=seed + stable_seed(project.title), avoid=used_titles)
            else:
                found[mood] = openverse_tracks(mood, cache, want=2, seed=seed, extra_query=queries.get(mood))
        lst = found[mood]
        # one track per mood; long videos rotate to a second track every few returns of that mood
        return lst[(occurrence // 3 + seed) % len(lst)] if lst else None

    # Real songs need room to breathe: fold mood sections shorter than 15 s into the previous section.
    merged: list[tuple[float, float, str]] = []
    for a, b, m in segs:
        if merged and (b - a < 15 or merged[-1][2] == m):
            merged[-1] = (merged[-1][0], b, merged[-1][2])
        else:
            merged.append((a, b, m))
    if len(merged) > 1 and merged[0][1] - merged[0][0] < 15:
        merged[1] = (0.0, merged[1][1], merged[1][2])
        merged.pop(0)
    segs = merged
    key = stable_hash("bed-v3", source, segs, round(total, 2), seed, queries, music.get("library"))
    out = cache / "music" / f"bed_{key}.wav"
    meta = out.with_suffix(".json")
    if out.exists() and meta.exists():
        from .music_library import Track
        return out, [Track(**t) for t in json.loads(meta.read_text())]
    out.parent.mkdir(parents=True, exist_ok=True)
    log(f"   building music bed from {source} (" + ", ".join(sorted({m for _, _, m in segs})) + ")")
    out, used = assemble(total, segs, pick, out)
    meta.write_text(json.dumps([t.__dict__ for t in used]))
    return out, used


def mood_segments(project: Project, plans: list[ScenePlan], default: str) -> list[tuple[float, float, str]]:
    """Scene `mood:` → (start, end, mood). A scene without a mood keeps the previous one."""
    segs: list[tuple[float, float, str]] = []
    cur = default
    for p in plans:
        m = project.scenes[p.scene_index].raw.get("mood")
        if m:
            if m not in MOODS:
                warn(f"scene {p.scene_index + 1}: unknown mood {m!r} (use {', '.join(MOODS)})")
            else:
                cur = m
        if segs and segs[-1][2] == cur:
            segs[-1] = (segs[-1][0], p.start + p.duration, cur)
        else:
            segs.append((p.start, p.start + p.duration, cur))
    return segs


def collect_sfx(project: Project, plans: list[ScenePlan]):
    """Scene `sfx` → (synth events, file events). Also adds automatic whooshes on cuts."""
    snd = project.settings.get("sound") or {}
    synth: list[tuple[float, str, float, float | None]] = []
    files: list[tuple[float, Path, float]] = []
    if snd.get("whoosh_on_cut"):
        wv = float(snd.get("whoosh_volume", 0.22))
        for plan in plans[1:]:
            synth.append((plan.start, "whoosh", wv, None))
    for plan in plans:
        raw = project.scenes[plan.scene_index].sfx
        if not raw:
            continue
        items = raw if isinstance(raw, list) else [raw]
        for it in items:
            if isinstance(it, str):
                it = {"sound": it} if it in BUILTIN else {"file": it}
            at = it.get("at", 0)
            if isinstance(at, str):
                wt = find_word_time(at, plan.audio.words)
                if wt is None:
                    warn(f"scene {plan.scene_index + 1}: sfx cue {at!r} not found in narration")
                    wt = 0.0
                at = wt
            t = plan.start + float(at)
            vol = float(it.get("volume", 0.7))
            if it.get("sound"):
                if it["sound"] not in BUILTIN:
                    warn(f"unknown built-in sound {it['sound']!r} (have: {', '.join(sorted(BUILTIN))})")
                    continue
                synth.append((t, it["sound"], vol, it.get("dur")))
            elif it.get("file"):
                path = project.resolve(it["file"])
                if path.exists():
                    files.append((t, path, vol))
                else:
                    warn(f"sfx not found: {path}")
    return synth, files


def contact_sheet(video: Path, plans: list[ScenePlan], out: Path, cols: int = 4) -> Path | None:
    """One frame from the middle of each scene, tiled — a quick QC overview of the whole video."""
    times = [p.start + p.duration * 0.6 for p in plans][:48]
    if not times:
        return None
    tmp = out.parent / ".sheet"
    tmp.mkdir(exist_ok=True)
    frames = []
    for i, t in enumerate(times):
        f = tmp / f"{i:03d}.jpg"
        try:
            run(["ffmpeg", "-y", "-v", "error", "-ss", f"{t:.2f}", "-i", video, "-frames:v", "1",
                 "-vf", f"scale=480:-2,drawtext=text='{i + 1}':x=10:y=10:fontsize=22:fontcolor=yellow:box=1:boxcolor=black@0.6", f])
            frames.append(f)
        except YtautoError:
            pass
    if not frames:
        return None
    rows = -(-len(frames) // cols)
    run(["ffmpeg", "-y", "-v", "error", "-framerate", "1", "-i", tmp / "%03d.jpg",
         "-vf", f"tile={cols}x{rows}:padding=4:color=black", "-frames:v", "1", "-q:v", "3", out])
    for f in frames:
        f.unlink()
    tmp.rmdir()
    return out


def _slug(s: str) -> str:
    out = "".join(c.lower() if c.isalnum() else "-" for c in s).strip("-")
    while "--" in out:
        out = out.replace("--", "-")
    return out[:80] or "video"


def make_thumbnail(project: Project, clips: list[Path], build: Path) -> Path | None:
    """1280x720 JPG: a background (image or a frame from the video) plus big bold text."""
    cfg = project.thumbnail or {}
    if cfg is False:
        return None
    out = build / "thumbnail.jpg"
    text = cfg.get("text", project.title)
    if cfg.get("image"):
        src = ["-i", project.resolve(cfg["image"])]
    else:
        clip_i = min(int(cfg.get("from_clip", 0)), len(clips) - 1)
        src = ["-ss", str(cfg.get("at", 1.0)), "-i", clips[clip_i]]
    font = find_font(bold=True)
    txt = project.cache_dir / "text" / f"thumb_{stable_hash(text)}.txt"
    txt.parent.mkdir(parents=True, exist_ok=True)
    # Simple word wrap at ~18 chars per line for punchy thumbnails.
    lines, cur = [], ""
    for w in str(text).split():
        if cur and len(cur) + 1 + len(w) > 18:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    lines.append(cur)
    txt.write_text("\n".join(lines[:4]), encoding="utf-8")
    size = int(cfg.get("font_size", 110 if len(lines) <= 2 else 86))
    color = cfg.get("color", "white")
    fontopt = f"fontfile='{font}':" if font else ""
    vf = ("scale=1280:720:force_original_aspect_ratio=increase,crop=1280:720,eq=brightness=-0.12:saturation=1.3,"
          f"drawtext={fontopt}textfile='{txt}':fontsize={size}:fontcolor={color}:line_spacing=10:"
          f"borderw=8:bordercolor=black:x=60:y=(h-text_h)/2")
    try:
        run(["ffmpeg", "-y", "-v", "error", *src, "-frames:v", "1", "-vf", vf, "-q:v", "2", out])
        return out
    except YtautoError as exc:
        warn(f"thumbnail failed: {exc}")
        return None

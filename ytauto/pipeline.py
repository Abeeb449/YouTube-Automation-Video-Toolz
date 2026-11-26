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
from .sound import ALLOWED, BUILTIN, TRANSITION, TRANSITION_FILE, build_track
from .tts import Cue, SceneAudio, build_scene_audio, lead_in, narration_inputs, shutdown_workers, strip_directives
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


def _shift_numeric_cues(spec, by: float):
    """Add `by` seconds to every cue written as a number (`at`, `…At`), in the visual and its fallbacks."""
    if isinstance(spec, list):
        return [_shift_numeric_cues(x, by) for x in spec]
    if not isinstance(spec, dict):
        return spec
    out = {}
    for k, v in spec.items():
        if (k == "at" or k.endswith("At")) and isinstance(v, (int, float)) and not isinstance(v, bool):
            out[k] = v + by
        else:
            out[k] = _shift_numeric_cues(v, by)
    return out


def _with_narration_text(spec, text: str):
    """KineticText with no text of its own shows the scene's narration, wherever it sits (the visual itself or
    any fallback_visual / fallback inside it)."""
    if isinstance(spec, list):
        return [_with_narration_text(x, text) for x in spec]
    if not isinstance(spec, dict):
        return spec
    out = {k: (_with_narration_text(v, text) if k in ("fallback_visual", "fallback") else v) for k, v in spec.items()}
    if out.get("remotion") == "KineticText" and not (out.get("props") or {}).get("text"):
        out["props"] = {**(out.get("props") or {}), "text": text}
    return out


def write_captions(cues: list[Cue], build: Path, settings: dict) -> tuple[Path, Path]:
    srt = build / "captions.srt"
    srt.write_text("".join(f"{i}\n{_srt_time(c.start)} --> {_srt_time(c.end)}\n{c.text}\n\n"
                           for i, c in enumerate(cues, 1)), encoding="utf-8")
    sub = settings["subtitles"]
    W, H = settings["width"], settings["height"]
    scale = min(W, H) / 1080   # sizes are for a 1080-pixel short side (16:9 1080p, or a 1080x1920 Short)
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


def _with_sprites(spec: dict, man: dict) -> dict:
    """Hand the 3D sprite manifest to templates that draw creatures (including a scene's fallback visual)."""
    if spec.get("remotion") in ("OceanScene", "Anatomy"):
        spec = {**spec, "props": {**(spec.get("props") or {}), "sprites": man}}
    fb = spec.get("fallback_visual")
    if isinstance(fb, dict):
        spec = {**spec, "fallback_visual": _with_sprites(fb, man)}
    return spec


# Every sound effect is softened and capped well below the narrator (peak about -20 dBFS against a voice
# around -26 dB RMS / -8 dB peaks), so no effect can ever jump out over the voice.
SFX_SAFE = "lowpass=f=9000,acompressor=threshold=-30dB:ratio=6:attack=3:release=150,alimiter=limit=0.1:attack=2:release=200"


def _resolve_spec_cues(spec, words, offset: float, dur: float, where: str):
    if not isinstance(spec, dict):
        return spec
    out = dict(spec)
    if isinstance(out.get("props"), dict):
        out["props"] = resolve_cues(out["props"], words, offset, dur, where=where)
    fb = out.get("fallback_visual")
    if isinstance(fb, dict):
        out["fallback_visual"] = _resolve_spec_cues(fb, words, offset, dur, where)
    elif isinstance(fb, list):
        out["fallback_visual"] = [_resolve_spec_cues(x, words, offset, dur, where) for x in fb]
    return out


_FX_LEN = {"whoosh": 0.7, "swell": 1.6, "riser": 2.5, "hit": 1.6, "thud": 1.2, "boom": 3.0, "tick": 0.1, "ticks": 3.0,
           "typing": 1.0, "glitch": 0.4, "beep": 0.2, "alarm": 2.0}


def _fx_windows(synth_events, file_events) -> list[tuple[float, float]]:
    """(start, end) of every sound effect the script asked for, over its full length."""
    from .utils import ffprobe_duration
    win = [(t, t + float(dur or _FX_LEN.get(name, 2.0))) for t, name, _vol, dur in synth_events]
    for t, path, _vol in file_events:
        try:
            win.append((t, t + ffprobe_duration(path)))
        except Exception:  # noqa: BLE001
            win.append((t, t + 3.0))
    return win


def audio_qc(mix: Path, voice: Path, report: Path, planned: list[tuple[float, float]] | None = None) -> list[float]:
    """Find sudden sounds that are NOT the narrator: moments where the mix jumps > 6 dB within 50 ms while the
    voice doesn't, and rises clearly above the voice. Returns their times (also written to `report`)."""
    import numpy as np
    import soundfile as sf

    def frames(path: Path):
        y, sr = sf.read(str(path), always_2d=True, dtype="float32")
        y = y.mean(1)
        n = int(0.05 * sr)
        k = len(y) // n
        return np.maximum(20 * np.log10(np.sqrt((y[:k * n].reshape(k, n) ** 2).mean(1)) + 1e-9), -70.0)
    m, v = frames(mix), frames(voice)
    k = min(len(m), len(v))
    m, v = m[:k], v[:k]
    jump_m = np.diff(m, prepend=m[0])
    jump_v = np.diff(v, prepend=v[0])
    bad = np.where((jump_m > 6) & (jump_v < 3) & (m > v + 3) & (m > -40))[0]
    times, last = [], -9.0
    for i in bad:
        t = i * 0.05
        if any(a - 0.3 <= t <= b + 0.5 for a, b in planned or []):   # a sound effect the script asked for
            continue
        if t - last > 1.0:
            times.append(round(t, 2))
            last = t
    lines = [f"{int(t) // 60}:{int(t) % 60:02d}.{int((t % 1) * 10)}" for t in times]
    report.write_text(("Sudden non-voice sounds:\n" + "\n".join(lines)) if lines else "No sudden non-voice sounds.\n")
    if times:
        warn(f"audio check: {len(times)} sudden non-voice sound(s) at " + ", ".join(lines[:10]) + " (see build/audio_check.txt)")
    else:
        log("   audio check: no sudden non-voice sounds")
    return times


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
    from . import stock
    stock.species_photos = bool(st.get("species_photos", True))
    # 1) B-roll first: every stock photo/clip the script asks for is searched, checked and downloaded before any
    #    voice or picture is made, so the edit starts with all its material on disk (build/broll_report.txt)
    log("Step 1/6: collecting b-roll (search, check, download)")
    from .broll import collect_broll
    collect_broll(project)
    log("Step 2/6: generating voiceover")
    from .sound_director import direct_narration
    direct_narration(project)   # how the narrator sounds, from the script's own content
    if (st.get("voice") or {}).get("engine") in ("qwen", "chatterbox"):
        log(f"   narrator: {st['voice'].get('instruct')}")
    voice_cache = cache / "tts"

    def do_audio(scene):
        text, voice, sst = narration_inputs(scene.text, {**st["voice"], **(scene.voice or {})}, st)
        return build_scene_audio(text, voice, voice_cache, sst, scene.duration)

    with ThreadPoolExecutor(max_workers=4) as ex:
        audios = list(ex.map(do_audio, project.scenes))
    shutdown_workers()  # release voice-model memory before rendering

    # The opening: `intro` seconds of music and picture before the first word. Silent scenes at the top (an intro
    # with its own visuals) count toward it; the rest is added in front of the first narrated scene, whose opening
    # shot simply starts that much earlier.
    lead, lead_scene = 0.0, None
    intro = float(st.get("intro") or 0)
    if intro > 0:
        silent = 0.0
        for k, scene in enumerate(project.scenes):
            if scene.text:
                lead, lead_scene = max(0.0, intro - silent), k
                break
            silent += audios[k].duration
        if lead > 0.05 and lead_scene is not None:
            audios[lead_scene] = lead_in(audios[lead_scene], lead, voice_cache)
            project.scenes[lead_scene].raw["_lead"] = lead
            log(f"   opening: {intro:.0f}s of music and picture before the first word")
        else:
            lead, lead_scene = 0.0, None

    plans: list[ScenePlan] = []
    t = 0.0
    for k, (scene, audio) in enumerate(zip(project.scenes, audios)):
        dur = audio.duration + (float(st["padding"]) if scene.text else 0.0)
        if scene.duration:
            dur = max(dur, scene.duration + (lead if k == lead_scene else 0.0))
        total_frames = max(len(scene.visuals), round(dur * fps))
        n = len(scene.visuals)
        lead_frames = min(total_frames - n, round(lead * fps)) if k == lead_scene else 0
        base, extra = divmod(total_frames - lead_frames, n)
        frames = [base + (1 if i < extra else 0) for i in range(n)]
        frames[0] += lead_frames   # the opening shot carries the intro
        dur = total_frames / fps  # snap to whole frames so audio and video never drift
        plans.append(ScenePlan(scene.index, t, dur, audio, frames))
        t += dur
    total = t
    log(f"   narration ready — video length will be {fmt_ts(total)} ({total:.1f}s)")

    # 2) Visual clips -----------------------------------------------------------------------
    log("Step 3/6: rendering visuals")
    renderer = ClipRenderer(project)
    sprite_man = {}
    if st.get("render3d", True):
        from .sprites import manifest, render_set, SETS, used_sprites
        for creature, view in sorted(used_sprites(project)):
            try:
                render_set(creature, view, SETS[creature][view])
            except YtautoError as exc:
                warn(f"3D sprite {creature}/{view} unavailable ({exc}); using the drawn version")
        sprite_man = manifest()
    jobs = []
    seq = 0
    for plan in plans:
        scene = project.scenes[plan.scene_index]
        offset_frames = 0
        for vi, (spec, fr) in enumerate(zip(scene.visuals, plan.clip_frames)):
            # Remotion KineticText with no explicit text uses the narration.
            # Also inside fallbacks: a stock shot that can't be found falls back to KineticText, which was blank.
            spec = _with_narration_text(spec, strip_directives(scene.text))
            # 3D creature sprites (Blender) replace the flat drawings when available.
            if isinstance(spec, dict) and st.get("render3d", True) and sprite_man:
                spec = _with_sprites(spec, sprite_man)
            # Word cues (at: "Hiroshima") → seconds within this clip, in the visual AND in its fallbacks
            # (a fallback that still held cue words crashed the animation when a stock search failed).
            # In the scene that carries the opening, timings written in seconds count from the first word, not from
            # the start of the music (a label "at 0.2" must not pop up before the narrator speaks).
            if vi == 0 and scene.raw.get("_lead"):
                spec = _shift_numeric_cues(spec, float(scene.raw["_lead"]))
            spec = _resolve_spec_cues(spec, plan.audio.words, offset_frames / fps, fr / fps, f"scene {plan.scene_index + 1}")
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
    from .verify import shutdown as _verify_shutdown
    _verify_shutdown()   # free the picture-check model before the heavy joins
    log("Step 4/6: joining clips and narration")
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
    log("Step 5/6: mixing audio")
    _apply_sound_director(project, plans)
    # Mix, then check: if any sudden non-voice sound remains, the music track playing at that moment is banned
    # and the music is rebuilt without it (up to 3 rounds). Moments right at a planned effect are not counted.
    from . import music_library as _ml
    mfile = None
    for _round in range(3):
        mfile = None
        inputs = ["-i", narration]
        filters = ["[0:a]aresample=48000,aformat=channel_layouts=stereo[vo]"]
        mix = ["[vo]"]
        idx = 1
        synth_events, file_events = collect_sfx(project, plans)
        snd = st.get("sound") or {}
        if synth_events or float(snd.get("drone", 0) or 0) > 0:
            track = build_track(total, synth_events, float(snd.get("drone", 0) or 0), work / "sound_design.wav")
            inputs += ["-i", track]
            filters.append(f"[{idx}:a]aresample=48000,aformat=channel_layouts=stereo,volume={float(snd.get('volume', 1.0))},{SFX_SAFE}[sd]")
            mix.append("[sd]")
            idx += 1
        for at, path, vol in file_events:
            inputs += ["-i", path]
            ms = int(max(0, at) * 1000)
            filters.append(f"[{idx}:a]aresample=48000,aformat=channel_layouts=stereo,volume={vol},{SFX_SAFE},adelay={ms}|{ms}[s{idx}]")
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
                vol = float(music.get("volume", 0.5))
                space = ",aecho=0.8:0.55:90|170|290:0.32|0.22|0.14" if generated else ""
                # Normalise any track to the same loudness first, so `volume` means the same for every song.
                level = "loudnorm=I=-20:TP=-2" if not music.get("source") or generated else "volume=2dB"
                filters.append(f"[{idx}:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,{level}{space},"
                               f"volume={vol},atrim=0:{total:.3f},afade=t=in:d=2,afade=t=out:st={max(0, total - 7):.3f}:d=7[mus]")
                idx += 1
                duck = music.get("duck", 0.4)
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
        filters.append(f"{''.join(mix)}amix=inputs={len(mix)}:duration=first:normalize=0[aout]")
        premix = work / "premix.wav"
        run(["ffmpeg", "-y", "-v", "error", *inputs, "-filter_complex", ";".join(filters), "-map", "[aout]",
             "-t", f"{total:.3f}", "-c:a", "pcm_s16le", premix])
        fx_windows = _fx_windows(synth_events, file_events)
        try:
            sudden = audio_qc(premix, narration, build / "audio_check.txt", fx_windows)
        except Exception as exc:  # noqa: BLE001 — a check must never stop the render
            warn(f"audio check skipped: {exc}")
            sudden = []
        tl = None
        if sudden and mfile is not None and Path(str(mfile)).with_suffix(".timeline.json").exists():
            tl = json.loads(Path(str(mfile)).with_suffix(".timeline.json").read_text())
        culprits = {title for t in sudden for a0, b0, title in (tl or []) if title and a0 - 4 <= t <= b0 + 4}
        if not culprits:
            break
        warn(f"audio check: removing music that made sudden sounds ({', '.join(sorted(culprits))}) and rebuilding")
        _ml.BANNED |= culprits
    # Two-pass, linear loudness normalisation: one fixed gain for the whole video (no pumping or squashing).
    meas = run(["ffmpeg", "-v", "info", "-i", premix, "-af", f"loudnorm=I={lufs}:TP=-1.5:LRA=11:print_format=json",
                "-f", "null", "-"])
    try:
        m = json.loads(meas[meas.rindex("{"):meas.rindex("}") + 1])
        ln = (f"loudnorm=I={lufs}:TP=-1.5:LRA=11:measured_I={m['input_i']}:measured_TP={m['input_tp']}:"
              f"measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true")
    except (ValueError, KeyError):
        ln = f"loudnorm=I={lufs}:TP=-1.5:LRA=11"
    mixed = work / "mix.m4a"
    run(["ffmpeg", "-y", "-v", "error", "-i", premix, "-af",
         f"{ln},aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo", "-ac", "2",
         "-c:a", "aac", "-b:a", "192k", mixed])

    # 5) Captions, watermark, chapters, final mux -----------------------------------------
    log("Step 6/6: captions + final encode")
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
    from .stock import credits, providers_used, write_credits
    chapter_block = ("\n\nChapters:\n" + "\n".join(f"{fmt_ts(s)} {n}" for s, n in marks)) if len(marks) >= 3 else ""
    if providers_used():
        desc += "\n\nStock footage and photos: " + ", ".join(providers_used())
    # Credits: every photo/clip with author, licence and source link. YouTube allows 5000 characters, so if they
    # don't all fit, the legally required ones (CC BY / BY-SA) stay and optional ones (CC0, public domain) go.
    for lines in (credits(), credits(required_only=True)):
        block = ("\nPhoto/video credits:\n" + "\n".join(f"- {c}" for c in lines)) if lines else ""
        if len(desc + block + chapter_block) <= 4900:
            break
    else:
        warn("Not all photo credits fit in the YouTube description (5000 characters); see build/credits.json")
        keep = []
        for c in credits(required_only=True):
            if len(desc + chapter_block) + sum(len(x) + 3 for x in keep) + len(c) + 30 > 4900:
                break
            keep.append(c)
        block = "\nPhoto/video credits:\n" + "\n".join(f"- {c}" for c in keep)
    desc += block + chapter_block
    write_credits(build / "credits.json")
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
    from .music_library import BANNED
    key = stable_hash("bed-v9", source, segs, round(total, 2), seed, queries, music.get("library"), sorted(BANNED))
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


def _apply_sound_director(project: Project, plans: list[ScenePlan]) -> None:
    """Moods and effects from what each scene says (ytauto/sound_director.py). Hand-written mood:/sfx: win."""
    snd = project.settings.get("sound") or {}
    if snd.get("director", True) is False:
        return
    from .sound_director import direct
    order = [p.scene_index for p in plans]
    seen = list(dict.fromkeys(order))
    dur = {i: 0.0 for i in seen}
    for p in plans:
        dur[p.scene_index] += p.duration
    scenes = [project.scenes[i] for i in seen]
    moods, sfx, trans = direct([s.text or "" for s in scenes], [s.chapter for s in scenes],
                               [s.raw.get("mood") for s in scenes], [bool(s.sfx) for s in scenes],
                               durations=[dur[i] for i in seen])
    # a silent opening scene plays the mood of the first words, so the music doesn't change when the voice comes in
    k = next((i for i, sc in enumerate(scenes) if sc.text), 0)
    if k > 0 and not scenes[0].raw.get("mood"):
        moods[0] = moods[k] or scenes[k].raw.get("mood") or moods[0]
        for j in range(1, k + 1):
            if not scenes[j].raw.get("mood"):
                moods[j] = None      # the same mood simply continues
    n_fx = 0
    for s, m, fx, tr in zip(scenes, moods, sfx, trans):
        if m and not s.raw.get("mood"):
            s.raw["mood"] = m
        if fx and not s.sfx:
            s.sfx = fx
            n_fx += len(fx)
        s.raw["_transition"] = tr
    log(f"   sound director: {sum(1 for m in moods if m)} mood changes, {n_fx} effects "
        f"(from the script's own words; no transition sounds)")


def collect_sfx(project: Project, plans: list[ScenePlan]):
    """Scene `sfx` → (synth events, file events). Transition-style sounds are never included."""
    snd = project.settings.get("sound") or {}
    synth: list[tuple[float, str, float, float | None]] = []
    files: list[tuple[float, Path, float]] = []
    if snd.get("effects", True) is False:   # a project can switch every effect off with sound: {effects: false}
        return synth, files
    # No transition sounds, ever: no whoosh on cuts or chapter changes (the old `whoosh_on_cut` setting is ignored)
    # and any whoosh / swell / riser / glitch a script still lists is left out of the mix.
    dropped = 0
    for plan in plans:
        raw = project.scenes[plan.scene_index].sfx
        if not raw:
            continue
        items = raw if isinstance(raw, list) else [raw]
        for it in items:
            if isinstance(it, str):
                it = {"sound": it} if it in BUILTIN else {"file": it}
            at = it.get("at", 0)
            if not isinstance(at, str):   # seconds count from the first word when the scene carries the opening
                at = float(at) + float(project.scenes[plan.scene_index].raw.get("_lead") or 0)
            if isinstance(at, str):
                wt = find_word_time(at, plan.audio.words)
                if wt is None:
                    warn(f"scene {plan.scene_index + 1}: sfx cue {at!r} not found in narration")
                    wt = 0.0
                at = wt
            t = max(0.0, plan.start + float(at) + float(it.get("offset", 0)))
            vol = float(it.get("volume", 0.7))
            if it.get("sound"):
                if it["sound"] in TRANSITION:
                    dropped += 1
                    continue
                if it["sound"] not in BUILTIN:
                    warn(f"unknown built-in sound {it['sound']!r} (have: {', '.join(sorted(ALLOWED))})")
                    continue
                synth.append((t, it["sound"], vol, it.get("dur")))
            elif it.get("file"):
                if TRANSITION_FILE.search(Path(str(it["file"])).name):
                    dropped += 1
                    continue
                path = project.resolve(it["file"])
                if path.exists():
                    files.append((t, path, vol))
                else:
                    warn(f"sfx not found: {path}")
    if dropped:
        log(f"   left out {dropped} transition-style sound(s) the script listed (whoosh/swell/riser/glitch are never used)")
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

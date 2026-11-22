"""Turn a scene's visual spec into a normalised silent H.264 clip of an exact length.

Every clip shares resolution, fps, pixel format and encoder settings so the final
video can be joined with a lossless concat (fast even for 15-minute videos).

Visual spec forms (string or mapping):

  assets/photo.jpg                 image with a slow Ken Burns move
  assets/clip.mp4                  video, trimmed/looped to fit
  https://…/file.jpg|mp4           downloaded once, then as above
  "#112233"                        solid colour
  pexels:city at night             stock VIDEO search (Pexels / Pixabay)
  pexels-photo:mountain lake       stock PHOTO search
  remotion:TitleCard               Remotion template (props via mapping form)
  blender:intro                    procedural Blender 3D template

  {image: x.jpg, zoom: in|out|left|right|none, fit: cover|contain}
  {video: x.mp4, start: 12.5, speed: 1.0, fit: cover|contain}
  {color: "#000", text: "Chapter 1", subtext: "The beginning"}
  {stock: "ocean waves", type: video|photo}
  {remotion: BulletList, props: {title: "...", items: [...]}}
  {blender: intro, props: {text: "MY CHANNEL"}}   or   {blender: scenes/logo.blend}
"""
from __future__ import annotations

import json
import os
import shutil
import threading
from pathlib import Path
from typing import Any

from .stock import download, fetch_stock
from .utils import REPO_ROOT, YtautoError, file_fingerprint, find_font, log, run, stable_hash, warn, which

IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif", ".tif", ".tiff"}
VIDEO_EXT = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"}
ZOOMS = ["in", "out", "left", "right"]

_heavy = threading.Semaphore(1)  # Remotion/Blender already use all cores; run them one at a time


def normalize_spec(spec: Any) -> dict:
    if isinstance(spec, dict):
        spec = dict(spec)
        if "pexels" in spec:
            spec["stock"] = spec.pop("pexels")
        return spec
    if not isinstance(spec, str):
        raise YtautoError(f"Unsupported visual: {spec!r}")
    s = spec.strip()
    low = s.lower()
    if low.startswith("#"):
        return {"color": s}
    for prefix, out in (("pexels-photo:", {"type": "photo"}), ("photo:", {"type": "photo"}),
                        ("pexels:", {"type": "video"}), ("stock:", {"type": "video"})):
        if low.startswith(prefix):
            return {"stock": s[len(prefix):].strip(), **out}
    if low.startswith("remotion:"):
        return {"remotion": s.split(":", 1)[1].strip()}
    if low.startswith("blender:"):
        return {"blender": s.split(":", 1)[1].strip()}
    if low.startswith(("http://", "https://")):
        return {"url": s}
    ext = Path(s).suffix.lower()
    if ext in IMAGE_EXT:
        return {"image": s}
    if ext in VIDEO_EXT:
        return {"video": s}
    raise YtautoError(f"Can't tell what kind of visual {spec!r} is (use a mapping like {{image: ...}})")


_remotion_fp: str | None = None


def remotion_fingerprint() -> str:
    """Hash of the Remotion template sources, so editing a template re-renders its clips."""
    global _remotion_fp
    if _remotion_fp is None:
        import hashlib
        h = hashlib.sha256()
        for d in (REPO_ROOT / "remotion" / "src", Path(os.environ.get("YTAUTO_REMOTION_DIR", "/nonexistent")) / "src"):
            if d.exists():
                for f in sorted(d.rglob("*")):
                    if f.is_file():
                        h.update(f.read_bytes())
                break
        _remotion_fp = h.hexdigest()[:12]
    return _remotion_fp


class ClipRenderer:
    def __init__(self, project):
        self.p = project
        st = project.settings
        self.W, self.H, self.fps = int(st["width"]), int(st["height"]), int(st["fps"])
        self.cache = project.cache_dir
        self.clip_dir = self.cache / "clips"
        self.clip_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ encoding
    def enc_args(self) -> list[str]:
        st = self.p.settings
        tune = ["-tune", st["tune"]] if st.get("tune") else []
        return ["-c:v", "libx264", "-preset", st["preset"], "-crf", str(st["crf"]), *tune, "-pix_fmt", "yuv420p",
                "-r", str(self.fps), "-g", str(self.fps * 2), "-video_track_timescale", "90000",
                "-movflags", "+faststart", "-an"]

    def frames(self, duration: float) -> int:
        return max(1, round(duration * self.fps))

    def _fade(self, duration: float, fade_in: bool, fade_out: bool) -> str:
        st = self.p.settings
        if st.get("transition", "fade") != "fade":
            return ""
        fd = min(float(st["fade_duration"]), duration / 3)
        parts = []
        if fade_in:
            parts.append(f"fade=t=in:st=0:d={fd:.3f}")
        if fade_out:
            parts.append(f"fade=t=out:st={duration - fd:.3f}:d={fd:.3f}")
        return ("," + ",".join(parts)) if parts else ""

    def _fit(self, fit: str) -> str:
        W, H = self.W, self.H
        if fit == "contain":
            return (f"split[a][b];[a]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
                    f"boxblur=30:3,eq=brightness=-0.08[bg];[b]scale={W}:{H}:force_original_aspect_ratio=decrease[fg];"
                    f"[bg][fg]overlay=(W-w)/2:(H-h)/2")
        return f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}"

    # ------------------------------------------------------------------ public
    def render(self, spec: Any, duration: float, seq: int, fade_in: bool, fade_out: bool) -> Path:
        spec = normalize_spec(spec)
        spec = self._resolve_sources(spec, seq)
        fingerprint = None
        for k in ("image", "video"):
            if k in spec:
                fingerprint = file_fingerprint(Path(spec[k]))
        if "remotion" in spec:
            fingerprint = (fingerprint, remotion_fingerprint())
        elif "blender" in spec:
            fingerprint = (fingerprint, file_fingerprint(REPO_ROOT / "blender" / "render.py"))
        key = stable_hash("clip-v3", spec, fingerprint, round(duration, 3), self.W, self.H, self.fps,
                          self.p.settings["crf"], self.p.settings["preset"], self.p.settings["transition"],
                          self.p.settings["fade_duration"], fade_in, fade_out, seq % len(ZOOMS),
                          self.p.settings.get("theme"))
        out = self.clip_dir / f"clip_{key}.mp4"
        if out.exists() and out.stat().st_size > 0:
            return out
        tmp = out.with_suffix(".tmp.mp4")
        if "image" in spec:
            self._image(spec, duration, seq, tmp, fade_in, fade_out)
        elif "video" in spec:
            self._video(spec, duration, tmp, fade_in, fade_out)
        elif "remotion" in spec:
            with _heavy:
                self._remotion(spec, duration, tmp, fade_in, fade_out)
        elif "blender" in spec:
            with _heavy:
                self._blender(spec, duration, tmp, fade_in, fade_out)
        elif "color" in spec or "text" in spec:
            self._color(spec, duration, tmp, fade_in, fade_out)
        else:
            raise YtautoError(f"Unknown visual spec {spec}")
        tmp.rename(out)
        return out

    # ------------------------------------------------------------------ sources
    def _resolve_sources(self, spec: dict, seq: int) -> dict:
        spec = dict(spec)
        if "url" in spec:
            url = spec.pop("url")
            ext = Path(url.split("?")[0]).suffix.lower() or ".bin"
            local = download(url, self.cache / "downloads" / f"{stable_hash(url)}{ext}")
            spec["image" if ext in IMAGE_EXT else "video"] = str(local)
        if "stock" in spec:
            query = spec.pop("stock")
            kind = "image" if spec.pop("type", "video") in ("photo", "image") else "video"
            try:
                local, kind = fetch_stock(query, kind, self.cache, self.W, nth=seq)
                spec[kind] = str(local)
            except Exception as exc:  # noqa: BLE001
                warn(f"Stock '{query}': {exc}. Using a text card instead.")
                spec = {"color": self.p.settings["default_visual"].get("color", "#0f172a"), "text": query.title()}
        for k in ("image", "video"):
            if k in spec:
                path = self.p.resolve(spec[k])
                if not path.exists():
                    raise YtautoError(f"Visual file not found: {path}")
                spec[k] = str(path)
        return spec

    # ------------------------------------------------------------------ kinds
    def _image(self, spec, duration, seq, out, fade_in, fade_out):
        W, H, fps = self.W, self.H, self.fps
        n = self.frames(duration)
        zoom = spec.get("zoom") or ZOOMS[seq % len(ZOOMS)]
        amount = float(spec.get("zoom_amount", 0.12))
        # Pre-scale to 2x output so zoompan's integer positions don't jitter visibly.
        W2, H2 = W * 2, H * 2
        if spec.get("fit") == "contain":
            pre = f"{self._fit('contain').replace(f'{W}:{H}', f'{W2}:{H2}')}"
        else:
            pre = f"scale={W2}:{H2}:force_original_aspect_ratio=increase,crop={W2}:{H2}"
        cx, cy = "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"
        if zoom == "out":
            z, x, y = f"{1 + amount}-{amount}*on/{n}", cx, cy
        elif zoom == "left":
            z, x, y = f"{1 + amount}", f"(iw-iw/zoom)*(1-on/{n})", cy
        elif zoom == "right":
            z, x, y = f"{1 + amount}", f"(iw-iw/zoom)*on/{n}", cy
        elif zoom == "none":
            z, x, y = "1", "0", "0"
        else:
            z, x, y = f"1+{amount}*on/{n}", cx, cy
        vf = (f"{pre},zoompan=z='{z}':x='{x}':y='{y}':d=1:s={W}x{H}:fps={fps},setsar=1,format=yuv420p"
              + self._fade(duration, fade_in, fade_out))
        run(["ffmpeg", "-y", "-v", "error", "-loop", "1", "-framerate", str(fps), "-i", spec["image"],
             "-filter_complex", vf, "-frames:v", str(n), *self.enc_args(), out])

    def _video(self, spec, duration, out, fade_in, fade_out):
        n = self.frames(duration)
        speed = float(spec.get("speed", 1.0))
        pts = f"setpts={1 / speed:.4f}*PTS," if speed != 1.0 else ""
        vf = (f"{pts}{self._fit(spec.get('fit', 'cover'))},fps={self.fps},setsar=1,format=yuv420p"
              + self._fade(duration, fade_in, fade_out))
        cmd = ["ffmpeg", "-y", "-v", "error", "-stream_loop", "-1"]
        if spec.get("start"):
            cmd += ["-ss", str(spec["start"])]
        cmd += ["-i", spec["video"], "-filter_complex", vf, "-frames:v", str(n), *self.enc_args(), out]
        run(cmd)

    def _color(self, spec, duration, out, fade_in, fade_out):
        W, H, fps = self.W, self.H, self.fps
        color = str(spec.get("color", "#0f172a")).replace("#", "0x")
        vf = "format=yuv420p"
        font = find_font(bold=True)
        txt_dir = self.cache / "text"
        txt_dir.mkdir(parents=True, exist_ok=True)

        def drawtext(text: str, size: int, y: str, color_: str) -> str:
            f = txt_dir / f"{stable_hash(text)}.txt"
            f.write_text(text, encoding="utf-8")
            fontopt = f"fontfile='{font}':" if font else ""
            return (f",drawtext={fontopt}textfile='{f}':fontsize={size}:fontcolor={color_}:"
                    f"x=(w-text_w)/2:y={y}:shadowcolor=black@0.5:shadowx=3:shadowy=3")

        s = W / 1920
        if spec.get("text"):
            vf += drawtext(str(spec["text"]), int(spec.get("size", 110) * s), "(h-text_h)/2-40*" + f"{s:.3f}",
                           spec.get("text_color", "white"))
        if spec.get("subtext"):
            vf += drawtext(str(spec["subtext"]), int(54 * s), f"(h/2)+{int(70 * s)}", spec.get("accent", "0xfacc15"))
        vf += self._fade(duration, fade_in, fade_out)
        run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", f"color=c={color}:s={W}x{H}:r={fps}",
             "-vf", vf, "-frames:v", str(self.frames(duration)), *self.enc_args(), out])

    def _normalize(self, src: Path, duration: float, out: Path, fade_in: bool, fade_out: bool):
        """Re-encode an externally rendered clip to the shared format and exact length."""
        vf = (f"{self._fit('cover')},fps={self.fps},setsar=1,tpad=stop_mode=clone:stop_duration={duration:.3f},"
              f"format=yuv420p" + self._fade(duration, fade_in, fade_out))
        run(["ffmpeg", "-y", "-v", "error", "-i", src, "-filter_complex", vf,
             "-frames:v", str(self.frames(duration)), *self.enc_args(), out])

    def _remotion(self, spec, duration, out, fade_in, fade_out):
        # Prefer the repo's templates when their deps are installed; otherwise use the copy
        # baked into the Docker image (YTAUTO_REMOTION_DIR).
        rdir = REPO_ROOT / "remotion"
        if not (rdir / "node_modules").exists() and os.environ.get("YTAUTO_REMOTION_DIR"):
            rdir = Path(os.environ["YTAUTO_REMOTION_DIR"])
        if not (rdir / "node_modules").exists():
            raise YtautoError(f"Remotion not installed. Run: cd {rdir} && npm install")
        comp = spec["remotion"]
        props = self._stage_assets(spec.get("props") or {}, rdir)
        theme = {**(self.p.settings.get("theme") or {}), **(props.get("theme") or {})}
        props.update({"durationInSeconds": duration, "width": self.W, "height": self.H, "fps": self.fps, "theme": theme})
        props_file = out.with_suffix(".props.json")
        props_file.write_text(json.dumps(props))
        raw = out.with_suffix(".remotion.mp4")
        cmd = ["npx", "remotion", "render", "src/index.ts", comp, str(raw), f"--props={props_file}",
               "--log=error", "--codec=h264", "--crf=10"]
        chrome = os.environ.get("YTAUTO_CHROME")
        if chrome:
            cmd.append(f"--browser-executable={chrome}")
        if os.environ.get("YTAUTO_REMOTION_CONCURRENCY"):
            cmd.append(f"--concurrency={os.environ['YTAUTO_REMOTION_CONCURRENCY']}")
        log(f"Remotion: rendering {comp} ({duration:.1f}s)")
        run(cmd, cwd=rdir)
        # Remotion templates fade themselves; don't double-fade.
        self._normalize(raw, duration, out, False, False)
        raw.unlink(missing_ok=True)
        props_file.unlink(missing_ok=True)

    def _stage_assets(self, obj, rdir: Path):
        """Copy local files referenced by `image:` props into remotion/public so templates can load them."""
        if isinstance(obj, list):
            return [self._stage_assets(v, rdir) for v in obj]
        if not isinstance(obj, dict):
            return obj
        out = {}
        for k, v in obj.items():
            if k in ("image", "lottie", "footage") and isinstance(v, str) and not v.startswith(("http://", "https://")):
                low = v.lower()
                if k == "footage" and low.startswith(("pexels:", "stock:", "pexels-photo:")):
                    query = v.split(":", 1)[1].strip()
                    try:
                        src, _ = fetch_stock(query, "video", self.cache, self.W, nth=len(query))
                    except Exception as exc:  # noqa: BLE001 — no key / no network: fall back to the drawn backdrop
                        warn(f"B-roll '{query}': {exc}. Using the drawn background instead.")
                        for fk, fv in (obj.get("fallback") or {}).items():  # e.g. drawn actors for the same beat
                            out.setdefault(fk, self._stage_assets(fv, rdir))
                        continue
                else:
                    src = self.p.resolve(v)
                if not src.exists():
                    raise YtautoError(f"{k} file not found: {src}")
                pub = rdir / "public" / "ytauto"
                pub.mkdir(parents=True, exist_ok=True)
                name = f"{stable_hash(file_fingerprint(src))}{src.suffix.lower()}"
                if not (pub / name).exists():
                    shutil.copyfile(src, pub / name)
                out[k] = f"ytauto/{name}"
            elif k == "fallback":
                continue  # only used when footage can't be fetched
            else:
                out[k] = self._stage_assets(v, rdir)
        return out

    def _blender(self, spec, duration, out, fade_in, fade_out):
        exe = os.environ.get("YTAUTO_BLENDER") or which("blender")
        if not exe:
            raise YtautoError("Blender not found (install it or set YTAUTO_BLENDER)")
        target = spec["blender"]
        frames_dir = out.parent / f"{out.stem}_frames"
        frames_dir.mkdir(parents=True, exist_ok=True)
        props = spec.get("props") or {}
        args = ["--out", str(frames_dir), "--duration", f"{duration:.3f}", "--width", str(self.W),
                "--height", str(self.H), "--fps", str(self.fps),
                "--samples", str(spec.get("samples", os.environ.get("YTAUTO_BLENDER_SAMPLES", 16))),
                "--props", json.dumps(props)]
        script = REPO_ROOT / "blender" / "render.py"
        if target.endswith(".blend"):
            blend = self.p.resolve(target)
            if not blend.exists():
                raise YtautoError(f"Blender file not found: {blend}")
            cmd = [exe, "-b", blend, "-P", script, "--", "--mode", "file", *args]
        else:
            cmd = [exe, "-b", "--factory-startup", "-P", script, "--", "--mode", "template", "--template", target, *args]
        log(f"Blender: rendering {target} ({duration:.1f}s) — CPU render, this can take a few minutes")
        run(cmd)
        pngs = sorted(frames_dir.glob("frame_*.png"))
        if not pngs:
            raise YtautoError("Blender produced no frames")
        raw = out.with_suffix(".blender.mp4")
        run(["ffmpeg", "-y", "-v", "error", "-framerate", str(self.fps), "-i", frames_dir / "frame_%05d.png",
             "-c:v", "libx264", "-crf", "16", "-pix_fmt", "yuv420p", raw])
        self._normalize(raw, duration, out, fade_in, fade_out)
        raw.unlink(missing_ok=True)
        for p in pngs:
            p.unlink()
        frames_dir.rmdir()

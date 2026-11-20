"""Shared helpers: logging, subprocess, ffprobe, hashing."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


class YtautoError(RuntimeError):
    pass


def log(msg: str) -> None:
    print(f"[ytauto {time.strftime('%H:%M:%S')}] {msg}", flush=True)


def warn(msg: str) -> None:
    print(f"[ytauto WARNING] {msg}", file=sys.stderr, flush=True)


def run(cmd: list[str], cwd: str | Path | None = None, quiet: bool = True, env: dict | None = None) -> str:
    """Run a command; raise with the tail of its output when it fails."""
    full_env = {**os.environ, **(env or {})}
    proc = subprocess.run(
        [str(c) for c in cmd],
        cwd=cwd,
        env=full_env,
        stdout=subprocess.PIPE if quiet else None,
        stderr=subprocess.STDOUT if quiet else None,
        text=True,
    )
    if proc.returncode != 0:
        tail = (proc.stdout or "")[-3000:]
        raise YtautoError(f"Command failed ({proc.returncode}): {' '.join(map(str, cmd))[:400]}\n{tail}")
    return proc.stdout or ""


def which(name: str) -> str | None:
    return shutil.which(name)


def ffprobe_duration(path: str | Path) -> float:
    out = run([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", path,
    ])
    try:
        return float(out.strip())
    except ValueError as exc:
        raise YtautoError(f"Could not read duration of {path}") from exc


def has_audio(path: str | Path) -> bool:
    out = run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=index", "-of", "csv=p=0", path])
    return bool(out.strip())


def stable_hash(*parts) -> str:
    h = hashlib.sha256()
    for p in parts:
        h.update(json.dumps(p, sort_keys=True, default=str).encode())
    return h.hexdigest()[:16]


def file_fingerprint(path: Path) -> str:
    """Cheap fingerprint (size + mtime) so edited assets invalidate the cache."""
    try:
        st = path.stat()
        return f"{path}:{st.st_size}:{int(st.st_mtime)}"
    except OSError:
        return str(path)


def fmt_ts(seconds: float) -> str:
    """YouTube chapter style timestamp (M:SS or H:MM:SS)."""
    s = int(round(seconds))
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    return f"{h}:{m:02d}:{sec:02d}" if h else f"{m}:{sec:02d}"


def find_font(bold: bool = True) -> str | None:
    """Locate a TTF font for ffmpeg drawtext."""
    env = os.environ.get("YTAUTO_FONT")
    if env and Path(env).exists():
        return env
    candidates = [
        REPO_ROOT / "assets" / "fonts" / "font.ttf",
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"),
        Path("/usr/share/fonts/truetype/freefont/FreeSansBold.ttf"),
        Path("/Library/Fonts/Arial Bold.ttf"),
        Path("C:/Windows/Fonts/arialbd.ttf"),
    ]
    for c in candidates:
        if c.exists():
            return str(c)
    return None

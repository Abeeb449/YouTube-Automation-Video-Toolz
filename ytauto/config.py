"""Load and validate a project's script.yaml."""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .utils import YtautoError

DEFAULT_SETTINGS: dict[str, Any] = {
    "width": 1920,
    "height": 1080,
    "fps": 30,
    "crf": 20,              # x264 quality (lower = better/larger). 18-23 is sensible.
    "preset": "veryfast",   # x264 speed preset
    "padding": 0.35,        # seconds of silence after every scene's narration
    "sentence_gap": 0.12,   # seconds of silence between sentences inside a scene
    "transition": "fade",   # fade | none
    "fade_duration": 0.3,
    "workers": 0,           # parallel ffmpeg clip renders; 0 = auto
    "loudness": -14,        # target integrated loudness (LUFS). YouTube normalises to -14.
    "voice": {
        "engine": "edge",               # edge | piper | elevenlabs | espeak
        "name": "en-US-AndrewNeural",   # engine specific voice id
        "rate": "+0%",                  # edge: "+10%"; others: ignored or engine specific
        "pitch": "+0Hz",
        "fallback": "espeak",           # used if the main engine fails (e.g. no internet)
    },
    "subtitles": {
        "enabled": True,
        "burn": True,            # burn captions into the picture (also writes .srt either way)
        "max_chars": 42,         # per caption line
        "font_size": 56,
        "font": "DejaVu Sans",
        "primary_color": "&H00FFFFFF",
        "outline_color": "&H00000000",
        "outline": 3,
        "margin_v": 70,
    },
    "music": None,               # {file: assets/music.mp3, volume: 0.12, duck: true}
    "watermark": None,           # {file: assets/logo.png, position: top-right, opacity: 0.8, scale: 0.08}
    "theme": {},                 # default Remotion theme for every remotion scene
    "default_visual": {"color": "#0f172a"},
}


@dataclass
class Scene:
    index: int
    text: str
    visuals: list[Any]
    duration: float | None = None      # fixed duration (for scenes without narration or to force length)
    chapter: str | None = None
    voice: dict | None = None          # per-scene voice override
    sfx: str | None = None             # sound effect file mixed at scene start
    raw: dict = field(default_factory=dict)


@dataclass
class Project:
    root: Path
    title: str
    description: str
    tags: list[str]
    settings: dict[str, Any]
    scenes: list[Scene]
    thumbnail: dict | None
    youtube: dict

    @property
    def build_dir(self) -> Path:
        return self.root / "build"

    @property
    def cache_dir(self) -> Path:
        return self.root / ".cache"

    def resolve(self, p: str | Path) -> Path:
        path = Path(p).expanduser()
        return path if path.is_absolute() else (self.root / path)


def _deep_merge(base: dict, override: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def load_project(path: str | Path, overrides: dict | None = None) -> Project:
    path = Path(path)
    script = path / "script.yaml" if path.is_dir() else path
    if not script.exists():
        raise YtautoError(f"No script.yaml found at {script}")
    data = yaml.safe_load(script.read_text(encoding="utf-8")) or {}

    settings = _deep_merge(DEFAULT_SETTINGS, data.get("settings") or {})
    if overrides:
        settings = _deep_merge(settings, overrides)

    raw_scenes = data.get("scenes") or []
    if not raw_scenes:
        raise YtautoError(f"{script}: 'scenes' is empty — add at least one scene.")

    scenes: list[Scene] = []
    for i, s in enumerate(raw_scenes):
        if isinstance(s, str):
            s = {"text": s}
        text = (s.get("text") or "").strip()
        visual = s.get("visual", s.get("visuals"))
        if visual is None:
            visuals = [settings["default_visual"]]
        elif isinstance(visual, list):
            visuals = visual
        else:
            visuals = [visual]
        if not text and not s.get("duration"):
            raise YtautoError(f"Scene {i + 1}: needs 'text' (narration) or a fixed 'duration'.")
        scenes.append(Scene(
            index=i,
            text=text,
            visuals=visuals,
            duration=float(s["duration"]) if s.get("duration") else None,
            chapter=s.get("chapter"),
            voice=s.get("voice"),
            sfx=s.get("sfx"),
            raw=s,
        ))

    return Project(
        root=script.parent.resolve(),
        title=data.get("title") or script.parent.name,
        description=data.get("description") or "",
        tags=list(data.get("tags") or []),
        settings=settings,
        scenes=scenes,
        thumbnail=data.get("thumbnail"),
        youtube=data.get("youtube") or {},
    )

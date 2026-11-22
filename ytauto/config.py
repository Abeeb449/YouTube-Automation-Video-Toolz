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
    "tune": None,           # x264 tune: "animation" for flat 2D art, "film" for live footage
    "padding": 0.35,        # seconds of silence after every scene's narration
    "sentence_gap": 0.12,   # seconds of silence between sentences inside a scene
    "align": "auto",        # exact word timings via faster-whisper when installed: auto | on | off
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
    "music": None,               # {generate: true, mood: wonder} (original score) or {file: assets/music.mp3}
                                 # + volume (0.8 ≈ 11 dB under the voice in pauses), duck (0.45 = level while speaking; false = off)
    "watermark": None,           # {file: assets/logo.png, position: top-right, opacity: 0.8, scale: 0.08}
    "sound": {                   # synthesized sound design (ytauto/sound.py) — no downloads
        "drone": 0,              # ambient tension bed level, e.g. 0.06; 0 = off
        "whoosh_on_cut": False,  # soft whoosh on every scene change
        "whoosh_volume": 0.22,
        "volume": 1.0,
    },
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
    sfx: Any = None                    # "boom" | "assets/x.mp3" | [{sound|file, at, volume, dur}]
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


# Style presets: `preset: documentary` at the top of script.yaml. Your own settings override them.
PRESETS: dict[str, dict] = {
    "documentary": {
        "crf": 18, "preset": "medium", "tune": "animation",   # crisp flat graphics
        # The "what-if" infographic documentary look (see .claude/skills/whatif-documentary).
        "transition": "none",          # templates fade their own content over a shared backdrop
        "padding": 0.5,
        "voice": {"engine": "kokoro", "name": "bm_george", "speed": 0.94, "fallback": "edge"},
        "subtitles": {"burn": False},  # key phrases appear as on-screen callouts; full captions go to YouTube as .srt
        "music": {"source": "incompetech", "generate": True, "mood": "mystery", "volume": 0.8, "duck": 0.45},
        "sound": {"drone": 0.0, "whoosh_on_cut": True, "whoosh_volume": 0.15},
    },
    "ocean": {
        "crf": 18, "preset": "medium", "tune": "animation",   # crisp flat graphics
        # "Danger & wonder" deep-sea animal documentaries (remotion/src/ocean, see .claude/skills/ocean-documentary).
        "transition": "none",
        "padding": 0.45,
        "voice": {"engine": "kokoro", "name": "bm_george", "speed": 0.92, "fallback": "edge"},
        "subtitles": {"burn": False},
        "music": {"source": "incompetech", "generate": True, "mood": "wonder", "volume": 0.8, "duck": 0.45},
        "sound": {"drone": 0.0, "whoosh_on_cut": True, "whoosh_volume": 0.15},
    },
    "shorts": {"width": 1080, "height": 1920, "subtitles": {"burn": True, "font_size": 64, "max_chars": 22, "margin_v": 520}},
}


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

    base = DEFAULT_SETTINGS
    for name in ([data["preset"]] if isinstance(data.get("preset"), str) else data.get("preset") or []):
        if name not in PRESETS:
            raise YtautoError(f"Unknown preset {name!r}. Available: {', '.join(PRESETS)}")
        base = _deep_merge(base, PRESETS[name])
    settings = _deep_merge(base, data.get("settings") or {})
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

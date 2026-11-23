"""Turn a plain narration script into a full script.yaml (scenes, visuals, moods, cues) — free and offline.

The built-in rule-based director splits the script into beats and picks templates from what the text
mentions (animals, depths, numbers, danger/wonder words, short punchy lines), varying the shots.
For a hand-directed result, give agent/SYSTEM_PROMPT.md + agent/SKILL.md to any AI assistant (free ones work)
and let it write script.yaml directly — no paid API is needed anywhere in this project.
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

from .utils import REPO_ROOT, YtautoError, log, warn

STYLES = {
    "ocean": ".claude/skills/ocean-documentary",
    "documentary": ".claude/skills/whatif-documentary",
}
EXAMPLES = {
    "ocean": "projects/ocean-giant-squid/script.yaml",
    "documentary": "projects/whatif-yellowstone/script.yaml",
}


# ------------------------------------------------------------------------------------------- rules
CREATURE_WORDS = [
    (r"sperm whale|whale", "spermWhale"), (r"giant squid|colossal squid|squid", "giantSquid"),
    (r"orca|killer whale", "orca"), (r"shark", "shark"), (r"angler ?fish|anglerfish", "anglerfish"),
    (r"jelly ?fish|jellyfish", "jellyfish"), (r"octopus", "octopus"), (r"\bdiver\b|\bscuba\b", "diver"),
    (r"\bfish\b|school of", "fishSchool"),
]
DANGER = re.compile(r"\b(kill|killed|attack|teeth|jaws|predator|hunt|hunts|hunting|venom|deadly|danger|dangerous|bite|crush|prey)\b", re.I)
WONDER = re.compile(r"\b(largest|biggest|incredible|amazing|beautiful|record|longest|loudest|discovered|glow|light)\b", re.I)
MYSTERY = re.compile(r"\b(mystery|unknown|nobody|never been|dark|darkness|deep|abyss|strange|secret)\b", re.I)
DEPTH = re.compile(r"(\d[\d,\.]*)\s*(metres|meters|m)\b[^.]*\b(deep|down|below|depth)|\b(depth|deep|below)[^.]*?(\d[\d,\.]*)\s*(metres|meters|m)\b", re.I)
DB = re.compile(r"(\d[\d,\.]*)\s*(decibels|dB)\b", re.I)
NUMBER = re.compile(r"\b(\d[\d,\.]*)\s*(metres|meters|tonnes|tons|kilograms|kg|years|kilometres|km|feet|centimetres|cm|%|percent|hearts|teeth)\b", re.I)


_UNITS = {w: i for i, w in enumerate("zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen "
                                      "fifteen sixteen seventeen eighteen nineteen".split())}
_TENS = {w: 10 * (i + 2) for i, w in enumerate("twenty thirty forty fifty sixty seventy eighty ninety".split())}
_SCALES = {"hundred": 100, "thousand": 1000, "million": 1_000_000}


def words_to_digits(text: str) -> str:
    """'two thousand metres' → '2000 metres' so number rules can see spelled-out numbers."""
    tokens = re.split(r"(\s+|-)", text)
    out, buf, total, cur = [], [], 0, 0

    def flush():
        nonlocal total, cur, buf
        if buf:
            out.append(str(total + cur))
        buf, total, cur = [], 0, 0

    for tok in tokens:
        w = tok.lower().strip(",.")
        if w in _UNITS or w in _TENS or w in _SCALES or (w == "and" and buf):
            buf.append(tok)
            if w in _UNITS:
                cur += _UNITS[w]
            elif w in _TENS:
                cur += _TENS[w]
            elif w in _SCALES:
                cur = max(cur, 1) * _SCALES[w]
                if _SCALES[w] >= 1000:
                    total, cur = total + cur, 0
            if tok.endswith((",", ".")):
                flush()
                out.append(tok[-1])
        elif tok.strip() == "" or tok == "-":
            if not buf:
                out.append(tok)
        else:
            if buf:
                flush()
                out.append(" ")
            out.append(tok)
    flush()
    return re.sub(r"\s+", " ", "".join(out))


def _creature(text: str, default: str | None = None) -> str | None:
    for pat, name in CREATURE_WORDS:
        if re.search(pat, text, re.I):
            return name
    return default


def _num(s: str) -> float:
    return float(s.replace(",", ""))


def _first_word(text: str) -> str:
    w = [x for x in re.findall(r"[A-Za-z']+", text) if len(x) > 3]
    return w[0] if w else text.split()[0]


def plan_with_rules(script: str, style: str, title: str | None) -> str:
    blocks = [b.strip() for b in re.split(r"\n\s*\n", script.strip()) if b.strip()]
    title = title or (blocks[0].lstrip("#").strip()[:70] if blocks and blocks[0].startswith("#") else "Untitled Documentary")
    main = _creature(script, "giantSquid")
    scenes: list[dict] = []
    chapter = None
    mood_prev = None
    n = 0
    for block in blocks:
        if block.startswith("#"):
            chapter = block.splitlines()[0].lstrip("#").strip()
            rest = "\n".join(block.splitlines()[1:]).strip()
            if not rest:
                continue
            block = rest
        sentences = re.split(r"(?<=[.!?])\s+", re.sub(r"\s+", " ", block))
        # group into beats of up to ~30 words
        beats, cur = [], ""
        for s in sentences:
            if cur and len((cur + " " + s).split()) > 30:
                beats.append(cur)
                cur = s
            else:
                cur = f"{cur} {s}".strip()
        if cur:
            beats.append(cur)
        for beat in beats:
            n += 1
            sc: dict = {}
            if chapter:
                sc["chapter"] = chapter
                chapter = None
            mood = "danger" if DANGER.search(beat) else "wonder" if WONDER.search(beat) else "mystery" if MYSTERY.search(beat) else None
            if n == 1:
                mood = mood or "calm"
            if mood and mood != mood_prev:
                sc["mood"] = mood
                mood_prev = mood
            sc["text"] = beat
            sc["visual"] = _rule_visual(beat, style, main, n)
            scenes.append(sc)
    data = {
        "preset": style, "title": title,
        "description": f"{title}. A narrated documentary.", "tags": [main, "documentary", "animals"] if style == "ocean" else ["documentary"],
        "thumbnail": {"text": title.upper()[:40]}, "youtube": {"privacy": "private"},
        "scenes": scenes,
    }
    return "# Planned automatically by the rule-based director — edit freely, then render.\n" + \
        yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=110)


def _rule_visual(beat: str, style: str, main: str, n: int) -> dict:
    creature = _creature(beat, main)
    cue = _first_word(beat)
    sentences = [x.strip() for x in re.split(r"(?<=[.!?])\s+", beat) if x.strip()]
    punchy = [x for x in sentences if len(x.split()) <= 5]
    numeric = words_to_digits(beat)
    if style != "ocean":
        m = NUMBER.search(beat)
        if m:
            return {"remotion": "Counter", "props": {"to": _num(m.group(1)), "label": m.group(2), "countAt": m.group(1).split(",")[0]}}
        if n % 4 == 0:
            return {"remotion": "Statement", "props": {"line1": " ".join(beat.split()[:4]), "line2": " ".join(beat.split()[4:8])}}
        return {"remotion": "KineticText", "props": {}}
    m = DEPTH.search(numeric)
    if m:
        val = _num(m.group(1) or m.group(5))
        return {"remotion": "OceanScene", "props": {
            "depth": 0.2, "depthTo": min(1.0, 0.3 + val / 1500), "depthMeter": {"from": 0, "to": val, "max": max(val * 1.1, 100), "unit": "m"},
            "actors": [{"creature": "diver", "x": 0.42, "y": 0.3, "to": [0.45, 0.55], "scale": 0.5, "rotate": 30}]}}
    m = DB.search(numeric)
    if m:
        return {"remotion": "Meter", "props": {"title": "How loud?", "to": _num(m.group(1)), "unit": "dB", "countAt": "decibels" if "decibel" in beat.lower() else m.group(1).split(",")[0]}}
    if punchy and not beat.strip().endswith("?"):
        # a short punchy line becomes a big reveal word over the creature
        line = punchy[-1]
        return {"remotion": "OceanScene", "props": {
            "depth": 0.85, "actors": [{"creature": creature, "x": 0.45, "y": 0.55, "to": [0.5, 0.55], "scale": 1.3}],
            "bigText": line.upper().rstrip("!") if len(line) <= 22 else " ".join(line.split()[-2:]).upper(),
            "bigAt": _first_word(line), "bigColor": "#e5372f" if DANGER.search(line) else "#e6edf2"}}
    if n % 5 == 0:  # real B-roll every fifth beat
        name = {"spermWhale": "sperm whale", "giantSquid": "squid", "fishSchool": "fish school", "anglerfish": "deep sea fish"}.get(creature, creature)
        props = {"footage": f"pexels:{name} underwater",
                 "fallback": {"depth": 0.6, "actors": [{"creature": creature, "x": 0.3, "y": 0.5, "to": [0.6, 0.5], "scale": 1.1}]}}
        short = [x for x in sentences if len(x.split()) <= 7]
        if short:
            props["callout"] = short[0].rstrip(".!")
        return {"remotion": "OceanScene", "props": props}
    m = NUMBER.search(numeric)
    if m:
        return {"remotion": "OceanScene", "props": {
            "depth": 0.8, "actors": [{"creature": creature, "x": 0.4, "y": 0.52, "scale": 1.2}],
            "facts": [{"text": f"{int(_num(m.group(1))):,} {m.group(2)}" if _num(m.group(1)).is_integer() else f"{m.group(1)} {m.group(2)}",
                       **({"at": m.group(1).split(",")[0]} if m.group(1) in beat else {"at": m.group(2)}),
                       "red": bool(DANGER.search(beat))}]}}
    if DANGER.search(beat):
        return {"remotion": "OceanScene", "props": {
            "depth": 0.85, "actors": [{"creature": creature, "x": 0.35, "y": 0.55, "to": [0.5, 0.55], "scale": 1.3},
                                      {"creature": "diver", "x": 0.85, "y": 0.35, "scale": 0.35, "flip": True, "target": {"at": cue}}]}}
    if "?" in beat:
        return {"remotion": "OceanScene", "props": {"depth": 0.9, "actors": [
            {"creature": creature, "x": 0.5, "y": 0.55, "scale": 1.2, "silhouette": "#05080b", "opacity": 0.9}], "title": beat.split("?")[0][-40:] + "?"}}
    variant = n % 4
    if variant == 0:  # close-up push-in
        return {"remotion": "OceanScene", "props": {
            "depth": 0.85, "zoom": [1, 1.8], "focus": [0.55, 0.5], "actors": [{"creature": creature, "x": 0.5, "y": 0.5, "scale": 1.2}]}}
    if variant == 1 and len(sentences) >= 2:  # fact chips from the shorter sentences
        chips = [{"text": x.rstrip(".!"), "at": _first_word(x)} for x in sentences if len(x.split()) <= 10][:3]
        if chips:
            chips[-1]["red"] = bool(DANGER.search(chips[-1]["text"]))
            return {"remotion": "OceanScene", "props": {"depth": 0.75, "facts": chips,
                                                        "actors": [{"creature": creature, "x": 0.32, "y": 0.52, "scale": 1.0}]}}
    if variant == 2:  # creature with a school of fish
        return {"remotion": "OceanScene", "props": {"depth": 0.5, "actors": [
            {"creature": "fishSchool", "x": 0.7, "y": 0.35, "to": [0.6, 0.3], "scale": 0.6},
            {"creature": creature, "x": 0.25, "y": 0.6, "to": [0.5, 0.58], "scale": 1.1}]}}
    return {"remotion": "OceanScene", "props": {
        "depth": 0.3 + (n % 6) * 0.1, "actors": [{"creature": creature, "x": 0.3, "y": 0.5, "to": [0.6, 0.52], "scale": 1.0}]}}


def plan(script: str, style: str, title: str | None, director: str = "rules", model: str | None = None) -> str:
    if style not in STYLES:
        raise YtautoError(f"Unknown style {style!r} (use {', '.join(STYLES)})")
    log("Planning scenes with the built-in director (free, offline)")
    return plan_with_rules(script, style, title)


def write_plan(script_path: Path, out_dir: Path, style: str, title: str | None, director: str = "rules", model: str | None = None) -> Path:
    text = plan(script_path.read_text(encoding="utf-8"), style, title, director, model)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "assets").mkdir(exist_ok=True)
    out = out_dir / "script.yaml"
    out.write_text(text if text.endswith("\n") else text + "\n", encoding="utf-8")
    # validate with the real loader so problems surface before rendering
    from .config import load_project
    load_project(out_dir)
    log(f"Plan written → {out}")
    return out

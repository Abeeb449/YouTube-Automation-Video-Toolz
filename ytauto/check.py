"""`ytauto check`: a pre-render review of a script for originality, sourcing and YouTube readiness.

It looks for what YouTube's "inauthentic content" policy targets (repetitive, template-based, mass-produced
videos) and for unsourced facts, before you spend time rendering:

  originality  shared passages, the same opening, or the same shot structure as your other projects
  sources      facts (numbers, years, percentages) without a listed source; source clippings without a source
  variety      one template or plain stock footage carrying most of the video
  readiness    title and description length, video length, AI disclosure, voice watermark

FAIL lines must be fixed (exit code 1); WARN lines are worth a look; INFO is for your information.
Works on a planned project (script.yaml) or a plain script.txt.
"""
from __future__ import annotations

import difflib
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .tts import strip_directives

NUM_WORDS = (r"one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|fifteen|twenty|thirty|forty|fifty|"
             r"sixty|seventy|eighty|ninety|hundred|thousand|million|billion|half|quarter|dozen")
FACT = re.compile(
    r"\b\d[\d,.]*\s*(?:%|percent|per cent)|"                         # 70%, 70 percent
    r"\b(?:1[5-9]\d\d|20\d\d)s?\b|"                                    # years
    r"\b\d[\d,.]*\s*(?:[a-z]+)|"                                       # 3.5 metres, 400 kilograms
    rf"\b(?:{NUM_WORDS})(?:[\s-]+(?:{NUM_WORDS}|and))*\s+(?:out of|in every|percent|per cent|times|metres|meters|"
    r"kilometres|kilometers|miles|feet|kilograms|kilos|tonnes|tons|pounds|years|species|teeth|degrees|hours|"
    r"minutes|seconds|days|weeks|months|pups|people|animals|individuals)\b", re.I)
STOCK_TEMPLATES = {"PhotoStory"}   # moving real photos: fine, but a video made only of them reads as a stock montage
PLACEHOLDER = re.compile(r"\bTODO\b|\bTBD\b|lorem ipsum|\[visual:|XXX|\?\?\?", re.I)


@dataclass
class Report:
    lines: list[tuple[str, str, str]] = field(default_factory=list)   # (level, section, message)

    def add(self, level: str, section: str, msg: str) -> None:
        self.lines.append((level, section, msg))

    @property
    def fails(self) -> int:
        return sum(1 for lv, _, _ in self.lines if lv == "FAIL")

    @property
    def warns(self) -> int:
        return sum(1 for lv, _, _ in self.lines if lv == "WARN")

    def render(self) -> str:
        out, sec = [], None
        for lv, s, m in self.lines:
            if s != sec:
                out.append(f"\n{s.upper()}")
                sec = s
            out.append(f"  {lv:<4}  {m}")
        out.append(f"\n{self.fails} to fix, {self.warns} to review."
                   + ("  Ready to render." if not self.fails else ""))
        return "\n".join(out)


# ------------------------------------------------------------------------------------------- reading projects
@dataclass
class Doc:
    root: Path
    title: str
    text: list[str]                 # narration per scene, tags removed
    templates: list[str]            # visual kind per scene
    chapters: list[str]
    sources: list[str]
    description: str
    data: dict
    scene_sources: list[bool]       # scene has its own `source:`
    clipcards: list[tuple[int, dict]]


def _kind(v) -> tuple[str, list]:
    """Short name for a visual, plus any ClipCards inside it."""
    cards = []
    if isinstance(v, str):
        return ("stock" if v.split(":")[0] in ("stock", "pexels", "pixabay") else "file"), cards
    if not isinstance(v, dict):
        return "other", cards
    if "remotion" in v:
        name = v["remotion"]
        props = v.get("props") or {}
        if name == "ClipCard":
            cards.append(props)
        if name == "PhotoStory" and all(str(ph.get("photo", "")).startswith("stock:") for ph in props.get("photos") or [{}]):
            return "PhotoStory(stock)", cards
        return name, cards
    if "stock" in v or "url" in v:
        return "stock", cards
    for k in ("blender", "image", "video"):
        if k in v:
            return k, cards
    return "text", cards


def load_doc(path: Path) -> Doc:
    path = Path(path)
    root = path if path.is_dir() else path.parent
    yml, txt = root / "script.yaml", root / "script.txt"
    if path.suffix == ".txt" or (not yml.exists() and txt.exists()):
        raw = (path if path.suffix == ".txt" else txt).read_text(encoding="utf-8")
        blocks = [b.strip() for b in re.split(r"\n\s*\n", raw.strip()) if b.strip()]
        title = blocks[0].lstrip("#").strip() if blocks and blocks[0].startswith("#") else root.name
        src = [ln.split(":", 1)[1].strip() for ln in raw.splitlines() if re.match(r"\s*sources?\s*:", ln, re.I)]
        paras = [b for b in blocks if not b.startswith("#") and not re.match(r"\s*(sources?|subject)\s*:", b, re.I)]
        chapters = [b.lstrip("#").strip() for b in blocks[1:] if b.startswith("#")]
        return Doc(root, title, [strip_directives(p) for p in paras], ["?"] * len(paras), chapters, src, "", {},
                   [False] * len(paras), [])
    from .config import load_project
    data = yaml.safe_load(yml.read_text(encoding="utf-8")) or {}
    proj = load_project(root)
    texts, kinds, chapters, own_src, cards = [], [], [], [], []
    for sc in proj.scenes:
        texts.append(strip_directives(sc.text or ""))
        ks = []
        for v in sc.visuals:
            k, cc = _kind(v)
            ks.append(k)
            cards += [(sc.index, c) for c in cc]
        kinds.append("+".join(ks) or "none")
        if sc.chapter:
            chapters.append(sc.chapter)
        own_src.append(bool(sc.raw.get("source") or sc.raw.get("sources")))
    sources = [str(s) for s in (data.get("sources") or [])]
    desc = proj.description or ""
    m = re.search(r"sources?\s*:(.+)", desc, re.I | re.S)
    if m:
        sources += [s.strip(" -•\t") for s in re.split(r"[;\n]", m.group(1)) if len(s.strip(" -•\t")) > 8]
    return Doc(root, proj.title, texts, kinds, chapters, sources, desc, data, own_src, cards)


def _words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9']+", text.lower())


def _shingles(words: list[str], n: int = 6) -> set[tuple]:
    return {tuple(words[i:i + n]) for i in range(len(words) - n + 1)}


def _first_sentence(texts: list[str]) -> str:
    joined = " ".join(t for t in texts if t)
    return re.split(r"(?<=[.!?])\s", joined, maxsplit=1)[0] if joined else ""


def other_docs(me: Path, extra: list[Path]) -> list[Doc]:
    out = []
    roots = {p.parent for p in Path("projects").glob("*/script.yaml")} | {p.parent for p in Path("projects").glob("*/script.txt")}
    for d in extra:
        roots |= {p.parent for p in Path(d).glob("*/script.yaml")} | {p.parent for p in Path(d).glob("*/script.txt")}
    for r in sorted(roots):
        if r.resolve() == me.resolve():
            continue
        try:
            out.append(load_doc(r))
        except Exception:  # noqa: BLE001 — a broken neighbour shouldn't stop the check
            continue
    return out


# ------------------------------------------------------------------------------------------- the checks
def check(path: Path, against: list[Path] | None = None) -> Report:
    doc = load_doc(Path(path))
    rep = Report()
    words = _words(" ".join(doc.text))
    n_words = len(words)

    # -- originality: compared with every other project on the channel
    mine = _shingles(words)
    others = other_docs(doc.root, against or [])
    worst = None
    for o in others:
        theirs = _shingles(_words(" ".join(o.text)))
        if not mine or not theirs:
            continue
        shared = mine & theirs
        share = len(shared) / len(mine)
        if worst is None or share > worst[0]:
            worst = (share, o, shared)
        op = difflib.SequenceMatcher(None, _first_sentence(doc.text).lower(), _first_sentence(o.text).lower()).ratio()
        if op > 0.7:
            rep.add("WARN", "originality", f"Opening line is {op:.0%} the same as '{o.title}'. Give each video its own hook.")
        if len(doc.templates) >= 10 and "?" not in doc.templates and "?" not in o.templates:
            st = difflib.SequenceMatcher(None, doc.templates, o.templates).ratio()
            if st > 0.8:
                rep.add("WARN", "originality", f"Shot structure is {st:.0%} the same as '{o.title}' "
                        "(same templates in the same order). Re-plan or rearrange scenes.")
        ch = set(map(str.lower, doc.chapters)) & set(map(str.lower, o.chapters))
        if len(ch) >= 3:
            rep.add("WARN", "originality", f"{len(ch)} chapter titles are shared with '{o.title}': {', '.join(sorted(ch)[:4])}")
    if worst and worst[0] > 0:
        share, o, shared = worst
        sample = " / ".join(" ".join(s) for s in list(shared)[:2])
        if share > 0.25:
            rep.add("FAIL", "originality", f"{share:.0%} of the narration repeats '{o.title}' word for word (e.g. \"{sample}\").")
        elif share > 0.06:
            rep.add("WARN", "originality", f"{share:.0%} of the narration repeats '{o.title}' (e.g. \"{sample}\").")
    if not any(lv != "INFO" for lv, s, _ in rep.lines if s == "originality"):
        rep.add("OK", "originality", f"No repeated passages, openings or structure across {len(others)} other project(s).")
    for i, t in enumerate(doc.text):
        if PLACEHOLDER.search(t):
            rep.add("FAIL", "originality", f"Scene {i}: placeholder text left in: \"{PLACEHOLDER.search(t).group(0)}\"")

    # -- sources
    facts = []
    for i, t in enumerate(doc.text):
        for s in re.split(r"(?<=[.!?])\s+", t):
            if FACT.search(s):
                facts.append((i, s.strip()))
    if not doc.sources:
        if facts:
            rep.add("FAIL", "sources", f"{len(facts)} factual claims with numbers or dates but no sources listed. Add "
                    "`sources:` (a list) to script.yaml, or a 'Sources: …' line to the description or script.txt.")
        else:
            rep.add("WARN", "sources", "No sources listed. Cite what your research is based on (`sources:` in script.yaml).")
    else:
        rep.add("OK", "sources", f"{len(doc.sources)} source(s) listed: " + "; ".join(s[:60] for s in doc.sources[:3])
                + (" …" if len(doc.sources) > 3 else ""))
        unsourced = [(i, s) for i, s in facts if not doc.scene_sources[i]]
        if unsourced:
            rep.add("INFO", "sources", f"Check these {len(unsourced)} facts against your sources before rendering "
                    "(or add `source:` to the scene to mark it checked):")
            for i, s in unsourced[:25]:
                rep.add("INFO", "sources", f"  scene {i}: {s[:140]}")
            if len(unsourced) > 25:
                rep.add("INFO", "sources", f"  … and {len(unsourced) - 25} more")
    for i, card in doc.clipcards:
        if not (card.get("source") or "").strip():
            rep.add("FAIL", "sources", f"Scene {i}: ClipCard (source clipping) has no `source`. Only show studies you can cite.")
        else:
            rep.add("OK", "sources", f"Scene {i}: ClipCard cites {card['source'][:70]}")

    # -- variety
    real = [k for k in doc.templates if k != "?"]
    if real:
        cnt = Counter(k.split("+")[0] for k in real)
        top, n = cnt.most_common(1)[0]
        stockish = sum(1 for k in real if k.split("+")[0] in ("stock", "PhotoStory(stock)", "video"))
        if n / len(real) > 0.5 and len(real) >= 8:
            rep.add("WARN", "variety", f"'{top}' is {n / len(real):.0%} of all scenes. Mix in close-ups, maps, data, clippings.")
        if stockish / len(real) > 0.7:
            rep.add("WARN", "variety", f"{stockish / len(real):.0%} of scenes are plain stock footage/photos: that reads as a "
                    "stock montage. Add scenes that show your research (ClipCard, DateStamp, maps, data, Anatomy).")
        run, prev, longest = 0, None, (0, "")
        for k in real:
            run = run + 1 if k == prev else 1
            prev = k
            if run > longest[0]:
                longest = (run, k)
        if longest[0] > 3:
            rep.add("WARN", "variety", f"{longest[0]} scenes in a row use '{longest[1]}'. Break the run with a different shot.")
        if not any(lv == "WARN" for lv, s, _ in rep.lines if s == "variety"):
            rep.add("OK", "variety", f"{len(cnt)} different shot types across {len(real)} scenes "
                    f"({', '.join(f'{k} {v}' for k, v in cnt.most_common(4))}).")
    else:
        rep.add("INFO", "variety", "Plain script: run `ytauto plan` first to check shot variety.")

    # -- readiness
    minutes = n_words / 150
    rep.add("INFO", "readiness", f"{n_words} words, about {minutes:.1f} min of narration.")
    if minutes < 8:
        rep.add("INFO", "readiness", "Under 8 minutes: YouTube only allows mid-roll ads on videos of 8 minutes or more.")
    if len(doc.title) > 100:
        rep.add("FAIL", "readiness", f"Title is {len(doc.title)} characters; YouTube allows 100.")
    elif doc.title.isupper():
        rep.add("WARN", "readiness", "Title is all capitals.")
    if doc.data:
        if len((doc.description or "").strip()) < 150:
            rep.add("WARN", "readiness", "Description is very short. Say what the video covers and what it is based on.")
        yt = doc.data.get("youtube") or {}
        if "synthetic_media" not in yt:
            rep.add("INFO", "readiness", "Narration is an AI voice. YouTube asks for the 'Altered or synthetic content' "
                    "box on realistic content; set `youtube: {synthetic_media: true}` or tick it at upload.")
        from .config import load_project
        voice = load_project(doc.root).settings.get("voice") or {}
        if voice.get("engine") == "chatterbox":
            rep.add("INFO", "readiness", "Chatterbox voice: the audio carries Resemble's inaudible PerTh watermark.")
        if not doc.data.get("thumbnail"):
            rep.add("INFO", "readiness", "No `thumbnail:` text set; a default thumbnail will be made.")
    return rep

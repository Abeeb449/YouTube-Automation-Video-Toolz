"""The creator's script.txt: narration, plus the creator's own directions for the video.

Everything the narrator says is plain paragraphs (blank line between them, optional "# Chapter" headings).
Directions are short labelled lines; they are never read aloud:

    Intro: 4                       seconds of music and picture before the first word ("0:04" works too; default 4)

    # Chapter title

    A paragraph of narration.
    B-roll: leopard seal resting on sea ice | leopard seal         video if one is found, else a photo
    Video: leopard seal swimming underwater                        a video clip only
    Photo: fur seal pups on a rocky beach -> a colony of fur seals with pups on rocks
                                                                   search words -> what the picture must show
    3D: Apollo 11 command module                                   a 3D model for this scene (free-licence
                                                                   libraries, or your own file: 3D: assets/x.glb)
    (a "3D:" line at the very top, before any narration, names the model the whole video is built around)

    Sources: Author (year), Journal; another source

Rules the toolkit follows:
  * B-roll (stock video and photos) is used ONLY where the script asks for it, with exactly the search words
    given. `|` separates alternatives, tried in order. Nothing is searched from words the toolkit picked itself.
  * A direction line belongs to the paragraph above it (on the next line, or after a blank line). Lines placed
    right under "Intro:" are the opening's own pictures.
  * Every picture or clip found is checked against the search words (or the text after "->" / a following
    "Details:" line) before it is used; if nothing passes, the scene keeps its drawn/3D shot.
  * Other labelled lines ("Visual:", "On screen:", "Note:") are kept as notes on the scene and never narrated.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

_KIND = r"(?:b[\s-]?roll|stock|footage|videos?|clips?|photos?|images?|pictures?|pics?|3[\s-]?d(?:\s+models?)?|models?)"
BROLL_LINE = re.compile(
    rf"^\s*[\[(]?\s*(?P<label>{_KIND}(?:\s+{_KIND})?(?:\s+(?:search(?:\s+(?:terms?|words?))?|keywords?|terms?))?"
    r"|search(?:\s+(?:terms?|words?))?|keywords?)"
    r"\s*(?:\d+\s*)?[:=]\s*(?P<body>.+?)\s*[\])]?\s*$", re.I)
BROLL_INLINE = re.compile(rf"\[\s*(?P<label>{_KIND}(?:\s+{_KIND})?)\s*[:=]\s*(?P<body>[^\]]+)\]", re.I)
DETAIL_LINE = re.compile(r"^\s*[\[(]?\s*(?:details?|shows?|must\s+show|should\s+show|description|check)\s*[:=]\s*(.+?)\s*[\])]?\s*$", re.I)
INTRO_LINE = re.compile(r"^\s*[\[(]?\s*(?:music\s+)?(?:intro|opening|cold\s+open)(?:\s+music)?\s*[:=]?\s*"
                        r"(?P<v>\d[\d:.]*\s*(?:s|secs?|seconds?|m|mins?|minutes?)?(?:\s+of\b[^\])]*)?)\s*[\])]?\s*$", re.I)
NOTE_LINE = re.compile(r"^\s*[\[(]?\s*(?:visuals?|on[\s-]?screen|notes?|direction|shot|animation|graphic)\s*[:=]\s*(.+?)\s*[\])]?\s*$", re.I)
SOURCES_LINE = re.compile(r"^\s*sources?\s*:\s*(.+)$", re.I)
SUBJECT_LINE = re.compile(r"^\s*subject\s*:\s*(.+)$", re.I)
SCENE_LABEL = re.compile(r"^\s*(?:scene|shot|part)\s*\d+\s*[:.\-–—]?\s*$", re.I)        # a bare "Scene 3" line
SPOKEN_PREFIX = re.compile(r"^\s*(?:(?:scene|shot)\s*\d+\s*[:.\-–—]\s*)?(?:narration|narrator|voice[\s-]?over|vo|script)\s*[:=]\s*", re.I)


@dataclass
class Broll:
    kind: str                 # "video" | "photo" | "either" (a clip or a photo, whichever suits the scene) | "model" (3D)
    search: str               # the creator's search words; alternatives joined with "|"
    detail: str | None = None  # what the picture must show (checked); None = the search words themselves


@dataclass
class Para:
    text: str
    chapter: str | None = None
    broll: list[Broll] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


@dataclass
class Script:
    title: str | None = None
    subject: str | None = None
    intro: str | None = None                      # as written ("30", "0:30"); None = not stated
    intro_broll: list[Broll] = field(default_factory=list)
    subject_model: str | None = None              # "3D: …" written before the first paragraph: the video's own 3D model
    paras: list[Para] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    trailing_chapter: str | None = None

    def clean(self) -> str:
        """Narration only, in the plain layout (headings and paragraphs), with nothing the narrator must not say."""
        out = []
        if self.subject:
            out.append(f"Subject: {self.subject}")
        for p in self.paras:
            if p.chapter:
                out.append(f"# {p.chapter}")
            out.append(p.text)
        return "\n\n".join(out) + "\n"

    @property
    def broll_count(self) -> int:
        return len(self.intro_broll) + sum(len(p.broll) for p in self.paras)


def _broll(label: str, body: str) -> Broll:
    lab = label.lower()
    kind = ("model" if re.search(r"3[\s-]?d|model", lab) else
            "video" if re.search(r"video|clip|footage", lab) else
            "photo" if re.search(r"photo|image|picture|pic", lab) else "either")
    detail = None
    m = re.split(r"\s*(?:->|=>|→|⇒)\s*", body, maxsplit=1)
    if len(m) == 2:
        body, detail = m[0], m[1].strip() or None
    alts = [re.sub(r"\s+", " ", a).strip(" \"'“”.,") for a in re.split(r"\s*(?:\||;| / )\s*", body)]
    return Broll(kind, "|".join(a for a in alts if a), detail)


def parse_script(raw: str) -> Script:
    sc = Script()
    buf: list[str] = []            # lines of the paragraph being read
    pending_chapter: str | None = None
    pending_broll: list[Broll] = []   # b-roll written before any paragraph (and not under Intro:)
    last_broll: Broll | None = None
    after_intro = False

    def flush() -> None:
        nonlocal buf, pending_chapter, pending_broll
        text = re.sub(r"\s+", " ", " ".join(buf)).strip()
        buf = []
        if not text:
            return
        p = Para(text, pending_chapter, pending_broll)
        pending_chapter, pending_broll = None, []
        sc.paras.append(p)

    def attach(b: Broll) -> None:
        nonlocal last_broll
        last_broll = b
        if not b.search:
            return
        if buf:                      # a direction inside the paragraph block: flush the text first, then attach
            flush()
        if sc.paras:
            sc.paras[-1].broll.append(b)
        elif b.kind == "model" and not after_intro:
            sc.subject_model = b.search       # before any narration: the 3D model the whole video is built around
        elif after_intro:
            sc.intro_broll.append(b)
        else:
            pending_broll.append(b)

    for line in raw.replace("\r\n", "\n").split("\n"):
        s = line.strip()
        if not s:
            flush()
            continue
        if s.startswith("#"):
            flush()
            head = s.lstrip("#").strip()
            if sc.title is None and not sc.paras:
                sc.title = head
            pending_chapter = head
            continue
        m = SUBJECT_LINE.match(s)
        if m:
            flush()
            sc.subject = m.group(1).strip()
            continue
        m = SOURCES_LINE.match(s)
        if m:
            flush()
            sc.sources += [x.strip() for x in re.split(r";\s*", m.group(1)) if x.strip()]
            continue
        m = INTRO_LINE.match(s)
        if m and not sc.paras and not buf:
            sc.intro = m.group("v").strip()
            after_intro = True
            continue
        m = BROLL_LINE.match(s)
        if m:
            attach(_broll(m.group("label"), m.group("body")))
            continue
        m = DETAIL_LINE.match(s)
        if m and last_broll is not None:
            last_broll.detail = m.group(1).strip()
            continue
        m = NOTE_LINE.match(s)
        if m:
            if buf:
                flush()
            if sc.paras:
                sc.paras[-1].notes.append(m.group(1).strip())
            continue
        if SCENE_LABEL.match(s):
            flush()
            continue
        # narration (a paragraph may carry inline [b-roll: …] directions)
        after_intro = False
        s = SPOKEN_PREFIX.sub("", s)
        found = [(_broll(x.group("label"), x.group("body"))) for x in BROLL_INLINE.finditer(s)]
        s = BROLL_INLINE.sub(" ", s).strip()
        if s:
            buf.append(s)
        if found:
            flush()
            for b in found:
                attach(b)
    flush()
    if pending_broll and sc.paras:
        sc.paras[-1].broll += pending_broll
    sc.trailing_chapter = pending_chapter
    return sc


def narration_only(raw: str) -> str:
    return parse_script(raw).clean()

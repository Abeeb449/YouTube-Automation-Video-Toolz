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

The script writer's layout is read as it is, too (pasted text or a PDF):

    SCENE 2: THE SHARK CAPITAL (0:46 to 1:55)      a chapter ("HOOK" / "INTRO" belong to the title, no chapter card)
    3D footage only in this scene.                  a direction; never narrated
    [B-roll] IMAGE: Map of the coast with the towns marked. Keywords: "Western Cape coast map", "Gansbaai map"
    NARRATION:                                      (optional)
    The story starts in a small fishing town …

  A cue written this way ("[B-roll]" first, then VIDEO or IMAGE) sits ABOVE the narration it covers, so it
  belongs to the paragraph that FOLLOWS it. The keywords are the search words, tried in order; the sentence
  before "Keywords:" says what the picture must show. The header lines (TITLE, CENTRAL QUESTION, SHAPE, LENGTH,
  TITLE PROMISE) and the closing sections (B-ROLL KEYWORD LIST, SOURCES, NEEDS CHECKING) are never narrated;
  the numbered sources go to the description.

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


# --- the script writer's layout ---------------------------------------------------------------------------------
CUE_LINE = re.compile(r"^\s*\[\s*b[\s-]?roll\s*\]\s*(?P<kind>videos?|clips?|footage|images?|photos?|pictures?|maps?)?\s*[:.\-–—]?\s*(?P<body>.*)$", re.I)
KEYWORDS = re.compile(r"\bkey\s*words?\s*[:=]\s*(?P<k>.+)$", re.I | re.S)
SCENE_HEAD = re.compile(r"^\s*(?:final\s+scene|(?:scene|part|chapter)\s*\d+)\s*[:.\-–—]\s*(?P<name>[^()]*?)\s*"
                        r"(?:\(\s*\d+:\d+(?::\d+)?\s*(?:to|-|–|—)\s*\d+:\d+(?::\d+)?\s*\))?\s*$", re.I)
ONLY_3D = re.compile(r"^\s*[*_(\[]*\s*3[\s-]?d\s+(?:footage\s+|animation\s+)?only\b[^.]*\.?\s*[*_)\]]*\s*$", re.I)
META_LINE = re.compile(r"^\s*(?P<k>title|central\s+question|shape|length|title\s+promise|angle|word\s+count)\s*:\s*(?P<v>.*)$", re.I)
END_SECTION = re.compile(r"^\s*(?P<k>b[\s-]?roll\s+keyword\s+list|sources?|references|needs\s+checking)\s*:?\s*$", re.I)
SKIP_LINE = re.compile(r"^\s*(?:the\s+script|narration|script)\s*:?\s*$", re.I)
_OPENERS = re.compile(r"^(?:hook|intro(?:duction)?|cold\s+open|opening|teaser)$", re.I)
_SMALL = {"a", "an", "and", "as", "at", "but", "by", "for", "in", "nor", "of", "on", "or", "the", "to", "vs", "with", "from"}


def _chapter_name(name: str) -> str | None:
    """A scene heading's name as a chapter title: 'THE SHARK CAPITAL' → 'The Shark Capital'. Opening scenes
    ('HOOK') get none: they belong to the title."""
    name = re.sub(r"\s+and\s+(?:the\s+)?(?:cta|call\s+to\s+action|outro)\b", "", name.strip(" :.-–—"), flags=re.I).strip()
    if not name or _OPENERS.match(name):
        return None
    if name.lower() in ("answer", "cta", "outro", "ending"):
        return "The Answer"
    if name.isupper() or name.islower():
        words = name.lower().split()
        name = " ".join(w if (i and w in _SMALL) else w[:1].upper() + w[1:] for i, w in enumerate(words))
    return name


def _cue(kind: str | None, body: str) -> Broll:
    """'[B-roll] IMAGE: what to show. Keywords: "a", "b"' → the search words (in order) and what must be seen."""
    body = re.sub(r"\s+", " ", body).strip()
    m = KEYWORDS.search(body)
    show, keys = (body[:m.start()], m.group("k")) if m else (body, "")
    show = re.sub(r"^(?:the\s+)?(?:real\s+)?(?:drone\s+)?(?:photos?|footage|videos?|images?|pictures?|clips?)\s+of\s+", "",
                  show.strip(" .:-–—"), flags=re.I).strip()
    words = [w.strip(" \"'“”‘’.,;") for w in re.findall(r"[\"“]([^\"”]+)[\"”]", keys)] or \
            [w.strip(" \"'“”‘’.") for w in re.split(r"\s*[;,|]\s*", keys)]
    words = [w for w in words if w]
    k = (kind or "").lower()
    what = "video" if re.match(r"video|clip|footage", k) else "photo" if k else "either"
    return Broll(what, "|".join(words) if words else show, show or None)


def _prepare(raw: str) -> str:
    """Tidy text that came from a document: bullets and invisible characters off, a cue that runs over several
    lines (and its 'Keywords:' line) joined into one, a first bare line read as the title."""
    lines = [re.sub(r"[\u200b\u200c\u200d\ufeff\u00ad]", "", ln).replace("\u00a0", " ").rstrip()
             for ln in raw.replace("\r\n", "\n").replace("\f", "\n").split("\n")]
    lines = [re.sub(r"^\s*[•●▪◦·]\s*", "", ln) for ln in lines]
    out: list[str] = []
    i = 0
    while i < len(lines):
        ln = lines[i]
        if CUE_LINE.match(ln):
            j = i + 1
            while j < len(lines) and lines[j].strip() and not CUE_LINE.match(lines[j]) and \
                    (not KEYWORDS.search(ln) or re.search(r'[,"“]\s*$', ln) or ln.count('"') % 2):
                ln += " " + lines[j].strip()
                j += 1
            out += [ln, ""]                  # a cue never runs into the narration under it
            i = j
            continue
        out.append(ln)
        i += 1
    # a document's first line is its title when the scenes are labelled and it carries no mark of its own
    body = [k for k, ln in enumerate(out) if ln.strip()]
    if body and any(SCENE_HEAD.match(ln) for ln in out):
        first = out[body[0]].strip()
        if not first.startswith("#") and not SCENE_HEAD.match(first) and not META_LINE.match(first) \
                and len(first.split()) <= 18 and not re.search(r"[.!?]$", first):
            out[body[0]] = "# " + first
    return "\n".join(out)


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

    section = None                 # a closing section of the document ("sources", "b-roll keyword list", …)
    for line in _prepare(raw).split("\n"):
        s = line.strip()
        if not s:
            flush()
            continue
        m = END_SECTION.match(s)
        if m and (sc.paras or buf):
            flush()
            section = "sources" if re.match(r"sources?|references", m.group("k"), re.I) else "other"
            pending_chapter = None
            continue
        if section:                    # nothing after the script itself is narrated
            if section == "sources":
                item = re.match(r"^\s*\d+[.)]\s*(.+)$", s)
                if item:
                    sc.sources.append(item.group(1).strip())
                elif END_SECTION.match(s):
                    section = "other"
                elif sc.sources and (sc.sources[-1].count("(") > sc.sources[-1].count(")") or sc.sources[-1].endswith(",")):
                    sc.sources[-1] += " " + s          # a source that ran onto a second line
            continue
        m = META_LINE.match(s)
        if m and not sc.paras and not buf:
            if m.group("k").lower() == "title" and m.group("v").strip():
                sc.title = sc.title or m.group("v").strip()
            continue
        if SKIP_LINE.match(s):
            flush()
            continue
        if ONLY_3D.match(s):
            flush()
            continue
        m = SCENE_HEAD.match(s)
        if m and (m.group("name").strip() or True):
            flush()
            pending_chapter = _chapter_name(m.group("name")) or pending_chapter
            continue
        m = CUE_LINE.match(s)
        if m:                          # the writer's cue: it covers the narration that FOLLOWS it
            flush()
            b = _cue(m.group("kind"), m.group("body"))
            last_broll = b
            if b.search:
                pending_broll.append(b)
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


def read_script_file(path) -> str:
    """The text of a script file. A PDF is read with its paragraphs kept apart (pdftotext -layout, else pypdf)."""
    import shutil
    import subprocess
    from pathlib import Path
    path = Path(path)
    if path.suffix.lower() != ".pdf":
        return path.read_text(encoding="utf-8", errors="replace")
    if shutil.which("pdftotext"):
        text = subprocess.run(["pdftotext", "-layout", str(path), "-"], capture_output=True, text=True, check=True).stdout
    else:
        from pypdf import PdfReader
        text = "\f".join((pg.extract_text() or "") for pg in PdfReader(str(path)).pages)
    # a paragraph that runs over a page break is one paragraph: join where the page ends mid-sentence
    pages = [pg.strip("\n") for pg in text.split("\f") if pg.strip()]
    out = pages[:1]
    for pg in pages[1:]:
        prev = out[-1].rstrip()
        first = pg.lstrip("\n").split("\n", 1)[0].strip()
        mid = prev and not re.search(r'[.!?:"”)]$', prev) and first[:1].islower()
        out[-1] = prev + ("\n" if mid else "\n\n") + pg.lstrip("\n")
    return "\n".join(ln.strip() if not CUE_LINE.match(ln) else ln.strip() for ln in "".join(out).split("\n")) + "\n"

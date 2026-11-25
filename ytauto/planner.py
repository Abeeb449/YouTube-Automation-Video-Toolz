"""Turn a plain narration script into a full script.yaml (scenes, visuals, moods, cues) — free and offline.

The built-in rule-based director splits the script into beats and picks templates from what the text
mentions, for ANY animal: the subject (from the title or a "Subject:" line), body parts (→ close-ups with
callouts: 3D when a model exists, otherwise a real photo of that part), dates (→ typed date card), numbers
(→ counters / dot grids), short punchy lines (→ big statements), and real photo / video B-roll from free
sources between them. Styles: nature (any animal, real-photo led), ocean (drawn ocean scenes + photos),
documentary (what-if infographics).
For a hand-directed result, give agent/SYSTEM_PROMPT.md + agent/SKILL.md to any AI assistant (free ones work)
and let it write script.yaml directly — no paid API is needed anywhere in this project.
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

from .utils import REPO_ROOT, YtautoError, log, warn

STYLES = {
    "nature": ".claude/skills/animal-documentary",
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
    (r"leopard seals?", "leopardSeal"), (r"sea lions?|fur seals?", "seaLion"), (r"penguins?", "penguin"),
    (r"\bkrill\b", "krill"), (r"\bfish\b|school of", "fishSchool"),
]
PARTS = re.compile(r"\b(teeth|tooth|jaws?|fangs?|canines?|bite|claws?|talons?|eyes?|ears?|tails?|fins?|flippers?|tentacles?|"
                   r"suckers?|stingers?|stings?|venom|horns?|tusks?|beaks?|bills?|wings?|feathers?|skin|scales|fur|whiskers?|"
                   r"legs?|feet|paws?|hooves|mandibles?|antennae?|shells?|spines?|quills?|trunk|snout|nose|tongue|gills?|"
                   r"armou?r|plates|crest|mane|stripes|spots)\b", re.I)
DATE = re.compile(r"\b(?:in|by|since|until|during|on|around|about|circa|from|of)\s+((?:(?:January|February|March|April|May|June|"
                  r"July|August|September|October|November|December)\s+(?:\d{1,2}(?:st|nd|rd|th)?,?\s+)?)?(?:(?:1[0-9]\d\d|20\d\d)s?|\d{1,4}\s?(?:BC|BCE|AD|CE)))\b", re.I)
PLACE = re.compile(r"\b(?:in|at|near|off|on|from)\s+((?:the\s+)?[A-Z][a-z]+(?:\s+(?:[A-Z][a-z]+|of|de|del))*)")
# 3D models with known anatomy points (x, y inside the visible model, 0-1). Add an entry when a model is added.
ANATOMY_3D = {
    "leopardSeal": {"sprite": {"creature": "leopardSealHead", "view": "jaw"}, "parts": {
        "teeth": (0.5, 0.44, "Three-pointed cheek teeth"), "tooth": (0.5, 0.44, "Cheek teeth"),
        "canine": (0.86, 0.55, "Long canines"), "fang": (0.86, 0.55, "Long canines"),
        "jaw": (0.33, 0.46, "A huge gape"), "bite": (0.86, 0.55, "Built to grip")}},
    "seaLion": {"sprite": {"creature": "seaLion", "view": "rest"}, "parts": {
        "ear": (0.84, 0.08, "Small external ears"), "flipper": (0.8, 0.8, "Long front flippers"),
        "whisker": (0.95, 0.3, "Whiskers")}},
}
_STOPW = set("why do does did how what when where who the a an is are was were of in on at to and or for with from "
             "would never want meet you your this that these those it its fear afraid most really".split())
DANGER = re.compile(r"\b(kill|killed|attack|teeth|jaws|predator|hunt|hunts|hunting|venom|deadly|danger|dangerous|bite|crush|prey)\b", re.I)
WONDER = re.compile(r"\b(largest|biggest|incredible|amazing|beautiful|record|longest|loudest|discovered|glow|light)\b", re.I)
MYSTERY = re.compile(r"\b(mystery|unknown|nobody|never been|dark|darkness|deep|abyss|strange|secret)\b", re.I)
DEPTH = re.compile(r"(\d[\d,\.]*)\s*(metres|meters|m)\b[^.]*\b(deep|down|below|depth)|\b(depth|deep|below)[^.]*?(\d[\d,\.]*)\s*(metres|meters|m)\b", re.I)
DB = re.compile(r"(\d[\d,\.]*)\s*(decibels|dB)\b", re.I)
NUMBER = re.compile(r"\b(\d[\d,\.]*)\s*(metres|meters|tonnes|tons|kilograms|kg|years|kilometres|kilometers|km|miles|feet|"
                    r"centimetres|cm|millimetres|mm|%|percent|hearts|teeth|microseconds|milliseconds|seconds|minutes|"
                    r"hours|days|degrees|times|litres|liters|gallons|watts|volts|light-years|people|species|workers)\b", re.I)


_UNITS = {w: i for i, w in enumerate("zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen "
                                      "fifteen sixteen seventeen eighteen nineteen".split())}
_TENS = {w: 10 * (i + 2) for i, w in enumerate("twenty thirty forty fifty sixty seventy eighty ninety".split())}
_SCALES = {"hundred": 100, "thousand": 1000, "million": 1_000_000, "billion": 1_000_000_000}
_NUMW = "|".join(sorted([*_UNITS, *_TENS, "hundred", "thousand", "million", "billion"], key=len, reverse=True))
_NUMW_DET = "|".join(w for w in _NUMW.split("|") if w != "one")   # 'each one carries…': 'one' is a pronoun
_HALF = re.compile(rf"\b((?:(?:{_NUMW}|\d+)[\s-]+)*?(?:{_NUMW}|\d+)) and a half(?:\s+(hundred|thousand|million|billion))?\b", re.I)
_HALF_A = re.compile(r"\bhalf an? (hundred|thousand|million|billion)\b", re.I)


def _figure_heading(beat: str, cue: str) -> dict:
    """The words around a figure, shown as the counter's heading from the first frame ('GPS would drift by around
    ten kilometres every single day'), so the screen says what the number is before it counts."""
    clause = _clause_with(beat, cue)
    if not clause or clause == cue:
        return {}
    clause = clause if len(clause) <= 64 else clause[:64].rsplit(" ", 1)[0] + "…"
    return {"heading": clause}


def _counter_value(val: float, before: str) -> dict:
    """Counter props that read the way the narrator says the number: 6.5 (not 7), 1.5 million, 13 billion,
    and a minus sign for 'minus 200 degrees'."""
    props: dict = {}
    if re.search(r"(?:\bminus|\bnegative|−|-)\s*$", before.strip()[-10:] + " ", re.I) or re.search(r"\bminus\s*$", before, re.I):
        props["prefix"] = "−"
    for big, word in ((1e9, "billion"), (1e6, "million")):
        if val >= big and (val / big) * 10 == int((val / big) * 10):
            val = val / big
            props["suffix"] = f" {word}"
            break
    props["to"] = val
    if val != int(val):
        props["decimals"] = 1 if (val * 10) == int(val * 10) else 2
    return props


def _spoken(beat: str, digits: str) -> str:
    """The word the narrator actually says for a number (a cue must be a spoken word): '1,500' if written in
    digits, else the first number word ('one and a half million' → 'one')."""
    first = digits.split(",")[0]
    if re.search(rf"\b{re.escape(first)}", beat):
        return first
    # the spelled-out number that IS this value ('twenty thousand' for 20000, not the 'thirty' earlier in the line)
    try:
        target = float(digits.replace(",", ""))
    except ValueError:
        target = None
    run = re.compile(rf"\b(?:{_NUMW}|half|a)(?:[\s-]+(?:{_NUMW}|and|a|half))*\b", re.I)
    for m in run.finditer(beat):
        phrase = m.group(0)
        if not re.search(rf"\b(?:{_NUMW}|half)\b", phrase, re.I):
            continue
        val = re.findall(r"\d+(?:\.\d+)?", words_to_digits(phrase))
        if target is not None and val and abs(float(val[0]) - target) < 1e-6:
            return re.split(r"[\s-]", phrase)[0] if not phrase.lower().startswith("a ") else re.split(r"[\s-]", phrase)[1]
    w = re.search(rf"\b({_NUMW}|half|a dozen)\b", beat, re.I)
    return w.group(1).split()[0] if w else first


def _numstr(v: float) -> str:
    return str(int(v)) if v == int(v) else f"{v:g}"


def words_to_digits(text: str) -> str:
    """'two thousand metres' → '2000 metres' so number rules can see spelled-out numbers.
    'one and a half million' → '1500000', 'six and a half metres' → '6.5 metres', 'half a million' → '500000'."""
    def half(m: re.Match) -> str:
        base = m.group(1)
        n = float(base) if base.isdigit() else float(_words_to_digits(base).strip() or 0)
        return _numstr((n + 0.5) * _SCALES.get((m.group(2) or "").lower(), 1))
    # spoken years: 'nineteen ninety' → 1990, 'eighteen ninety-eight' → 1898, 'twenty twenty-one' → 2021
    def year(m: re.Match) -> str:
        hi = _UNITS.get(m.group(1).lower()) or _TENS.get(m.group(1).lower(), 0)
        lo = _TENS[m.group(2).lower()] + (_UNITS[m.group(3).lower()] if m.group(3) else 0)
        return str(hi * 100 + lo)
    text = re.sub(r"\b(eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty)\s+"
                  r"(twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety)(?:[\s-](one|two|three|four|five|six|seven|eight|nine))?\b",
                  year, text, flags=re.I)
    text = _HALF.sub(half, text)
    text = _HALF_A.sub(lambda m: _numstr(0.5 * _SCALES[m.group(1).lower()]), text)
    return _words_to_digits(text)


def _words_to_digits(text: str) -> str:
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
                dangling = buf[-1].lower() == "and"   # "one and the other": the 'and' is not part of the number
                if dangling:
                    buf.pop()
                flush()
                out.append(" and " if dangling else " ")
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


def find_subject(script: str, title: str) -> str:
    """The animal the video is about: a "Subject: …" line wins; otherwise the title phrase (1-3 words)
    that the script repeats most ("Why Do Sea Lions Fear Leopard Seals?" → "leopard seal")."""
    m = re.search(r"^\s*subject\s*:\s*(.+)$", script, re.I | re.M)
    if m:
        return m.group(1).strip().lower()
    words = [w for w in re.findall(r"[a-z]+", title.lower())]
    body = script.lower()
    best, score = "", 0
    for n in (3, 2, 1):
        for i in range(len(words) - n + 1):
            grams = words[i:i + n]
            if any(g in _STOPW for g in (grams[0], grams[-1])):
                continue
            phrase = " ".join(grams)
            stem = re.sub(r"ies$", "y", phrase) if phrase.endswith("ies") else re.sub(r"(?<!s)s$", "", phrase)
            c = len(re.findall(r"\b" + re.escape(stem), body)) * (1 + 0.6 * (n - 1))
            if c > score:
                best, score = stem, c
    return best or "wildlife"


_VERBS = set("""built made make makes took take went go goes found find began begin became become came come gave give
held hold kept keep left leave lost lose said say sent send stood stand told tell wrote write rose rise fell fall
grew grow knew know ran run saw see sees sat sit won win works work changed change exploded sank sink fear fears
hunts hunt kills kill does did happened happen built""".split())
_GENERIC_NAMES = {"Earth", "World", "Universe", "God", "Christmas", "Christmas Day", "Christmas Eve", "Easter",
                  "New Year", "New Year's Day", "Celsius", "Fahrenheit", "Kelvin", "Today", "Mr", "Mrs", "Dr"}


def find_topic(script: str, title: str) -> str:
    """What a non-animal video is about: a "Subject: …" line wins; otherwise the named thing in the script that the
    title also names, widened with neighbouring title words the script uses ("Webb" → "Webb Telescope");
    otherwise the title phrase the script repeats most."""
    m = re.search(r"^\s*subject\s*:\s*(.+)$", script, re.I | re.M)
    if m:
        return m.group(1).strip()
    tw = [re.sub(r"'s$", "", w) for w in re.findall(r"[A-Za-z][\w'-]*", title)]
    low = [w.lower() for w in tw]
    body = " ".join(b for b in re.split(r"\n\s*\n", script) if not b.strip().startswith("#")).lower()
    from collections import Counter
    ents = Counter(e for b in re.split(r"\n\s*\n", script) if not b.strip().startswith("#") for e in _entities(b))
    raw_body = " ".join(b for b in re.split(r"\n\s*\n", script) if not b.strip().startswith("#"))
    for w in tw:   # a title word the script only ever writes capitalised is a name, even at a sentence start ("Venice")
        if (w.lower() not in _STOPW and len(w) > 2 and re.search(rf"\b{re.escape(w)}\b", raw_body)
                and not re.search(rf"\b{re.escape(w.lower())}\b", raw_body)):
            ents[w] += 1
    best = ""
    for e, _c in ents.most_common():
        ew = [w.lower() for w in e.split()]
        if e in _GENERIC_NAMES or not all(w in low for w in ew):
            continue
        i, j = low.index(ew[0]), low.index(ew[-1]) + 1
        def used(w: str) -> bool:   # the script uses this exact word (a plural may appear as its singular), not a verb
            if w.endswith(("ed", "ing")) or w in _VERBS:
                return False
            forms = [w] + ([w[:-1]] if w.endswith("s") and not w.endswith(("ss", "es")) else [])
            return any(re.search(rf"\b{re.escape(f)}\b", body) for f in forms)
        while j < len(low) and low[j] not in _STOPW and used(low[j]):
            j += 1
        while i > 0 and low[i - 1] not in _STOPW and used(low[i - 1]):
            i -= 1
        best = " ".join(tw[i:j])
        break
    if best:
        return best
    # the title names nothing the script talks about ("The Notebooks Too Radioactive to Touch"): the video is about
    # the name the script keeps returning to ("Marie" ×2 + "Marie Curie" → Marie Curie)
    named = Counter({e: c for e, c in ents.items() if e not in _GENERIC_NAMES and e not in _BROAD_PLACES})
    if named:
        score = {e: sum(c for f, c in named.items() if f in e or e in f) for e in named}
        top = max(score, key=lambda e: (score[e], len(e)))
        if score[top] >= 2:
            return top
    words = [w for w in tw if w.lower() not in _STOPW and w.lower() not in _VERBS and not w.lower().endswith(("ed", "ing"))]
    return " ".join(words[:3]) or title


def _opening(blocks: list[str]) -> str:
    """The script's first two sentences, as a starting point for the YouTube description."""
    text = " ".join(b for b in blocks if not b.startswith("#"))
    text = re.sub(r"\[[^\]]*\]", " ", text)
    sents = re.split(r"(?<=[.!?])\s+", re.sub(r"\s+", " ", text).strip())
    return " ".join(sents[:2])[:300]


def _tags(title: str, subject: str, script: str = "") -> list[str]:
    """The video's topic plus the names the script itself keeps mentioning."""
    from collections import Counter
    ents = Counter(e for b in re.split(r"\n\s*\n", script) if not b.strip().startswith("#") for e in _entities(b))
    names = [e for e, c in ents.most_common(6) if e.lower() not in subject.lower()]
    out = list(dict.fromkeys([subject.lower()] + [n.lower() for n in names] + ["documentary"]))
    return [t for t in out if t][:12]


def _thumb_text(title: str, limit: int = 40) -> str:
    """Thumbnail words: the title in capitals, cut at a word boundary (never mid-word)."""
    t = title.upper().strip()
    if len(t) <= limit:
        return t
    cut = t[:limit + 1].rsplit(" ", 1)[0].rstrip(" ,:;-")
    return cut or t[:limit]


def plan_with_rules(script: str, style: str, title: str | None, fmt: str = "video") -> str:
    sources = [ln.split(":", 1)[1].strip() for ln in script.splitlines() if re.match(r"\s*sources?\s*:", ln, re.I)]
    blocks = [b.strip() for b in re.split(r"\n\s*\n", script.strip()) if b.strip()
              and not re.match(r"^\s*(subject|sources?)\s*:", b, re.I)]
    title = title or (blocks[0].lstrip("#").strip()[:70] if blocks and blocks[0].startswith("#") else "Untitled Documentary")
    narration = "\n".join(ln for ln in script.splitlines() if not re.match(r"\s*sources?\s*:", ln, re.I))
    subject = find_subject(narration, title) if style in ("nature", "ocean") else find_topic(narration, title)
    ctx = _script_context(narration, subject)
    topic_q = f"{subject} {ctx}".strip() if ctx else subject
    if style not in ("nature", "ocean") and re.fullmatch(r"[A-Z0-9]{2,5}", subject or ""):
        # an acronym alone ('GPS', 'MRI') finds devices, logos and diagrams: search it with the thing the script
        # keeps talking about ('GPS satellites')
        from collections import Counter
        forms: dict[str, list[str]] = {}
        for b in blocks:
            if not b.startswith("#"):
                for n in _key_nouns(b):
                    forms.setdefault(n[:-1] if _plural(n) else n, []).append(n)
        ranked = sorted(forms.items(), key=lambda kv: -len(kv[1]))
        top = next((max(v, key=len) for k, v in ranked if len(v) >= 2 and k.lower() != subject.lower()), None)
        if top:
            topic_q = f"{subject} {top}"
    main = _creature(subject, None) or _creature(script, "giantSquid" if style == "ocean" else "fishSchool")
    scenes: list[dict] = []
    chapter = None
    mood_prev = None
    n = 0
    body_low = " ".join(b for b in blocks if not b.startswith("#")).lower()
    weak = style not in ("nature", "ocean") and not any(
        w in body_low for w in re.findall(r"[a-z]{4,}", (subject or "").lower()) if w not in _STOPW)
    local_subject, local_q = subject, topic_q
    for block in blocks:
        if block.startswith("#"):
            chapter = block.splitlines()[0].lstrip("#").strip()
            rest = "\n".join(block.splitlines()[1:]).strip()
            # a list video ('# 3. Velcro') or a title that names nothing in the script: each chapter is about its
            # own thing, so its lines are searched with the chapter's subject, not the video's title
            numbered = re.match(r"^(?:#?\d+[.):]?|number\s+\d+[.:]?)\s+", chapter, re.I)
            head = re.sub(r"^(?:#?\d+[.):]?|number\s+\d+[.:]?)\s+", "", chapter, flags=re.I)
            head = re.sub(r"^(?:the|a|an)\s+", "", head, flags=re.I).strip(" .:!?")
            if style not in ("nature", "ocean") and head and blocks.index(block) > 0 and (numbered or weak):
                local_subject = local_q = head
            elif blocks.index(block) > 0:
                local_subject, local_q = subject, topic_q
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
            # music mood and sound effects are left to the sound director (ytauto/sound_director.py), which reads
            # every scene's words and emotion at render time; write mood:/sfx: by hand only to override it
            sc["text"] = beat
            vis = _rule_visual(beat, style, main, n, local_subject, local_q)
            sc["visuals" if isinstance(vis, list) else "visual"] = vis
            scenes.append(sc)
    data = {
        "preset": [style, "shorts"] if fmt == "shorts" else style, "title": title,
        # from the creator's own words: the script's opening lines (edit before upload; add your sources)
        "description": _opening(blocks),
        "tags": _tags(title, subject, script),
        **({"sources": [x.strip() for src in sources for x in re.split(r";\s*", src) if x.strip()]} if sources else {}),
        "thumbnail": {"text": _thumb_text(title)}, "youtube": {"privacy": "private"},
        "scenes": scenes,
    }
    return "# Planned automatically by the rule-based director — edit freely, then render.\n" + \
        yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=110)


# What the line says about WHERE/HOW the animal is, so the picture is checked against it (ytauto/verify.py)
SETTINGS = [
    (r"\b(underwater|beneath|below the surface|dives?|diving|swims?|swimming|in the water|in the sea|in the ocean)\b", "swimming underwater"),
    (r"\b(hunts?|hunting|attacks?|chases?|ambush|catch(?:es)?|kills?|prey)\b", "hunting"),
    (r"\b(on (?:the )?ice|ice floes?|sea ice|icebergs?|floes?|ice)\b", "on or near sea ice"),
    (r"\b(on land|on (?:the )?beach|on (?:the )?rocks|on shore|hauls? out|basking|lying)\b", "on land"),
    (r"\b(flies|flying|in flight|soars?)\b", "flying"),
    (r"\b(sleeps?|sleeping|rests?|resting)\b", "resting"),
    (r"\b(eats?|eating|feeds?|feeding)\b", "feeding"),
]


def _setting(beat: str) -> str:
    for pat, phrase in SETTINGS:
        if re.search(pat, beat, re.I):
            return phrase
    return ""


def _describe(subject: str, beat: str) -> str:
    """'a wild leopard seal swimming underwater': what the stock picture must actually show for this line."""
    s = _setting(beat)
    return f"a photo of a wild {subject}" + (f" {s}" if s else "")


def _photo(query: str, fallback: dict, callout: str | None = None, layout: str = "full", n: int = 0,
           verify: str | None = None) -> dict:
    ph = {"photo": f"stock:{query}", "parallax": layout == "full", "pick": n % 3}
    if verify:
        ph["verify"] = verify
    props: dict = {"layout": layout, "photos": [ph]}
    if callout:
        props.update(callout=callout[:48], calloutAt=_first_word(callout))
    return {"remotion": "PhotoStory", "props": props, "fallback_visual": fallback}


def _clause_with(beat: str, word: str) -> str:
    for part in re.split(r"(?<=[.!?;,:])\s+", beat):
        if re.search(r"\b" + re.escape(word), part, re.I):
            return part.strip().rstrip(".,;:!")
    return word


def _general_visual(beat: str, style: str, main: str, n: int, subject: str, drawn: dict) -> dict | list | None:
    """Rules that work for any animal: dates, body parts, real photos/video. None = let the style decide."""
    numeric = words_to_digits(beat)
    d = DATE.search(numeric)
    if d:
        place = PLACE.search(beat)
        stamp = {"remotion": "DateStamp", "props": {"date": d.group(1).upper(), "at": 0.2,
                                                    **({"place": place.group(1)} if place and place.group(1) not in d.group(1) else {})}}
        # what the line shows besides its date (the date removed from the number-normalised text, so a spelled-out
        # year like 'nineteen ninety' can never be found again and loop forever)
        rest = _general_visual(DATE.sub("", numeric), style, main, n + 1, subject, drawn) or drawn
        return [stamp, rest if isinstance(rest, dict) else rest[-1]]
    p = PARTS.search(beat)
    if p:
        part = p.group(1).lower()
        key = re.sub(r"(es|s)$", "", part) if part not in ("teeth", "feet", "hooves", "scales", "plates", "stripes", "spots") else part
        key = {"teeth": "teeth", "feet": "foot", "jaws": "jaw"}.get(key, key)
        ana = ANATOMY_3D.get(main)
        if ana and key in ana["parts"]:
            x, y, label = ana["parts"][key]
            return {"remotion": "Anatomy", "props": {"sprite": ana["sprite"], "backdrop": "abyss",
                    "callouts": [{"x": x, "y": y, "label": label, "at": p.group(1), "side": "right" if x > 0.5 else "left"}],
                    "zoom": [{"at": p.group(1), "x": x, "y": y, "scale": 1.35}]}}
        return _photo(f"{subject} {part}", drawn, callout=_clause_with(beat, p.group(1)), n=n)
    if style == "nature":
        want = _describe(subject, beat)
        if n % 2 == 0:  # real video clip every other shot (falls back to a checked photo, then the drawn shot)
            return {"stock": f"{subject}", "verify": want, "fallback_visual": _photo(subject, drawn, n=n, verify=want)}
        return _photo(subject, drawn, layout="print" if n % 4 == 1 else "full", n=n, verify=want)
    if style == "ocean" and n % 4 == 2:
        return _photo(subject, drawn, n=n, verify=_describe(subject, beat))
    return None


def _rule_visual(beat: str, style: str, main: str, n: int, subject: str = "", topic_q: str | None = None) -> dict | list:
    creature = _creature(beat, main)
    if style in ("ocean", "nature"):
        if style == "nature":
            drawn = {"remotion": "Statement", "props": {"line1": " ".join(beat.split()[:4]), "line2": " ".join(beat.split()[4:9])}}
            m = NUMBER.search(words_to_digits(beat))
            if m and not DATE.search(words_to_digits(beat)):
                val = _num(m.group(1))
                if m.group(2).lower() in ("%", "percent") and val <= 100:
                    return {"remotion": "DotGrid", "props": {"value": f"{val:g}%", "label": _clause_with(beat, m.group(2))[:60],
                                                             "count": 100, "highlight": int(val)}}
                num = words_to_digits(beat)
                cue = _spoken(beat, m.group(1))
                return {"remotion": "Counter", "props": {**_counter_value(val, num[:m.start()]), "label": m.group(2),
                                                         "countAt": cue, **_figure_heading(beat, cue)}}
            sents = [x.strip() for x in re.split(r"(?<=[.!?])\s+", beat) if x.strip()]
            punchy = [x for x in sents if 2 <= len(x.split()) <= 5 and not x.endswith("?")]
            if punchy and n % 3 != 2:
                card = {"remotion": "Statement", "props": {"line1": punchy[-1].rstrip(".!"), "at": 0.1}}
                if len(sents) == 1:
                    return card
                shot = _general_visual(beat, style, main, n, subject or main, drawn)
                if isinstance(shot, dict):   # the animal, then the line's punch (or the punch first when it leads)
                    return [card, shot] if sents[0] == punchy[-1] else [shot, card]
        else:
            drawn = _ocean_visual(beat, main, n, creature)
        g = _general_visual(beat, style, main, n, subject or main, drawn)
        if g is not None:
            return g
        return drawn
    if style == "ocean":
        return _ocean_visual(beat, main, n, creature)
    return _general_beat_visual(beat, n, subject, _doc_visual(beat, n), topic_q)


# ---------------------------------------------------------------------------------- what is THIS line about?
# Any topic: the named things in the line (people, places, objects, events) and its key nouns become the
# picture searched for, most specific first; every result is picture-checked (ytauto/verify.py).
_COMMON = set("""about above after again against almost along already also although always among another
around because become been before began begin being below between beyond both bring brought called came
cannot could course different does doing done during each early either enough even every everything example
except far fact few find first found from further gave give given going gone good great half having here high
however just keep kept known large last later least less like little long made make many may means might
more most much must near nearly need never next nothing number often only other others over part people
perhaps place point quite rather really right same second seen several should show since small some something
sometimes still such take taken than that their them then there these they thing things think this those
though three through time times today together took toward under until upon used using very want ways well
went were what when where whether which while whole whose will with within without world would year years
yet your around almost exactly enough inside outside still almost across against another
image images picture pictures photo photos photograph photographs video videos footage clip clips film shot shots
view views look looks story stories question questions answer answers reason reasons idea ideas kind kinds sort
type types lot lots bit bits piece pieces side sides end ends way kind version moment moments
past future present catch delay delays moment moments distance distances amount amounts level levels
rate rates chance chances problem problems fact facts truth result results difference differences effect effects
force forces night nights day mornings morning evening case cases explanation explanations theory theories idea model models
injury injuries wound wounds body bodies corpse corpses blood death deaths remains victim victims skull skeleton
january february march april june july august september october november december
team teams crew crews group groups member members century centuries decade decades
hour hours minute minutes week weeks month months era eras age ages""".split())
_ENTITY_SKIP = {"The", "It", "In", "On", "At", "For", "But", "And", "Then", "Today", "This", "That", "These", "Those",
                "There", "Here", "Nobody", "No", "One", "Every", "Each", "When", "While", "After", "Before", "If",
                "Archaeologists", "Scientists", "Researchers", "Historians", "Experts", "We", "You", "They", "He",
                "She", "His", "Her", "Its", "Their", "A", "An", "As", "By", "From", "With", "Some", "Most", "Many",
                "BC", "BCE", "AD", "CE", "January", "February", "March", "April", "May", "June", "July", "August",
                "September", "October", "November", "December", "Monday", "Tuesday", "Wednesday", "Thursday",
                "Friday", "Saturday", "Sunday"}


_NUMWORDS = set("""one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen
seventeen eighteen nineteen twenty thirty forty fifty sixty
seventy eighty ninety hundred hundreds thousand thousands million millions billion billions dozen dozens half
quarter percent""".split())
_PEOPLE = set("""people person archaeologists scientists researchers historians experts someone everyone anyone
nobody man men woman women""".split())
_ADJ = set("""oldest largest biggest smallest greatest longest highest tallest deepest first last only entire whole
ancient old new great big small huge tiny vast giant early late modern famous same other own single main final
best worst true real wet dry dark bright heavy light hidden lost secret strange golden silver thin thick
powerful huge massive tiny distant nearby empty full narrow wide deep shallow""".split())
_UNIT_WORDS = set("""metres meters metre meter kilometres kilometers miles feet foot inches centimetres tonnes tons kilograms
kilos pounds degrees celsius fahrenheit percent years months weeks days hours minutes seconds light-years
gram grams milligrams micrograms litres liters millilitres gallons ounces acres hectares watts volts""".split())


def _entities(beat: str) -> list[str]:
    """Named things in the line: 'Great Pyramid of Giza', 'Khufu', 'Nile' (capitalised runs, joined by of/the/de).
    A single capitalised word at the start of a sentence is just a sentence start ('Teams', 'Wet'), not a name."""
    text = re.sub(r"\[[^\]]*\]", " ", beat)
    out = []
    for m in re.finditer(r"\b([A-Z][\w'-]+(?:\s+(?:of|the|de|del|da|von|van|al|el)?\s*[A-Z][\w'-]+)*)", text):
        before = text[:m.start()].rstrip()
        sentence_start = not before or before[-1] in ".!?:;\"“"
        if sentence_start and len(m.group(1).split()) == 1:
            continue
        words = m.group(1).split()
        while words and words[0] in _ENTITY_SKIP:
            words = words[1:]
        while words and words[-1].lower() in ("of", "the", "de", "and"):
            words = words[:-1]
        ent = re.sub(r"'s$", "", " ".join(words))
        if ent and len(ent) > 2 and ent not in out and ent not in _GENERIC_NAMES:
            out.append(ent)
    return sorted(out, key=lambda e: -len(e.split()))


def _plural(w: str) -> bool:
    """'sledges', 'wolves' yes; 'tennis', 'glass', 'virus', 'basis' no."""
    return w.endswith("s") and not w.endswith(("ss", "is", "us", "os"))


def _key_nouns(beat: str) -> list[str]:
    """The things the line points at: heads of noun phrases ('the oldest papyrus', 'the sledges', 'their
    bakeries'), skipping numbers, people-words and adjectives."""
    text = re.sub(r"'s\b", "", re.sub(r"\[[^\]]*\]", " ", beat).lower())   # "his dog's fur" → "his dog fur"
    text = re.sub(r"\b(?:a|an|the)\s+[a-z-]+\s+ones?\b", " ", text)        # "made a weak one": no noun there
    names = {w.lower() for e in _entities(beat) for w in e.split()}   # 'Marie kept…': a name, searched as an entity
    def ok(w: str) -> bool:
        if w in names:
            return False
        if any(part in _NUMWORDS for part in w.split("-")):   # twenty-eight
            return False
        return (len(w) > 3 and w not in _VERBS and w not in _COMMON and w not in _STOPW and w not in _NUMWORDS and w not in _PEOPLE
                and w not in _ADJ and w not in _UNIT_WORDS and w != "ever" and not w.endswith(("ly", "ing")) and not w.isdigit())
    heads = []
    for m in re.finditer(r"\b(?:called|named|known as)\s+([a-z][a-z'-]+(?:\s+[a-z][a-z'-]+)?)", text):   # "a mineral called pitchblende"
        w = m.group(1).split()
        if ok(w[0]):
            heads.append(" ".join(w) if len(w) > 1 and ok(w[1]) else w[0])
    for m in re.finditer(r"(?:^|[.!?]\s+)([a-z][a-z'-]+)", text):   # the subject a sentence starts with ("wolves, elk…")
        if ok(m.group(1)):
            heads.append(m.group(1))
    for m in re.finditer(r"\b([a-z]{4,}s)\s*(,|\band\b)", text):   # items of a list: "wolves, elk and wild horses"
        after = text[m.end():m.end() + 40]
        if m.group(2) == "," and not re.search(r"\band\b", after.split(".")[0]):
            continue   # "as the universe expands, that light…" is a clause, not a list
        if ok(m.group(1)):
            heads.append(m.group(1))
    for m in re.finditer(rf"\b(?:the|a|an|their|its|his|her|this|these|those|our|of|\d[\d,.]*|{_NUMW_DET})\s+((?:[a-z'-]+(?:\s+|$|(?=[.,;:!?]))){{0,3}})", text):
        ws = m.group(1).split()
        k = 0
        def adjective(i: int) -> bool:   # "hexagonal mirror", "wooden piles": a describing word before a noun
            return (ws[i].endswith(("al", "ic", "ous", "ful", "ive", "ish", "en", "ed")) and i + 1 < len(ws) and ok(ws[i + 1]))
        while k < len(ws) and (ws[k] in _ADJ or ws[k] in _NUMWORDS or adjective(k) or (ws[k] in names and k + 1 < len(ws)) or ws[k] in (
                "the", "a", "an", "their", "its", "his", "her", "this", "these", "those", "our", "front", "side",
                "middle", "top", "bottom", "kind", "sort", "part", "size", "layer", "piece", "number", "group")):
            k += 1
        if (k + 1 < len(ws) and ws[k].endswith(("al", "ic", "ous", "ful", "ive", "ish", "ed")) and ws[k + 1].isalpha()
                and not ok(ws[k + 1])):
            continue   # "a physical explanation": the describing word of a noun that isn't a subject itself
        if k < len(ws) and ok(ws[k]):
            phrase = ws[k]
            if (k + 1 < len(ws) and ok(ws[k + 1]) and not ws[k + 1].endswith(("ed", "s")) and ws[k + 1] not in _VERBS
                    and not _plural(ws[k])):   # "tennis court", but not "buildings rest" (noun + verb)
                phrase += " " + ws[k + 1]
            heads.append(phrase)
    return list(dict.fromkeys(heads))[:3]


def _script_context(script: str, topic: str) -> str:
    """The name the whole script keeps coming back to (a place, person or object: 'Giza', 'Rome', 'Apollo 11'),
    so a fallback search for the topic finds THIS story's topic, not any pyramid or any empire."""
    from collections import Counter
    ents = Counter()
    for block in re.split(r"\n\s*\n", script):
        if block.strip().startswith("#"):
            continue
        for e in _entities(block):
            ents[e] += 1
    if not ents:
        return ""
    # a name contained in longer names counts for them too ("Giza" in "Great Pyramid of Giza")
    ents = Counter({e: c for e, c in ents.items() if e not in _GENERIC_NAMES})
    if not ents:
        return ""
    score = {e: sum(c for f, c in ents.items() if e in f) for e in ents}
    best = max(score, key=lambda e: (score[e], -len(e)))
    if score[best] < 2 or best.lower() in topic.lower():
        return ""
    return best


# Whole countries, continents and oceans: in a line about something inside them ("Italy closed the tower") a photo
# of "Italy" shows any Italian scene, so they only lead the search when the video is about that place itself
_BROAD_PLACES = set("""Afghanistan Albania Algeria Argentina Armenia Australia Austria Bangladesh Belgium Bolivia Brazil
Bulgaria Cambodia Cameroon Canada Chile China Colombia Croatia Cuba Czechia Denmark Ecuador Egypt England Estonia
Ethiopia Finland France Germany Ghana Greece Hungary Iceland India Indonesia Iran Iraq Ireland Israel Italy Japan
Jordan Kenya Korea Latvia Lebanon Libya Lithuania Malaysia Mexico Mongolia Morocco Nepal Netherlands Nigeria Norway
Pakistan Peru Philippines Poland Portugal Romania Russia Scotland Senegal Serbia Singapore Slovakia Somalia Spain
Sudan Sweden Switzerland Syria Tanzania Thailand Tunisia Turkey Uganda Ukraine Venezuela Vietnam Wales Yemen Zambia
Zimbabwe Africa Asia Europe America Antarctica Oceania Britain USA UK Soviet Russian American British French German
Chinese Japanese Italian Spanish European African Asian""".split()) | {
    "United States", "United Kingdom", "Soviet Union", "South Africa", "New Zealand", "Saudi Arabia", "North America",
    "South America", "Atlantic", "Pacific", "Indian Ocean", "Atlantic Ocean", "Pacific Ocean", "Arctic", "Mediterranean"}


def _queries(beat: str, topic: str, topic_q: str | None = None) -> list[str]:
    """Search alternatives for this line, most specific first, ending with the video's topic itself."""
    ents = [topic_q if (topic_q and e == topic) else e for e in _entities(beat)[:2]]
    # a place the line only mentions in passing ("visitors in Paris", "lifted off from French Guiana") or a whole
    # country is searched after the thing the line is about
    def passing(e: str) -> bool:
        return bool(re.search(rf"\b(?:in|at|from|to|near|across|over|outside|inside|around)\s+(?:the\s+)?{re.escape(e)}\b", beat))
    broad = [e for e in ents if topic and e.lower() not in topic.lower() and (e in _BROAD_PLACES or passing(e))]
    q = [e for e in ents if e not in broad]
    topic_words = set(topic.lower().split())
    for n in _key_nouns(beat)[:2]:
        if re.search(rf"\b(?:called|named|known as)\s+{re.escape(n)}\b", beat, re.I):
            q.append(n)   # a named thing ("a mineral called pitchblende") is searched by its own name
            continue
        tw = {t.rstrip("s") for t in topic_words}
        q.append((topic_q or topic or n) if all(x.rstrip("s") in tw for x in n.split()) else f"{n} {topic}".strip())
    if topic:
        q.append(topic_q or topic)
    q += broad
    return list(dict.fromkeys(x for x in q if x))[:5]


def _general_beat_visual(beat: str, n: int, topic: str, drawn: dict, topic_q: str | None = None) -> dict | list:
    """Any topic: dates → a typed date card; percentages/numbers → data graphics; otherwise a real video clip
    (every other line) or photo of what the line is about, each with the drawn/text shot as fallback."""
    numeric = words_to_digits(beat)
    d = DATE.search(numeric)
    if d:
        place = _entities(DATE.sub("", beat))
        stamp = {"remotion": "DateStamp", "props": {"date": d.group(1).upper(), "at": 0.2,
                                                    **({"place": place[0]} if place else {})}}
        rest = _general_beat_visual(DATE.sub("", numeric), n + 1, topic, drawn, topic_q)
        return [stamp, rest if isinstance(rest, dict) else rest[-1]]
    m = next((x for x in NUMBER.finditer(numeric)
              if not re.match(r"\s*(?:later|ago|after|before|earlier|on|afterwards)\b", numeric[x.end():], re.I)), None)
    figure = None
    if m:
        val = _num(m.group(1))
        if m.group(2).lower() in ("%", "percent") and val <= 100:
            figure = {"remotion": "DotGrid", "props": {"value": f"{val:g}%", "label": _clause_with(beat, m.group(2))[:60],
                                                       "count": 100, "highlight": int(val)}}
        else:
            cue = _spoken(beat, m.group(1))
            figure = {"remotion": "Counter", "props": {**_counter_value(val, numeric[:m.start()]), "label": m.group(2),
                                                       "countAt": cue, **_figure_heading(beat, cue)}}
        if not _entities(beat) and not _key_nouns(beat):
            return figure
    qs = _queries(beat, topic, topic_q)
    if figure and qs:
        # the line names a thing AND a figure: show the thing, then the number as it is said (or the other way round
        # when the number comes first), each for half the line
        # the counter first only when the number opens the line; otherwise it follows the shot, so it never sits
        # empty waiting for its number (a cue already passed simply shows the count under way)
        early = m.start() < len(numeric) * 0.15
        q = "|".join(qs)
        shot = {"stock": q, "fallback_visual": _photo(q, drawn, n=n)} if n % 2 == 0 else _photo(q, drawn, n=n)
        return [figure, shot] if early else [shot, figure]
    if figure:
        return figure
    if not qs:
        return drawn
    query = "|".join(qs)
    if n % 2 == 0:   # a real video clip, else a checked photo, else the drawn/text shot
        shot = {"stock": query, "fallback_visual": _photo(query, drawn, n=n)}
    else:
        shot = _photo(query, drawn, layout="print" if n % 4 == 1 else "full", n=n)
    # a short, punchy sentence ("It glowed blue in the dark.") lands as words on screen, so the video is not a
    # stock montage; on two lines in three that have one, and only when the line has more to show around it
    sents = [x.strip() for x in re.split(r"(?<=[.!?])\s+", beat) if x.strip()]
    punchy = [x for x in sents if 2 <= len(x.split()) <= 6 and not x.endswith("?")]
    if punchy and len(sents) > 1 and n % 3 != 2:
        line = punchy[0].rstrip(".!")
        card = {"remotion": "Statement", "props": {"line1": line, "at": 0.1}}
        return [card, shot] if sents[0] == punchy[0] else [shot, card]
    return shot


def _doc_visual(beat: str, n: int) -> dict:
    m = NUMBER.search(beat)
    if m:
        return {"remotion": "Counter", "props": {**_counter_value(_num(m.group(1)), beat[:m.start()]), "label": m.group(2),
                                                 "countAt": _spoken(beat, m.group(1))}}
    if n % 4 == 0:
        return {"remotion": "Statement", "props": {"line1": " ".join(beat.split()[:4]), "line2": " ".join(beat.split()[4:8])}}
    return {"remotion": "KineticText", "props": {}}


def _ocean_visual(beat: str, main: str, n: int, creature: str) -> dict:
    cue = _first_word(beat)
    sentences = [x.strip() for x in re.split(r"(?<=[.!?])\s+", beat) if x.strip()]
    punchy = [x for x in sentences if len(x.split()) <= 5]
    numeric = words_to_digits(beat)
    m = DEPTH.search(numeric)
    if m:
        val = _num(m.group(1) or m.group(5))
        return {"remotion": "OceanScene", "props": {
            "depth": 0.2, "depthTo": min(1.0, 0.3 + val / 1500), "depthMeter": {"from": 0, "to": val, "max": max(val * 1.1, 100), "unit": "m"},
            "actors": [{"creature": "diver", "x": 0.42, "y": 0.3, "to": [0.45, 0.55], "scale": 0.5, "rotate": 30}]}}
    m = DB.search(numeric)
    if m:
        return {"remotion": "Meter", "props": {"title": "How loud?", "to": _num(m.group(1)), "unit": "dB", "countAt": "decibels" if "decibel" in beat.lower() else _spoken(beat, m.group(1))}}
    if punchy and not beat.strip().endswith("?"):
        # a short punchy line becomes a big reveal word over the creature
        line = punchy[-1]
        return {"remotion": "OceanScene", "props": {
            "depth": 0.85, "actors": [{"creature": creature, "x": 0.45, "y": 0.55, "to": [0.5, 0.55], "scale": 1.3}],
            "bigText": line.upper().rstrip("!") if len(line) <= 22 else " ".join(line.split()[-2:]).upper(),
            "bigAt": _first_word(line), "bigColor": "#e5372f" if DANGER.search(line) else "#e6edf2"}}
    if n % 5 == 0:  # real B-roll every fifth beat
        name = {"spermWhale": "sperm whale", "giantSquid": "squid", "fishSchool": "fish school", "anglerfish": "deep sea fish"}.get(creature, creature)
        props = {"footage": f"stock:{name} underwater",
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


def plan(script: str, style: str, title: str | None, director: str = "rules", model: str | None = None,
         fmt: str = "video") -> str:
    if style not in STYLES:
        raise YtautoError(f"Unknown style {style!r} (use {', '.join(STYLES)})")
    log("Planning scenes with the built-in director (free, offline)")
    return plan_with_rules(script, style, title, fmt)


def auto_style(script: str, title: str | None = None) -> str:
    """Pick the look from the topic: an animal → nature (real photos, 3D close-ups); anything else (history, science,
    space, places, what-if scenarios) → documentary (maps, globes, counters, timelines)."""
    blocks = [b.strip() for b in re.split(r"\n\s*\n", script.strip()) if b.strip()]
    title = title or (blocks[0].lstrip("#").strip() if blocks and blocks[0].startswith("#") else "")
    subject = find_subject(script, title)
    if re.search(r"^\s*subject\s*:", script, re.I | re.M) or _creature(subject) or _creature(title):
        return "nature"
    # an animal-like name alone is not enough ("telescope" is also a sea snail): the script itself must read like
    # it is about a living creature
    bio = len(re.findall(r"\b(eat|eats|eating|ate|hunt\w*|prey|predator\w*|species|habitat|breed\w*|mat(e|es|ing)|"
                         r"nest\w*|pups?|cubs?|chicks?|calves|young|feed\w*|swim\w*|fly|flies|wings?|fur|feathers?|"
                         r"scales|teeth|claws?|wild|animal\w*|mammal\w*|bird\w*|fish|reptile\w*|insect\w*|venom\w*)\b",
                         script, re.I))
    if bio < 3:
        return "documentary"
    try:  # is the subject a living species? (iNaturalist knows every named animal)
        from .stock import _inat_taxon
        tx, _ = _inat_taxon(subject)
        if tx and tx.get("iconic_taxon_name") in ("Animalia", "Mammalia", "Aves", "Reptilia", "Amphibia", "Actinopterygii",
                                                  "Mollusca", "Arachnida", "Insecta"):
            return "nature"
    except Exception:  # noqa: BLE001 — offline: fall through
        pass
    return "documentary"


def write_plan(script_path: Path, out_dir: Path, style: str, title: str | None, director: str = "rules", model: str | None = None,
               fmt: str = "video") -> Path:
    raw = script_path.read_text(encoding="utf-8")
    if style == "auto":
        style = auto_style(raw, title)
        log(f"Style: {style} (picked from the topic; use --style to choose)")
    text = plan(raw, style, title, director, model, fmt)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "assets").mkdir(exist_ok=True)
    out = out_dir / "script.yaml"
    out.write_text(text if text.endswith("\n") else text + "\n", encoding="utf-8")
    # validate with the real loader so problems surface before rendering
    from .config import load_project
    load_project(out_dir)
    log(f"Plan written → {out}")
    return out

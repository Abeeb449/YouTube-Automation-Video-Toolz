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
DATE = re.compile(r"\b(?:in|by|since|until|during|on|around|about|circa|from)\s+((?:(?:January|February|March|April|May|June|"
                  r"July|August|September|October|November|December)\s+(?:\d{1,2},?\s+)?)?(?:(?:1[0-9]\d\d|20\d\d)s?|\d{1,4}\s?(?:BC|BCE|AD|CE)))\b", re.I)
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
            stem = re.sub(r"(?<!s)s$", "", phrase)
            c = len(re.findall(r"\b" + re.escape(stem), body)) * (1 + 0.6 * (n - 1))
            if c > score:
                best, score = stem, c
    return best or "wildlife"


def _opening(blocks: list[str]) -> str:
    """The script's first two sentences, as a starting point for the YouTube description."""
    text = " ".join(b for b in blocks if not b.startswith("#"))
    text = re.sub(r"\[[^\]]*\]", " ", text)
    sents = re.split(r"(?<=[.!?])\s+", re.sub(r"\s+", " ", text).strip())
    return " ".join(sents[:2])[:300]


def _tags(title: str, subject: str) -> list[str]:
    words = [w for w in re.findall(r"[a-z][a-z'-]+", title.lower())
             if w not in _STOPW and len(w) > 3 and w not in {"were", "built", "made", "became", "happened", "does", "nothing",
                                                          "never", "every", "really", "inside", "about"}]
    out = list(dict.fromkeys([subject] + words + ["documentary"]))
    return [t for t in out if t][:12]


def plan_with_rules(script: str, style: str, title: str | None) -> str:
    blocks = [b.strip() for b in re.split(r"\n\s*\n", script.strip()) if b.strip()
              and not re.match(r"^\s*subject\s*:", b, re.I)]
    title = title or (blocks[0].lstrip("#").strip()[:70] if blocks and blocks[0].startswith("#") else "Untitled Documentary")
    subject = find_subject(script, title)
    main = _creature(subject, None) or _creature(script, "giantSquid" if style == "ocean" else "fishSchool")
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
            # music mood and sound effects are left to the sound director (ytauto/sound_director.py), which reads
            # every scene's words and emotion at render time; write mood:/sfx: by hand only to override it
            sc["text"] = beat
            vis = _rule_visual(beat, style, main, n, subject)
            sc["visuals" if isinstance(vis, list) else "visual"] = vis
            scenes.append(sc)
    data = {
        "preset": style, "title": title,
        # from the creator's own words: the script's opening lines (edit before upload; add your sources)
        "description": _opening(blocks),
        "tags": _tags(title, subject if style in ("nature", "ocean") else ""),
        "thumbnail": {"text": title.upper()[:40]}, "youtube": {"privacy": "private"},
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
        rest = _general_visual(DATE.sub("", beat), style, main, n + 1, subject, drawn) or drawn
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


def _rule_visual(beat: str, style: str, main: str, n: int, subject: str = "") -> dict | list:
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
                return {"remotion": "Counter", "props": {"to": val, "label": m.group(2), "countAt": m.group(1).split(",")[0]}}
            sents = [x for x in re.split(r"(?<=[.!?])\s+", beat) if x.strip()]
            if any(len(x.split()) <= 5 for x in sents) and n % 2 == 0:
                line = [x for x in sents if len(x.split()) <= 5][-1].rstrip(".!")
                return {"remotion": "Statement", "props": {"line1": line}}
        else:
            drawn = _ocean_visual(beat, main, n, creature)
        g = _general_visual(beat, style, main, n, subject or main, drawn)
        if g is not None:
            return g
        return drawn
    if style == "ocean":
        return _ocean_visual(beat, main, n, creature)
    return _general_beat_visual(beat, n, subject, _doc_visual(beat, n))


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
yet your around almost exactly enough inside outside still almost across against another""".split())
_ENTITY_SKIP = {"The", "It", "In", "On", "At", "For", "But", "And", "Then", "Today", "This", "That", "These", "Those",
                "There", "Here", "Nobody", "No", "One", "Every", "Each", "When", "While", "After", "Before", "If",
                "Archaeologists", "Scientists", "Researchers", "Historians", "Experts", "We", "You", "They", "He",
                "She", "His", "Her", "Its", "Their", "A", "An", "As", "By", "From", "With", "Some", "Most", "Many",
                "BC", "BCE", "AD", "CE", "January", "February", "March", "April", "May", "June", "July", "August",
                "September", "October", "November", "December", "Monday", "Tuesday", "Wednesday", "Thursday",
                "Friday", "Saturday", "Sunday"}


_NUMWORDS = set("""one two three four five six seven eight nine ten eleven twelve twenty thirty forty fifty sixty
seventy eighty ninety hundred hundreds thousand thousands million millions billion billions dozen dozens half
quarter percent""".split())
_PEOPLE = set("""people person archaeologists scientists researchers historians experts someone everyone anyone
nobody man men woman women""".split())
_ADJ = set("""oldest largest biggest smallest greatest longest highest tallest deepest first last only entire whole
ancient old new great big small huge tiny vast giant early late modern famous same other own single main final
best worst true real wet dry dark bright heavy light hidden lost secret strange""".split())


def _entities(beat: str) -> list[str]:
    """Named things in the line: 'Great Pyramid of Giza', 'Khufu', 'Nile' (capitalised runs, joined by of/the/de).
    A single capitalised word at the start of a sentence is just a sentence start ('Teams', 'Wet'), not a name."""
    text = re.sub(r"\[[^\]]*\]", " ", beat)
    out = []
    for m in re.finditer(r"\b([A-Z][\w'-]+(?:\s+(?:of|the|de|del|da|von|van|al|el|and)?\s*[A-Z][\w'-]+)*)", text):
        before = text[:m.start()].rstrip()
        sentence_start = not before or before[-1] in ".!?:;\"“"
        if sentence_start and len(m.group(1).split()) == 1:
            continue
        words = m.group(1).split()
        while words and words[0] in _ENTITY_SKIP:
            words = words[1:]
        while words and words[-1].lower() in ("of", "the", "de", "and"):
            words = words[:-1]
        ent = " ".join(words)
        if ent and len(ent) > 2 and ent not in out:
            out.append(ent)
    return sorted(out, key=lambda e: -len(e.split()))


def _key_nouns(beat: str) -> list[str]:
    """The things the line points at: heads of noun phrases ('the oldest papyrus', 'the sledges', 'their
    bakeries'), skipping numbers, people-words and adjectives."""
    text = re.sub(r"\[[^\]]*\]", " ", beat).lower()
    def ok(w: str) -> bool:
        return (len(w) > 3 and w not in _COMMON and w not in _STOPW and w not in _NUMWORDS and w not in _PEOPLE
                and w not in _ADJ and not w.endswith(("ly", "ing")) and not w.isdigit())
    heads = []
    for m in re.finditer(r"\b(?:the|a|an|their|its|his|her|this|these|those|our|of)\s+((?:[a-z'-]+\s+){0,3})", text):
        for w in m.group(1).split():
            if w in _ADJ or w in _NUMWORDS or w in ("the", "a", "an", "their", "its", "his", "her", "this", "these",
                                                      "those", "our", "front", "side", "middle", "top", "bottom", "kind", "sort", "part"):
                continue
            if ok(w):
                heads.append(w)
            break
    return list(dict.fromkeys(heads))[:3]


def _queries(beat: str, topic: str) -> list[str]:
    """Search alternatives for this line, most specific first, ending with the video's topic itself."""
    q = list(_entities(beat)[:2])
    topic_words = set(topic.lower().split())
    for n in _key_nouns(beat)[:2]:
        q.append(n if n.rstrip("s") in {t.rstrip("s") for t in topic_words} else f"{n} {topic}".strip())
    if topic:
        q.append(topic)
    return list(dict.fromkeys(x for x in q if x))[:5]


def _general_beat_visual(beat: str, n: int, topic: str, drawn: dict) -> dict | list:
    """Any topic: dates → a typed date card; percentages/numbers → data graphics; otherwise a real video clip
    (every other line) or photo of what the line is about, each with the drawn/text shot as fallback."""
    numeric = words_to_digits(beat)
    d = DATE.search(numeric)
    if d:
        place = _entities(DATE.sub("", beat))
        stamp = {"remotion": "DateStamp", "props": {"date": d.group(1).upper(), "at": 0.2,
                                                    **({"place": place[0]} if place else {})}}
        rest = _general_beat_visual(DATE.sub("", beat), n + 1, topic, drawn)
        return [stamp, rest if isinstance(rest, dict) else rest[-1]]
    m = NUMBER.search(numeric)
    if m and not _entities(beat):
        val = _num(m.group(1))
        if m.group(2).lower() in ("%", "percent") and val <= 100:
            return {"remotion": "DotGrid", "props": {"value": f"{val:g}%", "label": _clause_with(beat, m.group(2))[:60],
                                                     "count": 100, "highlight": int(val)}}
        return {"remotion": "Counter", "props": {"to": val, "label": m.group(2), "countAt": m.group(1).split(",")[0]}}
    qs = _queries(beat, topic)
    if not qs:
        return drawn
    query = "|".join(qs)
    if n % 2 == 0:   # a real video clip, else a checked photo, else the drawn/text shot
        return {"stock": query, "fallback_visual": _photo(query, drawn, n=n)}
    return _photo(query, drawn, layout="print" if n % 4 == 1 else "full", n=n)


def _doc_visual(beat: str, n: int) -> dict:
    m = NUMBER.search(beat)
    if m:
        return {"remotion": "Counter", "props": {"to": _num(m.group(1)), "label": m.group(2), "countAt": m.group(1).split(",")[0]}}
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


def plan(script: str, style: str, title: str | None, director: str = "rules", model: str | None = None) -> str:
    if style not in STYLES:
        raise YtautoError(f"Unknown style {style!r} (use {', '.join(STYLES)})")
    log("Planning scenes with the built-in director (free, offline)")
    return plan_with_rules(script, style, title)


def auto_style(script: str, title: str | None = None) -> str:
    """Pick the look from the topic: an animal → nature (real photos, 3D close-ups); anything else (history, science,
    space, places, what-if scenarios) → documentary (maps, globes, counters, timelines)."""
    blocks = [b.strip() for b in re.split(r"\n\s*\n", script.strip()) if b.strip()]
    title = title or (blocks[0].lstrip("#").strip() if blocks and blocks[0].startswith("#") else "")
    subject = find_subject(script, title)
    if re.search(r"^\s*subject\s*:", script, re.I | re.M) or _creature(subject) or _creature(title):
        return "nature"
    try:  # is the subject a living species? (iNaturalist knows every named animal)
        from .stock import _inat_taxon
        tx, _ = _inat_taxon(subject)
        if tx and tx.get("iconic_taxon_name") in ("Animalia", "Mammalia", "Aves", "Reptilia", "Amphibia", "Actinopterygii",
                                                  "Mollusca", "Arachnida", "Insecta"):
            return "nature"
    except Exception:  # noqa: BLE001 — offline: fall through
        pass
    return "documentary"


def write_plan(script_path: Path, out_dir: Path, style: str, title: str | None, director: str = "rules", model: str | None = None) -> Path:
    raw = script_path.read_text(encoding="utf-8")
    if style == "auto":
        style = auto_style(raw, title)
        log(f"Style: {style} (picked from the topic; use --style to choose)")
    text = plan(raw, style, title, director, model)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "assets").mkdir(exist_ok=True)
    out = out_dir / "script.yaml"
    out.write_text(text if text.endswith("\n") else text + "\n", encoding="utf-8")
    # validate with the real loader so problems surface before rendering
    from .config import load_project
    load_project(out_dir)
    log(f"Plan written → {out}")
    return out

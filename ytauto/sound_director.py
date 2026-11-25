"""Sound director: music mood and sound effects decided from what each script actually says, for any topic.

Nothing here is a template. For every scene it reads the narration and its [tone …] directions and decides:

  mood     the emotion of the passage (danger, tension, mystery, wonder, epic, calm), smoothed so the music
           doesn't flip between scenes; it drives which music plays (ytauto/music_library.py)
  effects  soft accents at the exact word that calls for one (an impact on "crashed", a rise before
           "suddenly", a swell on a reveal, ticks on a date, typing on "records"), only when the line is
           intense enough, never in quiet passages, within a budget (at most one per 8 s, the same effect at
           most once per 45 s)
  cuts     a transition sound between chapters only when the mood or energy actually changes

Anything written by hand in script.yaml wins: a scene's own `mood:` or `sfx:` is kept as it is.
Turn it off with settings.sound.director: false.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# ---------------------------------------------------------------------------------------------- vocabulary
# General words, not tied to one subject: the same director scores a war, a volcano, a heist or a predator.
MOOD_WORDS = {
    "danger": r"kill|killed|killing|deadly|death|died|die|dies|dying|attack|attacks|prey|predator|venom|poison|bite|"
              r"blood|war|battle|bomb|explosion|explode|disaster|catastroph\w*|destroy\w*|massacre|violent|weapon|"
              r"threat|lethal|fatal|crush\w*|devour\w*|hunt|hunts|hunting|eruption|erupt\w*|collapse\w*|drown\w*",
    "tension": r"suddenly|waiting|waits|wait|watch|watching|edge|warning|countdown|seconds|dead ahead|"
               r"approach\w*|closer|hesitat\w*|risk|trap|hidden|hiding|nervous|afraid|fear|feared|tense|"
               r"chase|escape|panic|alarm|stalk\w*|ambush|before it was too late",
    "mystery": r"mystery|mysterious|unknown|unexplained|secret|secrets|strange|vanish\w*|disappear\w*|no one knows|"
               r"nobody knows|hidden|dark|darkness|deep|abyss|shadow\w*|puzzle|riddle|ancient|lost|legend",
    "wonder": r"incredible|amazing|astonishing|beautiful|remarkable|extraordinary|largest|biggest|longest|record|"
              r"discover\w*|marvel|vast|billions|galaxy|stars|glow\w*|light|miracle|wonder|breathtaking|unique",
    "epic": r"empire|armies|army|triumph|victory|conquer\w*|rise|rose|legendary|greatest|history|historic|"
            r"launch\w*|revolution|kingdom|mighty|titan\w*|colossal|thunder\w*",
    "calm": r"peace|peaceful|quiet|calm|gentle|rest|resting|sleep\w*|home|family|together|safe|warm|soft|slowly|"
            r"breathe|hope|recover\w*|heal\w*|grief|loss|lonely|alone|remember",
}
TONE_MOOD = [  # [tone …] directions written in the script
    (r"tense|suspense|urgent|alarm|ominous|menac", "tension"),
    (r"grave|dark|grim|danger|threat|brutal", "danger"),
    (r"hushed|whisper|myster|eerie|secret", "mystery"),
    (r"awe|amazed|wonder|marvel|fascinat|excited", "wonder"),
    (r"epic|triumph|grand|heroic|rousing", "epic"),
    (r"tender|gentle|calm|warm|sad|somber|sombre|reflective|soft", "calm"),
]
# word → effect, with the minimum intensity needed and where to place it relative to the word
CUES = [
    (r"crash\w*|slam\w*|struck|strikes?|smash\w*|collid\w*|impact|explo\w*|blast|shatter\w*|snap\w*|bites?|crush\w*",
     "hit", 0.15, 0.0),
    (r"suddenly|without warning|in an instant|in a flash|lunges?|bursts?|erupts?|strikes? from below|fast\b",
     "riser", 0.1, -1.4),
    (r"falls?|fell|drops?|plunges?|dives?|sinks?|swoops?|rushes?|races?|speeds?|flies|thrown",
     "whoosh", 0.12, -0.2),
    (r"discovered|revealed|reveal|the answer|this is (the|why|how)|it turns out|for the first time|finally",
     "swell", 0.0, -0.6),
    (r"thud|heavy|massive|giant|tonnes?|thunder\w*|rumbl\w*|quake|tremor",
     "thud", 0.2, 0.0),
    (r"records|data|files|documents|computer|database|signal|coordinates|transmission|scientists? (found|recorded)",
     "typing", 0.0, 0.0),
    (r"alarm|siren|alert|emergency", "alarm", 0.3, 0.0),
]
QUIET = re.compile(r"\b(silent|silence|quiet|still|stillness|whisper\w*|hush\w*|peaceful|asleep)\b", re.I)
YEAR = re.compile(r"\b(1[5-9]\d\d|20\d\d)\b|\b(nineteen|eighteen|seventeen|two thousand|twenty) [a-z\- ]*\b", re.I)
INTENSIFIERS = re.compile(r"\b(never|nothing|only|most|every|all|always|terrifying|brutal|instantly|massive|"
                          r"enormous|deadliest|worst|first|last|ever)\b", re.I)

FX_GAP = 8.0           # seconds between any two effects
SAME_FX_GAP = 45.0     # seconds between two of the same effect
FX_VOLUME = {"hit": 0.45, "thud": 0.4, "riser": 0.3, "whoosh": 0.28, "swell": 0.3, "typing": 0.25, "ticks": 0.25,
             "alarm": 0.18}


@dataclass
class SceneSound:
    mood: str | None
    intensity: float
    quiet: bool
    cues: list[tuple[str, str, float]]   # (effect, cue word, offset seconds relative to the word)


def _tags(text: str) -> list[str]:
    return [t.lower() for t in re.findall(r"\[tone ([^\]]+)\]", text, re.I)]


def analyse(text: str) -> SceneSound:
    """Mood, intensity and candidate effects for one scene's narration (tags included)."""
    plain = re.sub(r"\[[^\]]*\]", " ", text)
    low = plain.lower()
    scores = {m: len(re.findall(rf"\b(?:{pat})\b", low)) for m, pat in MOOD_WORDS.items()}
    for tag in _tags(text):
        for pat, m in TONE_MOOD:
            if re.search(pat, tag):
                scores[m] = scores.get(m, 0) + 2      # the writer's own direction counts double
    best = max(scores, key=lambda m: scores[m])
    mood = best if scores[best] > 0 else None
    words = max(1, len(plain.split()))
    sentences = [s for s in re.split(r"(?<=[.!?])\s+", plain.strip()) if s]
    short = sum(1 for s in sentences if len(s.split()) <= 4)
    intensity = min(1.0, 0.15 * len(INTENSIFIERS.findall(plain)) + 0.18 * short + 0.25 * plain.count("!")
                    + 0.12 * (scores.get("danger", 0) + scores.get("tension", 0)) + (40 - min(40, words)) / 160)
    quiet = bool(QUIET.search(plain)) and scores.get("danger", 0) == 0
    if quiet and mood in (None, "tension"):
        mood = "calm"
    cues: list[tuple[str, str, float]] = []
    if not quiet:
        for pat, fx, need, offset in CUES:
            m = re.search(rf"\b({pat})", plain, re.I)
            if m and intensity >= need:
                cues.append((fx, m.group(1).split()[0], offset))
        y = YEAR.search(plain)
        if y:
            cues.append(("ticks", y.group(0).split()[0], -0.2))
    return SceneSound(mood, intensity, quiet, cues)


def direct(texts: list[str], chapters: list[str | None], given_moods: list[str | None],
           given_sfx: list[bool], durations: list[float] | None = None) -> tuple[list[str | None], list[list[dict]], list[bool]]:
    """For a whole script: (mood per scene, sfx per scene, transition-sound per scene start).
    Scenes with a hand-written mood/sfx keep theirs. Times are word cues, resolved at render."""
    info = [analyse(t) for t in texts]
    # 1) moods: the scene's own words; a scene with no clear emotion keeps the current mood, and a one-scene
    #    blip that returns straight to the current mood is ignored (the music shouldn't flip back and forth)
    raw = [i.mood for i in info]
    eff: list[str] = []
    cur = None
    for k in range(len(info)):
        if given_moods[k]:
            cur = given_moods[k]
        elif raw[k] and raw[k] != cur:
            nxt = next((m for m in raw[k + 1:] if m), None)
            if cur is None or nxt != cur:
                cur = raw[k]
        eff.append(cur or "calm")
    moods: list[str | None] = [eff[k] if (k == 0 or eff[k] != eff[k - 1] or given_moods[k]) else None
                               for k in range(len(eff))]
    # 2) effects, within the budget
    sfx: list[list[dict]] = []
    last_any, last_fx = -1e9, {}
    t = 0.0
    for k, i in enumerate(info):
        here: list[dict] = []
        if not given_sfx[k]:
            for fx, word, off in i.cues:
                if t - last_any < FX_GAP or t - last_fx.get(fx, -1e9) < SAME_FX_GAP:
                    continue
                here.append({"sound": fx, "at": word, "volume": FX_VOLUME.get(fx, 0.3), "offset": off,
                             **({"dur": 3} if fx == "ticks" else {})})
                last_any, last_fx[fx] = t, t
                break            # one accent per scene at most
        sfx.append(here)
        t += durations[k] if durations else max(3.0, len(re.sub(r"\[[^\]]*\]", " ", texts[k]).split()) / 2.5)
    # 3) transitions: only where a new chapter also changes the mood or the energy jumps
    trans = [False] * len(texts)
    for k in range(1, len(texts)):
        if chapters[k] and not info[k].quiet and (eff[k] != eff[k - 1] or abs(info[k].intensity - info[k - 1].intensity) > 0.35):
            trans[k] = True
    return moods, sfx, trans

"""Sound director: music mood and sound effects decided from what each script actually says, for any topic.

Nothing here is a template. For every scene it reads the narration and its [tone …] directions and decides:

  mood     the emotion of the passage (danger, tension, mystery, wonder, epic, calm), smoothed so the music
           doesn't flip between scenes; it drives which music plays (ytauto/music_library.py)
  effects  soft accents at the exact word that calls for one (a low impact on "crashed", a deep thud on
           "massive", ticks on a date, typing on "records"), only when the line is intense enough, never in
           quiet passages, within a budget (at most one per 8 s, the same effect at most once per 45 s)

Never any transition-style sound: no whoosh, swell, riser or glitch, not between chapters, not on a reveal, not
at the opening (ytauto/sound.py TRANSITION). The music carries every change of scene on its own.

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
              r"threat|lethal|fatal|crushed to death|devour\w*|hunt|hunts|hunting|eruption|erupt\w*|collapse\w*|drown\w*",
    "tension": r"suddenly|waiting|waits|wait|watch|watching|edge|warning|countdown|seconds|dead ahead|"
               r"approach\w*|closer|hesitat\w*|risk|trap|hiding|nervous|afraid|fear|feared|tense|"
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
    (r"thud|heavy|massive|giant|tonnes?|thunder\w*|rumbl\w*|quake|tremor",
     "thud", 0.2, 0.0),
    (r"records|data|files|documents|computer|database|signal|coordinates|transmission|scientists? (found|recorded)",
     "typing", 0.0, 0.0),
    # a literal alarm only: "the alarm sounded", "sirens" (never "alarming", "alert to", "an emergency")
    (r"alarms?\b(?= (?:sound\w*|rang|rings?|went off|blar\w*|wail\w*|bells?))|sirens?\b|klaxons?\b", "alarm", 0.3, 0.0),
]
QUIET = re.compile(r"\b(silent|silence|quiet|stillness|whisper\w*|hush\w*|peaceful|asleep)\b", re.I)
YEAR = re.compile(r"\b(1[5-9]\d\d|20\d\d)\b|\b(nineteen|eighteen|seventeen|two thousand|twenty) [a-z\- ]*\b", re.I)
INTENSIFIERS = re.compile(r"\b(never|nothing|only|most|every|all|always|terrifying|brutal|instantly|massive|"
                          r"enormous|deadliest|worst|first|last|ever)\b", re.I)

FX_GAP = 8.0           # seconds between any two effects
SAME_FX_GAP = 45.0     # seconds between two of the same effect
FX_VOLUME = {"hit": 0.45, "thud": 0.4, "typing": 0.25, "ticks": 0.25,
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
            m = re.search(rf"\b({pat})\b", plain, re.I)   # whole words: "heavy", not "heavily"; "data", not "database"
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
    # 3) no transition sounds between chapters (kept in the return value for older callers: always False)
    trans = [False] * len(texts)
    return moods, sfx, trans


# ---------------------------------------------------------------------------------------------- narration
# How the narrator should sound, decided from the content (never a fixed house tone).
OVERALL = {
    "danger": "measured and serious, letting tension build where the story builds it",
    "tension": "controlled and suspenseful, unhurried, holding back where the story holds back",
    "mystery": "low, intimate and curious, unhurried",
    "wonder": "warm and curious, with a sense of discovery where the story reveals something",
    "epic": "confident and resonant, with gravitas",
    "calm": "gentle, warm and unhurried",
}
SCENE_TONE = {
    "danger": "grave and controlled",
    "tension": "quieter and tense, a little slower",
    "mystery": "hushed and curious",
    "wonder": "awed and warm",
    "epic": "strong and confident",
    "calm": "soft and gentle",
}


def narration_style(texts: list[str]) -> str:
    """The narrator's overall direction for THIS script: from the balance of emotions across its scenes and how
    much of it is facts and numbers. Used when the project doesn't set its own `voice.instruct`."""
    info = [analyse(t) for t in texts]
    counts: dict[str, float] = {}
    gravity = {"danger": 1.6, "tension": 1.4}   # a grave or tense story is grave overall even with lighter moments
    for i in info:
        if i.mood:
            counts[i.mood] = counts.get(i.mood, 0) + (1 + i.intensity) * gravity.get(i.mood, 1.0)
    total = sum(counts.values()) or 1
    ranked = sorted(counts.items(), key=lambda kv: -kv[1])
    serious = counts.get("danger", 0) + counts.get("tension", 0)
    if ranked and ranked[0][0] not in ("danger", "tension") and serious >= ranked[0][1]:
        # danger and tension together are the story's main thread: lead with the stronger of the two
        lead = "danger" if counts.get("danger", 0) >= counts.get("tension", 0) else "tension"
        ranked = [(lead, serious)] + [kv for kv in ranked if kv[0] not in ("danger", "tension")]
    parts = []
    if ranked and ranked[0][1] / total >= 0.35:
        parts.append(OVERALL[ranked[0][0]])
        if len(ranked) > 1 and ranked[1][1] / total >= 0.25:
            parts.append(f"turning {SCENE_TONE[ranked[1][0]]} where the story does")
    else:
        parts.append("clear and engaging, letting each passage's own emotion come through")
    plain = " ".join(re.sub(r"\[[^\]]*\]", " ", t) for t in texts)
    facts = len(re.findall(r"\b\d[\d,.]*\b|\b(percent|million|billion)\b", plain, re.I))
    if facts / max(1, len(plain.split())) > 0.04:
        parts.append("precise and clear on facts and numbers")
    return "Narrate as a documentary narrator: " + "; ".join(parts) + "."


def scene_tones(texts: list[str], given: list[bool]) -> list[str | None]:
    """Per-scene delivery that follows each scene's own emotion (None = no change). `given`: the scene already
    has the writer's own [tone …] direction, which wins."""
    out: list[str | None] = []
    cur = None
    for t, g in zip(texts, given):
        i = analyse(t)
        cur = i.mood or cur          # a scene with no emotion words of its own carries the current one
        if g:
            out.append(None)
            continue
        tone = SCENE_TONE.get(cur or "")
        if tone and cur in ("danger", "tension") and i.intensity > 0.6:
            tone += ", with quiet urgency"
        out.append(tone)
    return out


# The default delivery: one even voice from the first word to the last. A narrator whose tone, pace and volume
# change with every scene's mood sounds as if it rises and falls; the picture and the music carry the mood instead.
# One mood for the whole video, read from the script. Each is a moderate, natural way of speaking: the mood colours
# the voice, it never turns into acting. The narrator's reference clip is recorded with it and every line follows.
STEADY_MOOD = {
    "danger": ("serious", "measured and serious"),
    "tension": ("suspenseful", "serious and quietly suspenseful"),
    "mystery": ("curious", "thoughtful and curious"),
    "wonder": ("warm", "warm and quietly fascinated"),
    "epic": ("confident", "confident and clear"),
    "calm": ("relaxed", "relaxed, warm and friendly"),
    None: ("clear", "clear, friendly and matter-of-fact"),
}


def steady_mood(texts: list[str]) -> tuple[str, str]:
    """(mood word, direction for the narrator) for a whole script: the emotion that carries most of its weight,
    spoken in a moderate, natural way and kept the same from the first line to the last."""
    info = [analyse(t) for t in texts]
    counts: dict[str, float] = {}
    gravity = {"danger": 1.6, "tension": 1.4}
    for i in info:
        if i.mood:
            counts[i.mood] = counts.get(i.mood, 0) + (1 + i.intensity) * gravity.get(i.mood, 1.0)
    lead = max(counts, key=counts.get) if counts else None
    felt = sum(1 for i in info if i.mood) / max(1, len(info))
    if lead is None or felt < 0.08:          # almost all facts: a clear, plain read
        lead = None
    word, how = STEADY_MOOD[lead]
    return word, (f"Narrate as a calm, steady documentary narrator, {how}. A natural talking voice at a moderate "
                  f"pace. Keep the same even pitch and the same volume from the first word to the last, with no "
                  f"sudden emphasis.")


STEADY = ("Narrate as a calm, steady documentary narrator. Keep the same even pace, the same pitch and the same "
          "volume from the first word to the last, with no sudden emphasis.")


def direct_narration(project) -> None:
    """Set the narrator's direction before the voice is recorded. `voice.delivery`:
      steady      (default) one even direction for the whole video, no per-scene changes of tone;
      expressive  the overall style from the content (unless the project sets voice.instruct itself) and a
                  per-scene tone (unless a scene has its own [tone …] or voice tone)."""
    st = project.settings
    snd = st.get("sound") or {}
    voice = st.get("voice") or {}
    if snd.get("director", True) is False or voice.get("follow_content") is False:
        return
    if str(voice.get("delivery", "steady")).lower() != "expressive":
        if not voice.get("instruct") or str(voice.get("instruct")).strip().lower() == "auto":
            # the mood comes from this script's own content; it is then held for the whole video
            voice["mood"], voice["instruct"] = steady_mood([s.text or "" for s in project.scenes])
        voice["delivery"] = "steady"
        st["voice"] = voice
        return
    texts = [s.text or "" for s in project.scenes]
    if not voice.get("instruct") or str(voice.get("instruct")).strip().lower() == "auto":
        voice["instruct"] = narration_style(texts)
        st["voice"] = voice
    given = [bool(re.search(r"\[tone ", s.text or "", re.I)) or bool((s.voice or {}).get("tone")) for s in project.scenes]
    for s, tone in zip(project.scenes, scene_tones(texts, given)):
        if tone:
            s.voice = {**(s.voice or {}), "tone": tone}

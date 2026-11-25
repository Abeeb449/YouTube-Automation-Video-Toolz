"""Resolve word cues to seconds so graphics land on the narrator's words.

Any prop named `at` or ending in `At` (e.g. `calloutAt`, `statsAt`) can be:
  - a number            seconds from the start of the clip
  - "word"              when the narrator says that word (first match in the scene)
  - "two words"         a phrase
  - "word#2"            the 2nd time that word is said
  - "word+0.5" / "word-0.3"   offset in seconds
"""
from __future__ import annotations

import re
from typing import Any

from .utils import warn

_CUE_RE = re.compile(r"^(?P<phrase>.*?)(?:#(?P<nth>\d+))?(?P<off>[+-]\d+(?:\.\d+)?)?$")


def _norm(w: str) -> str:
    return re.sub(r"[^\w]", "", w.lower())


def find_word_time(cue: str, words: list) -> float | None:
    m = _CUE_RE.match(cue.strip())
    if not m:
        return None
    phrase = [_norm(x) for x in m.group("phrase").split() if _norm(x)]
    nth = int(m.group("nth") or 1)
    off = float(m.group("off") or 0)
    if not phrase:
        return None
    toks = [_norm(w.text) for w in words]
    hits = 0
    for i in range(len(toks) - len(phrase) + 1):
        if all(toks[i + j] == phrase[j] or (j == len(phrase) - 1 and toks[i + j].startswith(phrase[j])) for j in range(len(phrase))):
            hits += 1
            if hits == nth:
                return words[i].start + off
    # a spelled-out number cue ("twenty") when the transcript wrote it in digits ("20,000"): the first number said
    if len(phrase) == 1 and phrase[0] in _NUMBER_WORDS:
        digits = [i for i, t in enumerate(toks) if t[:1].isdigit()]
        if len(digits) >= nth:
            return words[digits[nth - 1]].start + off
    return None


_NUMBER_WORDS = set("""one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen
seventeen eighteen nineteen twenty thirty forty fifty sixty seventy eighty ninety hundred thousand million billion
half a""".split()) - {"a"}


def resolve_cues(obj: Any, words: list, clip_offset: float, clip_dur: float, where: str = "") -> Any:
    """Return a copy of `obj` with word cues replaced by seconds relative to the clip."""
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if (k == "at" or k.endswith("At")) and isinstance(v, str):
                t = find_word_time(v, words)
                if t is None:
                    warn(f"{where}: cue word {v!r} not found in the narration — showing it at the start")
                    out[k] = 0.3
                else:
                    out[k] = round(min(max(0.0, t - clip_offset), max(0.0, clip_dur - 0.3)), 3)
            else:
                out[k] = resolve_cues(v, words, clip_offset, clip_dur, where)
        return out
    if isinstance(obj, list):
        return [resolve_cues(v, words, clip_offset, clip_dur, where) for v in obj]
    return obj

"""Resolve word cues to seconds so graphics land on the narrator's words.

Any prop named `at` or `out`, or ending in `At` (e.g. `calloutAt`, `statsAt`), can be:
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


_ONES = ("zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen "
         "eighteen nineteen").split()
_TENS = "x x twenty thirty forty fifty sixty seventy eighty ninety".split()
_ORD = {"first": 1, "second": 2, "third": 3, "fifth": 5, "eighth": 8, "ninth": 9, "twelfth": 12, "twentieth": 20, "thirtieth": 30}
_SPELL = {"metres": "meters", "metre": "meter", "kilometres": "kilometers", "kilometre": "kilometer", "favourite": "favorite",
          "colour": "color", "grey": "gray", "centre": "center", "travelled": "traveled", "harbour": "harbor", "litres": "liters"}


def _number_words() -> dict[str, str]:
    out: dict[str, str] = {}
    for n in range(100):
        word = _ONES[n] if n < 20 else _TENS[n // 10] + (_ONES[n % 10] if n % 10 else "")
        out[word] = str(n)
        if n:                                           # ordinals: third, sixteenth, twentythird …
            last = _ONES[n] if n < 20 else (_ONES[n % 10] if n % 10 else _TENS[n // 10])
            head = "" if n < 20 or not n % 10 else _TENS[n // 10]
            o = next((k for k, v in _ORD.items() if (v == n % 10 and n > 20 and n % 10) or v == n), None)
            if n > 20 and n % 10:
                o = next((k for k, v in _ORD.items() if v == n % 10), None) or _ONES[n % 10] + "th"
            elif o is None:
                o = (last[:-1] + "ieth") if last.endswith("y") else last + "th"
            out[head + o] = str(n)
    out.update({"hundred": "100", "thousand": "1000", "hundredth": "100"})
    return out


_NUM = _number_words()


def _norm(w: str) -> str:
    """A word as it is compared: lower case, no punctuation; numbers and dates the same whether written out or in
    digits ("third", "3rd" and "3"; "twenty-third" and "23rd"), British and American spellings the same."""
    t = re.sub(r"[^\w]", "", w.lower())
    m = re.fullmatch(r"(\d+)(st|nd|rd|th)", t)
    if m:
        return m.group(1)
    return _NUM.get(t) or _SPELL.get(t, t)


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
    # a number that was heard differently from how it is written ("five and a half" heard as "5.5"): the first number said
    if len(phrase) == 1 and phrase[0].isdigit():
        digits = [i for i, t in enumerate(toks) if t[:1].isdigit()]
        if len(digits) >= nth:
            return words[digits[nth - 1]].start + off
    return None


_NUMBER_WORDS = set("""one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen
seventeen eighteen nineteen twenty thirty forty fifty sixty seventy eighty ninety hundred thousand million billion
half a""".split()) - {"a"}


NOT_CUES = {"lookAt"}       # props that end in "At" but name a thing, not a moment


def resolve_cues(obj: Any, words: list, clip_offset: float, clip_dur: float, where: str = "") -> Any:
    """Return a copy of `obj` with word cues replaced by seconds relative to the clip."""
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if (k in ("at", "out") or k.endswith("At")) and k not in NOT_CUES and isinstance(v, str):
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

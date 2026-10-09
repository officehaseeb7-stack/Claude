"""Unsafe-situation detection. Pure functions: the clock is passed in, never read."""
from __future__ import annotations

import re
from datetime import datetime

NOT_SAFE_PLACE = "not_safe_place"
CHILD_OR_PET = "child_or_pet"
EXTREME_WEATHER = "extreme_weather"
REMOTE_AREA = "remote_area"
NIGHT = "night"

# Night is 20:00 up to (not including) 06:00 on the clock passed to triage().
NIGHT_START_HOUR = 20
NIGHT_END_HOUR = 6

# Keyword lists are deliberately broad. Plain keyword matching cannot see negation
# ("no kids"), so it may over-flag; for safety that is the right direction to err.
_KEYWORDS = {
    CHILD_OR_PET: [
        r"child", r"children", r"kids?", r"baby", r"babies", r"infant", r"toddler",
        r"newborn", r"pets?", r"dogs?", r"puppy", r"puppies", r"cats?", r"kittens?",
    ],
    EXTREME_WEATHER: [
        r"storm\w*", r"blizzard", r"snow\w*", r"freezing", r"icy", r"ice", r"frost\w*",
        r"heat ?wave", r"scorching", r"sweltering", r"extreme (?:heat|cold|weather)",
        r"flood\w*", r"hurricane", r"tornado", r"hail", r"lightning", r"below zero",
        r"very (?:hot|cold)",
    ],
    REMOTE_AREA: [
        r"remote", r"isolated", r"deserted", r"desert", r"middle of nowhere", r"rural",
        r"countryside", r"highway", r"motorway", r"freeway", r"hard shoulder",
        r"no (?:signal|service|reception|cell)", r"dirt road", r"trailhead", r"forest",
        r"mountain\w*", r"off[- ]grid",
    ],
}
_PATTERNS = {
    signal: re.compile(r"\b(?:" + "|".join(words) + r")\b", re.IGNORECASE)
    for signal, words in _KEYWORDS.items()
}


def is_night(now: datetime) -> bool:
    return now.hour >= NIGHT_START_HOUR or now.hour < NIGHT_END_HOUR


def detect_signals(safe_place: bool, location: str, issue: str, now: datetime) -> tuple[str, ...]:
    """Return every unsafe signal found, in a fixed order. Any one of them is enough."""
    text = f"{location} {issue}"
    signals = []
    if not safe_place:
        signals.append(NOT_SAFE_PLACE)
    for signal in (CHILD_OR_PET, EXTREME_WEATHER, REMOTE_AREA):
        if _PATTERNS[signal].search(text):
            signals.append(signal)
    if is_night(now):
        signals.append(NIGHT)
    return tuple(signals)

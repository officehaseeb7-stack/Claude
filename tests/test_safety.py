"""Unsafe-signal detection."""
from datetime import datetime

import pytest

from triage.safety import (
    CHILD_OR_PET,
    EXTREME_WEATHER,
    NIGHT,
    NOT_SAFE_PLACE,
    REMOTE_AREA,
    detect_signals,
    is_night,
)

DAY = datetime(2026, 10, 9, 12, 0)


def signals(location="Mall car park", issue="Keys inside", safe=True, now=DAY):
    return detect_signals(safe, location, issue, now)


def test_clean_daytime_request_has_no_signals():
    assert signals() == ()


def test_explicit_not_safe_answer():
    assert signals(safe=False) == (NOT_SAFE_PLACE,)


@pytest.mark.parametrize("text", [
    "my baby is asleep in the back", "there is a dog inside", "Two kids in the car", "a cat is in the carrier",
])
def test_child_or_pet_keywords(text):
    assert signals(issue=text) == (CHILD_OR_PET,)


@pytest.mark.parametrize("text", [
    "there is a blizzard", "freezing out here", "heatwave today", "flooding on the road", "huge storm coming",
])
def test_extreme_weather_keywords(text):
    assert signals(location=text) == (EXTREME_WEATHER,)


@pytest.mark.parametrize("text", [
    "middle of nowhere", "on the highway shoulder", "a remote trailhead", "no signal here", "rural road",
])
def test_remote_area_keywords(text):
    assert signals(location=text) == (REMOTE_AREA,)


def test_keywords_match_whole_words_only():
    assert signals(issue="the petrol cap is stuck, catalytic converter noise") == ()


def test_multiple_signals_are_all_reported():
    found = signals(location="remote road", issue="storm and my dog is inside", safe=False)
    assert set(found) == {NOT_SAFE_PLACE, CHILD_OR_PET, EXTREME_WEATHER, REMOTE_AREA}


@pytest.mark.parametrize("hour,expected", [(0, True), (5, True), (6, False), (12, False),
                                           (19, False), (20, True), (23, True)])
def test_is_night(hour, expected):
    assert is_night(datetime(2026, 10, 9, hour, 30)) is expected


def test_night_signal_uses_the_clock_passed_in():
    assert signals(now=datetime(2026, 10, 9, 22, 0)) == (NIGHT,)

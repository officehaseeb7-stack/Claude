"""Triage engine: every route, plus the precedence cases."""
from datetime import datetime

import pytest

from triage.engine import (
    ACTION_REMOTE_UNLOCK,
    AUTO_RESOLVE,
    DUPLICATE,
    ESCALATE_HUMAN,
    NAME_MISMATCH,
    NAME_PARTIAL,
    NEEDS_VERIFICATION,
    NO_ACTIVE_RENTAL,
    REPEAT_LOCKOUT,
    UNSAFE_SITUATION,
    URGENT_SAFETY,
    VEHICLE_NOT_FOUND,
    VEHICLE_OFFLINE,
    DUPLICATE_TICKET,
    LockoutRequest,
    match_name,
    triage,
)

DAY = datetime(2026, 10, 9, 12, 0)
NIGHT = datetime(2026, 10, 9, 23, 30)

VEHICLE = {"id": "V-1", "telematics_online": True}
RENTAL = {"id": "R-1", "vehicle_id": "V-1", "renter_name": "Amira Khan", "active": True, "prior_lockouts": 0}
OPEN_TICKET = {"id": "T-0007", "vehicle_id": "V-1", "status": "Escalated"}


def req(**overrides):
    base = dict(vehicle_id="V-1", renter_name="Amira Khan", phone="555-0100",
                location="Mall car park, level 2", issue="Keys are inside the car.", safe_place=True)
    base.update(overrides)
    return LockoutRequest(**base)


def run(request=None, vehicle=VEHICLE, rental=RENTAL, tickets=(), prior=0, now=DAY):
    return triage(request or req(), vehicle, rental, list(tickets), prior, now)


# ---- one test per route ------------------------------------------------------

def test_auto_resolve_when_everything_is_clean():
    d = run()
    assert d.route == AUTO_RESOLVE
    assert d.auto_actions == (ACTION_REMOTE_UNLOCK,)
    assert d.counts_as_lockout and d.rental_id == "R-1"


def test_needs_verification_unknown_vehicle_asks_for_vehicle_id_only():
    d = run(req(vehicle_id="V-9999"), vehicle=None, rental=None)
    assert (d.route, d.reason_code, d.ask_for) == (NEEDS_VERIFICATION, VEHICLE_NOT_FOUND, "vehicle_id")
    assert not d.auto_actions


def test_needs_verification_partial_name_asks_for_full_name_only():
    d = run(req(renter_name="Amira"))
    assert (d.route, d.reason_code, d.ask_for) == (NEEDS_VERIFICATION, NAME_PARTIAL, "full_name")
    assert not d.counts_as_lockout


def test_escalate_vehicle_offline():
    d = run(vehicle={**VEHICLE, "telematics_online": False})
    assert (d.route, d.reason_code) == (ESCALATE_HUMAN, VEHICLE_OFFLINE)
    assert not d.auto_actions


def test_escalate_missing_telematics_flag_is_treated_as_offline():
    assert run(vehicle={"id": "V-1"}).reason_code == VEHICLE_OFFLINE


def test_escalate_name_mismatch():
    d = run(req(renter_name="Jordan Smith"))
    assert (d.route, d.reason_code) == (ESCALATE_HUMAN, NAME_MISMATCH)
    assert not d.counts_as_lockout


def test_escalate_repeat_lockout_counts_current_request():
    assert run(prior=0).route == AUTO_RESOLVE
    d = run(prior=1)
    assert (d.route, d.reason_code) == (ESCALATE_HUMAN, REPEAT_LOCKOUT)


def test_escalate_no_active_rental():
    d = run(rental={**RENTAL, "active": False})
    assert (d.route, d.reason_code) == (ESCALATE_HUMAN, NO_ACTIVE_RENTAL)
    d = run(rental=None)
    assert d.reason_code == NO_ACTIVE_RENTAL


def test_urgent_safety_when_renter_is_not_in_a_safe_place():
    d = run(req(safe_place=False))
    assert d.route == URGENT_SAFETY and d.call_now
    assert d.reason_code == UNSAFE_SITUATION and not d.auto_actions


def test_duplicate_links_existing_ticket():
    d = run(tickets=[OPEN_TICKET])
    assert (d.route, d.related_ticket) == (DUPLICATE, "T-0007")


def test_duplicate_ignores_resolved_awaiting_and_other_vehicles():
    others = [
        {"id": "T-1", "vehicle_id": "V-1", "status": "Resolved"},
        {"id": "T-2", "vehicle_id": "V-1", "status": "Awaiting info"},
        {"id": "T-3", "vehicle_id": "V-2", "status": "Escalated"},
    ]
    assert run(tickets=others).route == AUTO_RESOLVE


# ---- unsafe overrides everything --------------------------------------------

UNSAFE = dict(safe_place=False)


def test_unsafe_beats_offline():
    d = run(req(**UNSAFE), vehicle={**VEHICLE, "telematics_online": False})
    assert d.route == URGENT_SAFETY
    assert VEHICLE_OFFLINE in d.flags and not d.auto_actions


def test_unsafe_beats_name_mismatch():
    d = run(req(renter_name="Someone Else", **UNSAFE))
    assert d.route == URGENT_SAFETY and NAME_MISMATCH in d.flags


def test_unsafe_beats_repeat_lockout():
    d = run(req(**UNSAFE), prior=2)
    assert d.route == URGENT_SAFETY and REPEAT_LOCKOUT in d.flags


def test_unsafe_beats_unknown_vehicle():
    d = run(req(vehicle_id="V-9999", **UNSAFE), vehicle=None, rental=None)
    assert d.route == URGENT_SAFETY and VEHICLE_NOT_FOUND in d.flags


def test_unsafe_beats_no_active_rental():
    d = run(req(**UNSAFE), rental={**RENTAL, "active": False})
    assert d.route == URGENT_SAFETY and NO_ACTIVE_RENTAL in d.flags


def test_unsafe_beats_partial_name():
    d = run(req(renter_name="Amira", **UNSAFE))
    assert d.route == URGENT_SAFETY and NAME_PARTIAL in d.flags


def test_unsafe_is_not_swallowed_by_duplicate():
    d = run(req(**UNSAFE), tickets=[OPEN_TICKET])
    assert d.route == URGENT_SAFETY
    assert d.related_ticket == "T-0007"          # linked, so the history is not lost
    assert DUPLICATE_TICKET in d.flags and d.call_now


def test_unsafe_with_everything_wrong_still_urgent():
    d = run(req(renter_name="Nobody", **UNSAFE), vehicle={**VEHICLE, "telematics_online": False},
            tickets=[OPEN_TICKET], prior=3)
    assert d.route == URGENT_SAFETY
    assert set(d.flags) == {NAME_MISMATCH, DUPLICATE_TICKET, VEHICLE_OFFLINE, REPEAT_LOCKOUT}


def test_unsafe_from_keywords_without_the_safe_flag():
    d = run(req(issue="My dog is in the back seat and it is very hot"))
    assert d.route == URGENT_SAFETY


# ---- night -------------------------------------------------------------------

def test_night_alone_is_urgent_and_unlocks_when_otherwise_clean():
    d = run(now=NIGHT)
    assert d.route == URGENT_SAFETY and d.call_now
    assert d.signals == ("night",)
    assert d.auto_actions == (ACTION_REMOTE_UNLOCK,)


@pytest.mark.parametrize("kwargs", [
    dict(vehicle={**VEHICLE, "telematics_online": False}),
    dict(request=req(renter_name="Someone Else")),
    dict(request=req(renter_name="Amira")),
    dict(prior=1),
    dict(tickets=[OPEN_TICKET]),
    dict(rental={**RENTAL, "active": False}),
])
def test_night_with_any_problem_is_urgent_without_unlock(kwargs):
    d = run(now=NIGHT, **kwargs)
    assert d.route == URGENT_SAFETY and not d.auto_actions and d.call_now


def test_night_plus_another_signal_does_not_unlock():
    d = run(req(safe_place=False), now=NIGHT)
    assert d.route == URGENT_SAFETY and not d.auto_actions
    assert set(d.signals) == {"not_safe_place", "night"}


@pytest.mark.parametrize("hour,expected", [(5, URGENT_SAFETY), (6, AUTO_RESOLVE),
                                           (19, AUTO_RESOLVE), (20, URGENT_SAFETY)])
def test_night_boundaries(hour, expected):
    assert run(now=datetime(2026, 10, 9, hour, 0)).route == expected


# ---- precedence among the non-urgent checks ---------------------------------

def test_duplicate_beats_offline_and_repeat():
    d = run(vehicle={**VEHICLE, "telematics_online": False}, tickets=[OPEN_TICKET], prior=1)
    assert d.route == DUPLICATE


def test_name_mismatch_beats_duplicate():
    d = run(req(renter_name="Someone Else"), tickets=[OPEN_TICKET])
    assert d.route == ESCALATE_HUMAN and d.reason_code == NAME_MISMATCH
    assert d.related_ticket is None              # no ticket link shown to an unverified person


def test_partial_name_beats_duplicate_and_offline():
    d = run(req(renter_name="Khan"), tickets=[OPEN_TICKET], vehicle={**VEHICLE, "telematics_online": False})
    assert d.route == NEEDS_VERIFICATION and d.ask_for == "full_name"


def test_unknown_vehicle_beats_everything_but_safety():
    d = run(req(vehicle_id="V-9999"), vehicle=None, rental=None, prior=5)
    assert d.route == NEEDS_VERIFICATION


def test_no_active_rental_beats_offline():
    d = run(rental={**RENTAL, "active": False}, vehicle={**VEHICLE, "telematics_online": False})
    assert d.reason_code == NO_ACTIVE_RENTAL and VEHICLE_OFFLINE in d.flags


def test_offline_beats_repeat():
    d = run(vehicle={**VEHICLE, "telematics_online": False}, prior=1)
    assert d.reason_code == VEHICLE_OFFLINE and REPEAT_LOCKOUT in d.flags


def test_vehicle_id_is_normalised():
    d = run(req(vehicle_id=" v-1 "), tickets=[OPEN_TICKET])
    assert d.route == DUPLICATE and d.vehicle_id == "V-1"


# ---- name matching -----------------------------------------------------------

@pytest.mark.parametrize("entered,agreed,expected", [
    ("Amira Khan", "Amira Khan", "exact"),
    ("  amira   KHAN ", "Amira Khan", "exact"),
    ("Khan, Amira", "Amira Khan", "exact"),
    ("Amira Jane Khan", "Amira Khan", "exact"),
    ("Tomas Garcia", "Tomás García", "exact"),
    ("Amira", "Amira Khan", "partial"),
    ("khan", "Amira Khan", "partial"),
    ("Amira Smith", "Amira Khan", "mismatch"),
    ("Jordan Smith", "Amira Khan", "mismatch"),
    ("", "Amira Khan", "mismatch"),
])
def test_match_name(entered, agreed, expected):
    assert match_name(entered, agreed) == expected

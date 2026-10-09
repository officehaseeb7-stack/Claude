"""Rules-based lockout triage.

Pure functions only: no Flask, no file access, no clock reads. Everything the rules
need (vehicle, rental, existing tickets, prior lockouts, the current time) is passed in.

Decision order (first match wins):
  1. Any unsafe signal            -> URGENT_SAFETY   (overrides everything below)
  2. Vehicle not in fleet         -> NEEDS_VERIFICATION (ask for the vehicle ID)
  3. No active rental             -> ESCALATE_HUMAN
  4. Name mismatch                -> ESCALATE_HUMAN
     Name partly matches          -> NEEDS_VERIFICATION (ask for the full name)
  5. Open ticket for the vehicle  -> DUPLICATE
  6. Vehicle offline              -> ESCALATE_HUMAN
  7. Repeat lockout               -> ESCALATE_HUMAN
  8. Otherwise                    -> AUTO_RESOLVE
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime

from .safety import NIGHT, detect_signals

AUTO_RESOLVE = "AUTO_RESOLVE"
NEEDS_VERIFICATION = "NEEDS_VERIFICATION"
ESCALATE_HUMAN = "ESCALATE_HUMAN"
URGENT_SAFETY = "URGENT_SAFETY"
DUPLICATE = "DUPLICATE"

# Reason / finding codes
UNSAFE_SITUATION = "UNSAFE_SITUATION"
VEHICLE_NOT_FOUND = "VEHICLE_NOT_FOUND"
NO_ACTIVE_RENTAL = "NO_ACTIVE_RENTAL"
NAME_MISMATCH = "NAME_MISMATCH"
NAME_PARTIAL = "NAME_PARTIAL"
DUPLICATE_TICKET = "DUPLICATE_TICKET"
VEHICLE_OFFLINE = "VEHICLE_OFFLINE"
REPEAT_LOCKOUT = "REPEAT_LOCKOUT"
ALL_CLEAR = "ALL_CLEAR"

ASK_VEHICLE_ID = "vehicle_id"
ASK_FULL_NAME = "full_name"

ACTION_REMOTE_UNLOCK = "remote_unlock"

# Tickets in these statuses are finished or waiting on the operator, so they do not
# count as "open" for duplicate detection.
NON_OPEN_STATUSES = frozenset({"Resolved", "Awaiting info", "Closed"})

# Findings are collected in decision order; the first one decides the route.
_ROUTE_FOR_FINDING = {
    VEHICLE_NOT_FOUND: NEEDS_VERIFICATION,
    NO_ACTIVE_RENTAL: ESCALATE_HUMAN,
    NAME_MISMATCH: ESCALATE_HUMAN,
    NAME_PARTIAL: NEEDS_VERIFICATION,
    DUPLICATE_TICKET: DUPLICATE,
    VEHICLE_OFFLINE: ESCALATE_HUMAN,
    REPEAT_LOCKOUT: ESCALATE_HUMAN,
}
_ASK_FOR_FINDING = {VEHICLE_NOT_FOUND: ASK_VEHICLE_ID, NAME_PARTIAL: ASK_FULL_NAME}


@dataclass(frozen=True)
class LockoutRequest:
    vehicle_id: str
    renter_name: str
    phone: str
    location: str
    issue: str
    safe_place: bool


@dataclass(frozen=True)
class Decision:
    route: str
    reason_code: str
    # Other problems found. For URGENT_SAFETY this is every finding, so nothing is hidden
    # from the person who has to call; for other routes it is everything but the decider.
    flags: tuple = ()
    signals: tuple = ()
    related_ticket: str | None = None
    auto_actions: tuple = ()
    ask_for: str | None = None
    call_now: bool = False
    # True when this request is a verified lockout on a real rental (counts toward "repeat").
    counts_as_lockout: bool = False
    vehicle_id: str = ""
    rental_id: str | None = None


def normalize_vehicle_id(raw: str | None) -> str:
    return re.sub(r"\s+", "", raw or "").upper()


def is_open_ticket(ticket: dict) -> bool:
    return ticket.get("status") not in NON_OPEN_STATUSES


def find_open_ticket(tickets: list[dict], vehicle_id: str) -> dict | None:
    """Most recent open ticket for the vehicle, or None."""
    vid = normalize_vehicle_id(vehicle_id)
    matches = [
        t for t in tickets
        if is_open_ticket(t) and normalize_vehicle_id(t.get("vehicle_id")) == vid
    ]
    return matches[-1] if matches else None


def _name_tokens(name: str) -> frozenset[str]:
    decomposed = unicodedata.normalize("NFKD", name or "")
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return frozenset(re.sub(r"[^a-z0-9]+", " ", stripped.casefold()).split())


def match_name(entered: str, agreed: str) -> str:
    """'exact', 'partial' or 'mismatch'.

    Case, accents, punctuation and word order are ignored.
      exact    - every word on the agreement is present (extra words such as a middle name are fine)
      partial  - what was typed is only part of the agreed name (e.g. just "Amira")
      mismatch - anything else, including sharing a first name but giving a different surname
    """
    typed, on_file = _name_tokens(entered), _name_tokens(agreed)
    if not typed or not on_file:
        return "mismatch"
    if on_file <= typed:
        return "exact"
    if typed < on_file:
        return "partial"
    return "mismatch"


def triage(
    request: LockoutRequest,
    vehicle: dict | None,
    rental: dict | None,
    tickets: list[dict],
    prior_lockouts: int,
    now: datetime,
) -> Decision:
    """Decide what to do with a lockout request. See the module docstring for the order."""
    vid = normalize_vehicle_id(request.vehicle_id)
    signals = detect_signals(request.safe_place, request.location, request.issue, now)
    duplicate = find_open_ticket(tickets, vid)

    findings: list[str] = []
    name_result = None
    rental_active = bool(rental and rental.get("active"))

    if vehicle is None:
        findings.append(VEHICLE_NOT_FOUND)
    elif not rental_active:
        findings.append(NO_ACTIVE_RENTAL)
    else:
        name_result = match_name(request.renter_name, rental.get("renter_name", ""))
        if name_result == "mismatch":
            findings.append(NAME_MISMATCH)
        elif name_result == "partial":
            findings.append(NAME_PARTIAL)
    if duplicate:
        findings.append(DUPLICATE_TICKET)
    if vehicle is not None and not vehicle.get("telematics_online", False):
        findings.append(VEHICLE_OFFLINE)
    # "2 or more in the same rental" counts this request, so one earlier lockout is enough.
    if rental_active and prior_lockouts + 1 >= 2:
        findings.append(REPEAT_LOCKOUT)

    common = dict(
        signals=signals,
        vehicle_id=vid,
        rental_id=rental.get("id") if rental_active else None,
        counts_as_lockout=(name_result == "exact"),
    )

    if signals:
        # Night as the only concern, with every other check clean, is the one case where
        # the car can safely be opened for them while a person calls.
        night_only_and_clean = signals == (NIGHT,) and not findings
        return Decision(
            route=URGENT_SAFETY,
            reason_code=UNSAFE_SITUATION,
            flags=tuple(findings),
            related_ticket=duplicate["id"] if duplicate else None,
            auto_actions=(ACTION_REMOTE_UNLOCK,) if night_only_and_clean else (),
            call_now=True,
            **common,
        )

    if not findings:
        return Decision(
            route=AUTO_RESOLVE,
            reason_code=ALL_CLEAR,
            auto_actions=(ACTION_REMOTE_UNLOCK,),
            **common,
        )

    decider = findings[0]
    return Decision(
        route=_ROUTE_FOR_FINDING[decider],
        reason_code=decider,
        flags=tuple(findings[1:]),
        related_ticket=duplicate["id"] if decider == DUPLICATE_TICKET else None,
        ask_for=_ASK_FOR_FINDING.get(decider),
        **common,
    )

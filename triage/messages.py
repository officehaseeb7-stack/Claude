"""Plain-language wording for each outcome. Pure functions: ticket dict in, display dict out.

All timeline values and the self-help checklist are prototype placeholders, not real
service levels or procedures.
"""
from __future__ import annotations

from datetime import datetime

from . import safety
from .engine import (
    ASK_FULL_NAME,
    ASK_VEHICLE_ID,
    AUTO_RESOLVE,
    DUPLICATE,
    DUPLICATE_TICKET,
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
)

TIMELINES = {
    AUTO_RESOLVE: "Within about 1 minute.",
    NEEDS_VERIFICATION: "We pick this up as soon as you send that one detail.",
    ESCALATE_HUMAN: "A support team member will contact you within 30 minutes.",
    URGENT_SAFETY: "Call the renter now. Target: a person on the phone within 5 minutes.",
}

STATUS = {
    AUTO_RESOLVE: ("Resolved", "good"),
    NEEDS_VERIFICATION: ("One detail needed from you", "info"),
    ESCALATE_HUMAN: ("Passed to a person", "warn"),
    URGENT_SAFETY: ("URGENT: call the renter now", "urgent"),
    DUPLICATE: ("Already being handled", "info"),
}

TICKET_STATUS = {
    AUTO_RESOLVE: "Resolved",
    NEEDS_VERIFICATION: "Awaiting info",
    ESCALATE_HUMAN: "Escalated",
    URGENT_SAFETY: "Urgent",
}

ASK_TEXT = {
    ASK_VEHICLE_ID: "the correct vehicle ID",
    ASK_FULL_NAME: "the renter's full name, exactly as it appears on the rental agreement",
}

SIGNAL_TEXT = {
    safety.NOT_SAFE_PLACE: "the renter said they are not in a safe place",
    safety.CHILD_OR_PET: "a child or pet may be inside the vehicle",
    safety.EXTREME_WEATHER: "extreme weather is mentioned",
    safety.REMOTE_AREA: "the renter seems to be in a remote area",
    safety.NIGHT: "it is night time",
}

FINDING_TEXT = {
    VEHICLE_NOT_FOUND: "vehicle {vehicle_id} is not in the fleet",
    NO_ACTIVE_RENTAL: "the vehicle has no active rental",
    NAME_MISMATCH: "the name given does not match the rental agreement",
    NAME_PARTIAL: "the name given only partly matches the rental agreement",
    DUPLICATE_TICKET: "there is already an open ticket for this vehicle",
    VEHICLE_OFFLINE: "the vehicle is offline, so it cannot be unlocked remotely",
    REPEAT_LOCKOUT: "this renter has already been locked out during this rental",
}

CHECKLIST = (
    "Ask the renter to check every door and the boot or trunk, not just the one they tried.",
    "If they have a spare key or phone access, ask them to try it.",
    "Keep them in a well-lit spot with other people around while they wait.",
    "Do not ask them to force a door or break a window.",
)


def _join(items: list[str]) -> str:
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + " and " + items[-1]


def _clock(iso: str | None) -> str:
    if not iso:
        return "just now"
    return "at " + datetime.fromisoformat(iso).strftime("%H:%M")


def _reason(t: dict) -> str:
    code = t["reason_code"]
    vehicle_id = t.get("vehicle_id", "")
    if code == UNSAFE_SITUATION:
        why = _join([SIGNAL_TEXT[s] for s in t.get("signals", [])])
        text = f"The renter may be in an unsafe situation: {why}."
        if t.get("unlock_sent"):
            text += " Everything else checks out: the name matches and the vehicle is online."
        return text
    if code == VEHICLE_NOT_FOUND:
        return f"We could not find vehicle {vehicle_id} in your fleet."
    if code == NO_ACTIVE_RENTAL:
        return (f"Vehicle {vehicle_id} has no active rental right now, "
                "so we cannot confirm this person is allowed to be in it.")
    if code == NAME_MISMATCH:
        return "The name you gave does not match the name on the rental agreement."
    if code == NAME_PARTIAL:
        return "The name you gave matches only part of the name on the rental agreement."
    if code == DUPLICATE_TICKET:
        return f"There is already an open ticket for vehicle {vehicle_id}, so no new one was created."
    if code == VEHICLE_OFFLINE:
        return "The vehicle is offline right now, so we cannot unlock it remotely."
    if code == REPEAT_LOCKOUT:
        return ("This renter has already been locked out during this rental, "
                "so a person needs to look at it before anyone unlocks the car again.")
    return ("Everything checks out: the vehicle has an active rental, the name matches, "
            "the vehicle is online and this is the first lockout.")


def describe(t: dict, related: dict | None = None) -> dict:
    """Build everything the result screen shows. `related` is the linked ticket, if any."""
    route = t["route"]
    label, tone = STATUS[route]
    phone = t.get("phone", "")
    ticket_id = t.get("id")
    also = [FINDING_TEXT[f].format(vehicle_id=t.get("vehicle_id", "")) for f in t.get("flags", [])
            if f != DUPLICATE_TICKET]

    steps: list[str] = []
    checklist: tuple = ()
    timeline = TIMELINES.get(route, "")
    ask = None

    if route == AUTO_RESOLVE:
        steps = [
            f"The unlock was sent to the vehicle {_clock(t.get('unlock_at'))}.",
            "Ask the renter to try the door now.",
            "If it still will not open, contact support and quote the ticket number.",
        ]
    elif route == NEEDS_VERIFICATION:
        ask = ASK_TEXT[t["ask_for"]]
        steps = [
            f"Submit the form again with {ask}.",
            "Nothing else is needed from you.",
        ]
    elif route == ESCALATE_HUMAN:
        steps = [
            "A support team member will review this and contact you.",
            f"Please keep the renter's phone ({phone}) reachable.",
        ]
        checklist = CHECKLIST
    elif route == URGENT_SAFETY:
        steps = [
            f"Call the renter now on {phone}.",
            "Support has been alerted and the ticket is marked call now.",
        ]
        if t.get("unlock_sent"):
            steps.append(f"The car was already unlocked {_clock(t.get('unlock_at'))}. "
                         "Still call to check the renter is okay.")
        if t.get("related_ticket"):
            steps.append(f"This is linked to the open ticket {t['related_ticket']} for the same vehicle.")
        steps.append("If anyone is in danger, tell them to call local emergency services.")
        checklist = CHECKLIST
    elif route == DUPLICATE:
        rid = t["related_ticket"]
        status = related["status"] if related else "open"
        timeline = f"No new clock starts. This follows ticket {rid} (status: {status})."
        steps = [
            "No new ticket was created.",
            f"Follow ticket {rid} in the ticket log.",
            "If the renter is no longer safe, submit the form again and answer No to "
            "\"Is the renter in a safe place?\".",
        ]

    return {
        "route": route,
        "tone": tone,
        "status_label": label,
        "reason": _reason(t),
        "next_steps": steps,
        "timeline": timeline,
        "ask": ask,
        "checklist": list(checklist),
        "also_noted": also,
        "call_now": bool(t.get("call_now")),
        "phone": phone,
        "ticket_id": ticket_id,
        "related_ticket": t.get("related_ticket"),
    }

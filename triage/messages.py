"""Plain-language wording for each outcome. Pure functions: ticket dict in, display dict out.

Two voices:
  describe()      - what the RENTER sees on the result screen, written to "you".
  staff_reason()  - the one-line decision reason kept in the ticket log, for staff.

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
    AUTO_RESOLVE: "Your vehicle should unlock within about 1 minute.",
    NEEDS_VERIFICATION: "We carry on as soon as you send that detail.",
    ESCALATE_HUMAN: "A support team member will contact you within 30 minutes.",
    URGENT_SAFETY: "We aim to have someone on the phone with you within 5 minutes.",
}

# (headline shown to the renter, colour tone)
STATUS = {
    AUTO_RESOLVE: ("Your vehicle is being unlocked", "good"),
    NEEDS_VERIFICATION: ("We need one more detail from you", "info"),
    ESCALATE_HUMAN: ("We're passing you to a person", "warn"),
    URGENT_SAFETY: ("Urgent: we're prioritising your request", "urgent"),
    DUPLICATE: ("We already have your request", "info"),
}

# Status words kept in the ticket log (staff view).
TICKET_STATUS = {
    AUTO_RESOLVE: "Resolved",
    NEEDS_VERIFICATION: "Awaiting info",
    ESCALATE_HUMAN: "Escalated",
    URGENT_SAFETY: "Urgent",
    DUPLICATE: "Closed",  # only used when an awaiting ticket turns out to be a duplicate
}

# What the single inline field asks for: (label, hint, ticket field it fills in)
ASK_FIELD = {
    ASK_VEHICLE_ID: ("Vehicle ID", "Enter the correct vehicle ID.", "vehicle_id"),
    ASK_FULL_NAME: ("Your full name",
                    "Exactly as it appears on your rental agreement.", "renter_name"),
}

SIGNAL_TEXT = {
    safety.NOT_SAFE_PLACE: "you said you are not in a safe place",
    safety.CHILD_OR_PET: "a child or pet may be inside the vehicle",
    safety.EXTREME_WEATHER: "you mentioned extreme weather",
    safety.REMOTE_AREA: "you seem to be in a remote area",
    safety.NIGHT: "it is night time",
}

STAFF_SIGNAL_TEXT = {
    safety.NOT_SAFE_PLACE: "the renter said they are not in a safe place",
    safety.CHILD_OR_PET: "a child or pet may be inside the vehicle",
    safety.EXTREME_WEATHER: "extreme weather is mentioned",
    safety.REMOTE_AREA: "the renter seems to be in a remote area",
    safety.NIGHT: "it is night time",
}

FINDING_TEXT = {
    VEHICLE_NOT_FOUND: "vehicle {vehicle_id} isn't in the fleet",
    NO_ACTIVE_RENTAL: "the vehicle has no active rental",
    NAME_MISMATCH: "the name you gave doesn't match the rental agreement",
    NAME_PARTIAL: "the name you gave only partly matches the rental agreement",
    DUPLICATE_TICKET: "there is already an open ticket for this vehicle",
    VEHICLE_OFFLINE: "your vehicle is offline, so we can't unlock it remotely",
    REPEAT_LOCKOUT: "you've already been locked out during this rental",
}

CHECKLIST = (
    "Check every door and the boot or trunk, not just the one you tried.",
    "If you have a spare key or phone access, try it.",
    "Wait somewhere well lit with other people around.",
    "Please don't force a door or break a window.",
)


def _join(items: list[str]) -> str:
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + " and " + items[-1]


def _clock(iso: str | None) -> str:
    if not iso:
        return "just now"
    return "at " + datetime.fromisoformat(iso).strftime("%H:%M")


def staff_reason(t: dict) -> str:
    """One-line decision reason for the ticket log (third person, for staff)."""
    code = t["reason_code"]
    vehicle_id = t.get("vehicle_id", "")
    if code == UNSAFE_SITUATION:
        why = _join([STAFF_SIGNAL_TEXT[s] for s in t.get("signals", [])])
        text = f"The renter may be in an unsafe situation: {why}."
        if t.get("unlock_sent"):
            text += " Everything else checks out: the name matches and the vehicle is online."
        return text
    if code == VEHICLE_NOT_FOUND:
        return f"Vehicle {vehicle_id} is not in the fleet."
    if code == NO_ACTIVE_RENTAL:
        return f"Vehicle {vehicle_id} has no active rental, so the renter cannot be verified."
    if code == NAME_MISMATCH:
        return "The name given does not match the name on the rental agreement."
    if code == NAME_PARTIAL:
        return "The name given matches only part of the name on the rental agreement."
    if code == DUPLICATE_TICKET:
        link = f" ({t['related_ticket']})" if t.get("related_ticket") else ""
        return f"There is already an open ticket for vehicle {vehicle_id}{link}, so no new one was created."
    if code == VEHICLE_OFFLINE:
        return "The vehicle is offline, so it cannot be unlocked remotely."
    if code == REPEAT_LOCKOUT:
        return ("The renter has already been locked out during this rental, "
                "so a person must review before unlocking again.")
    return ("Everything checks out: active rental, name matches, vehicle online, "
            "first lockout.")


def _reason_for_renter(t: dict) -> str:
    code = t["reason_code"]
    vehicle_id = t.get("vehicle_id", "")
    if code == UNSAFE_SITUATION:
        why = _join([SIGNAL_TEXT[s] for s in t.get("signals", [])])
        text = f"You may be in an unsafe situation: {why}."
        if t.get("unlock_sent"):
            text += " Everything else checks out: your name matches and your vehicle is online."
        return text
    if code == VEHICLE_NOT_FOUND:
        return f"We couldn't find vehicle {vehicle_id} in the fleet."
    if code == NO_ACTIVE_RENTAL:
        return (f"We couldn't find an active rental for vehicle {vehicle_id}, "
                "so we can't confirm you're allowed to be in it.")
    if code == NAME_MISMATCH:
        return "The name you gave doesn't match the name on the rental agreement."
    if code == NAME_PARTIAL:
        return "The name you gave matches only part of the name on the rental agreement."
    if code == DUPLICATE_TICKET:
        return (f"We already have an open ticket for vehicle {vehicle_id}, "
                "so we haven't opened a new one.")
    if code == VEHICLE_OFFLINE:
        return "Your vehicle isn't connected right now, so we can't unlock it remotely."
    if code == REPEAT_LOCKOUT:
        return ("You've already been locked out once during this rental, so a person needs "
                "to check before your vehicle is unlocked again.")
    return ("Everything checks out: your rental is active, your name matches, "
            "and your vehicle is online.")


def describe(t: dict, related: dict | None = None) -> dict:
    """Build everything the result screen shows, written to the renter. `related` is the linked ticket."""
    route = t["route"]
    label, tone = STATUS[route]
    phone = t.get("phone", "")
    also = [FINDING_TEXT[f].format(vehicle_id=t.get("vehicle_id", "")) for f in t.get("flags", [])
            if f != DUPLICATE_TICKET]

    steps: list[str] = []
    checklist: tuple = ()
    timeline = TIMELINES.get(route, "")
    ask_label = ask_hint = ask_value = None
    banner_note = ""

    if route == AUTO_RESOLVE:
        steps = [
            f"We sent the unlock to your vehicle {_clock(t.get('unlock_at'))}.",
            "Try the door now.",
            "If it still won't open, contact support and quote your ticket number.",
        ]
    elif route == NEEDS_VERIFICATION:
        ask_label, ask_hint, source = ASK_FIELD[t["ask_for"]]
        ask_value = t.get(source, "")
        steps = [
            "Enter it in the box on this page and press Send.",
            "You don't need to fill in the form again.",
        ]
    elif route == ESCALATE_HUMAN:
        steps = [
            f"A support team member will review your request and contact you on {phone}.",
            "Please keep your phone with you.",
        ]
        checklist = CHECKLIST
    elif route == URGENT_SAFETY:
        banner_note = f"Keep your phone with you. We'll call you on {phone}."
        steps = [
            f"We'll call you on {phone}. Please answer.",
            "Our team has been alerted and your request is marked urgent.",
        ]
        if t.get("unlock_sent"):
            steps.append(f"We've already unlocked your vehicle {_clock(t.get('unlock_at'))}. "
                         "We'll still call to check you're okay.")
        if t.get("related_ticket"):
            steps.append(f"We've linked this to your earlier open ticket {t['related_ticket']}.")
        steps.append("If you are in danger, call your local emergency number now.")
        checklist = CHECKLIST
    elif route == DUPLICATE:
        rid = t["related_ticket"]
        status = related["status"] if related else "open"
        timeline = f"No new clock starts. This follows ticket {rid} (status: {status})."
        steps = [
            "We haven't opened a new ticket.",
            f"You can follow your existing ticket, {rid}, in the ticket log.",
            "If things have changed and you no longer feel safe, send a new request and "
            "answer No to \"Are you in a safe place?\".",
        ]

    return {
        "route": route,
        "tone": tone,
        "status_label": label,
        "banner_note": banner_note,
        "reason": _reason_for_renter(t),
        "next_steps": steps,
        "timeline": timeline,
        "ask_label": ask_label,
        "ask_hint": ask_hint,
        "ask_value": ask_value,
        "checklist": list(checklist),
        "also_noted": also,
        "ticket_id": t.get("id"),
        "related_ticket": t.get("related_ticket"),
    }

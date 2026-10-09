"""Pages: intake form, result screen (with the inline answer field), ticket log."""
from __future__ import annotations

from flask import Blueprint, abort, current_app, redirect, render_template, request, url_for

from triage.engine import (
    ACTION_REMOTE_UNLOCK,
    DUPLICATE,
    NEEDS_VERIFICATION,
    LockoutRequest,
    normalize_vehicle_id,
    triage,
)
from triage.messages import ASK_FIELD, TICKET_STATUS, describe, staff_reason

from . import simulate
from .store import prior_lockouts
from .validation import validate_answer, validate_form

bp = Blueprint("main", __name__)


def _store():
    return current_app.extensions["tickets"]


def _now():
    return simulate.get_now(current_app.config["TRIAGE_NOW"])


def _run_triage(lockout: LockoutRequest, now):
    fleet, store = current_app.extensions["fleet"], _store()
    vid = normalize_vehicle_id(lockout.vehicle_id)
    tickets = store.all()
    rental = fleet.rental(vid)
    return triage(lockout, fleet.vehicle(vid), rental, tickets, prior_lockouts(rental, tickets), now)


def _send_unlock(decision, now) -> str | None:
    """Perform the simulated unlock if the decision calls for one; return when it was sent."""
    if ACTION_REMOTE_UNLOCK not in decision.auto_actions:
        return None
    result = simulate.remote_unlock(decision.vehicle_id, now)
    current_app.logger.info("Simulated remote unlock sent to %s at %s",
                            decision.vehicle_id, result["sent_at"])
    return result["sent_at"]


def _ticket_fields(lockout: LockoutRequest, decision, now, unlock_at) -> dict:
    fields = {
        "created_at": now.isoformat(timespec="seconds"),
        "vehicle_id": decision.vehicle_id,
        "rental_id": decision.rental_id,
        "renter_name": lockout.renter_name,
        "phone": lockout.phone,
        "location": lockout.location,
        "issue": lockout.issue,
        "safe_place": lockout.safe_place,
        "route": decision.route,
        "status": TICKET_STATUS[decision.route],
        "reason_code": decision.reason_code,
        "signals": list(decision.signals),
        "flags": list(decision.flags),
        "related_ticket": decision.related_ticket,
        "ask_for": decision.ask_for,
        "call_now": decision.call_now,
        "unlock_sent": unlock_at is not None,
        "unlock_at": unlock_at,
        "counts_as_lockout": decision.counts_as_lockout,
    }
    fields["reason"] = staff_reason(fields)
    return fields


@bp.get("/")
def form():
    return render_template("form.html", values={}, errors={})


@bp.post("/")
def submit():
    values, errors = validate_form(request.form)
    if errors:
        return render_template("form.html", values=values, errors=errors), 400

    now = _now()
    lockout = LockoutRequest(
        vehicle_id=values["vehicle_id"],
        renter_name=values["renter_name"],
        phone=values["phone"],
        location=values["location"],
        issue=values["issue"],
        safe_place=values["safe_place"] == "yes",
    )
    decision = _run_triage(lockout, now)
    if decision.route == DUPLICATE:
        return redirect(url_for("main.duplicate", ticket_id=decision.related_ticket), code=303)

    unlock_at = _send_unlock(decision, now)
    ticket = _store().add(_ticket_fields(lockout, decision, now, unlock_at))
    return redirect(url_for("main.result", ticket_id=ticket["id"]), code=303)


@bp.get("/result/<ticket_id>")
def result(ticket_id):
    return _render_result(_get_or_404(ticket_id))


@bp.post("/result/<ticket_id>/answer")
def answer(ticket_id):
    """The renter supplies the one missing detail on the result page; triage runs again
    on the same ticket, so there is still one ticket per request."""
    ticket = _get_or_404(ticket_id)
    if ticket["route"] != NEEDS_VERIFICATION:       # already answered; just show where it stands
        return redirect(url_for("main.result", ticket_id=ticket_id), code=303)

    target = ASK_FIELD[ticket["ask_for"]][2]
    value, error = validate_answer(ticket["ask_for"], target, request.form.get("answer"))
    if error:
        return _render_result(ticket, answer_value=value, answer_error=error), 400

    details = {**ticket, target: value}
    lockout = LockoutRequest(
        vehicle_id=details["vehicle_id"],
        renter_name=details["renter_name"],
        phone=details["phone"],
        location=details["location"],
        issue=details["issue"],
        safe_place=details["safe_place"],
    )
    now = _now()
    decision = _run_triage(lockout, now)
    unlock_at = _send_unlock(decision, now)
    fields = _ticket_fields(lockout, decision, now, unlock_at)
    del fields["created_at"]                         # keep when the request was first made
    _store().update(ticket_id, fields)
    return redirect(url_for("main.result", ticket_id=ticket_id), code=303)


@bp.get("/duplicate/<ticket_id>")
def duplicate(ticket_id):
    existing = _get_or_404(ticket_id)
    shown = {
        "route": DUPLICATE,
        "reason_code": "DUPLICATE_TICKET",
        "vehicle_id": existing["vehicle_id"],
        "related_ticket": ticket_id,
        "phone": "",
    }
    return render_template("result.html", d=describe(shown, existing),
                           answer_value=None, answer_error=None)


@bp.get("/tickets")
def tickets():
    return render_template("tickets.html", tickets=list(reversed(_store().all())))


def _get_or_404(ticket_id: str) -> dict:
    ticket = _store().get(ticket_id)
    if ticket is None:
        abort(404)
    return ticket


def _render_result(ticket: dict, answer_value=None, answer_error=None):
    related = _store().get(ticket["related_ticket"]) if ticket.get("related_ticket") else None
    return render_template("result.html", d=describe(ticket, related),
                           answer_value=answer_value, answer_error=answer_error)

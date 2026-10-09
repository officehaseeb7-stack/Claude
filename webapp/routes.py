"""Pages: intake form, result screen, ticket log."""
from __future__ import annotations

from flask import Blueprint, abort, current_app, redirect, render_template, request, url_for

from triage.engine import (
    ACTION_REMOTE_UNLOCK,
    DUPLICATE,
    LockoutRequest,
    normalize_vehicle_id,
    triage,
)
from triage.messages import TICKET_STATUS, describe

from . import simulate
from .store import prior_lockouts
from .validation import validate_form

bp = Blueprint("main", __name__)


def _store():
    return current_app.extensions["tickets"]


@bp.get("/")
def form():
    return render_template("form.html", values={}, errors={})


@bp.post("/")
def submit():
    values, errors = validate_form(request.form)
    if errors:
        return render_template("form.html", values=values, errors=errors), 400

    fleet, store = current_app.extensions["fleet"], _store()
    now = simulate.get_now(current_app.config["TRIAGE_NOW"])
    lockout = LockoutRequest(
        vehicle_id=values["vehicle_id"],
        renter_name=values["renter_name"],
        phone=values["phone"],
        location=values["location"],
        issue=values["issue"],
        safe_place=values["safe_place"] == "yes",
    )
    vid = normalize_vehicle_id(lockout.vehicle_id)
    tickets = store.all()
    rental = fleet.rental(vid)
    decision = triage(lockout, fleet.vehicle(vid), rental, tickets,
                      prior_lockouts(rental, tickets), now)

    if decision.route == DUPLICATE:
        return redirect(url_for("main.duplicate", ticket_id=decision.related_ticket), code=303)

    unlock_at = None
    if ACTION_REMOTE_UNLOCK in decision.auto_actions:
        result = simulate.remote_unlock(vid, now)
        unlock_at = result["sent_at"]
        current_app.logger.info("Simulated remote unlock sent to %s at %s", vid, unlock_at)

    fields = {
        "created_at": now.isoformat(timespec="seconds"),
        "vehicle_id": vid,
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
    fields["reason"] = describe(fields)["reason"]
    ticket = store.add(fields)
    return redirect(url_for("main.result", ticket_id=ticket["id"]), code=303)


@bp.get("/result/<ticket_id>")
def result(ticket_id):
    ticket = _store().get(ticket_id)
    if ticket is None:
        abort(404)
    related = _store().get(ticket["related_ticket"]) if ticket.get("related_ticket") else None
    return render_template("result.html", d=describe(ticket, related))


@bp.get("/duplicate/<ticket_id>")
def duplicate(ticket_id):
    existing = _store().get(ticket_id)
    if existing is None:
        abort(404)
    vehicle_id = existing["vehicle_id"]
    shown = {
        "route": DUPLICATE,
        "reason_code": "DUPLICATE_TICKET",
        "vehicle_id": vehicle_id,
        "related_ticket": ticket_id,
        "phone": "",
    }
    return render_template("result.html", d=describe(shown, existing))


@bp.get("/tickets")
def tickets():
    return render_template("tickets.html", tickets=list(reversed(_store().all())))

"""Flask app factory."""
from __future__ import annotations

import os
from datetime import datetime

from flask import Flask

from . import simulate
from .store import Fleet, TicketStore

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")


def create_app(config: dict | None = None) -> Flask:
    app = Flask(__name__)
    app.config.update(
        DATA_DIR=DATA_DIR,
        TICKETS_PATH=os.environ.get("TICKETS_PATH") or os.path.join(DATA_DIR, "tickets.json"),
        TICKETS_SEED_PATH=os.path.join(DATA_DIR, "tickets.seed.json"),
        TRIAGE_NOW=os.environ.get("TRIAGE_NOW", ""),
    )
    app.config.update(config or {})
    app.logger.setLevel("INFO")  # so each simulated unlock shows in the server log

    simulate.get_now(app.config["TRIAGE_NOW"])  # fail fast on a bad TRIAGE_NOW value
    app.extensions["fleet"] = Fleet.from_dir(app.config["DATA_DIR"])
    app.extensions["tickets"] = TicketStore(app.config["TICKETS_PATH"], app.config["TICKETS_SEED_PATH"])

    @app.template_filter("pretty_time")
    def pretty_time(iso):
        return datetime.fromisoformat(iso).strftime("%d %b %Y, %H:%M") if iso else ""

    @app.context_processor
    def clock_info():
        setting = app.config["TRIAGE_NOW"]
        return {
            "clock_now": simulate.get_now(setting).strftime("%d %b %Y, %H:%M"),
            "clock_kind": simulate.clock_label(setting),
        }

    from .routes import bp
    app.register_blueprint(bp)
    return app

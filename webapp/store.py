"""Reads the mock fleet and keeps the ticket log in a JSON file (no database)."""
from __future__ import annotations

import json
import os
import shutil
import tempfile
import threading

from triage.engine import normalize_vehicle_id


def load_json(path: str):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


class Fleet:
    """Vehicles and their rentals, looked up by vehicle ID (one rental per vehicle)."""

    def __init__(self, vehicles: list[dict], rentals: list[dict]):
        self._vehicles = {normalize_vehicle_id(v["id"]): v for v in vehicles}
        self._rentals = {normalize_vehicle_id(r["vehicle_id"]): r for r in rentals}

    @classmethod
    def from_dir(cls, data_dir: str) -> "Fleet":
        return cls(load_json(os.path.join(data_dir, "vehicles.json")),
                   load_json(os.path.join(data_dir, "rentals.json")))

    def vehicle(self, vehicle_id: str) -> dict | None:
        return self._vehicles.get(normalize_vehicle_id(vehicle_id))

    def rental(self, vehicle_id: str) -> dict | None:
        return self._rentals.get(normalize_vehicle_id(vehicle_id))


def prior_lockouts(rental: dict | None, tickets: list[dict]) -> int:
    """Earlier lockouts on this rental: the count on file plus verified tickets logged since."""
    if not rental:
        return 0
    logged = sum(1 for t in tickets
                 if t.get("rental_id") == rental["id"] and t.get("counts_as_lockout"))
    return rental.get("prior_lockouts", 0) + logged


class TicketStore:
    """Ticket log in one JSON file. Created from the seed file the first time it is needed."""

    def __init__(self, path: str, seed_path: str | None = None):
        self.path = path
        self._lock = threading.RLock()
        if not os.path.exists(path):
            if seed_path and os.path.exists(seed_path):
                shutil.copyfile(seed_path, path)
            else:
                self._write([])

    def all(self) -> list[dict]:
        with self._lock:
            return load_json(self.path)

    def get(self, ticket_id: str) -> dict | None:
        return next((t for t in self.all() if t["id"] == ticket_id), None)

    def add(self, fields: dict) -> dict:
        with self._lock:
            tickets = self.all()
            numbers = [int(t["id"].split("-")[1]) for t in tickets]
            ticket = {"id": f"T-{max(numbers, default=0) + 1:04d}", **fields}
            tickets.append(ticket)
            self._write(tickets)
            return ticket

    def _write(self, tickets: list[dict]) -> None:
        directory = os.path.dirname(os.path.abspath(self.path))
        fd, tmp = tempfile.mkstemp(dir=directory, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(tickets, fh, indent=2, ensure_ascii=False)
            os.replace(tmp, self.path)
        except BaseException:
            if os.path.exists(tmp):
                os.remove(tmp)
            raise

"""Intake form validation: one clear message per field."""
from __future__ import annotations

import re

FIELDS = ("vehicle_id", "renter_name", "phone", "location", "issue", "safe_place")

MAX_LEN = {"vehicle_id": 20, "renter_name": 100, "phone": 30, "location": 500, "issue": 500}

REQUIRED_MESSAGES = {
    "vehicle_id": "Enter the vehicle ID.",
    "renter_name": "Enter your name.",
    "phone": "Enter a phone number we can call you on.",
    "location": "Tell us where you are.",
    "issue": "Tell us what happened.",
    "safe_place": "Choose Yes or No.",
}


def validate_form(form) -> tuple[dict, dict]:
    """Return (cleaned values, errors by field). Errors empty means the form is valid."""
    values = {name: (form.get(name) or "").strip() for name in FIELDS}
    errors = {}
    for name in FIELDS:
        if not values[name]:
            errors[name] = REQUIRED_MESSAGES[name]
        elif name in MAX_LEN and len(values[name]) > MAX_LEN[name]:
            errors[name] = f"Keep this under {MAX_LEN[name]} characters."
    if "phone" not in errors and len(re.findall(r"\d", values["phone"])) < 7:
        errors["phone"] = "Enter a phone number with at least 7 digits."
    if "safe_place" not in errors and values["safe_place"].lower() not in ("yes", "no"):
        errors["safe_place"] = REQUIRED_MESSAGES["safe_place"]
    values["safe_place"] = values["safe_place"].lower()
    return values, errors


ANSWER_REQUIRED = {
    "vehicle_id": "Enter the vehicle ID.",
    "full_name": "Enter your full name.",
}


def validate_answer(ask_for: str, target_field: str, raw: str | None) -> tuple[str, str | None]:
    """Check the single inline answer. Returns (cleaned value, error or None)."""
    value = (raw or "").strip()
    if not value:
        return value, ANSWER_REQUIRED[ask_for]
    if len(value) > MAX_LEN[target_field]:
        return value, f"Keep this under {MAX_LEN[target_field]} characters."
    return value, None

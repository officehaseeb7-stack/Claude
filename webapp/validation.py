"""Intake form validation: one clear message per field."""
from __future__ import annotations

import re

FIELDS = ("vehicle_id", "renter_name", "phone", "location", "issue", "safe_place")

MAX_LEN = {"vehicle_id": 20, "renter_name": 100, "phone": 30, "location": 500, "issue": 500}

REQUIRED_MESSAGES = {
    "vehicle_id": "Enter the vehicle ID.",
    "renter_name": "Enter the renter's name.",
    "phone": "Enter a phone number we can call.",
    "location": "Describe where the vehicle is.",
    "issue": "Describe what happened.",
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

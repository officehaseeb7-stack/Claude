"""Flask app: validation, result screens, ticket log, and every demo scenario in the README."""
import html as htmllib
import json
import os

import pytest

from webapp import DATA_DIR, create_app

NIGHT_CLOCK = "2026-10-09T23:30"

GOOD = dict(vehicle_id="V-1001", renter_name="Amira Khan", phone="555-0101",
            location="Mall car park, level 2", issue="Keys are locked inside the car.",
            safe_place="yes")


def make_client(tmp_path, now=""):
    tickets_path = tmp_path / "tickets.json"
    app = create_app({"TESTING": True, "TICKETS_PATH": str(tickets_path), "TRIAGE_NOW": now})
    return app.test_client(), tickets_path


@pytest.fixture
def client(tmp_path):
    return make_client(tmp_path)[0]


def submit(client, **overrides):
    return client.post("/", data={**GOOD, **overrides})


def text(response) -> str:
    return htmllib.unescape(response.get_data(as_text=True))


def follow(client, response):
    assert response.status_code == 303
    return client.get(response.headers["Location"])


def tickets_on_disk(path):
    return json.loads(path.read_text(encoding="utf-8"))


# ---- validation --------------------------------------------------------------

@pytest.mark.parametrize("field,message", [
    ("vehicle_id", "Enter the vehicle ID."),
    ("renter_name", "Enter your name."),
    ("phone", "Enter a phone number we can call you on."),
    ("location", "Tell us where you are."),
    ("issue", "Tell us what happened."),
    ("safe_place", "Choose Yes or No."),
])
def test_each_missing_field_gets_its_own_error(tmp_path, field, message):
    client, path = make_client(tmp_path)
    data = {**GOOD, field: ""}
    response = client.post("/", data=data)
    assert response.status_code == 400
    html = response.get_data(as_text=True)
    assert message in htmllib.unescape(html)
    assert f'id="{field}-error"' in html
    assert html.count('class="error" id=') == 1          # only that field is flagged
    assert len(tickets_on_disk(path)) == 2                # nothing created (seed only)


def test_empty_form_flags_all_six_fields(client):
    response = client.post("/", data={})
    html = response.get_data(as_text=True)
    assert response.status_code == 400
    assert html.count('class="error" id=') == 6


def test_whitespace_only_counts_as_missing(client):
    assert 'id="issue-error"' in client.post("/", data={**GOOD, "issue": "   "}).get_data(as_text=True)


def test_short_phone_is_rejected(client):
    response = submit(client, phone="12")
    assert "at least 7 digits" in response.get_data(as_text=True)


def test_entered_values_are_kept_after_an_error(client):
    html = submit(client, issue="").get_data(as_text=True)
    assert 'value="Amira Khan"' in html


def test_user_text_is_escaped(client):
    html = submit(client, renter_name="<script>alert(1)</script>", issue="").get_data(as_text=True)
    assert "<script>alert(1)</script>" not in html


# ---- every route through the web app ----------------------------------------

def test_auto_resolve_logs_a_simulated_unlock(tmp_path):
    client, path = make_client(tmp_path)
    page = follow(client, submit(client))
    html = text(page)
    assert 'data-route="AUTO_RESOLVE"' in html
    assert "Your vehicle is being unlocked" in html and "within about 1 minute" in html
    ticket = tickets_on_disk(path)[-1]
    assert ticket["route"] == "AUTO_RESOLVE" and ticket["status"] == "Resolved"
    assert ticket["unlock_sent"] and ticket["unlock_at"] == "2026-10-09T12:00:00"


def test_needs_verification_asks_for_exactly_one_item(client):
    html = follow(client, submit(client, vehicle_id="V-9999")).get_data(as_text=True)
    assert 'data-route="NEEDS_VERIFICATION"' in html
    assert "the correct vehicle ID" in html
    assert "full name" not in html


def test_escalate_human_shows_checklist_and_timeline(client):
    html = text(follow(client, submit(client, vehicle_id="V-1002", renter_name="Daniel Okafor")))
    assert 'data-route="ESCALATE_HUMAN"' in html
    assert "isn't connected" in html and "within 30 minutes" in html
    assert "While you wait" in html


def test_urgent_safety_tells_the_renter_we_will_call_them(client):
    html = text(follow(client, submit(client, safe_place="no")))
    assert 'data-route="URGENT_SAFETY"' in html
    assert "We'll call you on 555-0101" in html and "emergency number" in html


def test_duplicate_creates_no_ticket_and_links_the_existing_one(tmp_path):
    client, path = make_client(tmp_path)
    before = len(tickets_on_disk(path))
    response = submit(client, vehicle_id="V-1004", renter_name="Marcus Lee")
    assert response.headers["Location"].endswith("/duplicate/T-0001")
    html = text(client.get(response.headers["Location"]))
    assert 'data-route="DUPLICATE"' in html and "T-0001" in html
    assert "We haven't opened a new ticket" in html
    assert len(tickets_on_disk(path)) == before


def test_unknown_result_page_is_404(client):
    assert client.get("/result/T-9999").status_code == 404
    assert client.get("/duplicate/T-9999").status_code == 404


# ---- precedence through the web app -----------------------------------------

def test_unsafe_and_offline_vehicle_is_urgent(tmp_path):
    client, path = make_client(tmp_path)
    html = text(follow(client, submit(client, vehicle_id="V-1006", renter_name="Hannah Weber",
                                      safe_place="no")))
    assert 'data-route="URGENT_SAFETY"' in html
    assert "we can't unlock it remotely" in html
    assert tickets_on_disk(path)[-1]["unlock_sent"] is False


def test_unsafe_with_open_duplicate_creates_a_linked_urgent_ticket(tmp_path):
    client, path = make_client(tmp_path)
    before = len(tickets_on_disk(path))
    response = submit(client, vehicle_id="V-1007", renter_name="Tomás García", safe_place="no")
    assert "/result/" in response.headers["Location"]
    html = client.get(response.headers["Location"]).get_data(as_text=True)
    assert 'data-route="URGENT_SAFETY"' in html and "T-0002" in html
    tickets = tickets_on_disk(path)
    assert len(tickets) == before + 1
    assert tickets[-1]["related_ticket"] == "T-0002" and tickets[-1]["call_now"]


def test_night_clean_request_is_urgent_with_unlock_sent(tmp_path):
    client, path = make_client(tmp_path, now=NIGHT_CLOCK)
    html = follow(client, submit(client)).get_data(as_text=True)
    assert 'data-route="URGENT_SAFETY"' in html and "already unlocked" in html
    ticket = tickets_on_disk(path)[-1]
    assert ticket["status"] == "Urgent" and ticket["unlock_sent"] and ticket["call_now"]


def test_night_with_offline_vehicle_does_not_unlock(tmp_path):
    client, path = make_client(tmp_path, now=NIGHT_CLOCK)
    submit(client, vehicle_id="V-1002", renter_name="Daniel Okafor")
    ticket = tickets_on_disk(path)[-1]
    assert ticket["route"] == "URGENT_SAFETY" and not ticket["unlock_sent"]


def test_second_lockout_on_same_rental_escalates(tmp_path):
    client, path = make_client(tmp_path)
    assert tickets_on_disk(path)[-1]["id"] == "T-0002"
    first = follow(client, submit(client)).get_data(as_text=True)
    assert 'data-route="AUTO_RESOLVE"' in first                     # resolved tickets are not "open"
    second = follow(client, submit(client)).get_data(as_text=True)
    assert 'data-route="ESCALATE_HUMAN"' in second and "already been locked out" in second


def test_verification_resubmission_is_not_a_duplicate(tmp_path):
    client, _ = make_client(tmp_path)
    first = follow(client, submit(client, renter_name="Amira")).get_data(as_text=True)
    assert 'data-route="NEEDS_VERIFICATION"' in first and "full name" in first
    second = follow(client, submit(client)).get_data(as_text=True)
    assert 'data-route="AUTO_RESOLVE"' in second


def test_a_mismatched_name_is_not_logged_as_a_lockout_for_the_real_renter(tmp_path):
    client, path = make_client(tmp_path)
    follow(client, submit(client, renter_name="Jordan Smith"))        # escalated: identity not verified
    ticket = tickets_on_disk(path)[-1]
    assert ticket["route"] == "ESCALATE_HUMAN" and ticket["counts_as_lockout"] is False


# ---- ticket log and demo clock ----------------------------------------------

def test_ticket_log_lists_every_ticket_with_status_and_reason(client):
    follow(client, submit(client))
    html = client.get("/tickets").get_data(as_text=True)
    for text in ("T-0001", "T-0002", "T-0003", "Escalated", "Resolved", "Decision reason"):
        assert text in html
    assert html.index("T-0003") < html.index("T-0001")                # newest first


def test_empty_ticket_log_message(tmp_path):
    (tmp_path / "tickets.json").write_text("[]")
    client, _ = make_client(tmp_path)
    assert "No tickets yet." in client.get("/tickets").get_data(as_text=True)


def test_bad_clock_setting_fails_fast(tmp_path):
    with pytest.raises(ValueError, match="TRIAGE_NOW"):
        make_client(tmp_path, now="tomorrow-ish")


def test_ticket_ids_keep_counting_up(client):
    follow(client, submit(client, vehicle_id="V-1002", renter_name="Daniel Okafor"))
    follow(client, submit(client, vehicle_id="V-1005", renter_name="Sofia Rossi"))
    html = client.get("/tickets").get_data(as_text=True)
    assert "T-0003" in html and "T-0004" in html


def test_seed_file_is_untouched_by_runtime_writes(tmp_path):
    seed = os.path.join(DATA_DIR, "tickets.seed.json")
    before = open(seed, encoding="utf-8").read()
    client, _ = make_client(tmp_path)
    submit(client)
    assert open(seed, encoding="utf-8").read() == before


# ---- the README demo table, executed ----------------------------------------
# (name, clock, form values, expected route, text that must appear on the result page)

SCENARIOS = [
    ("1 happy path", "", dict(), "AUTO_RESOLVE", "We sent the unlock"),
    ("2 night, otherwise clean", NIGHT_CLOCK, dict(), "URGENT_SAFETY", "already unlocked your vehicle"),
    ("3 vehicle offline", "", dict(vehicle_id="V-1002", renter_name="Daniel Okafor"),
     "ESCALATE_HUMAN", "isn't connected"),
    ("4 repeat lockout", "", dict(vehicle_id="V-1003", renter_name="Priya Nair"),
     "ESCALATE_HUMAN", "already been locked out"),
    ("5 name mismatch", "", dict(vehicle_id="V-1005", renter_name="Jordan Smith"),
     "ESCALATE_HUMAN", "doesn't match"),
    ("6 partial name", "", dict(vehicle_id="V-1005", renter_name="Sofia"),
     "NEEDS_VERIFICATION", "Exactly as it appears"),
    ("7 unknown vehicle", "", dict(vehicle_id="V-9999"), "NEEDS_VERIFICATION", "Enter the correct vehicle ID"),
    ("8 no active rental", "", dict(vehicle_id="V-1008", renter_name="Liam Walsh"),
     "ESCALATE_HUMAN", "an active rental"),
    ("9 duplicate", "", dict(vehicle_id="V-1004", renter_name="Marcus Lee"), "DUPLICATE", "T-0001"),
    ("10 renter not safe", "", dict(vehicle_id="V-1005", renter_name="Sofia Rossi", safe_place="no"),
     "URGENT_SAFETY", "not in a safe place"),
    ("11 child inside", "", dict(issue="My baby is asleep in the back seat."),
     "URGENT_SAFETY", "child or pet"),
    ("12 unsafe + offline", "", dict(vehicle_id="V-1006", renter_name="Hannah Weber", safe_place="no"),
     "URGENT_SAFETY", "we can't unlock it remotely"),
    ("13 unsafe + duplicate", "", dict(vehicle_id="V-1007", renter_name="Tomás García", safe_place="no"),
     "URGENT_SAFETY", "T-0002"),
    ("14 unsafe + unknown vehicle", "", dict(vehicle_id="V-9999", safe_place="no"),
     "URGENT_SAFETY", "vehicle V-9999 isn't in the fleet"),
]


@pytest.mark.parametrize("name,clock,values,route,expected_text", SCENARIOS, ids=[s[0] for s in SCENARIOS])
def test_readme_demo_scenarios(tmp_path, name, clock, values, route, expected_text):
    client, _ = make_client(tmp_path, now=clock)
    response = submit(client, **values)
    html = text(client.get(response.headers["Location"]))
    assert f'data-route="{route}"' in html
    assert expected_text in html
    # The result screen speaks to the renter: never "the renter" or "renter's".
    assert "renter" not in html.lower()


# ---- answering the one missing detail on the result page ---------------------

def answer(client, ticket_id, value):
    return client.post(f"/result/{ticket_id}/answer", data={"answer": value})


def test_needs_verification_page_has_one_inline_field(client):
    html = text(follow(client, submit(client, vehicle_id="V-9999")))
    assert html.count('name="answer"') == 1
    assert 'action="/result/T-0003/answer"' in html
    assert 'value="V-9999"' in html                                  # what they typed is pre-filled
    assert "You don't need to fill in the form again." in html


def test_answering_a_wrong_vehicle_id_updates_the_same_ticket(tmp_path):
    client, path = make_client(tmp_path)
    follow(client, submit(client, vehicle_id="V-9999"))
    response = answer(client, "T-0003", "v-1001")
    assert response.status_code == 303 and response.headers["Location"].endswith("/result/T-0003")
    assert 'data-route="AUTO_RESOLVE"' in text(client.get(response.headers["Location"]))
    tickets = tickets_on_disk(path)
    assert len(tickets) == 3                                          # still one ticket for this request
    assert tickets[-1]["status"] == "Resolved" and tickets[-1]["vehicle_id"] == "V-1001"
    assert tickets[-1]["unlock_sent"] and tickets[-1]["created_at"] == "2026-10-09T12:00:00"


def test_answering_with_the_full_name_resolves_the_request(tmp_path):
    client, path = make_client(tmp_path)
    follow(client, submit(client, vehicle_id="V-1005", renter_name="Sofia"))
    assert 'value="Sofia"' in text(client.get("/result/T-0003"))
    answer(client, "T-0003", "Sofia Rossi")
    assert tickets_on_disk(path)[-1]["route"] == "AUTO_RESOLVE"
    assert tickets_on_disk(path)[-1]["renter_name"] == "Sofia Rossi"


def test_empty_answer_shows_an_error_beside_the_field_and_changes_nothing(tmp_path):
    client, path = make_client(tmp_path)
    follow(client, submit(client, vehicle_id="V-9999"))
    before = tickets_on_disk(path)
    response = answer(client, "T-0003", "   ")
    html = text(response)
    assert response.status_code == 400
    assert 'id="answer-error"' in html and "Enter the vehicle ID." in html
    assert tickets_on_disk(path) == before


def test_a_second_wrong_answer_asks_again(tmp_path):
    client, path = make_client(tmp_path)
    follow(client, submit(client, vehicle_id="V-9999"))
    page = text(follow(client, answer(client, "T-0003", "V-8888")))
    assert 'data-route="NEEDS_VERIFICATION"' in page and "vehicle V-8888" in page
    assert len(tickets_on_disk(path)) == 3


def test_answer_that_matches_an_open_ticket_closes_this_one_as_a_duplicate(tmp_path):
    client, path = make_client(tmp_path)
    follow(client, submit(client, vehicle_id="V-9999", renter_name="Marcus Lee"))
    page = text(follow(client, answer(client, "T-0003", "V-1004")))
    assert 'data-route="DUPLICATE"' in page and "T-0001" in page
    ticket = tickets_on_disk(path)[-1]
    assert ticket["status"] == "Closed" and ticket["related_ticket"] == "T-0001"
    assert len(tickets_on_disk(path)) == 3                            # no new ticket was added


def test_answering_a_ticket_that_is_no_longer_waiting_just_shows_it(tmp_path):
    client, path = make_client(tmp_path)
    follow(client, submit(client))                                    # T-0003, resolved
    before = tickets_on_disk(path)
    response = answer(client, "T-0003", "V-1002")
    assert response.status_code == 303 and tickets_on_disk(path) == before


def test_answer_for_unknown_ticket_is_404(client):
    assert answer(client, "T-9999", "V-1001").status_code == 404


def test_answer_cannot_change_the_phone_or_other_details(tmp_path):
    client, path = make_client(tmp_path)
    follow(client, submit(client, vehicle_id="V-9999", phone="555-0199"))
    answer(client, "T-0003", "V-1001")
    assert tickets_on_disk(path)[-1]["phone"] == "555-0199"


def test_ticket_log_stays_in_staff_voice(client):
    follow(client, submit(client, safe_place="no"))
    html = text(client.get("/tickets"))
    assert "The renter may be in an unsafe situation" in html and "CALL NOW" in html


def test_pages_use_the_inter_font(client):
    html = client.get("/").get_data(as_text=True)
    assert "fonts.googleapis.com/css2?family=Inter" in html
    assert '--font-body: "Inter"' in html


def test_header_marks_the_current_page(client):
    body = lambda path: client.get(path).get_data(as_text=True).split("<body>")[1]   # ignore the CSS
    form, log = body("/"), body("/tickets")
    assert form.count('aria-current="page"') == 1 and 'aria-current="page">New request' in form
    assert log.count('aria-current="page"') == 1 and 'aria-current="page">Ticket log' in log

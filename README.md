# Lockout triage prototype

A small Flask app that triages a "renter is locked out of the vehicle" request from a rental
operator, decides what to do, and tells the operator what happens next.

**About 1Now.** 1Now is an AI-powered fleet management platform for car rental operators. In its
own words: *"A car is the least used thing most people own. We help you turn yours into money."*
This prototype uses nothing else about the company: every timeline, checklist item and rule below
is a placeholder invented for the demo.

## Setup and run

Requires Python 3.10+. Only Flask and pytest are used.

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

flask --app app run                # then open http://127.0.0.1:5000
# or: python app.py
```

Run the tests:

```bash
python -m pytest
```

### The demo clock (night checks)

"Night" means 20:00 up to 06:00 on the app's clock. So that demos do not depend on when you run
them, the clock is **fixed at 09 Oct 2026, 12:00 by default**. The footer of every page shows the
clock in use.

| `TRIAGE_NOW` value | Effect |
|---|---|
| *(unset)* | Fixed daytime clock, 12:00 |
| `2026-10-09T23:30` | Any ISO time, e.g. to demo night |
| `real` | The machine's current time |

```bash
TRIAGE_NOW=2026-10-09T23:30 flask --app app run
```

### Resetting demo data

Tickets are saved in `data/tickets.json`, created from `data/tickets.seed.json` the first time the
app runs. Delete `data/tickets.json` to start again from the seed (two open tickets). The scenarios
below share vehicles, so **delete the file between scenarios** (or run them in separate sessions).

## What it does

1. **Intake form**: vehicle ID, renter name, phone, location, issue, "renter in a safe place" yes/no.
   Every field is required; each error appears next to its field.
2. **Triage** (`triage/`): plain rules in pure functions with no Flask imports.
3. **Result screen**: written to the renter ("you", "your vehicle"): plain-language status, reason,
   what happens next and expected timeline. If one detail is missing, a single field for it sits
   on the same page (see below).
4. **Ticket log** (`/tickets`): every ticket with status and decision reason, newest first.

### Decision order

The first rule that matches decides. All other findings are still recorded and shown as "Also noted".

| # | Condition | Outcome | Why it sits here |
|---|---|---|---|
| 1 | Any unsafe signal (see below) | **URGENT_SAFETY** | A person at risk outranks every business check, and wrongly delaying a safety case costs far more than wrongly escalating one. It also runs before the vehicle lookup, so a typo in the vehicle ID can never hide an unsafe renter. |
| 2 | Vehicle ID not in the fleet | **NEEDS_VERIFICATION**: asks for the vehicle ID | Nothing else can be checked without a vehicle. |
| 3 | Vehicle has no active rental | **ESCALATE_HUMAN** | There is no rental to verify the person against. |
| 4 | Name does not match the agreement | **ESCALATE_HUMAN** | Identity comes before anything is shared or done. |
| 4b | Name only partly matches (e.g. just "Sofia") | **NEEDS_VERIFICATION**: asks for the full name | Probably the right person, so ask for one thing. |
| 5 | An open ticket already exists for the vehicle | **DUPLICATE**: links it, creates no new ticket | The work is already in motion; this beats "offline" and "repeat" so they do not create a second ticket for the same incident. |
| 6 | Vehicle offline (telematics) | **ESCALATE_HUMAN** | A remote unlock is impossible. |
| 7 | Repeat lockout (2 or more in this rental, counting this one) | **ESCALATE_HUMAN** | A person should look before unlocking again. |
| 8 | None of the above | **AUTO_RESOLVE**: simulated unlock, logged | Everything checks out. |

**When one detail is missing.** NEEDS_VERIFICATION results show one input box right on the result
page, labelled for exactly what is missing (the vehicle ID, or the full name). Pressing **Send**
runs triage again on the *same ticket* with the new value, so there is still one ticket per
request and the renter never retypes the form. If the answer is still not good enough, the page
asks again. If it turns out an open ticket already exists, the waiting ticket is closed as a
duplicate and no extra ticket is created.

**Two voices.** The result screen speaks to the renter. The ticket log is the staff view, so it
keeps third person ("The renter may be in an unsafe situation..."), the CALL NOW flag, and the
"Unlock sent" note.

**Unsafe signals** (any one is enough): the form says the renter is *not* in a safe place; the
location or issue text mentions a child or pet, extreme weather, or a remote area; or it is night.
Keyword matching cannot read negation ("no kids") so it may over-flag, which is deliberate.

**Unsafe never gets swallowed.** An unsafe renter with an open duplicate ticket still gets
URGENT_SAFETY: a new ticket is created and linked to the existing one. An unsafe renter whose
vehicle is also offline, whose name does not match, or whose vehicle ID is wrong is still urgent.
Those problems appear under "Also noted" so the person who calls sees everything.

**Night, and the automated response.** Night alone is urgent, the moment the request lands. If night
is the *only* concern and every other check is clean (vehicle found, exact name match, online, no
repeat lockout, no open ticket), the app also sends the simulated unlock straight away, so the
renter is not left outside while the call happens. The ticket reads "Urgent" with "Unlock sent".
In every other urgent case a person decides about unlocking. Urgent and escalated results also show
a short self-help checklist for the renter to try while waiting.

**Name matching** ignores case, accents, punctuation and word order. A name is *exact* if every
word on the agreement is present (extra words like a middle name are fine), *partial* if what was
typed is only part of the agreed name, and a *mismatch* otherwise (including a shared first name
with a different surname).

## Demo scenarios

Default clock (12:00) unless stated. Fields not listed use: renter name as in the row, phone
`555-0100`, location `Mall car park, level 2`, issue `Keys are locked inside the car.`, safe place
`Yes`. The test suite (`tests/test_app.py`) runs every row below.

| # | Vehicle ID | Renter name | Other input | Expected outcome |
|---|---|---|---|---|
| 1 | V-1001 | Amira Khan | | **AUTO_RESOLVE**: unlock sent and logged. Run it twice without resetting: the second one is a repeat lockout. |
| 2 | V-1001 | Amira Khan | `TRIAGE_NOW=2026-10-09T23:30` | **URGENT_SAFETY**: call now, and the car was already unlocked (night is the only concern) |
| 3 | V-1002 | Daniel Okafor | | **ESCALATE_HUMAN**: vehicle offline |
| 4 | V-1003 | Priya Nair | | **ESCALATE_HUMAN**: repeat lockout (one earlier on this rental) |
| 5 | V-1005 | Jordan Smith | | **ESCALATE_HUMAN**: name does not match |
| 6 | V-1005 | Sofia | | **NEEDS_VERIFICATION**: one box asking only for the full name. Type `Sofia Rossi` in it and press Send: the same ticket becomes AUTO_RESOLVE. |
| 7 | V-9999 | Amira Khan | | **NEEDS_VERIFICATION**: one box asking only for the vehicle ID. Type `V-1001` and press Send: the same ticket becomes AUTO_RESOLVE. |
| 8 | V-1008 | Liam Walsh | | **ESCALATE_HUMAN**: no active rental |
| 9 | V-1004 | Marcus Lee | | **DUPLICATE**: points to T-0001, no new ticket |
| 10 | V-1005 | Sofia Rossi | Safe place: **No** | **URGENT_SAFETY** |
| 11 | V-1001 | Amira Khan | Issue: `My baby is asleep in the back seat.` | **URGENT_SAFETY** (child or pet) |
| 12 | V-1006 | Hannah Weber | Safe place: **No** | **URGENT_SAFETY**; "Also noted: vehicle is offline", no unlock |
| 13 | V-1007 | Tomás García | Safe place: **No** | **URGENT_SAFETY**: new ticket linked to open T-0002 (not swallowed as a duplicate) |
| 14 | V-9999 | Amira Khan | Safe place: **No** | **URGENT_SAFETY**; "Also noted: V-9999 is not in the fleet" |

Also worth trying: night plus an offline vehicle (V-1002 with the night clock) is urgent with no unlock.

## Assumptions

- **Storage**: one JSON file, no database. Writes are atomic. The seed file is never modified.
- **Telematics**: the `telematics_online` flag in `data/vehicles.json`. A missing flag counts as offline.
- **Unlock**: simulated. It always succeeds, writes the time to the ticket and logs a line to the
  server log. Nothing is sent anywhere. Likewise "support has been alerted" is simulated.
- **Repeat count**: the rental's `prior_lockouts` plus earlier tickets for that rental whose renter
  name matched exactly. Requests that were only asking for a missing detail, or that failed the name
  check, do not count.
- **Open ticket** means any status other than Resolved, Awaiting info or Closed. A request waiting
  for one detail therefore never blocks its own answer or a fresh resubmission.
- **Time zones**: one clock for everything; there are no per-vehicle time zones.
- **Placeholder timelines** (not real service levels):

  | Outcome | Shown to the operator |
  |---|---|
  | AUTO_RESOLVE | Within about 1 minute |
  | NEEDS_VERIFICATION | As soon as the one detail is sent |
  | ESCALATE_HUMAN | A support team member will contact you within 30 minutes |
  | URGENT_SAFETY | Call now; target a person on the phone within 5 minutes |
  | DUPLICATE | No new clock; follows the existing ticket |

- No sign-in and no notifications. The answer box on the result page is the only reply step.

## Look and feel

Colours and fonts live in one place: the `THEME` block at the top of `webapp/templates/base.html`.

**Colours** follow the 1now.ai site. They were sampled from a screenshot (the site could not be
reached from the build environment), so treat them as close, not exact:

| Use | Value | Source |
|---|---|---|
| Main text and headings | `#14253A` | Exact: read from the site's computed style |
| Orange (buttons, accents) | `#F47845` | Sampled from the screenshot |
| Header bar | `#121F2F` | Sampled |
| Page background / cards | `#FAF8F4` / `#FFFFFF` | Sampled |
| Darker orange for small text and links | `#B8481A` | Derived, so it passes contrast on white |
| Muted text, borders, hover orange, tints | `#5E6B7A`, `#E7E2D8`, `#E4642F`, `#FDF1E9` | Derived |

Style choices copied from the site: dark navy header, pill-shaped orange buttons, large rounded
white cards with soft shadows, and small orange uppercase section labels. The urgent banner stays
**red** on purpose, so it cannot be mistaken for the orange brand colour. A dark-mode palette is
included.

**Known gap: white text on the orange buttons has a contrast ratio of 2.76:1** (WCAG asks for 4.5:1).
That matches the site, so it is the default. To fix it, set `--on-brand: #14253A` in the theme
block, which gives 5.62:1. Every other colour pair passes.

**Fonts are not applied yet.** The typefaces could not be identified from a screenshot, so the app
uses the system font. Once the names are known, set `--font-body` and `--font-heading` and add the
font link above the `<style>` tag.

## Project layout

```
app.py                     Entry point (flask --app app run)
triage/
  engine.py                Decision rules: pure triage(...) -> Decision
  safety.py                Unsafe-signal detection (safe=No, keywords, night)
  messages.py              Plain-language status, reason, next steps, timelines
webapp/
  __init__.py              App factory, demo clock setting
  routes.py                Form, result, duplicate and ticket-log pages
  validation.py            Required-field checks, one message per field
  store.py                 Fleet lookup and the JSON ticket log
  simulate.py              Demo clock and the fake remote unlock
  templates/               form, result, tickets, base
data/
  vehicles.json            8 vehicles with telematics status
  rentals.json             One rental per vehicle (one is inactive)
  tickets.seed.json        Two open tickets used by the duplicate demos
tests/                     Engine, safety and app tests (pytest)
```

# Prompt and Workflow: 1Now Client Success & Support assessment

Status: **plan only. Nothing further is built until this is approved.**

## 1. Decisions to confirm
| # | Question | Default if you don't answer |
|---|---|---|
| 1 | Problem to solve | Mid-rental lockout (already prototyped) |
| 2 | Scope for this pass | Harden and extend the existing prototype, don't restart |
| 3 | Stack | Node, zero dependencies, single-page UI |
| 4 | Research gap | `1now.ai` and LinkedIn were unreachable from the sandbox; you paste key facts from them |

## 2. Workflow
1. **Research (you, outside Claude):** read 1now.ai and the LinkedIn page. Note 3 to 5 facts: customers, vocabulary, tone, features. Paste them into section 3.
2. **Plan (done):** this document.
3. **Approve:** you edit or approve the prompt below.
4. **Build (Claude Code):** run the prompt. Tests first for each new rule, then the code.
5. **Verify:** `npm test`, then run the app and click through every preset.
6. **Ship:** commit and push to `claude/fervent-rubin-r2kmgd`. Open a PR only if you ask.
7. **Submit (you):** GitHub link, Loom (see section 5), resume as PDF or Word.

## 3. The prompt for Claude Code
```
Role: You are building a working prototype for 1Now's Client Success & Support
assessment. 1Now sells fleet-management software to vehicle rental operators
(ID verification, rental agreements, tracking, direct booking).

Facts about 1Now to reflect in wording: <PASTE 3-5 FACTS FROM 1now.ai / LinkedIn>

Problem: A renter is locked out of a vehicle mid-rental. The operator must
reach support, wait, and gets no status. Support checks ID, payment,
device state and urgency by hand.

Goal: One intake-to-resolution flow that closes the loop for the operator,
including the messy edges. Working code, not a write-up.

Existing code (extend it, don't rewrite): lib/triage.js (rules),
lib/data.js (mock data), server.js (JSON API), public/index.html (UI), test/.

Add, in this order, with a failing test before each change:
1. Idempotent retries: reject double-submits within 60s using the same
   rental + issue, without a second SMS.
2. Reopen: a resolved ticket reopened by the operator within 24h goes
   straight to a human with the prior timeline attached.
3. Renter verification step: before any remote unlock, require the operator
   to confirm the renter's last 4 phone digits; 3 wrong tries lock the
   ticket to trust_and_safety.
4. Operator-facing ETA: every escalated ticket shows the next step and who
   owns it in plain language.
5. Metrics panel: counts of auto-resolved vs escalated vs reopened, by cause.

Constraints:
- Node 18+, zero dependencies, no external network calls.
- Mock data only; keep every threshold as a named constant.
- Do not remote-unlock when ID, agreement or payment checks fail unless a
  human approves.
- Keep UI plain, accessible, and working at phone width.

Done when: npm test passes, every preset in the UI behaves as the README
table says, README table is updated, and changes are committed and pushed
to claude/fervent-rubin-r2kmgd. Report anything skipped or failing.
```

## 4. Acceptance checklist
- [ ] Each new rule has a test that failed before the code
- [ ] `npm test` is green
- [ ] Every preset rental produces the documented outcome in the UI
- [ ] README routing table matches the code
- [ ] No secrets, no network calls, no new dependencies

## 5. Loom outline (about 3 minutes)
1. 20s: who you are and why support.
2. 30s: the problem, from the operator's side.
3. 90s: demo. Happy path, offline lock, unverified ID, safety flag, "still locked", skip 11 min.
4. 40s: what you'd build next and what you'd ask 1Now's team.

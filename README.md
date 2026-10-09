# Lockout Recovery: 1Now client-support prototype

**Problem:** A renter is locked out of a car mid-rental and the operator has to call support, wait, and has no idea what happens next. Support has to manually check ID, payment, device status and urgency before it can act.

**Solution:** One intake form that checks the rental, applies unlock policy, tries a remote unlock when it's safe, and otherwise routes to the right human queue with an SLA. It then *closes the loop*: the operator is asked "did it work?", a failure triggers one retry then a human handoff, and silence triggers an automatic follow-up after 10 minutes.

## Run
```
npm start        # http://localhost:3000  (Node 18+, zero dependencies)
npm test         # 14 tests on the triage logic
```
In the UI, click a preset rental to walk each branch; **Skip 11 min** demonstrates the unconfirmed-ticket follow-up.

## Routing logic (`lib/triage.js`)
| Situation | Result |
|---|---|
| Missing fields / unknown rental / another operator's rental | Rejected with a clear message (no leak of other accounts) |
| Open ticket already exists for rental | Merged, support not paged twice |
| Safety flag (child/pet, night, unsafe, medical) | **P1**, on-call human, 5 min SLA; policy gates can only be overridden by a human |
| Rental ended, ID unverified, agreement unsigned, payment failed, "won't start" | No remote unlock; routed to trust & safety / billing / roadside |
| Lock device offline (>15 min no ping) | Roadside fallback, never pretends to unlock |
| Healthy device | Remote unlock, renter SMS, audit event, 10-min check-in |
| Unlock command fails (e.g. low battery) | Escalate with flag |
| Operator says "still locked" | One retry, then human handoff |
| No confirmation in 10 min | Auto-escalate to support follow-up |

## Layout
`lib/triage.js` rules · `lib/data.js` mock data · `server.js` JSON API + static UI · `public/index.html` UI · `test/` tests.

## Next steps (not built)
Real device/SMS integrations, auth, persistence, ID-based renter callback verification before unlock, analytics on lockout causes per operator.

*Built with Claude Code. Mock data only; 1Now's real APIs and policies were not available, so the thresholds are assumptions.*

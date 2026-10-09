'use strict';
const test = require('node:test');
const assert = require('node:assert');
const { seed, MIN } = require('../lib/data');
const { createTicket, confirm, sweep } = require('../lib/triage');

const NOW = 1_700_000_000_000;
const mk = () => seed(NOW);
const base = { operatorId: 'op_1', issue: 'locked_out' };

test('validation: missing fields', () => {
  const r = createTicket(mk(), { operatorId: 'op_1' }, NOW);
  assert.equal(r.outcome, 'invalid');
});
test('rental not found / other operator\'s rental get the same answer', () => {
  const s = mk();
  assert.equal(createTicket(s, { ...base, rentalId: 'NOPE' }, NOW).outcome, 'needs_info');
  assert.equal(createTicket(s, { ...base, rentalId: 'R2001' }, NOW).outcome, 'needs_info');
});
test('happy path: auto unlock then operator confirms', () => {
  const s = mk();
  const r = createTicket(s, { ...base, rentalId: 'r1001' }, NOW);
  assert.equal(r.outcome, 'auto_unlock');
  assert.equal(r.ticket.status, 'awaiting_confirmation');
  assert.equal(confirm(s, r.ticket.id, true, NOW + MIN).ticket.status, 'resolved');
});
test('duplicate request merges', () => {
  const s = mk();
  createTicket(s, { ...base, rentalId: 'R1001' }, NOW);
  const r = createTicket(s, { ...base, rentalId: 'R1001' }, NOW + MIN);
  assert.equal(r.outcome, 'duplicate');
  assert.equal(Object.keys(s.tickets).length, 1);
});
test('offline device falls back to roadside, not a false unlock', () => {
  const r = createTicket(mk(), { ...base, rentalId: 'R1002' }, NOW);
  assert.equal(r.ticket.queue, 'roadside');
  assert.ok(r.ticket.flags.includes('device_offline'));
});
test('unverified ID is never remote unlocked', () => {
  const r = createTicket(mk(), { ...base, rentalId: 'R1003' }, NOW);
  assert.equal(r.ticket.queue, 'trust_and_safety');
  assert.equal(r.ticket.attempts, 0);
});
test('failed payment routes to billing', () => {
  assert.equal(createTicket(mk(), { ...base, rentalId: 'R1004' }, NOW).ticket.queue, 'billing');
});
test('ended rental is not unlocked', () => {
  const r = createTicket(mk(), { ...base, rentalId: 'R1005' }, NOW);
  assert.equal(r.ticket.attempts, 0);
  assert.equal(r.ticket.status, 'escalated');
});
test('unlock command failure escalates with low battery flag', () => {
  const r = createTicket(mk(), { ...base, rentalId: 'R1006' }, NOW);
  assert.ok(r.ticket.flags.includes('low_battery'));
  assert.equal(r.ticket.status, 'escalated');
});
test('safety report => P1 human, even when policy blocks unlock', () => {
  const r = createTicket(mk(), { ...base, rentalId: 'R1003', safety: ['child_or_pet_inside'] }, NOW);
  assert.equal(r.ticket.priority, 'P1');
  assert.equal(r.ticket.queue, 'on_call_human');
  assert.equal(r.ticket.slaMinutes, 5);
  assert.equal(r.ticket.attempts, 0);
});
test('safety + healthy device still attempts unlock at P1 priority', () => {
  const r = createTicket(mk(), { ...base, rentalId: 'R1001', safety: ['stranded_at_night'] }, NOW);
  assert.equal(r.ticket.priority, 'P1');
  assert.equal(r.ticket.attempts, 1);
});
test('"did not work" retries once, then hands to a human', () => {
  const s = mk();
  const t = createTicket(s, { ...base, rentalId: 'R1001' }, NOW).ticket;
  assert.equal(confirm(s, t.id, false, NOW + MIN).retried, true);
  const r = confirm(s, t.id, false, NOW + 2 * MIN);
  assert.equal(r.escalated, true);
  assert.equal(t.queue, 'roadside');
});
test('unconfirmed tickets are swept to human follow-up', () => {
  const s = mk();
  const t = createTicket(s, { ...base, rentalId: 'R1001' }, NOW).ticket;
  assert.deepEqual(sweep(s, NOW + 5 * MIN), []);
  assert.deepEqual(sweep(s, NOW + 11 * MIN), [t.id]);
  assert.equal(t.queue, 'support_followup');
});
test('confirm on wrong state / unknown ticket is rejected', () => {
  const s = mk();
  assert.ok(confirm(s, 'T-nope', true).error);
  const t = createTicket(s, { ...base, rentalId: 'R1002' }, NOW).ticket;
  assert.ok(confirm(s, t.id, true).error);
});

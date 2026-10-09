'use strict';
const { MIN } = require('./data');

const ISSUES = ['locked_out', 'key_not_working', 'app_unlock_failed', 'car_wont_start'];
const SAFETY = ['stranded_at_night', 'unsafe_location', 'child_or_pet_inside', 'medical'];
const OFFLINE_AFTER = 15 * MIN;
const CONFIRM_WINDOW = 10 * MIN;
const MAX_AUTO_ATTEMPTS = 2;
const SLA = { P1: 5, P2: 30, P3: 120 }; // minutes to first human response

// Pure-ish: mutates only the passed-in store.
function createTicket(store, input, now = Date.now()) {
  const errors = [];
  const rentalId = String(input.rentalId || '').trim().toUpperCase();
  const issue = input.issue;
  const safety = Array.isArray(input.safety) ? input.safety.filter(s => SAFETY.includes(s)) : [];
  if (!input.operatorId || !store.operators[input.operatorId]) errors.push('Unknown operator.');
  if (!rentalId) errors.push('Rental ID is required.');
  if (!ISSUES.includes(issue)) errors.push('Choose what is happening.');
  if (errors.length) return { outcome: 'invalid', errors };

  // Edge: rental not found, or belongs to another operator (do not leak existence).
  const rental = store.rentals[rentalId];
  if (!rental || rental.operatorId !== input.operatorId) {
    return { outcome: 'needs_info', errors: [`We can't find rental ${rentalId} on your account. Check the ID in your bookings list.`] };
  }

  // Edge: duplicate. Return the open ticket instead of paging support twice.
  const dupe = Object.values(store.tickets).find(t => t.rentalId === rentalId && !['resolved', 'closed'].includes(t.status));
  if (dupe) {
    addEvent(dupe, now, 'system', 'Duplicate request merged into this ticket.');
    return { outcome: 'duplicate', ticket: dupe };
  }

  const ticket = {
    id: `T-${1000 + ++store.seq}`, operatorId: input.operatorId, rentalId, issue, safety,
    notes: String(input.notes || '').slice(0, 500), createdAt: now, status: 'open', priority: 'P3',
    route: null, attempts: 0, flags: [], events: [], renterMessage: null, operatorMessage: null,
  };
  store.tickets[ticket.id] = ticket;
  addEvent(ticket, now, 'system', `Ticket opened: ${issue.replace(/_/g, ' ')} on ${rental.vehicle}.`);
  route(store, ticket, rental, now);
  return { outcome: ticket.route, ticket };
}

function route(store, t, rental, now) {
  const device = store.devices[rental.deviceId];
  const online = device && now - device.lastPing <= OFFLINE_AFTER;
  const safety = t.safety.length > 0;
  if (safety) { t.priority = 'P1'; t.flags.push('safety'); }

  // Policy gates for remote unlock.
  const blockers = [];
  if (rental.status !== 'active') blockers.push('rental is not active');
  if (!rental.idVerified) blockers.push('renter ID is not verified');
  if (!rental.agreementSigned) blockers.push('rental agreement is not signed');
  if (rental.paymentStatus !== 'paid') blockers.push('payment has not cleared');
  if (t.issue === 'car_wont_start') blockers.push('remote unlock will not fix a start problem');

  if (blockers.length && !safety) {
    t.flags.push('policy_block');
    const identity = blockers.some(b => /ID|agreement/.test(b));
    t.priority = rental.status === 'active' ? 'P2' : 'P3';
    return escalate(t, now, identity ? 'trust_and_safety' : blockers[0].includes('start') ? 'roadside' : 'billing',
      `Remote unlock withheld: ${blockers.join('; ')}.`,
      'Support will review and contact you. We did not unlock the car because the checks above must pass first.',
      rental.status === 'active' ? `Hi ${rental.renter}, we're sorting out access to your ${rental.vehicle}. Someone will call you shortly.` : null);
  }
  if (blockers.length && safety) {
    // Safety overrides policy, but only a human can approve it.
    t.flags.push('policy_override_needs_human');
    return escalate(t, now, 'on_call_human', `Safety reported. Policy gates not met (${blockers.join('; ')}); human must approve any unlock.`,
      'Safety issue reported. An on-call agent is calling you within 5 minutes. If anyone is in danger call 911 now.',
      `Hi ${rental.renter}, if you are in danger call 911. We are calling you now.`);
  }
  if (!online) {
    t.flags.push('device_offline');
    t.priority = safety ? 'P1' : 'P2';
    return escalate(t, now, safety ? 'on_call_human' : 'roadside',
      `Lock device offline (last ping ${Math.round((now - device.lastPing) / MIN)} min ago). Remote unlock impossible; dispatching fallback.`,
      'The car\'s lock hardware is offline so we can\'t unlock it remotely. Backup: use the physical key code/hidden key from your listing notes; otherwise roadside is being arranged.',
      `Hi ${rental.renter}, we can't reach your car's lock remotely. We're arranging help and will update you.`);
  }

  // Happy path: attempt remote unlock.
  attemptUnlock(store, t, device, now);
  if (t.status === 'awaiting_confirmation') return;
  // Unlock failed: edge, command rejected on an online device.
  t.flags.push('unlock_failed');
  if (device.battery < 15) t.flags.push('low_battery');
  t.priority = safety ? 'P1' : 'P2';
  escalate(t, now, safety ? 'on_call_human' : 'roadside',
    `Remote unlock command failed${device.battery < 15 ? ` (lock battery ${device.battery}%)` : ''}. Escalating.`,
    'We sent an unlock command but the lock didn\'t respond. A specialist has been assigned and will contact you.',
    `Hi ${rental.renter}, we tried unlocking your car remotely but it didn't work. Help is on the way.`);
}

function attemptUnlock(store, t, device, now) {
  t.attempts++;
  if (device.unlockWorks) {
    t.status = 'awaiting_confirmation';
    t.route = 'auto_unlock';
    t.confirmBy = now + CONFIRM_WINDOW;
    t.operatorMessage = 'Unlock command delivered. Please confirm whether the renter is in the car. We\'ll check back in 10 minutes.';
    t.renterMessage = 'Your car has been unlocked remotely. Reply HELP if it is still locked.';
    addEvent(t, now, 'system', `Remote unlock sent to device ${device.id} (attempt ${t.attempts}). Logged to rental audit trail.`);
    addEvent(t, now, 'notify', 'SMS to renter: car unlocked.');
  } else {
    addEvent(t, now, 'system', `Remote unlock attempt ${t.attempts} failed on device ${device.id}.`);
  }
}

function escalate(t, now, queue, reason, operatorMessage, renterMessage) {
  t.status = 'escalated';
  t.route = 'escalated';
  t.queue = queue;
  t.slaMinutes = SLA[t.priority];
  t.slaDueAt = now + t.slaMinutes * MIN;
  t.operatorMessage = operatorMessage;
  t.renterMessage = renterMessage;
  addEvent(t, now, 'system', reason);
  addEvent(t, now, 'route', `Routed to ${queue.replace(/_/g, ' ')} (${t.priority}, first response within ${t.slaMinutes} min).`);
  if (renterMessage) addEvent(t, now, 'notify', 'SMS to renter sent.');
  addEvent(t, now, 'notify', 'Operator notified in dashboard.');
}

// Operator closes the loop: did it work?
function confirm(store, ticketId, worked, now = Date.now()) {
  const t = store.tickets[ticketId];
  if (!t) return { error: 'Ticket not found.' };
  if (t.status !== 'awaiting_confirmation') return { error: `Ticket is ${t.status}; nothing to confirm.`, ticket: t };
  if (worked) {
    t.status = 'resolved'; t.resolvedAt = now;
    t.operatorMessage = 'Resolved. Thanks for confirming.';
    addEvent(t, now, 'operator', 'Operator confirmed renter is back in the car.');
    return { ticket: t };
  }
  const rental = store.rentals[t.rentalId];
  addEvent(t, now, 'operator', 'Operator reports unlock did NOT work.');
  const device = store.devices[rental.deviceId];
  if (t.attempts < MAX_AUTO_ATTEMPTS) {
    attemptUnlock(store, t, device, now);
    if (t.status === 'awaiting_confirmation') return { ticket: t, retried: true };
  }
  t.flags.push('repeat_failure');
  t.priority = t.safety.length ? 'P1' : 'P2';
  escalate(t, now, 'roadside', `Auto-recovery failed after ${t.attempts} attempt(s). Handing to a human.`,
    'Sorry, the automatic fix did not work. A specialist now owns this ticket and will call you.',
    `Hi ${rental.renter}, we're sending someone to help with your car.`);
  return { ticket: t, escalated: true };
}

// Nobody answered the "did it work?" check: don't let the ticket rot.
function sweep(store, now = Date.now()) {
  const moved = [];
  for (const t of Object.values(store.tickets)) {
    if (t.status === 'awaiting_confirmation' && now >= t.confirmBy) {
      t.priority = t.safety.length ? 'P1' : 'P3';
      addEvent(t, now, 'system', 'No confirmation received within 10 min.');
      escalate(t, now, 'support_followup', 'Unconfirmed auto-unlock. A human will check in with the operator.', 'We haven\'t heard back, so support will follow up with you.', null);
      moved.push(t.id);
    }
  }
  return moved;
}

function addEvent(t, at, kind, text) { t.events.push({ at, kind, text }); }

module.exports = { createTicket, confirm, sweep, ISSUES, SAFETY, SLA, CONFIRM_WINDOW };

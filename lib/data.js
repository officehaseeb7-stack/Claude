'use strict';
// Mock data. "now" is injected so tests are deterministic.
const MIN = 60 * 1000;

function seed(now = Date.now()) {
  return {
    operators: {
      op_1: { id: 'op_1', name: 'Sunset Rentals (Miami)', phone: '+1-305-555-0101' },
      op_2: { id: 'op_2', name: 'Bayline Auto', phone: '+1-305-555-0102' },
    },
    rentals: {
      R1001: { id: 'R1001', operatorId: 'op_1', renter: 'Dana K.', vehicle: '2023 Tesla Model 3', status: 'active',
        idVerified: true, agreementSigned: true, paymentStatus: 'paid', endsAt: now + 20 * 3600e3, deviceId: 'D1' },
      R1002: { id: 'R1002', operatorId: 'op_1', renter: 'Marcus T.', vehicle: '2022 Toyota Corolla', status: 'active',
        idVerified: true, agreementSigned: true, paymentStatus: 'paid', endsAt: now + 5 * 3600e3, deviceId: 'D2' },
      R1003: { id: 'R1003', operatorId: 'op_1', renter: 'Priya S.', vehicle: '2021 Honda CR-V', status: 'active',
        idVerified: false, agreementSigned: true, paymentStatus: 'paid', endsAt: now + 8 * 3600e3, deviceId: 'D3' },
      R1004: { id: 'R1004', operatorId: 'op_1', renter: 'Leo M.', vehicle: '2020 Ford Escape', status: 'active',
        idVerified: true, agreementSigned: true, paymentStatus: 'failed', endsAt: now + 3 * 3600e3, deviceId: 'D4' },
      R1005: { id: 'R1005', operatorId: 'op_1', renter: 'Ana R.', vehicle: '2022 Kia Soul', status: 'ended',
        idVerified: true, agreementSigned: true, paymentStatus: 'paid', endsAt: now - 6 * 3600e3, deviceId: 'D5' },
      R1006: { id: 'R1006', operatorId: 'op_1', renter: 'Sam W.', vehicle: '2023 Hyundai Elantra', status: 'active',
        idVerified: true, agreementSigned: true, paymentStatus: 'paid', endsAt: now + 12 * 3600e3, deviceId: 'D6' },
      R2001: { id: 'R2001', operatorId: 'op_2', renter: 'Chris B.', vehicle: '2022 BMW X1', status: 'active',
        idVerified: true, agreementSigned: true, paymentStatus: 'paid', endsAt: now + 4 * 3600e3, deviceId: 'D7' },
    },
    devices: {
      D1: { id: 'D1', lastPing: now - 1 * MIN, battery: 88, unlockWorks: true },
      D2: { id: 'D2', lastPing: now - 120 * MIN, battery: 64, unlockWorks: true },   // offline
      D3: { id: 'D3', lastPing: now - 2 * MIN, battery: 90, unlockWorks: true },
      D4: { id: 'D4', lastPing: now - 3 * MIN, battery: 75, unlockWorks: true },
      D5: { id: 'D5', lastPing: now - 5 * MIN, battery: 70, unlockWorks: true },
      D6: { id: 'D6', lastPing: now - 1 * MIN, battery: 9, unlockWorks: false },     // online, command fails
      D7: { id: 'D7', lastPing: now - 1 * MIN, battery: 80, unlockWorks: true },
    },
    tickets: {},
    seq: 0,
  };
}
module.exports = { seed, MIN };

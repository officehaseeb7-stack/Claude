'use strict';
const http = require('http');
const fs = require('fs');
const path = require('path');
const { seed } = require('./lib/data');
const { createTicket, confirm, sweep } = require('./lib/triage');

let store = seed();
let clockSkew = 0; // demo control: fast-forward time
const now = () => Date.now() + clockSkew;

function send(res, code, body, type = 'application/json') {
  res.writeHead(code, { 'Content-Type': type });
  res.end(type === 'application/json' ? JSON.stringify(body) : body);
}
function readBody(req) {
  return new Promise((ok, fail) => {
    let d = ''; req.on('data', c => { d += c; if (d.length > 1e5) req.destroy(); });
    req.on('end', () => { try { ok(d ? JSON.parse(d) : {}); } catch { fail(new Error('Bad JSON')); } });
  });
}

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url, 'http://x');
  try {
    sweep(store, now());
    if (req.method === 'GET' && (url.pathname === '/' || url.pathname === '/index.html'))
      return send(res, 200, fs.readFileSync(path.join(__dirname, 'public/index.html')), 'text/html');
    if (req.method === 'GET' && url.pathname === '/api/state')
      return send(res, 200, { now: now(), operators: store.operators, rentals: store.rentals,
        devices: store.devices, tickets: Object.values(store.tickets).reverse() });
    if (req.method === 'POST' && url.pathname === '/api/tickets')
      return send(res, 200, createTicket(store, await readBody(req), now()));
    const m = url.pathname.match(/^\/api\/tickets\/([\w-]+)\/confirm$/);
    if (req.method === 'POST' && m) {
      const { worked } = await readBody(req);
      return send(res, 200, confirm(store, m[1], !!worked, now()));
    }
    if (req.method === 'POST' && url.pathname === '/api/demo/skip-minutes') {
      const { minutes = 11 } = await readBody(req); clockSkew += minutes * 60000;
      return send(res, 200, { ok: true });
    }
    if (req.method === 'POST' && url.pathname === '/api/demo/reset') {
      store = seed(); clockSkew = 0; return send(res, 200, { ok: true });
    }
    send(res, 404, { error: 'Not found' });
  } catch (e) { send(res, 400, { error: e.message }); }
});

if (require.main === module) {
  const port = process.env.PORT || 3000;
  server.listen(port, () => console.log(`Lockout recovery prototype on http://localhost:${port}`));
}
module.exports = server;

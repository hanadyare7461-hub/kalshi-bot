from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse

from .config import settings
from .db import Database

app = FastAPI(title='Kalshi Bot Dashboard')
db = Database(settings.sqlite_path)

HTML = '''
<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>Kalshi Bot Dashboard</title>
  <style>
    body { font-family: Arial, sans-serif; margin: 24px; }
    table { border-collapse: collapse; width: 100%; margin-top: 12px; }
    th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
    th { background: #f4f4f4; }
    .cards { display: flex; gap: 16px; margin-bottom: 16px; }
    .card { border: 1px solid #ddd; padding: 12px; border-radius: 8px; min-width: 220px; }
    code { background: #f5f5f5; padding: 2px 4px; }
  </style>
</head>
<body>
  <h1>Kalshi Bot Dashboard</h1>
  <div class="cards">
    <div class="card"><h3>Realized PnL</h3><div id="realized"></div></div>
    <div class="card"><h3>Tracked Markets</h3><div id="markets_count"></div></div>
  </div>
  <h2>Markets</h2>
  <table id="markets"><thead><tr><th>Ticker</th><th>YES Pos</th><th>Avg YES</th><th>Realized PnL (¢)</th><th>Stop Armed</th><th>Updated</th></tr></thead><tbody></tbody></table>
  <h2>Recent Fills</h2>
  <table id="fills"><thead><tr><th>Time</th><th>Ticker</th><th>Side</th><th>Action</th><th>Count</th><th>Price</th></tr></thead><tbody></tbody></table>
<script>
async function refresh() {
  const r = await fetch('/api/summary');
  const data = await r.json();
  document.getElementById('realized').textContent = data.totals.realized_pnl_cents;
  document.getElementById('markets_count').textContent = data.markets.length;
  const mtbody = document.querySelector('#markets tbody');
  mtbody.innerHTML = '';
  for (const m of data.markets) {
    const tr = document.createElement('tr');
    tr.innerHTML = `<td>${m.ticker}</td><td>${m.yes_position}</td><td>${m.avg_yes_price}</td><td>${m.realized_pnl_cents}</td><td>${m.stop_armed}</td><td>${m.updated_at}</td>`;
    mtbody.appendChild(tr);
  }
  const ftbody = document.querySelector('#fills tbody');
  ftbody.innerHTML = '';
  for (const f of data.recent_fills) {
    const tr = document.createElement('tr');
    tr.innerHTML = `<td>${f.ts}</td><td>${f.ticker}</td><td>${f.side}</td><td>${f.action}</td><td>${f.count}</td><td>${f.price}</td>`;
    ftbody.appendChild(tr);
  }
}
refresh(); setInterval(refresh, 3000);
</script>
</body>
</html>
'''

@app.get('/', response_class=HTMLResponse)
def home():
    return HTML

@app.get('/api/summary', response_class=JSONResponse)
def summary():
    return db.dashboard_summary()

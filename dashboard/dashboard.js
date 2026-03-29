// --- CONFIG ---
const PORTFOLIO_URL = '../data/crypto_portfolio.json';
const GRID_URL      = '../data/crypto_grid.json';
const LOG_URL       = '../logs/trading.jsonl';

const GRID_LOWER  = 70;
const GRID_UPPER  = 100;
const GRID_LEVELS = 10;
const GRID_STEP   = (GRID_UPPER - GRID_LOWER) / (GRID_LEVELS - 1);
const GRID_CAPITAL = 500;

// --- HELPERS ---
const $  = id => document.getElementById(id);
const fmt = (n, d=2) => n == null ? 'N/A' : '$' + parseFloat(n).toFixed(d);
const fmtNum = (n, d=4) => n == null ? '--' : parseFloat(n).toFixed(d);

function fgColor(val) {
  if (val <= 20) return '#E05A5A';
  if (val <= 40) return '#E07A20';
  if (val <= 60) return '#EFA820';
  if (val <= 80) return '#8BC34A';
  return '#3DB88A';
}

function pnlColor(n) {
  if (n > 0) return 'var(--green)';
  if (n < 0) return 'var(--red)';
  return 'var(--amber)';
}

function toPacific(ts) {
  try {
    const d = new Date(ts);
    return d.toLocaleString('en-US', {
      timeZone: 'America/Los_Angeles',
      day: 'numeric', month: 'short',
      hour: '2-digit', minute: '2-digit',
      hour12: false
    });
  } catch { return ts; }
}

// --- PARSE JSONL ---
function parseJSONL(text) {
  return text.trim().split('\n').filter(l => l.trim()).map(l => {
    try { return JSON.parse(l); } catch { return null; }
  }).filter(Boolean);
}

// --- STATE ---
let allLogs = [];
let activityFilter = 'all';
let activityPage = 0;
const EVENTS_PER_PAGE = 30;

// --- LOAD ALL DATA ---
async function loadAll() {
  $('timestamp').textContent = new Date().toLocaleString('en-US', {
    timeZone: 'America/Los_Angeles',
    month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', second: '2-digit',
    hour12: false
  }) + ' PT';

  const results = await Promise.allSettled([
    fetch(PORTFOLIO_URL).then(r => r.json()),
    fetch(GRID_URL).then(r => r.json()),
    fetch(LOG_URL).then(r => r.text())
  ]);

  const portfolio = results[0].status === 'fulfilled' ? results[0].value : null;
  const grid      = results[1].status === 'fulfilled' ? results[1].value : null;
  const logs      = results[2].status === 'fulfilled' ? parseJSONL(results[2].value) : [];
  allLogs = logs;

  renderCapital(portfolio, grid);
  renderGrid(grid, logs);
  renderSignal(logs);
  renderDCA(logs);
  renderPortfolioChart(portfolio, grid, logs);
  renderGkHistory(logs);
  renderActivityLog(logs);
  renderStatusBar(portfolio, grid, logs);
}

// --- CAPITAL PANEL ---
function renderCapital(p, grid) {
  if (!p) return;

  const gridCap = p.grid_capital ?? 500;
  const dcaCap  = p.dca_reserve  ?? 450;
  const bufCap  = p.buffer        ?? 50;
  const gridPnl = grid ? (grid.pnl_usd || 0) : 0;

  // Compute holdings value using last known trade price per coin
  const holdings = p.holdings || {};
  const trades   = p.trades || [];
  const prices   = {};
  trades.forEach(t => { if (t.price) prices[t.symbol] = t.price; });

  let holdingsTotal = 0;
  const coins = ['BTC', 'ETH', 'SOL'];
  const holdingsHtml = coins.map(coin => {
    const units = holdings[coin] || 0;
    const price = prices[coin] || 0;
    const val   = units * price;
    holdingsTotal += val;
    if (units === 0) return `
      <div class="holding-row">
        <div class="holding-left">
          <span class="coin-badge">${coin}</span>
          <span class="coin-units">0.000000</span>
        </div>
        <div class="coin-value" style="color:var(--dim)">--</div>
      </div>`;
    return `
      <div class="holding-row">
        <div class="holding-left">
          <span class="coin-badge">${coin}</span>
          <span class="coin-units">${fmtNum(units, 6)}</span>
        </div>
        <div>
          <div class="coin-value">${fmt(val)}</div>
          <div class="holding-source">via DCA gatekeeper</div>
        </div>
      </div>`;
  }).join('');

  // Total = grid capital + dca reserve + holdings value + buffer + grid pnl
  const total = gridCap + dcaCap + holdingsTotal + bufCap + gridPnl;

  $('total-value').textContent = fmt(total, 0);
  $('grid-cap').textContent = fmt(gridCap, 0);
  $('dca-cap').textContent  = fmt(dcaCap, 0);
  $('holdings-cap').textContent = fmt(holdingsTotal, 0);
  $('buf-cap').textContent  = fmt(bufCap, 0);

  $('grid-bar').style.width     = (gridCap / total * 100) + '%';
  $('dca-bar').style.width      = (dcaCap  / total * 100) + '%';
  $('holdings-bar').style.width  = (holdingsTotal / total * 100) + '%';
  $('buf-bar').style.width      = (bufCap  / total * 100) + '%';

  $('holdings-list').innerHTML = holdingsHtml || '<div class="empty-state">No positions yet</div>';
}

// --- GRID PANEL ---
function renderGrid(g, logs) {
  if (!g) {
    $('grid-levels').innerHTML = '<div class="empty-state">No grid data found</div>';
    return;
  }

  const active  = g.active !== false;
  const levels  = g.levels || [];
  const pnl     = g.pnl_usd || 0;
  const solPrice = g.current_price || null;

  // Header stats
  $('sol-price').textContent     = solPrice ? '$' + parseFloat(solPrice).toFixed(2) : '--';
  $('sol-price-val').textContent = solPrice ? '$' + parseFloat(solPrice).toFixed(2) : '--';
  $('grid-pnl').textContent      = fmt(pnl);
  $('grid-pnl').style.color      = pnlColor(pnl);
  $('grid-pnl-left').textContent = fmt(pnl);
  $('grid-pnl-left').style.color = pnlColor(pnl);

  // Round trips = levels where both buy and sell filled
  const roundTrips = levels.filter(l => l.buy_filled && l.sell_filled).length;
  const avgProfit = roundTrips > 0 ? pnl / roundTrips : 0;
  const roi = (pnl / GRID_CAPITAL * 100);

  $('grid-round-trips').textContent = roundTrips;
  $('grid-pnl').textContent = fmt(pnl);
  $('grid-roi').textContent = roi.toFixed(1) + '%';
  $('grid-roi').style.color = pnlColor(roi);

  // Grid uptime: days since first grid trade in logs
  const gridTrades = (logs || []).filter(l => l.event === 'CRYPTO_GRID_TRADE');
  if (gridTrades.length > 0) {
    const firstFill = new Date(gridTrades[0].timestamp);
    const now = new Date();
    const days = Math.floor((now - firstFill) / (1000 * 60 * 60 * 24));
    $('grid-uptime').textContent = days + 'd';
  } else {
    $('grid-uptime').textContent = '--';
  }

  const fills = levels.filter(l => l.buy_filled || l.sell_filled).length;
  $('grid-fills-left').textContent = fills;

  // BUG FIX: Always sync UI to actual grid state
  if (!active) {
    $('grid-paused-banner').style.display = 'block';
    $('grid-active-badge').innerHTML = '&#x2B1B; PAUSED';
    $('grid-active-badge').style.color = 'var(--red)';
  } else {
    $('grid-paused-banner').style.display = 'none';
    $('grid-active-badge').innerHTML = '&#x25CF; ACTIVE';
    $('grid-active-badge').style.color = 'var(--green)';
  }

  // Range position indicator
  if (solPrice) {
    const pct = Math.max(0, Math.min(100, (solPrice - GRID_LOWER) / (GRID_UPPER - GRID_LOWER) * 100));
    $('range-fill').style.width = pct + '%';
    $('range-marker').style.left = 'calc(' + pct + '% - 1.5px)';
    $('range-price-label').textContent = '$' + parseFloat(solPrice).toFixed(2);
    $('range-price-label').style.color = pct < 33 ? 'var(--red)' : pct < 66 ? 'var(--amber)' : 'var(--green)';
  }

  // Price axis (reversed: high at top)
  const sorted = [...levels].sort((a, b) => b.price - a.price);
  const axisLabels = [];
  sorted.forEach((l, i) => {
    if (i % 3 === 0) axisLabels.push('<div class="axis-label">$' + parseFloat(l.price).toFixed(0) + '</div>');
    else axisLabels.push('<div class="axis-label"></div>');
  });
  $('price-axis').innerHTML = axisLabels.join('');

  // Grid levels
  const levelsHtml = sorted.map(l => {
    const price = parseFloat(l.price);
    const isCurrent = solPrice && Math.abs(price - parseFloat(solPrice)) < GRID_STEP / 2;
    const isBuy  = l.buy_filled && !l.sell_filled;
    const isSell = l.sell_filled;

    let cls = 'unfilled';
    let statusText = 'UNFILLED';
    let statusCls  = 'none';
    let barColor   = 'transparent';
    let pnlText    = '';

    if (isCurrent && !isSell) {
      cls = 'current'; statusText = '&#x25C0; PRICE'; statusCls = 'cur'; barColor = 'rgba(74,144,217,0.2)';
    } else if (isSell) {
      cls = 'sell-filled'; statusText = '&#x2713; SOLD'; statusCls = 'sell'; barColor = 'rgba(61,184,138,0.15)';
      const units = parseFloat(l.units) || 0;
      const profit = units * GRID_STEP;
      pnlText = '<span class="level-pnl pos">+' + fmt(profit) + '</span>';
    } else if (isBuy) {
      cls = 'buy-filled'; statusText = '&#x25CF; BOUGHT'; statusCls = 'buy'; barColor = 'rgba(239,168,32,0.18)';
    }

    return '<div class="grid-level ' + cls + '">' +
      '<div class="level-bar" style="background:' + barColor + ';width:100%"></div>' +
      '<span class="level-price">$' + price.toFixed(2) + '</span>' +
      '<span class="level-status ' + statusCls + '">' + statusText + '</span>' +
      (l.units ? '<span class="level-units">' + parseFloat(l.units).toFixed(4) + ' SOL</span>' : '') +
      pnlText +
    '</div>';
  }).join('');

  $('grid-levels').innerHTML = levelsHtml || '<div class="empty-state">No levels initialized</div>';
}

// --- SIGNAL PANEL ---
function renderSignal(logs) {
  const signals = logs.filter(l => l.event === 'CRYPTO_INSTITUTIONAL_SIGNAL');
  const last    = signals[signals.length - 1];

  if (!last) {
    $('step-flow').innerHTML =
      '<div class="empty-state" style="padding:16px 0">' +
        'No signal checks yet.<br>Run option 1 in run.py.' +
      '</div>';
    return;
  }

  const d    = last.data || {};
  const step = d.step_reached || 1;
  const fg   = d.scores?.fear_greed;
  const btcF = d.scores?.btc_funding;
  const ethF = d.scores?.eth_funding;
  const etf  = d.scores?.etf_7day_flow;

  // Update F&G display
  if (fg != null) {
    $('fg-value').textContent = fg;
    $('fg-bar').style.width   = fg + '%';
    $('fg-bar').style.background = fgColor(fg);
    $('fg-class').textContent = fg <= 20 ? 'Extreme Fear' : fg <= 40 ? 'Fear' : fg <= 60 ? 'Neutral' : fg <= 80 ? 'Greed' : 'Extreme Greed';
  }

  function fmtFunding(rate) {
    if (rate === null || rate === undefined) return '<span style="color:var(--red)">API error</span>';
    const pct = rate * 100;
    const color = rate < 0 ? 'var(--green)' : rate > 0 ? 'var(--red)' : 'var(--cream)';
    return '<span style="color:' + color + '">' + pct.toFixed(4) + '%</span>';
  }

  const lastTs = toPacific(last.timestamp);

  function circle(num, pass, reached) {
    if (!reached) return '<div class="step-circle pending">' + num + '</div>';
    return '<div class="step-circle ' + (pass ? 'pass' : 'fail') + '">' + (pass ? '&#x2713;' : '&#x2717;') + '</div>';
  }

  $('step-flow').innerHTML =
    '<div class="step-row">' +
      '<div class="step-line">' +
        circle(1, step >= 2, true) +
        '<div class="step-connector"></div>' +
      '</div>' +
      '<div class="step-content">' +
        '<div class="step-name">Fear &amp; Greed</div>' +
        '<div class="step-detail">Must be below 20 (Extreme Fear)</div>' +
        '<div class="step-value" style="color:' + (step >= 2 ? 'var(--green)' : 'var(--red)') + '">' +
          (fg != null ? 'Index: ' + fg : '--') +
        '</div>' +
      '</div>' +
    '</div>' +

    '<div class="step-row">' +
      '<div class="step-line">' +
        circle(2, step >= 3, step >= 2) +
        '<div class="step-connector"></div>' +
      '</div>' +
      '<div class="step-content">' +
        '<div class="step-name">Funding Rates</div>' +
        '<div class="step-detail">BTC + ETH must both be negative</div>' +
        '<div class="step-value">' +
          'BTC: ' + fmtFunding(btcF) +
          ' &middot; ETH: ' + fmtFunding(ethF) +
        '</div>' +
        '<div style="font-size:9px;color:var(--dim);margin-top:2px">Updated: ' + lastTs + '</div>' +
      '</div>' +
    '</div>' +

    '<div class="step-row">' +
      '<div class="step-line">' +
        circle(3, step >= 3 && d.action !== 'SKIP', step >= 3) +
      '</div>' +
      '<div class="step-content">' +
        '<div class="step-name">ETF Flows (Farside)</div>' +
        '<div class="step-detail">7-day rolling net flow</div>' +
        '<div class="step-value" style="color:' + (step >= 3 ? (etf > 0 ? 'var(--green)' : 'var(--red)') : 'var(--dim)') + '">' +
          (etf != null ? '7d flow: ' + (etf > 0 ? '+' : '') + etf.toFixed(0) + 'M USD' : step >= 3 ? '<span style="color:var(--red)">API error</span>' : 'Not reached') +
        '</div>' +
      '</div>' +
    '</div>';

  const action = d.action || 'SKIP';
  const actionMap = {
    'FULL':     ['full',     '&#x2705; FULL DCA &#x2014; Run Option 3 ($50)'],
    'HALF':     ['half',     '&#x26A0; HALF DCA &#x2014; Run Option 3 ($25)'],
    'ENHANCED': ['enhanced', '&#x1F6A8; ENHANCED &#x2014; Run Option 3 NOW ($75)'],
    'SKIP':     ['skip',     '&#x23ED; SKIP &#x2014; Check again tomorrow'],
  };
  const [cls, label] = actionMap[action] || actionMap['SKIP'];
  $('action-badge-wrap').innerHTML = '<div class="action-badge ' + cls + '">' + label + '</div>';

  $('status-signal').textContent = 'Last check: ' + lastTs;
}

// --- DCA LOG ---
function renderDCA(logs) {
  const signals = logs.filter(l => l.event === 'CRYPTO_INSTITUTIONAL_SIGNAL');
  const trades  = logs.filter(l => l.event === 'CRYPTO_DCA_BUY');

  $('f1-count').textContent = signals.length;
  $('f2-count').textContent = signals.filter(l => (l.data?.step_reached || 1) >= 2).length;
  $('f3-count').textContent = trades.length;

  if (!trades.length) {
    $('dca-trades').innerHTML = '<div class="empty-state">No DCA trades yet.<br>Gatekeeper waiting for conditions.</div>';
    return;
  }

  const html = [...trades].reverse().slice(0, 20).map(t => {
    const d = t.data || {};
    const ts = toPacific(t.timestamp);
    return '<div class="trade-row">' +
      '<div>' +
        '<div class="trade-coin">' + (d.symbol || '?') + '</div>' +
        '<div class="trade-detail">' + ts + ' @ $' + parseFloat(d.price||0).toFixed(2) + '</div>' +
      '</div>' +
      '<div>' +
        '<div class="trade-amount">' + fmt(d.usd_amount) + '</div>' +
        '<div class="trade-units">' + fmtNum(d.units_bought, 6) + ' units</div>' +
      '</div>' +
    '</div>';
  }).join('');

  $('dca-trades').innerHTML = html;
}

// --- PORTFOLIO CHART ---
function renderPortfolioChart(portfolio, grid, logs) {
  const canvas = $('portfolio-chart');
  const ctx = canvas.getContext('2d');

  // Set actual pixel dimensions
  const rect = canvas.parentElement.getBoundingClientRect();
  canvas.width = rect.width * 2;
  canvas.height = 400;
  ctx.scale(2, 2);
  const W = rect.width;
  const H = 200;

  // Build daily portfolio snapshots from logs
  const snapshots = [];
  let dcaReserve = 450;
  let buffer = 50;
  let gridCap = 500;
  let gridPnl = 0;
  let holdingsUnits = {};
  let holdingsPrices = {};

  // Group logs by date
  const byDate = {};
  logs.forEach(l => {
    const dateStr = l.timestamp.substring(0, 10);
    if (!byDate[dateStr]) byDate[dateStr] = [];
    byDate[dateStr].push(l);
  });

  const dates = Object.keys(byDate).sort();
  dates.forEach(dateStr => {
    const dayLogs = byDate[dateStr];

    dayLogs.forEach(l => {
      if (l.event === 'CRYPTO_DCA_BUY') {
        const d = l.data;
        dcaReserve -= d.usd_amount;
        holdingsUnits[d.symbol] = (holdingsUnits[d.symbol] || 0) + d.units_bought;
        holdingsPrices[d.symbol] = d.price;
      }
      if (l.event === 'CRYPTO_GRID_TRADE' && l.data.type === 'SELL') {
        gridPnl += l.data.profit_usd || 0;
      }
    });

    // Compute holdings value at last known prices
    let holdVal = 0;
    for (const coin in holdingsUnits) {
      holdVal += holdingsUnits[coin] * (holdingsPrices[coin] || 0);
    }

    snapshots.push({
      date: dateStr,
      value: gridCap + Math.max(0, dcaReserve) + buffer + holdVal + gridPnl
    });
  });

  if (snapshots.length < 2) {
    ctx.fillStyle = '#3A3D55';
    ctx.font = '11px IBM Plex Mono';
    ctx.textAlign = 'center';
    ctx.fillText('Not enough data points for chart', W/2, H/2);
    return;
  }

  const values = snapshots.map(s => s.value);
  const minV = Math.min(...values) * 0.98;
  const maxV = Math.max(...values) * 1.02;
  const range = maxV - minV || 1;

  const padL = 55, padR = 15, padT = 15, padB = 30;
  const chartW = W - padL - padR;
  const chartH = H - padT - padB;

  // Background
  ctx.fillStyle = '#0C0E1A';
  ctx.fillRect(0, 0, W, H);

  // Grid lines
  ctx.strokeStyle = '#1C1F35';
  ctx.lineWidth = 0.5;
  for (let i = 0; i <= 4; i++) {
    const y = padT + (chartH / 4) * i;
    ctx.beginPath();
    ctx.moveTo(padL, y);
    ctx.lineTo(W - padR, y);
    ctx.stroke();

    const val = maxV - (range / 4) * i;
    ctx.fillStyle = '#6B6F8A';
    ctx.font = '9px IBM Plex Mono';
    ctx.textAlign = 'right';
    ctx.fillText('$' + val.toFixed(0), padL - 6, y + 3);
  }

  // X-axis labels
  ctx.fillStyle = '#6B6F8A';
  ctx.font = '9px IBM Plex Mono';
  ctx.textAlign = 'center';
  const labelInterval = Math.max(1, Math.floor(snapshots.length / 6));
  snapshots.forEach((s, i) => {
    if (i % labelInterval === 0 || i === snapshots.length - 1) {
      const x = padL + (i / (snapshots.length - 1)) * chartW;
      const parts = s.date.split('-');
      ctx.fillText(parts[1] + '/' + parts[2], x, H - 8);
    }
  });

  // Line
  ctx.beginPath();
  ctx.strokeStyle = '#EFA820';
  ctx.lineWidth = 1.5;
  snapshots.forEach((s, i) => {
    const x = padL + (i / (snapshots.length - 1)) * chartW;
    const y = padT + chartH - ((s.value - minV) / range) * chartH;
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  });
  ctx.stroke();

  // Fill under line
  const lastX = padL + chartW;
  const lastY = padT + chartH - ((snapshots[snapshots.length-1].value - minV) / range) * chartH;
  ctx.lineTo(lastX, padT + chartH);
  ctx.lineTo(padL, padT + chartH);
  ctx.closePath();
  ctx.fillStyle = 'rgba(239,168,32,0.08)';
  ctx.fill();

  // Current value dot
  ctx.beginPath();
  ctx.arc(lastX, lastY, 3, 0, Math.PI * 2);
  ctx.fillStyle = '#EFA820';
  ctx.fill();

  // Current value label
  ctx.fillStyle = '#EFA820';
  ctx.font = '600 11px IBM Plex Mono';
  ctx.textAlign = 'right';
  ctx.fillText('$' + snapshots[snapshots.length-1].value.toFixed(0), lastX - 8, lastY - 8);

  // $1000 baseline
  const baseY = padT + chartH - ((1000 - minV) / range) * chartH;
  if (baseY >= padT && baseY <= padT + chartH) {
    ctx.setLineDash([4, 4]);
    ctx.strokeStyle = '#3A3D55';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(padL, baseY);
    ctx.lineTo(W - padR, baseY);
    ctx.stroke();
    ctx.setLineDash([]);
    ctx.fillStyle = '#3A3D55';
    ctx.font = '9px IBM Plex Mono';
    ctx.textAlign = 'left';
    ctx.fillText('$1,000 start', padL + 4, baseY - 4);
  }
}

// --- GATEKEEPER HISTORY ---
function toggleGkHistory() {
  const el = $('gk-history');
  const btn = $('gk-toggle');
  if (el.style.display === 'none') {
    el.style.display = 'block';
    btn.textContent = 'Hide';
  } else {
    el.style.display = 'none';
    btn.textContent = 'Show';
  }
}

function renderGkHistory(logs) {
  const signals = logs.filter(l => l.event === 'CRYPTO_INSTITUTIONAL_SIGNAL');
  const last14 = signals.slice(-14);

  if (!last14.length) {
    $('gk-history').innerHTML = '<div class="empty-state">No gatekeeper checks recorded</div>';
    return;
  }

  let html = '<table class="gk-table">' +
    '<thead><tr>' +
    '<th>Date</th>' +
    '<th>F&amp;G</th>' +
    '<th>BTC Funding</th>' +
    '<th>ETH Funding</th>' +
    '<th>ETF Flow</th>' +
    '<th>Result</th>' +
    '</tr></thead><tbody>';

  [...last14].reverse().forEach(l => {
    const d = l.data || {};
    const s = d.scores || {};
    const dateStr = toPacific(l.timestamp);
    const fg = s.fear_greed != null ? s.fear_greed : '--';
    const fgClr = s.fear_greed != null && s.fear_greed < 20 ? 'var(--green)' : s.fear_greed != null ? 'var(--red)' : 'var(--dim)';

    function fmtFR(rate) {
      if (rate === null || rate === undefined) return '<span style="color:var(--dim)">--</span>';
      const pct = rate * 100;
      const c = rate < 0 ? 'var(--green)' : 'var(--red)';
      return '<span style="color:' + c + '">' + pct.toFixed(4) + '%</span>';
    }

    const etfText = s.etf_7day_flow != null ?
      '<span style="color:' + (s.etf_7day_flow > 0 ? 'var(--green)' : 'var(--red)') + '">' + (s.etf_7day_flow > 0 ? '+' : '') + s.etf_7day_flow.toFixed(0) + 'M</span>' :
      '<span style="color:var(--dim)">--</span>';

    const action = d.action || 'SKIP';
    const isPass = action !== 'SKIP';
    const badge = isPass ?
      '<span class="badge-pass">' + action + '</span>' :
      '<span class="badge-skip">SKIP</span>';

    html += '<tr>' +
      '<td>' + dateStr + '</td>' +
      '<td style="color:' + fgClr + '">' + fg + '</td>' +
      '<td>' + fmtFR(s.btc_funding) + '</td>' +
      '<td>' + fmtFR(s.eth_funding) + '</td>' +
      '<td>' + etfText + '</td>' +
      '<td>' + badge + '</td>' +
      '</tr>';
  });

  html += '</tbody></table>';
  $('gk-history').innerHTML = html;
}

// --- ACTIVITY LOG ---
function setActivityFilter(filter) {
  activityFilter = filter;
  activityPage = 0;
  $('filter-all').className = 'filter-btn' + (filter === 'all' ? ' active' : '');
  $('filter-my').className = 'filter-btn' + (filter === 'my' ? ' active' : '');
  renderActivityLog(allLogs);
}

function setActivityPage(page) {
  activityPage = page;
  renderActivityLog(allLogs);
}

function renderActivityLog(logs) {
  let filtered = logs;
  if (activityFilter === 'my') {
    filtered = logs.filter(l =>
      l.event === 'CRYPTO_DCA_BUY' ||
      l.event === 'CRYPTO_GRID_TRADE' ||
      l.event === 'CRYPTO_GRID_PAUSED' ||
      l.event === 'CRYPTO_DCA_SKIPPED'
    );
  }

  const threeDaysAgo = new Date();
  threeDaysAgo.setDate(threeDaysAgo.getDate() - 3);
  const recent = filtered.filter(l => new Date(l.timestamp) >= threeDaysAgo);
  const displayLogs = recent.length > 0 ? recent : filtered.slice(-EVENTS_PER_PAGE);

  const reversed = [...displayLogs].reverse();
  const totalPages = Math.ceil(reversed.length / EVENTS_PER_PAGE);
  const paged = reversed.slice(activityPage * EVENTS_PER_PAGE, (activityPage + 1) * EVENTS_PER_PAGE);

  if (!paged.length) {
    $('activity-list').innerHTML = '<div class="empty-state">No activity in the last 3 days</div>';
    $('activity-pages').innerHTML = '';
    return;
  }

  const html = paged.map(l => {
    const d = l.data || {};
    const ts = toPacific(l.timestamp);
    let rowClass = 'skip';
    let typeText = '';
    let detail = '';

    if (l.event === 'CRYPTO_INSTITUTIONAL_SIGNAL') {
      const action = d.action || 'SKIP';
      rowClass = action === 'SKIP' ? 'skip' : 'signal';
      typeText = '<span style="color:' + (action === 'SKIP' ? 'var(--muted)' : 'var(--amber)') + '">Signal: ' + action + '</span>';
      detail = d.reason || '';
      if (d.scores) {
        detail += ' | F&G:' + (d.scores.fear_greed ?? '--');
      }
    } else if (l.event === 'CRYPTO_DCA_BUY') {
      rowClass = 'trade';
      typeText = '<span style="color:var(--green)">DCA Buy</span>';
      detail = d.symbol + ' $' + (d.usd_amount || 0).toFixed(2) + ' @ $' + (d.price || 0).toFixed(2) + ' (' + (d.units_bought || 0).toFixed(6) + ' units)';
    } else if (l.event === 'CRYPTO_GRID_TRADE') {
      const isBuy = d.type === 'BUY';
      rowClass = isBuy ? 'grid-buy' : 'grid-sell';
      typeText = '<span style="color:' + (isBuy ? 'var(--amber)' : 'var(--green)') + '">Grid ' + d.type + '</span>';
      detail = d.symbol + ' @ $' + (d.price || 0).toFixed(2) + ' (' + (d.units || 0).toFixed(4) + ' SOL)';
      if (d.profit_usd) detail += ' P&L: +$' + d.profit_usd.toFixed(4);
    } else if (l.event === 'CRYPTO_GRID_PAUSED') {
      rowClass = 'skip';
      typeText = '<span style="color:var(--red)">Grid Paused</span>';
      detail = d.reason || '';
    } else if (l.event === 'CRYPTO_DCA_SKIPPED') {
      rowClass = 'skip';
      typeText = '<span style="color:var(--muted)">DCA Skipped</span>';
      detail = d.reason || '';
    } else {
      typeText = '<span style="color:var(--muted)">' + l.event + '</span>';
      detail = JSON.stringify(d).substring(0, 80);
    }

    return '<div class="activity-row ' + rowClass + '">' +
      '<div class="activity-time">' + ts + '</div>' +
      '<div class="activity-type">' + typeText + '</div>' +
      '<div class="activity-detail">' + detail + '</div>' +
    '</div>';
  }).join('');

  $('activity-list').innerHTML = html;

  // Pagination
  if (totalPages > 1) {
    let pages = '<button class="page-btn" onclick="setActivityPage(' + Math.max(0, activityPage - 1) + ')"' +
      (activityPage === 0 ? ' disabled' : '') + '>&lt; Prev</button>';
    pages += '<span style="color:var(--muted);font-size:10px">' + (activityPage + 1) + '/' + totalPages + '</span>';
    pages += '<button class="page-btn" onclick="setActivityPage(' + Math.min(totalPages - 1, activityPage + 1) + ')"' +
      (activityPage >= totalPages - 1 ? ' disabled' : '') + '>Next &gt;</button>';
    $('activity-pages').innerHTML = pages;
  } else {
    $('activity-pages').innerHTML = '';
  }
}

// --- STATUS BAR ---
function renderStatusBar(p, g, logs) {
  if (p) {
    $('status-portfolio').className = 'status-ok';
    $('status-portfolio').textContent = '\u25CF Portfolio loaded';
  }
  if (g) {
    const active = g.active !== false;
    $('status-grid').textContent = 'Grid: ' + (active ? 'ACTIVE' : 'PAUSED');
    $('status-grid').style.color = active ? 'var(--green)' : 'var(--red)';
  }
}

// --- INIT ---
loadAll();
setInterval(loadAll, 60000);

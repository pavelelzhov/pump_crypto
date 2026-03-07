const statusEl = document.getElementById('status');
const tbody = document.getElementById('signals');
const reportBox = document.getElementById('report-box');
const detectorForm = document.getElementById('detector-form');
const alertForm = document.getElementById('alert-form');

function renderRow(s) {
  const tr = document.createElement('tr');
  tr.innerHTML = `
    <td>${new Date(s.timestamp).toISOString()}</td>
    <td>${s.symbol}</td>
    <td>${s.score}</td>
    <td>${s.move_15s_pct}</td>
    <td>${s.move_60s_pct}</td>
    <td>${s.volume_spike_ratio}</td>
    <td>${s.suggested_take_profit_pct}</td>
    <td>${s.suggested_stop_loss_pct}</td>
    <td>${s.price}</td>`;
  tbody.prepend(tr);
}

function renderReport(report) {
  reportBox.textContent = JSON.stringify(report, null, 2);
}

async function refreshReport() {
  const res = await fetch('/api/report');
  const data = await res.json();
  renderReport(data);
}

detectorForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  const formData = new FormData(detectorForm);
  const payload = {};
  formData.forEach((value, key) => {
    payload[key] = Number(value);
  });
  await fetch('/api/config', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  statusEl.textContent = 'Настройки детектора сохранены';
  statusEl.className = 'ok';
});

alertForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  const formData = new FormData(alertForm);
  const payload = {
    enabled: alertForm.elements.enabled.checked,
    min_score_for_alert: Number(formData.get('min_score_for_alert')),
    telegram_bot_token: String(formData.get('telegram_bot_token') || ''),
    telegram_chat_id: String(formData.get('telegram_chat_id') || ''),
    webhook_url: String(formData.get('webhook_url') || ''),
  };
  await fetch('/api/alerts', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  statusEl.textContent = 'Настройки алертов сохранены';
  statusEl.className = 'ok';
});

function connect() {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  const ws = new WebSocket(`${proto}://${location.host}/ws`);

  ws.onopen = () => {
    statusEl.textContent = 'Подключено к live stream';
    statusEl.className = 'ok';
    ws.send('ping');
  };

  ws.onmessage = (event) => {
    const msg = JSON.parse(event.data);
    if (msg.type === 'bootstrap') {
      tbody.innerHTML = '';
      msg.signals.forEach(renderRow);
      renderReport(msg.report || {});
      return;
    }
    if (msg.type === 'signal') {
      renderRow(msg.payload);
      refreshReport();
      return;
    }
    if (msg.type === 'error') {
      statusEl.textContent = `Ошибка: ${msg.message}`;
      statusEl.className = 'err';
    }
  };

  ws.onclose = () => {
    statusEl.textContent = 'Соединение закрыто, переподключение...';
    statusEl.className = 'err';
    setTimeout(connect, 3000);
  };
}

refreshReport();
connect();

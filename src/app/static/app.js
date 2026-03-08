const statusEl = document.getElementById('status');
const tbody = document.getElementById('signals');

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
      return;
    }
    if (msg.type === 'signal') {
      renderRow(msg.payload);
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

connect();

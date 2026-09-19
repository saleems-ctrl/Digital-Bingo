const socket = io();

// ---- QR / join link -------------------------------------------------
const joinUrl = window.location.origin + '/join';
document.getElementById('join-link').textContent = joinUrl;
/* eslint-disable no-undef */
new QRCode(document.getElementById('qrcode'), {
  text: joinUrl,
  width: 160,
  height: 160,
  colorDark: '#211D1B',
  colorLight: '#ffffff',
});

// ---- board setup ------------------------------------------------------
const board = document.getElementById('board');
const cells = {};
for (let n = 1; n <= 90; n++) {
  const el = document.createElement('div');
  el.className = 'cell';
  el.textContent = n;
  board.appendChild(el);
  cells[n] = el;
}

// ---- prize list setup ---------------------------------------------------
const prizeList = document.getElementById('prize-list');
const prizeRows = {};
PRIZES.forEach((p) => {
  const row = document.createElement('div');
  row.className = 'prize-row';
  row.innerHTML = `<span class="name">${PRIZE_LABELS[p]}</span><span class="status">Open</span>`;
  prizeList.appendChild(row);
  prizeRows[p] = row;
});

function renderState(state) {
  // called board
  Object.values(cells).forEach((el) => el.classList.remove('called'));
  state.called_numbers.forEach((n) => cells[n] && cells[n].classList.add('called'));

  // current number
  const emptyEl = document.getElementById('caller-empty');
  const displayEl = document.getElementById('caller-display');
  if (state.current_number) {
    emptyEl.style.display = 'none';
    displayEl.style.display = 'block';
    document.getElementById('current-number').textContent = state.current_number;
    document.getElementById('current-nickname').textContent = NICKNAMES[state.current_number] || '';
  } else {
    emptyEl.style.display = 'block';
    displayEl.style.display = 'none';
  }

  document.getElementById('remaining-hint').textContent =
    `${state.called_numbers.length} called · ${state.remaining_count} remaining`;

  document.getElementById('btn-call').disabled = state.remaining_count === 0;

  // prizes
  PRIZES.forEach((p) => {
    const winner = state.winners[p];
    const row = prizeRows[p];
    if (winner) {
      row.classList.add('won');
      row.querySelector('.status').textContent = `Won by ${winner.name}`;
    } else {
      row.classList.remove('won');
      row.querySelector('.status').textContent = 'Open';
    }
  });

  document.getElementById('player-count').textContent = state.player_count;
  document.getElementById('auto-toggle').checked = state.auto_call;
}

socket.on('connect', () => socket.emit('host_join'));
socket.on('state_update', renderState);
socket.on('player_count', (d) => {
  document.getElementById('player-count').textContent = d.count;
});
socket.on('prize_won', (d) => {
  // quick visual pulse on the relevant row already handled by state_update
});

document.getElementById('btn-call').addEventListener('click', () => {
  socket.emit('call_number');
});

document.getElementById('auto-toggle').addEventListener('change', (e) => {
  const interval = parseInt(document.getElementById('auto-interval').value, 10) || 6;
  socket.emit('toggle_auto_call', { active: e.target.checked, interval });
});

document.getElementById('btn-reset').addEventListener('click', () => {
  if (confirm('Reset the game? This clears called numbers, prizes, and gives everyone a fresh ticket.')) {
    socket.emit('reset_game');
  }
});

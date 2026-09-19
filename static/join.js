const socket = io();

let playerId = localStorage.getItem('housie_player_id') || null;
let playerName = localStorage.getItem('housie_player_name') || null;
let myTicket = null;
let calledSet = new Set();
let markedByPlayer = new Set(); // numbers this player has manually tapped

const nameScreen = document.getElementById('name-screen');
const gameScreen = document.getElementById('game-screen');

function tryAutoJoin() {
  if (playerId && playerName) {
    socket.emit('join_game', { player_id: playerId, name: playerName });
  }
}

socket.on('connect', tryAutoJoin);

document.getElementById('name-form').addEventListener('submit', (e) => {
  e.preventDefault();
  const name = document.getElementById('name-input').value.trim();
  if (!name) return;
  playerName = name;
  playerId = playerId || (crypto.randomUUID ? crypto.randomUUID() : String(Date.now()) + Math.random());
  localStorage.setItem('housie_player_id', playerId);
  localStorage.setItem('housie_player_name', playerName);
  socket.emit('join_game', { player_id: playerId, name: playerName });
});

socket.on('joined', (data) => {
  playerId = data.player_id;
  playerName = data.name;
  myTicket = data.ticket;
  markedByPlayer = new Set(); // fresh ticket (first join or game reset) starts unmarked
  localStorage.setItem('housie_player_id', playerId);
  localStorage.setItem('housie_player_name', playerName);

  nameScreen.style.display = 'none';
  gameScreen.style.display = 'block';
  document.getElementById('player-name-display').textContent = playerName;

  renderTicket();
  renderClaims(data.state.winners);
  applyState(data.state);
});

function renderTicket() {
  const el = document.getElementById('ticket');
  el.innerHTML = '';
  for (let r = 0; r < 3; r++) {
    for (let c = 0; c < 9; c++) {
      const n = myTicket[r][c];
      const cell = document.createElement('div');
      if (n === null) {
        cell.className = 'cell blank';
      } else {
        cell.className = 'cell num';
        cell.textContent = n;
        cell.dataset.num = n;
        cell.addEventListener('click', () => onTicketCellTap(n, cell));
      }
      el.appendChild(cell);
    }
  }
}

function onTicketCellTap(n, cell) {
  if (markedByPlayer.has(n)) return; // already dabbed
  if (!calledSet.has(n)) {
    showToast("That number hasn't been called yet");
    return;
  }
  markedByPlayer.add(n);
  cell.classList.remove('callable');
  cell.classList.add('marked');
}

// Reflects which cells are tappable ("callable" — called but not yet
// dabbed by this player) vs already dabbed. Marking itself only ever
// happens from a tap in onTicketCellTap, never automatically.
function updateTicketHighlights() {
  document.querySelectorAll('#ticket .cell.num').forEach((cell) => {
    const n = parseInt(cell.dataset.num, 10);
    if (markedByPlayer.has(n)) {
      cell.classList.add('marked');
      cell.classList.remove('callable');
    } else if (calledSet.has(n)) {
      cell.classList.add('callable');
    } else {
      cell.classList.remove('callable');
    }
  });
}

function renderClaims(winners) {
  const grid = document.getElementById('claims-grid');
  grid.innerHTML = '';
  PRIZES.forEach((p) => {
    const btn = document.createElement('button');
    btn.className = 'claim-btn';
    btn.dataset.prize = p;
    const winner = winners[p];
    if (winner) {
      btn.classList.add('won');
      btn.disabled = true;
      btn.innerHTML = `${PRIZE_LABELS[p]}<span class="who">Won by ${winner.name}</span>`;
    } else {
      btn.innerHTML = `${PRIZE_LABELS[p]}<span class="who">Tap to claim</span>`;
      btn.addEventListener('click', () => {
        socket.emit('claim_prize', { player_id: playerId, prize: p });
      });
    }
    grid.appendChild(btn);
  });
}

function applyState(state) {
  calledSet = new Set(state.called_numbers);
  updateTicketHighlights();
  if (state.current_number) {
    document.getElementById('current-number').textContent = state.current_number;
    document.getElementById('current-nickname').textContent = NICKNAMES[state.current_number] || '';
  }
  renderClaims(state.winners);
}

socket.on('state_update', applyState);

let toastTimer = null;
function showToast(msg) {
  const toast = document.getElementById('winner-toast');
  toast.textContent = msg;
  toast.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toast.classList.remove('show'), 3500);
}

socket.on('prize_won', (d) => {
  showToast(`🎉 ${d.name} won ${d.label}!`);
});

socket.on('claim_result', (d) => {
  if (!d.ok) {
    showToast(d.reason === 'already_won' ? 'That prize is already won.' : 'Not valid yet — keep marking!');
  }
});

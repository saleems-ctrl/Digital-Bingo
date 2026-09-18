import json
import os
import random
import uuid
from functools import wraps

from flask import Flask, render_template, request, session, redirect, url_for
from flask_socketio import SocketIO, emit

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'apollo-housie-secret-change-me')
HOST_PASSCODE = os.environ.get('HOST_PASSCODE', 'apollo123')

socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

RANGES = [(1, 9), (10, 19), (20, 29), (30, 39), (40, 49),
          (50, 59), (60, 69), (70, 79), (80, 90)]

PRIZES = ['early_five', 'top_line', 'middle_line', 'bottom_line', 'full_house']
PRIZE_LABELS = {
    'early_five': 'Early Five',
    'top_line': 'Top Line',
    'middle_line': 'Middle Line',
    'bottom_line': 'Bottom Line',
    'full_house': 'Full House',
}

# Traditional housie/tambola call-out nicknames (folklore terms used for
# decades in housie halls — not tied to any single copyrighted source).
NICKNAMES = {
    1: "Kelly's Eye", 2: "One Little Duck", 3: "Cup of Tea", 4: "Knock at the Door",
    5: "Man Alive", 6: "Half a Dozen", 7: "Lucky Seven", 8: "Garden Gate",
    9: "Doctor's Orders", 10: "Cock and Hen", 11: "Legs Eleven", 12: "One Dozen",
    13: "Unlucky for Some", 14: "Valentine's Day", 15: "Young and Keen",
    16: "Sweet Sixteen", 17: "Dancing Queen", 18: "Coming of Age",
    19: "Goodbye Teens", 20: "One Score", 21: "Royal Salute", 22: "Two Little Ducks",
    23: "Thee and Me", 24: "Two Dozen", 25: "Duck and Dive", 26: "Pick and Mix",
    27: "Gateway to Heaven", 28: "In a State", 29: "Rise and Shine",
    30: "Dirty Gertie", 31: "Get Up and Run", 32: "Buckle My Shoe",
    33: "All the Threes", 34: "Ask for More", 35: "Jump and Jive",
    36: "Three Dozen", 37: "More Than Eleven", 38: "Christmas Cake", 39: "Steps",
    40: "Life Begins", 41: "Time for Fun", 42: "Winnie the Pooh",
    43: "Down on Your Knees", 44: "Droopy Drawers", 45: "Halfway There",
    46: "Up to Tricks", 47: "Four and Seven", 48: "Four Dozen", 49: "PC",
    50: "Half a Century", 51: "Tweak of the Thumb", 52: "Weeks in a Year",
    53: "Stuck in the Tree", 54: "Clean the Floor", 55: "Snakes Alive",
    56: "Was She Worth It", 57: "Heinz Varieties", 58: "Make Them Wait",
    59: "Brighton Line", 60: "Five Dozen", 61: "Baker's Bun", 62: "Turn the Screw",
    63: "Tickle Me", 64: "Red Raw", 65: "Old Age Pension", 66: "Clickety Click",
    67: "Made in Heaven", 68: "Pick a Ticket", 69: "Either Way Up",
    70: "Three Score and Ten", 71: "Bang on the Drum", 72: "Six Dozen",
    73: "Queen Bee", 74: "Hit the Floor", 75: "Strive and Strive",
    76: "Trombones", 77: "Sunset Strip", 78: "Heaven's Gate", 79: "One More Time",
    80: "Eight and Blank", 81: "Stop and Run", 82: "Straight On Through",
    83: "Time for Tea", 84: "Seven Dozen", 85: "Staying Alive",
    86: "Between the Sticks", 87: "Torquay in Devon", 88: "Two Fat Ladies",
    89: "Nearly There", 90: "Top of the Shop",
}

# ---------------------------------------------------------------------------
# In-memory game state (single-process only — run with -w 1, see Procfile)
# ---------------------------------------------------------------------------
game = {
    'called_numbers': [],          # ordered list of numbers called so far
    'remaining_pool': set(range(1, 91)),
    'players': {},                 # player_id -> {name, ticket, sid}
    'winners': {p: None for p in PRIZES},   # prize -> {name, player_id} or None
    'auto_call': False,
}


def generate_ticket(max_tries=2000):
    """Generate a valid 90-ball housie ticket: 3 rows x 9 cols, 15 numbers,
    5 per row, numbers within each column's range and ascending top-to-bottom."""
    for _ in range(max_tries):
        counts = [1] * 9
        remaining = 15 - 9
        guard = 0
        while remaining > 0 and guard < 10000:
            c = random.randrange(9)
            if counts[c] < 3:
                counts[c] += 1
                remaining -= 1
            guard += 1
        if sum(counts) != 15:
            continue

        row_capacity = [5, 5, 5]
        assignment = [[] for _ in range(9)]
        col_order = list(range(9))
        random.shuffle(col_order)
        feasible = True
        for c in col_order:
            cnt = counts[c]
            available = [r for r in range(3) if row_capacity[r] > 0]
            if len(available) < cnt:
                feasible = False
                break
            pool = available[:]
            weights = [row_capacity[r] for r in pool]
            chosen = []
            for _ in range(cnt):
                pick = random.choices(pool, weights=weights, k=1)[0]
                idx = pool.index(pick)
                pool.pop(idx)
                weights.pop(idx)
                chosen.append(pick)
            for r in chosen:
                row_capacity[r] -= 1
            assignment[c] = chosen
        if not feasible or any(rc != 0 for rc in row_capacity):
            continue

        ticket = [[None] * 9 for _ in range(3)]
        for c in range(9):
            lo, hi = RANGES[c]
            nums = sorted(random.sample(range(lo, hi + 1), counts[c]))
            rows_for_col = sorted(assignment[c])
            for r, n in zip(rows_for_col, nums):
                ticket[r][c] = n
        return ticket
    raise RuntimeError("failed to generate a valid ticket")


def ticket_numbers(ticket):
    return [n for row in ticket for n in row if n is not None]


def check_prize(ticket, prize, called_set):
    if prize == 'early_five':
        marked = sum(1 for n in ticket_numbers(ticket) if n in called_set)
        return marked >= 5
    if prize == 'top_line':
        row = [n for n in ticket[0] if n is not None]
        return all(n in called_set for n in row)
    if prize == 'middle_line':
        row = [n for n in ticket[1] if n is not None]
        return all(n in called_set for n in row)
    if prize == 'bottom_line':
        row = [n for n in ticket[2] if n is not None]
        return all(n in called_set for n in row)
    if prize == 'full_house':
        return all(n in called_set for n in ticket_numbers(ticket))
    return False


def reset_game():
    game['called_numbers'] = []
    game['remaining_pool'] = set(range(1, 91))
    game['winners'] = {p: None for p in PRIZES}
    game['auto_call'] = False
    for p in game['players'].values():
        p['ticket'] = generate_ticket()


def public_state():
    return {
        'called_numbers': game['called_numbers'],
        'current_number': game['called_numbers'][-1] if game['called_numbers'] else None,
        'remaining_count': len(game['remaining_pool']),
        'winners': {p: game['winners'][p] for p in PRIZES},
        'auto_call': game['auto_call'],
        'player_count': len(game['players']),
    }


# ---------------------------------------------------------------------------
# HTTP routes
# ---------------------------------------------------------------------------
def host_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get('is_host'):
            return redirect(url_for('host_login'))
        return f(*args, **kwargs)
    return wrapper


@app.route('/')
def index():
    return redirect(url_for('join'))


@app.route('/host-login', methods=['GET', 'POST'])
def host_login():
    error = None
    if request.method == 'POST':
        if request.form.get('passcode') == HOST_PASSCODE:
            session['is_host'] = True
            return redirect(url_for('host'))
        error = 'Wrong passcode. Try again.'
    return render_template('host_login.html', error=error)


@app.route('/host')
@host_required
def host():
    return render_template('host.html', prizes=PRIZES, prize_labels=PRIZE_LABELS,
                            nicknames_json=json.dumps(NICKNAMES))


@app.route('/join')
def join():
    return render_template('join.html', prizes=PRIZES, prize_labels=PRIZE_LABELS,
                            nicknames_json=json.dumps(NICKNAMES))


# ---------------------------------------------------------------------------
# Socket.IO events
# ---------------------------------------------------------------------------
@socketio.on('join_game')
def on_join_game(data):
    player_id = data.get('player_id') or str(uuid.uuid4())
    name = (data.get('name') or 'Player').strip()[:40]

    if player_id in game['players']:
        p = game['players'][player_id]
        p['sid'] = request.sid
        if name:
            p['name'] = name
    else:
        game['players'][player_id] = {
            'name': name,
            'ticket': generate_ticket(),
            'sid': request.sid,
        }

    p = game['players'][player_id]
    emit('joined', {
        'player_id': player_id,
        'name': p['name'],
        'ticket': p['ticket'],
        'state': public_state(),
    })
    emit('player_count', {'count': len(game['players'])}, broadcast=True)


@socketio.on('host_join')
def on_host_join():
    if not session.get('is_host'):
        return
    emit('state_update', public_state())


@socketio.on('call_number')
def on_call_number():
    if not session.get('is_host'):
        return
    _call_one_number()


def _call_one_number():
    if not game['remaining_pool']:
        return
    number = random.choice(tuple(game['remaining_pool']))
    game['remaining_pool'].discard(number)
    game['called_numbers'].append(number)
    emit('state_update', public_state(), broadcast=True)


@socketio.on('toggle_auto_call')
def on_toggle_auto_call(data):
    if not session.get('is_host'):
        return
    game['auto_call'] = bool(data.get('active'))
    interval = max(2, int(data.get('interval', 5)))
    if game['auto_call']:
        socketio.start_background_task(_auto_call_loop, interval)
    emit('state_update', public_state(), broadcast=True)


def _auto_call_loop(interval):
    while game['auto_call'] and game['remaining_pool']:
        socketio.sleep(interval)
        if not game['auto_call']:
            break
        _call_one_number()
    game['auto_call'] = False
    socketio.emit('state_update', public_state())


@socketio.on('reset_game')
def on_reset_game():
    if not session.get('is_host'):
        return
    reset_game()
    for pid, p in game['players'].items():
        socketio.emit('joined', {
            'player_id': pid,
            'name': p['name'],
            'ticket': p['ticket'],
            'state': public_state(),
        }, room=p['sid'])
    emit('state_update', public_state(), broadcast=True)


@socketio.on('claim_prize')
def on_claim_prize(data):
    player_id = data.get('player_id')
    prize = data.get('prize')
    if prize not in PRIZES or player_id not in game['players']:
        return
    if game['winners'][prize] is not None:
        emit('claim_result', {'prize': prize, 'ok': False, 'reason': 'already_won'})
        return

    player = game['players'][player_id]
    called_set = set(game['called_numbers'])
    if check_prize(player['ticket'], prize, called_set):
        game['winners'][prize] = {'name': player['name'], 'player_id': player_id}
        emit('prize_won', {
            'prize': prize,
            'label': PRIZE_LABELS[prize],
            'name': player['name'],
        }, broadcast=True)
        emit('state_update', public_state(), broadcast=True)
    else:
        emit('claim_result', {'prize': prize, 'ok': False, 'reason': 'not_valid'})


if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=True)

# Apollo Housie — Live Digital Housie/Tambola

A live, 90-ball housie (tambola) game for up to ~200 simultaneous players.
One person runs the **caller screen** (projector/laptop); everyone else
joins the **player page** on their own phone via a link or QR code.
Numbers auto-mark on each player's ticket in real time as they're called.

## How it works

- **`/host`** — the caller screen. Shows the current number (with its
  traditional housie nickname), a 1–90 called-number board, an auto-call
  option, the QR code / link for players to join, and live prize status.
  Protected by a simple passcode (see below).
- **`/join`** — the player screen. Each player enters their name once and
  gets a unique, validly-generated ticket (3 rows × 9 columns, 15 numbers).
  Their ticket auto-marks as numbers are called — no tapping required.
  Refreshing the page keeps the same ticket (stored in the browser).
- **Prizes**: Early Five, Top Line, Middle Line, Bottom Line, Full House.
  Players tap "Claim" and the server verifies it against the numbers
  actually called — first valid claim wins, and it's locked for everyone
  else after that.

The whole game runs in server memory for one live session — there's no
database. Resetting the game (button on the caller screen) clears the
board and prizes and gives everyone a fresh ticket for another round,
without needing to redeploy.

## Add your logo

Drop your Apollo Pharmacy logo file into `static/logo.png` before you
deploy (any image works, but a transparent-background PNG or SVG-as-PNG
looks best at ~40px tall). If the file isn't there, both pages fall back
to a plain "Apollo Pharmacy" text mark automatically, so nothing breaks
either way. The red/off-white color scheme in `static/style.css` is an
approximation of Apollo's palette — tweak `--apollo` in the `:root` block
at the top of that file if you have the exact brand hex codes.

## Set a host passcode

Anyone who knows the `/host` URL can control the game, so set your own
passcode as an environment variable rather than using the default:

- `HOST_PASSCODE` — passcode for `/host` (default: `apollo123` — change this)
- `SECRET_KEY` — Flask session secret (default is fine for a one-off event,
  but set your own for anything recurring)

## Deploy to Render

This follows the same setup as the quiz app, including the two gotchas
that came up there:

1. **Push this folder to a GitHub repo**, with `app.py`, `requirements.txt`,
   `Procfile`, `templates/`, and `static/` all at the **repository root**
   (not nested inside a subfolder — that's what caused the "template not
   found" error last time).
2. On **Render**, create a new **Web Service** from that repo.
3. **Set the Python version explicitly** — Render no longer reads
   `runtime.txt`. In the service's *Environment* tab, add:
   - `PYTHON_VERSION` = `3.11.9`
   (This avoids the `start_joinable_thread` eventlet crash that happens
   on newer Python versions.)
4. Also add your `HOST_PASSCODE` (and optionally `SECRET_KEY`) as
   environment variables there.
5. **Set the Start Command explicitly** to match the Procfile — Render's
   auto-detected default (`gunicorn app:app`) does *not* include the
   eventlet worker and will break Socket.IO:
   ```
   gunicorn -k eventlet -w 1 app:app
   ```
6. Deploy. Render gives you a URL like `https://your-app.onrender.com`.
   - Caller screen: `https://your-app.onrender.com/host`
   - Player link/QR (auto-generated on the caller screen): `.../join`

**Important:** keep `-w 1` (one worker). The game state lives in that one
process's memory — more workers would each run their own separate game
and players would see inconsistent state.

## Capacity notes for 200 players

- Render's **free tier** can struggle with 200 concurrent Socket.IO
  connections (limited RAM/CPU on a shared instance) — for a real 200-person
  session, use at least the **Starter** paid instance tier for headroom.
  Free-tier instances also sleep after inactivity, so do a test call a
  few minutes before the session starts.
- Test with a smaller group first (10–20 people) to confirm the flow,
  then scale up.

## Local testing

```bash
pip install -r requirements.txt
python app.py
```
Then open `http://localhost:5000/host` and `http://localhost:5000/join`
in separate tabs (or your phone, on the same Wi-Fi, using your computer's
local IP instead of `localhost`).

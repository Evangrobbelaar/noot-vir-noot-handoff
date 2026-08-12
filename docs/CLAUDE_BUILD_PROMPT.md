
# Gameshow System — Build Prompt for Claude Code

You are building a complete gameshow management system from scratch in a new directory called
`gameshow/`. Create every file inside that folder. Read the attached firmware file
`GameController_00c.cpp` before writing any code — the TCP protocol it implements is
fixed in hardware and must be matched exactly.

---

## OVERVIEW

A live gameshow runs on one Windows PC connected to a local WiFi router. Up to 12 physical
button units (tables) connect to the PC over WiFi TCP. Each unit has 4 answer buttons (A/B/C/D)
and LED lights controlled by a sub-board. The host plays question videos on a fullscreen
display, contestants press their buttons, the server collects answers and awards points, and
a leaderboard display shows live scores.

---

## HARDWARE PROTOCOL — READ THE FIRMWARE, DO NOT GUESS

Read `GameController_00c.cpp` in full. Key facts:

- The unit connects via WiFi TCP to a configurable server IP and port (default 8080).
- On connect it expects to immediately receive the string `Connected\r\n`.
- It sends button presses in this exact format:
  `ç|EMS|<SerialNo>|<Button>|<CounterValue>|\r\n`
  where `ç` is byte value 231 (0xE7), SerialNo is the table number (integer stored in
  preferences), Button is A/B/C/D, CounterValue is an incrementing integer from the sub-board.
- Every message the server sends is forwarded raw to the sub-board via USART_1. This is how
  LED colour commands reach the physical LEDs on the unit.
- When any server message contains the substring `READY`, the unit also turns off its four
  on-board indicator LEDs.
- The unit auto-reconnects if the connection drops.
- All TCP messages are `\r\n` terminated. Buffer incoming bytes and split on `\r\n`.

---

## FILE STRUCTURE

```
gameshow/
├── config.json       — all settings, single source of truth
├── server.py         — GameServer class (TCP server, no GUI, imported as a module)
├── leaderboard.py    — pygame scoring display + IPC TCP listener
├── video_player.py   — main application: VLC + Tkinter control panel + game logic
└── main.py           — auth, pre-launch checklist, process launcher, window switcher
```

`server.py` is a module, not a script. It is imported by `video_player.py` and runs its
TCP server in daemon threads. This keeps them in the same process so they share a
`queue.Queue` event bus directly — no inter-process communication needed for game events.

`leaderboard.py` runs as a separate subprocess because pygame and Tkinter cannot share a
process cleanly.

`main.py` launches `video_player.py` and `leaderboard.py` as subprocesses, then stays alive
as a lightweight window switcher.

---

## config.json

```json
{
  "server": {
    "host": "0.0.0.0",
    "port": 8080
  },
  "leaderboard_ipc": {
    "host": "127.0.0.1",
    "port": 8081
  },
  "gameshow": {
    "video_folder": "vid",
    "access_code": "00000",
    "toggle_key": "l"
  },
  "game": {
    "max_tables": 12,
    "correct_points": 100,
    "incorrect_points": -50,
    "dance_lights_interval_ms": 1000
  }
}
```

`toggle_key` is the physical clicker button key that switches between the gameshow and
leaderboard windows.

---

## server.py — GameServer class

A plain Python class with no GUI. Exposes methods that `video_player.py` calls directly.

### Constructor: `GameServer(config: dict, event_bus: queue.Queue)`

Stores config and event_bus. Initialises:
- `self.clients = []` — list of connected button unit sockets
- `self.client_lock = threading.Lock()`
- `self.correct_answer = None`
- `self.round_answers = {}` — `{table_number: {"answer": str, "timestamp": float, "counter": int}}`
  Only the FIRST answer per table per round is stored.
- `self.leaderboard_socket = None`
- `self.leaderboard_lock = threading.Lock()`
- `self.dance_active = False`
- `self.dance_timer = None`
- `self.colour_sequence_active = False`

### `start()`

Starts two daemon threads:
1. TCP accept loop on `config["server"]["host"]` : `config["server"]["port"]`
   — `SO_REUSEADDR` on the socket.
   — On each new connection: append to clients, send `"Connected\r\n"`, spawn a per-client
     read thread.
2. Leaderboard connection loop: tries to connect persistently to
   `config["leaderboard_ipc"]["host"]` : `config["leaderboard_ipc"]["port"]`.
   On success stores socket in `self.leaderboard_socket`.
   Retries every 5 seconds if not connected. Reconnects automatically if the connection drops.

### Per-client read thread

Buffers data, splits on `\r\n`, calls `process_message(table_socket, message)` for each
complete message.

### `process_message(sock, message: str)`

Parse and handle:

**Hardware button message** — first byte is 0xE7 (ç):
  Decode with `errors='replace'`, check `parts[1] == 'EMS'`.
  `table = int(parts[2])`, `button = parts[3].strip().upper()`, `counter = int(parts[4])`.
  Timestamp receipt: `ts = time.time()`.
  If table not already in `round_answers`, store `{answer, timestamp=ts, counter}`.
  Put `{"type": "answer", "table": table, "answer": button, "counter": counter}` into
  `event_bus`.
  Send `f"@{table}:{button}\n"` to leaderboard IPC.

**`DASHBOARD-READY-TRIGGER`**:
  Call `broadcast("READY\r\n")`.
  Put `{"type": "ready_sent"}` into `event_bus`.
  Start colour sequence (see below).

**`awns_A` / `awns_B` / `awns_C` / `awns_D`**:
  Extract answer letter, set `self.correct_answer`.
  Put `{"type": "correct_answer_set", "answer": letter}` into `event_bus`.

**`PING`**: ignore silently.

**`EMS-LEDS-*` commands** arriving from video_player's direct method calls — these are
NOT received over TCP from clients. See `broadcast_leds()` below.

### `broadcast(message: str)`

Sends message to all button unit clients. Removes dead connections on error. Thread-safe.

### `broadcast_leds(target: str, r: int, g: int, b: int)`

Calls `broadcast(f"EMS-LEDS-{target}|{r}|{g}|{b}|\r\n")`.
`target` is A, B, C, D, or X (all). `r`, `g`, `b` are each 0 or 10.

### `send_ready()`

Calls `broadcast("READY\r\n")`, puts ready_sent event into queue, starts colour sequence.

### `start_round()`

Clears `round_answers` and sets `correct_answer = None`.
Sends `"CLEAR_ANSWERS\n"` to leaderboard IPC.

### `award_points(correct_pts: int, incorrect_pts: int)`

Uses `self.correct_answer` and `self.round_answers`.
Builds two lists: correct tables (answer matches) and incorrect tables.
For correct tables: send `"*1*3+100\n"` style command to leaderboard IPC.
For incorrect tables: send negative command.
Format: `"*" + "*".join(str(t) for t in tables) + sign + str(abs(pts)) + "\n"`.
Returns a summary dict `{"correct": [...], "incorrect": [...]}` so the UI can log it.
Sends point commands ONLY to leaderboard — button units do not receive score commands.

### `send_to_leaderboard(message: str)`

Thread-safe send to `self.leaderboard_socket`. No-op if not connected.
Appends `\n` if not already present.

### `client_count() -> int`

Returns `len(self.clients)` under lock.

### Colour sequence (triggered by `send_ready()`)

Uses `threading.Timer` for sequencing. Only one sequence at a time.
- Immediately: `broadcast_leds("X", 10, 0, 0)` (RED all)
- After 5s: `broadcast("READY\r\n")` again + `broadcast_leds("X", 0, 10, 0)` (GREEN all)
- After another 10s: `broadcast_leds("X", 0, 0, 10)` (BLUE all)
- After another 5s: `broadcast_leds("X", 0, 0, 0)` (all off), `colour_sequence_active = False`

### Dance lights

`start_dance()`: sets `dance_active = True`, starts 1000ms repeating pattern via
`threading.Timer`. 5 random pattern types each beat:
1. Random single row (A/B/C/D), random single colour (red/green/blue).
2. All rows (X), random single colour.
3. Rows A+C one colour, rows B+D a different colour.
4. All off (`broadcast_leds("X", 0, 0, 0)`).
5. Each of A/B/C/D independently random colour or off.

`stop_dance()`: sets `dance_active = False`, cancels timer, sends all off.

---

## leaderboard.py

Standalone pygame application. Run as: `python leaderboard.py`

Starts a TCP server on `config["leaderboard_ipc"]["port"]` (default 8081) in a daemon
thread. Accepts one persistent connection at a time. Buffers and splits on `\n`.

### IPC commands received:

**Score update**: `*1*3+100` or `*2*4-50`
  Parse table numbers (split on `*`, skip empty), parse sign and points.
  Add/subtract points from each table. Recalculate sort order. Trigger animation reset.

**Answer indicator**: `@5:B`
  Set table 5's `last_answer` to B.

**Clear answers**: `CLEAR_ANSWERS`
  Set all tables' `last_answer` to None.

### Display (1200×680, or fullscreen when toggled):

Background: dark blue `(44, 62, 80)`.

Title "Leaderboard" centered at top.

12 tables in 2 columns sorted by score descending. Each row shows:
- Position change arrow: green upward triangle (moved up), red downward triangle (moved down),
  grey horizontal dash (unchanged).
- Table name: "Table N"
- Score (right-aligned)
- Answer indicator circle (A=`(46,204,113)` green, B=`(52,152,219)` blue,
  C=`(155,89,182)` purple, D=`(230,126,34)` orange) — only shown if `last_answer` is set.

Position animation: when scores change, rows smoothly interpolate to their new vertical
positions over ~20 frames at 60fps.

Keys: F = toggle fullscreen, Escape = quit.
Window title: `"Dynamic Leaderboard"`.
Set `SDL_VIDEO_MINIMIZE_ON_FOCUS_LOSS=0` before `pygame.init()`.

Reconnects automatically if `video_player.py` restarts and the IPC connection drops.

---

## video_player.py

The main application. Imports `GameServer` from `server.py`. Creates the shared event bus.
Runs Tkinter (fullscreen video display + control panel window) and VLC.

Run as: `python video_player.py`

### Startup sequence

1. Load `config.json`.
2. Create `event_bus = queue.Queue()`.
3. Create `server = GameServer(config, event_bus)`, call `server.start()`.
4. Build Tkinter root (fullscreen, title `"Gameshow Video Display"`).
5. Build control panel (`ControlPanel` as `tk.Toplevel`).
6. Set up VLC instance with args `['--no-xlib', '--aout=directsound', '--file-caching=1000']`.
7. Call `load_video_files()`.
8. Start event consumer thread (daemon): reads from `event_bus`, dispatches to handlers.
9. Show landing screen.
10. Start pynput global keyboard listener for PageDown → `handle_next()`.
11. `root.mainloop()`.

### Video folder structure

```
vid/
  visual/
    intro.mp4
  vrae/
    A_question1.mp4   ← answer A
    B_question2.mp4   ← answer B
    ...
  countdown/
    countdown1.mp4
    countdown2.mp4
    ...
```

Load all three folders at startup. Sort each list alphabetically. If a folder does not
exist or is empty: log a warning, do not crash. The system must start without any videos
present. If `intro.mp4` is missing, skip straight to waiting screen after LANDING.
If countdown folder is empty, show a "Game Complete" dialog when countdown would start.

### Filename prefix rules (fixed, do not change)

- First character before `_` is the correct answer: `A_`, `B_`, `C_`, `D_`.
  If no such prefix, `current_answer = None`.
- `F_` prefix: skip the second pause (only first pause at 5s and third pause at 20s fire).
- `.Q_` anywhere in the filename (e.g. `intro.Q_bridge.mp4`): no pauses at all, plays
  straight through.
- Detect F_ and Q_ at video load time and store flags with each file entry.

### Game states (enum)

`LANDING`, `INTRO`, `WAITING_TO_START`, `PLAYING`, `COUNTDOWN`

### Video pause logic

VLC fires `MediaPlayerTimeChanged` on a background thread. Bridge to main thread using
`root.after(0, fn)`. Never call Tkinter or server methods directly from the VLC thread.

Three boolean flags per video (reset to False on every new video start):
`first_pause_done`, `second_pause_done`, `third_pause_done`.

In the time-changed handler (after bridging to main thread):

1. If current state is `INTRO`, return — no pauses during intro.
2. If current video is a Q_ video, return — no pauses.
3. First pause: `current_time >= 5000` and not `first_pause_done`:
   - Pause player. Set `first_pause_done = True`.
   - Call `server.broadcast_leds("X", 10, 0, 0)` (RED all).
   - Update control panel status.
4. Second pause: `current_time >= 10000` and not `second_pause_done`
   and not current video is F_ prefix:
   - Pause player. Set `second_pause_done = True`.
5. Third pause: `current_time >= 20000` and not `third_pause_done`:
   - Pause player. Set `third_pause_done = True`.
   - Call `server.start_round()` (clears answer dict for new question).
   - If `current_answer` is set, call `server.correct_answer = current_answer`
     (storing for award_points later — do NOT broadcast awns_ here, that is only
     sent manually by the operator pressing NEXT at the third pause or the T button).

### handle_next()

Called by: NEXT button, keyboard n/Down/Up/PageDown/PageUp, pynput PageDown listener.

- `LANDING`: show video frame, play intro (call `server.start_dance()`, play intro.mp4,
  set state to INTRO).
- `WAITING_TO_START`: set state to PLAYING, play first VRAE video.
- `PLAYING` or `COUNTDOWN`:
  - If `first_pause_done` and not `second_pause_done`:
    Call `server.send_ready()` (broadcasts READY + starts colour sequence).
    Resume playback.
  - Elif `third_pause_done`:
    If `current_answer` is set and not yet sent this video:
      Send `f"awns_{current_answer}\r\n"` to all button unit clients via
      `server.broadcast(f"awns_{current_answer}\r\n")`.
      Mark answer as sent for this video.
    Resume playback.
  - Else:
    Resume playback.

### on_media_end (bridged to main thread)

- `INTRO` state: call `server.stop_dance()`, call `server.broadcast_leds("X",0,0,0)`,
  show waiting screen, set state to WAITING_TO_START.
- `COUNTDOWN` state: advance countdown index, play next countdown video.
  If no more countdown videos: show "Game Complete" dialog, quit.
- `PLAYING` state and current video is Q_ type: call `server.broadcast_leds("X",0,0,0)`,
  play next VRAE video.
- `PLAYING` state normal video: play next VRAE video.

When all VRAE videos have been played, automatically enter COUNTDOWN state.

### Event consumer thread

Reads from `event_bus` (blocking `get()`). Dispatches:

- `{"type": "answer", "table": N, "answer": X, "counter": C}`:
  `root.after(0, lambda: control_panel.log_answer(N, X, C))`
  Update the answer tracking display in the control panel.

- `{"type": "correct_answer_set", "answer": X}`:
  `root.after(0, lambda: control_panel.set_correct_answer_display(X))`

- `{"type": "ready_sent"}`:
  `root.after(0, lambda: control_panel.update_status("READY sent"))`

### Control Panel (ControlPanel — tk.Toplevel, always on top, dark theme)

Dark theme throughout: background `#121212`, text `#E0E0E0`, accent buttons with
colour-coded styling. Resizable.

#### Section: Status
- Game state label, current video filename, current answer label.
- "N clients connected" label (updates every second via `root.after` loop calling
  `server.client_count()`).
- LED sequence status label.

#### Section: Game Controls
- "NEXT (N)" button — calls `handle_next()`.
- "Skip to Countdown (S)" button — calls `start_countdown()` if state is PLAYING.
- "SEND READY (T)" button — calls `server.send_ready()`.
- Volume slider 0–100 (calls `media_player.audio_set_volume()`).

#### Section: LED Controls
Grid layout — rows: A / B / C / D / ALL, columns: Red / Green / Blue.
Each button calls `server.broadcast_leds(target, r, g, b)` with appropriate values
(0 or 10 per channel). "ALL OFF" button calls `server.broadcast_leds("X", 0, 0, 0)`.

#### Section: Current Round Answers
Shows a small table of which tables have answered this round and what they answered.
Colour-coded by answer (same colours as leaderboard). Populated by answer events from
the event_bus consumer. Cleared when `server.start_round()` is called.

#### Section: Answer & Points
- "Correct Answer:" radio buttons A/B/C/D. Selecting one sets `server.correct_answer`
  directly.
- "Correct Points" entry (default from config, 100).
- "Incorrect Points" entry (default from config, -50, can be negative).
- "Award Points" button: calls `server.award_points(correct_pts, incorrect_pts)`,
  logs result in the server log area.

#### Section: Manual Points
- Table selector: 12 toggle buttons (1–12), highlighted blue when selected.
  "Select All" and "Clear All".
- Points entry (default 100).
- "+Points" and "–Points" buttons: send directly to leaderboard IPC.
- Custom command entry (e.g. `*1*2+100`) with Send button and format hint label.

#### Section: Server Log
- `scrolledtext.ScrolledText` showing all server events, answer logs, points awarded.
- "Clear Log" button.

---

## main.py

### Auth flow
Show a small Tkinter dialog (dark theme) with a password entry field and "Enter" button.
Read the correct code from config.json (`gameshow.access_code`). Allow 3 attempts.
On failure: show error, sys.exit(1). On success: proceed.

### Pre-launch checklist
Show a Tkinter dialog with three checkboxes:
- "Table button units are powered on and connected to the router"
- "PC is connected to the router (check set_network.py if needed)"
- "Physical clicker is connected"
And a "Launch" button. The Launch button is only active when all three are checked.
On Launch: destroy the Tkinter root and proceed.

### Launch subprocesses

```python
import subprocess, sys, os, time, json

config = json.load(open("config.json"))

video_proc = subprocess.Popen([sys.executable, "video_player.py"],
                               creationflags=subprocess.CREATE_NEW_CONSOLE)
leaderboard_proc = subprocess.Popen([sys.executable, "leaderboard.py"],
                                     creationflags=subprocess.CREATE_NEW_CONSOLE)
```

Wait 4 seconds for windows to appear, then enter window switcher loop.

### Window switcher loop

Uses `keyboard` library for global key hook and `win32gui` for window management.

```python
GAMESHOW_TITLE = "Gameshow Video Display"
LEADERBOARD_TITLE = "Dynamic Leaderboard"
toggle_key = config["gameshow"]["toggle_key"]  # e.g. "l"
```

State: `showing_gameshow = True`

On `toggle_key` press:
- Find both window handles by title substring using `win32gui.EnumWindows`.
- If showing_gameshow: hide gameshow (`SW_HIDE`), show leaderboard (`SW_SHOW`),
  bring leaderboard to foreground (`BringWindowToTop`). Set `showing_gameshow = False`.
- Else: hide leaderboard, show gameshow, bring to foreground.
  Set `showing_gameshow = True`.

Main loop (runs every 500ms):
- Check if leaderboard process is still alive (`leaderboard_proc.poll()`).
  If dead: restart it, wait 2s, re-find window.
- Check if video_player process is still alive. If dead: exit — the show is over.

On `q` key: terminate both subprocesses, sys.exit(0).

---

## MESSAGE FORMAT REFERENCE

All TCP messages end with `\r\n` unless noted. Leaderboard IPC messages end with `\n`.

| Direction | Format | Example | Meaning |
|---|---|---|---|
| Button unit → Server | `ç\|EMS\|N\|X\|C\|` | `ç\|EMS\|5\|B\|1229\|` | Table 5 pressed B |
| Server → Button units | `Connected` | — | Greeting on connect |
| Server → Button units | `READY` | — | Arms buttons (LEDs off) |
| Server → Button units | `EMS-LEDS-T\|R\|G\|B\|` | `EMS-LEDS-A\|10\|0\|0\|` | Row A = RED |
| Server → Button units | `EMS-LEDS-X\|0\|10\|0\|` | — | ALL rows = GREEN |
| Server → Button units | `awns_A` | — | Correct answer broadcast |
| video_player → server (internal) | method call | `server.send_ready()` | Trigger READY |
| Server → Leaderboard IPC | `@5:B` | — | Table 5 answered B |
| Server → Leaderboard IPC | `*1*3+100` | — | Tables 1+3 get +100 |
| Server → Leaderboard IPC | `CLEAR_ANSWERS` | — | Clear answer dots |

LED targets: A, B, C, D = individual rows. X = all rows simultaneously.
LED values: R/G/B each 0 (off) or 10 (full on). Normally only one channel is non-zero.

---

## GAME FLOW SUMMARY

1. main.py: auth → checklist → launches video_player.py + leaderboard.py → window switcher.
2. video_player shows landing screen (blank/dot).
3. Operator presses NEXT → intro video plays with dance lights.
4. Intro ends → waiting screen.
5. Operator presses NEXT → PLAYING state, first VRAE video starts.
6. At 5s: video auto-pauses, all LEDs go RED. Operator presses NEXT → READY broadcast
   (arms button units, colour sequence: RED→GREEN→BLUE→OFF), video resumes.
7. At 10s: video auto-pauses (unless F_ video). Operator presses NEXT → resumes.
8. At 20s: video auto-pauses. `start_round()` clears answer dict. Operator presses NEXT
   → broadcasts `awns_<answer>`, video resumes.
9. Video ends → next VRAE video. Repeat from step 6.
10. All VRAE videos done → COUNTDOWN state, countdown videos play in sequence.
11. All countdown videos done → "Game Complete" dialog → quit.

Operator can switch the TV between gameshow window and leaderboard window at any time
by pressing the configured toggle key on the physical clicker.

---

## DEPENDENCIES

```
pip install python-vlc pygame pywin32 pynput keyboard psutil
```

VLC must be installed on the system (64-bit, matching Python architecture).

---

## RULES

1. Hardware protocol is immutable. The firmware is flashed on physical hardware.
   Every byte, format, and newline convention must match exactly.

2. Video pause timing (5s / 10s / 20s) and filename prefix rules (A_, F_, Q_) must
   be preserved exactly. Do not invent variations.

3. Never call Tkinter methods from a VLC callback thread or a TCP thread.
   Always use `root.after(0, fn)` to bridge to the main thread.

4. Leaderboard IPC uses a persistent TCP connection. Never open and close a new
   connection per message.

5. Use `queue.Queue` throughout. No asyncio.

6. Handle missing video folders gracefully — log a warning, do not crash.

7. Write `requirements.txt` with all pip dependencies.

8. Write a `README.md` explaining how to start the system (`python main.py`) and the
   expected folder structure under `vid/`.

---

## BUILD ORDER

Read `GameController_00c.cpp` first.
Then build files in this order:
`config.json` → `server.py` → `leaderboard.py` → `video_player.py` → `main.py`
→ `requirements.txt` → `README.md`

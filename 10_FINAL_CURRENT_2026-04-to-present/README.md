# Gameshow System

A live gameshow management system for Windows. Up to 12 physical button units (tables)
connect via WiFi TCP. The host plays question videos on a fullscreen display, contestants
press A/B/C/D buttons, the server collects answers, awards points, and a leaderboard
shows live scores.

---

## Requirements

- Windows 10/11
- Python 3.11+
- VLC media player (64-bit, matching your Python architecture): https://www.videolan.org/vlc/

Install Python dependencies:

```
pip install -r requirements.txt
```

---

## Starting the system

```
python main.py
```

This will:
1. Prompt for the access code (default: `00000`, set in `config.json`)
2. Show a pre-launch checklist
3. Launch `video_player.py` and `leaderboard.py` as separate windows
4. Enter the window-switching loop

---

## Video folder structure

Place video files under `gameshow/vid/`:

```
vid/
  visual/
    intro.mp4            ← plays on first NEXT press, with dance lights
  vrae/
    A_question1.mp4      ← answer is A (prefix = correct answer)
    B_question2.mp4      ← answer is B
    C_question3.mp4      ← answer is C
    D_question4.mp4      ← answer is D
    F_question5.mp4      ← fastest finger (no options; operator awards points manually)
    intro.Q_bridge.mp4   ← .Q_ anywhere: no pauses, plays straight through
  countdown/
    countdown1.mp4
```

**Filename prefix rules:**

| Prefix | Effect |
|--------|--------|
| `A_`, `B_`, `C_`, `D_` | Multiple choice — correct answer; 3 pauses |
| `F_` | Fastest finger — no correct-answer prefix; 2 pauses |
| `.Q_` anywhere | Bridge/transition — no pauses, auto-advances |

---

## Game flow

**Multiple choice (`A_` / `B_` / `C_` / `D_`):**

1. Video starts playing (intro section)
2. **Pause 1** (configurable, default 5 s) — press NEXT → buttons armed (READY sent), question appears
3. **Pause 2** (default 12 s) — press NEXT → options + countdown play
4. **Pause 3** (default 50 s) — end of timeout, just before answer — press NEXT → points auto-awarded, answer revealed
5. Video plays to end → holds on last frame → press NEXT for next question

**Fastest finger (`F_`):**

1. Video starts playing
2. **Pause 1** (default 5 s) — press NEXT → buttons armed, question appears
3. **Pause 2** (default 12 s) — press NEXT → countdown plays through → answer → holds on last frame
4. Operator uses Manual Points panel to award or deduct points → press NEXT for next question

All pause timestamps are configurable live in the **Pause Timing** section of the control panel.

---

## Window switching

Press the configured `toggle_key` (default: `l`) on the physical clicker to switch the
display between the gameshow video window and the leaderboard window.

Press `q` to quit all processes.

---

## config.json settings

| Key | Default | Description |
|-----|---------|-------------|
| `server.port` | 8080 | TCP port button units connect to |
| `leaderboard_ipc.port` | 8081 | Internal IPC port |
| `gameshow.access_code` | `00000` | Launch password |
| `gameshow.toggle_key` | `l` | Clicker key to switch windows |
| `game.correct_points` | 100 | Points for correct answer |
| `game.incorrect_points` | -50 | Points for incorrect answer |
| `game.dance_lights_interval_ms` | 1000 | LED dance beat interval |
| `timing.mc_pause1_ms` | 5000 | MC: pause between intro and question |
| `timing.mc_pause2_ms` | 12000 | MC: pause between question and options |
| `timing.mc_pause3_ms` | 50000 | MC: pause at end of timeout before answer |
| `timing.ff_pause1_ms` | 5000 | FF: pause between intro and question |
| `timing.ff_pause2_ms` | 12000 | FF: pause between question and countdown |

---

## Button unit setup (ESP32 firmware)

Use a Bluetooth terminal app to configure each unit before the show:

```
SSID:your_wifi_name
PASS:your_wifi_password
SERVER:192.168.1.x        ← PC's IP on the local router
PORT:8080
SN:1                      ← Table number (1–12)
SAVE
```

The unit will restart and connect automatically.

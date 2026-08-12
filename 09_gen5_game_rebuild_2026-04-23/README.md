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
cd gameshow
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
    A_question1.mp4      ← answer is A (filename prefix determines correct answer)
    B_question2.mp4      ← answer is B
    C_question3.mp4      ← answer is C
    D_question4.mp4      ← answer is D
    F_bridge.mp4         ← F_ prefix: skips the 10s pause only
    intro.Q_bridge.mp4   ← .Q_ anywhere: no pauses at all, plays straight through
  countdown/
    countdown1.mp4
    countdown2.mp4
```

**Filename prefix rules:**

| Prefix | Effect |
|--------|--------|
| `A_`, `B_`, `C_`, `D_` | Correct answer for this question |
| `F_` | Skip the 10-second pause; pauses at 5s and 20s only |
| `.Q_` anywhere | No pauses; plays straight through |

---

## Game flow

1. Launch → landing screen (dot)
2. NEXT → intro video with dance lights
3. Intro ends → "Ready to Start" screen
4. NEXT → first question video starts
5. **At 5 s**: video pauses, LEDs go RED → press NEXT to broadcast READY (arms button units)
6. **At 10 s**: video pauses → press NEXT to resume (skipped for F_ videos)
7. **At 20 s**: video pauses, round starts → press NEXT to reveal correct answer and resume
8. Video ends → next question. After all questions → countdown videos → "Game Complete"

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

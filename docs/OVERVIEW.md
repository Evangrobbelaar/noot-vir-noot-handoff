# Noot-vir-Noot Gameshow — Complete System Overview

Everything collected in one place. Read this before touching any code.

---

## What Is This System?

A live music-quiz gameshow ("Noot-vir-Noot" style). Up to 12 physical table units connect to
one Windows PC over WiFi. Each table has 4 buttons (A/B/C/D) with RGB LEDs. The operator
plays question videos, contestants press buttons, a server collects answers, and a leaderboard
shows live scores on a second screen/window.

---

## Hardware Summary

- **Button units**: ESP32 + sub-board with 4 RGB-LED buttons per table (A/B/C/D)
- **Connection**: WiFi TCP to PC, port 8080
- **Firmware**: `hardware/firmware/GameController_00c.cpp` — DO NOT CHANGE, flashed on hardware
- **Naming**: "Janus Game Controller", project 166, firmware version 00c
- **Max tables**: 12, each assigned a Serial Number 1–12 via Bluetooth config
- **Full protocol details**: `docs/HARDWARE_REFERENCE.md`

### Protocol Quick Reference

| Direction | Format | Example |
|---|---|---|
| Unit → PC (button press) | `\xE7\|EMS\|<SN>\|<Btn>\|<Counter>\|\r\n` | `ç\|EMS\|5\|B\|1229\|` |
| PC → Unit (connect greeting) | `Connected\r\n` | — |
| PC → Unit (arm buttons) | `READY\r\n` | — |
| PC → Unit (LED colour) | `EMS-LEDS-<T>\|<R>\|<G>\|<B>\|\r\n` | `EMS-LEDS-X\|10\|0\|0\|` |
| PC → Unit (correct answer) | `awns_<Letter>\r\n` | `awns_A\r\n` |
| PC → Leaderboard (score) | `*1*3+100\n` or `*2-50\n` | — |
| PC → Leaderboard (answer dot) | `@5:B\n` | — |

LED values: R/G/B each `0` or `10` only. Target: `A`/`B`/`C`/`D` or `X` (all).

---

## Folder Structure

```
noot-vir-noot-FINAL/
├── OVERVIEW.md               ← this file
├── docs/
│   ├── CLAUDE_BUILD_PROMPT.md    ← GOLDEN BUILD SPEC — complete system requirements
│   ├── HARDWARE_REFERENCE.md     ← hardware protocol reference
│   ├── README_gen5.md            ← gen5 readme
│   └── Gameshow System Documentation.docx
├── hardware/
│   ├── firmware/
│   │   ├── GameController_00c.cpp    ← CURRENT firmware (flashed on units)
│   │   └── GameController_00a.cpp.txt ← older firmware version
│   └── photos/
│       └── DJI_*.JPG               ← physical setup photos
├── gen1_gameshowold/         ← Oldest version
├── gen2_gamebegin/           ← Added access codes + simulators
├── gen3_gamnootnew/          ← Build prompt written, button tester, test reports
├── gen4_gameshowapp/         ← Simplified running app (4 files)
├── gen5_game_rebuild/        ← LATEST — clean rebuild, best code (START HERE)
└── gen6_flutter/             ← Flutter app attempt (abandoned)
```

---

## Code Generations

### gen1_gameshowold — Oldest Python version
**Key files:** `gameshow.py`, `gameshow2.py`, `bsd.py`, `leaderboard.py`, `cli.py`, `launch.py`, `all.py`
- Monolithic structure, everything mixed together
- `bsd.py` = BSD (Button Server/Driver) — handles TCP with button units
- `leaderboard.py` = pygame display
- Multiple launcher scripts tried different approaches
- Config in `config/config.json` and `config/game_config.json`

### gen2_gamebegin — Access codes + simulators
**Key files:** `gameshow2.py`, `bsd.py`, `leaderboard.py`, `access_codes.py`, `toggler.py`, `main.py`
**New in this gen:**
- Access code system (SQLite DB + CSV)
- `bsd_simulator.py`, `gameshow2_simulator.py`, `leaderboard_simulator.py` — for testing without hardware
- `sort22.py` — question video sorting utility
- `toggler.py` — window switching between gameshow and leaderboard

### gen3_gamnootnew — Test infrastructure + build prompt
**Key files:** `gameshow2.py`, `bsd.py`, `leaderboard.py`, `button_simulator.py`, `button_tester.py`
**New in this gen:**
- `CLAUDE_BUILD_PROMPT.md` — complete system specification written here
- `button_simulator.py` / `button_tester.py` — test hardware communication
- `gameshow_tester.py` — automated test suite
- `test_report.html` / `test_report.json` — test results
- `set_network.py` — PC network switching utility

### gen4_gameshowapp — Simplified working app
**Key files:** `Gameshow_launcher.py`, `gameshow2.py`, `bsd.py`, `leaderboard.py`, `toggler.py`
- Stripped down to just what's needed to run
- `Gameshow_launcher.py` = combined launcher with auth
- This is what was running on the Desktop before the rebuild

### gen5_game_rebuild — LATEST & BEST (start here)
**Key files:** `main.py`, `server.py`, `video_player.py`, `leaderboard.py`, `config.json`
**Architecture (clean separation of concerns):**
```
main.py          → auth dialog + pre-launch checklist + subprocess launcher + window switcher
server.py        → GameServer class (TCP, no GUI, imported by video_player)
video_player.py  → VLC + Tkinter fullscreen display + ControlPanel + game state machine
leaderboard.py   → pygame 1200×680 display + IPC TCP listener (runs as separate process)
config.json      → single source of truth for all settings
```
**Status:** Complete rebuild following the CLAUDE_BUILD_PROMPT.md spec. Most complete and
cleanest code. Has not been fully tested on live hardware yet.

**Additional files:**
- `show_builder.py` — utility to organise/sort video files before a session
- `set_network.py` — PC network switching utility
- `test_suite.py` — automated test suite
- `requirements.txt` — pip dependencies
- `network_profile.json` — saved static IP settings

### gen6_flutter — Flutter app (abandoned)
**Key files:** `main.dart`, `network_utils.dart`, `pubspec.yaml`
- Attempted a Flutter-based control app (presumably for tablet/phone operator control)
- Only 2 Dart source files — incomplete/proof of concept
- Not worth pursuing unless you want a mobile operator interface

---

## Video Folder Structure

```
vid/
├── visual/
│   └── intro.mp4              ← intro video (plays with dance lights)
├── vrae/                      ← question videos
│   ├── A_songname.mp4         ← correct answer = A
│   ├── B_songname.mp4         ← correct answer = B
│   ├── F_songname.mp4         ← F_ prefix: skip the 10s pause
│   └── intro.Q_bridge.mp4    ← .Q_ in name: no pauses, plays straight through
└── countdown/
    ├── F_1.mp4                ← countdown videos play in alphabetical order
    └── F_2.mp4
```

### Video Pause Logic (FIXED — matches firmware expectations)
1. **5 seconds** → auto-pause, LEDs go RED → operator presses NEXT → READY broadcast + colour sequence
2. **10 seconds** → auto-pause (skip if filename starts with `F_`) → operator presses NEXT → resume
3. **20 seconds** → auto-pause → `start_round()` clears answers → operator presses NEXT → broadcasts `awns_<answer>` + resume

---

## Game Flow

```
1. Run: python main.py
2. Enter access code (default: 00000)
3. Check three pre-launch boxes → Launch
4. Two windows open: "Gameshow Video Display" (fullscreen) + "Game Control Panel"
5. Leaderboard runs in its own window
6. Toggle key (default 'l') switches between gameshow and leaderboard
7. NEXT button / keyboard n / PageDown clicker advances through states
```

**States:** LANDING → INTRO → WAITING_TO_START → PLAYING → COUNTDOWN → Game Complete

---

## Dependencies

```
pip install python-vlc pygame pywin32 pynput keyboard psutil
```
VLC must be installed system-wide (64-bit, matching Python architecture).

---

## What Still Needs Work (for the final version)

Based on analysis of all generations:

1. **Test on live hardware** — gen5 has never been tested with real button units
2. **`show_builder.py`** — question video management UI is in gen5 but may need polish
3. **Access code system** — gen5 uses a simple single code; gen2/gen3 had multi-user DB-based codes
4. **`toggler.py`** — gen4 had a standalone toggler; gen5 integrates it into main.py
5. **`set_network.py`** — present in gen5, should be tested with actual network adapter names
6. **Video Q_ detection** — gen5 logic may be too broad (checks multiple patterns)
7. **Leaderboard animation** — gen5 has smooth position interpolation; verify 60fps on target PC
8. **Leaderboard IPC reconnect** — gen5 handles reconnect; verify no message loss during reconnect

---

## Quick Start (gen5)

```bash
cd gen5_game_rebuild
pip install -r requirements.txt
python main.py
```

Make sure VLC is installed and the `vid/` folder structure is in place.
To test without hardware: open `test_suite.py` and run the simulator tests.

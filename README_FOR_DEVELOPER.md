# Noot-vir-Noot Gameshow — Developer Handoff Package

**Prepared by:** Evan Grobbelaar  
**Date:** 2026-08-13  
**Contact:** evangrobbelaar@gmail.com

---

## What This Is

A live music-quiz gameshow system ("Noot-vir-Noot" style) built for Windows.  
Up to 12 physical table units connect over WiFi. Each unit has 4 RGB-LED buttons (A/B/C/D).  
The operator plays question videos, contestants press buttons, and a leaderboard shows live scores.

**Hardware:** ESP32 TCP button units (firmware fixed — DO NOT reflash)  
**Server:** Python 3.12 on Windows  
**Video playback:** VLC via python-vlc  
**Leaderboard display:** pygame  
**Question video generator:** PyQt5 + ffmpeg + Pillow

---

## Start Here (Active Codebase)

```
10_FINAL_CURRENT_2026-04-to-present/
```

This is the folder currently in development. It contains:

| File | Purpose |
|---|---|
| `main.py` | Auth + pre-launch checklist + subprocess launcher |
| `server.py` | GameServer TCP class (imported by video_player) |
| `video_player.py` | VLC + Tkinter fullscreen display + control panel |
| `leaderboard.py` | Pygame 1200×680 leaderboard + IPC TCP listener |
| `question_editor.py` | PyQt5 GUI to create/edit question videos |
| `config.json` | Single source of truth for all settings |
| `launch.bat` | Correct launcher (clears PYTHONHOME pollution) |
| `launch_editor.bat` | Launcher for question video editor |

### Run

```bat
launch.bat
```

Or in PowerShell:

```powershell
$env:PYTHONHOME=""; $env:PYTHONPATH=""; python main.py
```

> **IMPORTANT:** ZKBioTime software on this PC pollutes `PYTHONHOME` → always clear it first.

### Dependencies

```
pip install python-vlc pygame pywin32 pynput keyboard psutil PyQt5 Pillow numpy
```

VLC must be installed system-wide (64-bit, matching Python architecture).  
ffmpeg must be on PATH (for question video generation).

---

## Version History

| Folder | Generation | Date | What Changed |
|---|---|---|---|
| `01_gen0_flutter_2025-01/` | Gen 0 — Flutter | Jan 2025 | Flutter control app attempt (abandoned) |
| `02_gen0b_earliest_proto_2025-02/` | Gen 0b — Earliest proto | Feb 2025 | Earliest Python prototype (files not recovered) |
| `03_gen1_gameshowold_2025-02-to-03/` | Gen 1 | Feb–Mar 2025 | First live version: gameshow.py + bsd.py + leaderboard.py |
| `04_gen1b_transition_tt_2025-04/` | Gen 1b — Transition | Apr 2025 | VRAE question type consolidation (files not recovered) |
| `05_gen2_gamebegin_2025-04-to-2026-04/` | Gen 2 | Apr 2025 – Apr 2026 | Added access codes (SQLite), simulators |
| `06_gen2_gmail_snapshot_2026-02-09/` | Gen 2 — Gmail Snapshot | 9 Feb 2026 | Snapshot emailed to Janus de Jager — 5 key files |
| `07_gen3_gamnootnew_2026-04/` | Gen 3 | Apr 2026 | Build prompt written, button tester, test reports |
| `08_gen4_gameshowapp_2026-04/` | Gen 4 | Apr 2026 | Stripped production app, combined launcher |
| `09_gen5_game_rebuild_2026-04-23/` | Gen 5 | 23 Apr 2026 | Clean rebuild, separated concerns, best architecture |
| `10_FINAL_CURRENT_2026-04-to-present/` | FINAL (active) | Apr 2026 – present | Gen5 base + question video editor + BGM/SFX support |

---

## Hardware Reference

See `hardware/firmware/GameController_00c.cpp` — **DO NOT REFLASH** (flashed on physical units).  
See `docs/HARDWARE_REFERENCE.md` for full protocol docs.

### Protocol Quick Reference

| Direction | Format | Example |
|---|---|---|
| Unit → PC (button press) | `\xE7\|EMS\|<SN>\|<Btn>\|<Counter>\|\r\n` | `ç\|EMS\|5\|B\|1229\|` |
| PC → Unit (arm buttons) | `READY\r\n` | — |
| PC → Unit (LED colour) | `EMS-LEDS-<T>\|<R>\|<G>\|<B>\|\r\n` | `EMS-LEDS-X\|10\|0\|0\|` |
| PC → Unit (correct answer) | `awns_<Letter>\r\n` | `awns_A\r\n` |
| PC → Leaderboard (score) | `*1*3+100\n` | table 1 of 3 scores +100 |
| PC → Leaderboard (answer dot) | `@5:B\n` | table 5 pressed B |

LED values: R/G/B each `0` or `10` only. Target: `A`/`B`/`C`/`D` or `X` (all).

---

## What Still Needs Work

Based on analysis of all generations — items for continued development:

1. **Live hardware test** — Gen5/FINAL has never been fully tested with real button units
2. **Access code system** — FINAL uses single code; gen2/gen3 had multi-user SQLite DB codes
3. `set_network.py` — PC network switching, needs testing with actual adapter names
4. **Video Q_ detection** — video_player.py logic may be too broad (check multiple patterns)
5. **Leaderboard animation** — verify 60fps smooth on target PC
6. **Leaderboard IPC reconnect** — verify no message loss during reconnect
7. **question_editor.py** — question video generator fully built but only tested solo; verify ffmpeg path on target machine
8. **`vid/` folder** — question videos not included in handoff (large files). The folder structure must be:
   ```
   vid/vrae/    ← question videos (A_name.mp4, B_name.mp4, F_name.mp4)
   vid/visual/  ← intro.mp4
   vid/countdown/ ← F_1.mp4, F_2.mp4 etc.
   ```

---

## Gen 2 Gmail Files (folder 06)

These 5 files were sent by Evan to Janus de Jager on 2026-02-09 as an email attachment.  
They represent the working gen2 system at that point:

| File | Description |
|---|---|
| `install_gameshow (1).py` | Installer: copies files to Desktop, creates SQLite access_codes.db, generates Gameshow.bat launcher + desktop shortcut |
| `gameshow2.py` | Main video player (VLC + tkinter, pause at 5/10/20s, pynput PageDown) |
| `bsd.py` | Button server (tkinter TCP, LED controls, award points, dance lights) |
| `leaderboard.py` | Pygame leaderboard with named pipe IPC |
| `toggler.py` | Window toggler between gameshow/leaderboard (pywin32 + psutil) |

---

## Docs

| File | Description |
|---|---|
| `docs/OVERVIEW.md` | Complete system overview (read first) |
| `docs/CLAUDE_BUILD_PROMPT.md` | Full system requirements specification |
| `docs/HARDWARE_REFERENCE.md` | ESP32 button unit protocol reference |
| `docs/README_gen5.md` | Gen5 specific readme |
| `docs/Gameshow System Documentation.docx` | Original Word documentation |

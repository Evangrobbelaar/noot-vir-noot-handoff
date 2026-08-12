# Noot-vir-Noot — Game Flow & Product Brief

**Prepared by:** Evan Grobbelaar  
**Date:** August 2026  
**Audience:** Developer / Technical Team  
**Version:** 2.0

> This document describes the **game experience** — what the show looks like, how it flows, and what players and the host see and do. It is not a technical spec. The developer decides implementation; this document describes the desired outcome.

---

## 1. What This Is

Noot-vir-Noot is a live, in-person music and general knowledge quiz show. Contestant teams sit at numbered tables. Each table has a physical button unit with four RGB-LED buttons — A, B, C, and D. A question video plays on a large screen at the front of the room. Everyone watches the same screen.

The show is run by a single operator (the host) on a laptop. The operator uses a handheld wireless clicker to control the pacing of the game. The clicker is the only thing the host needs to hold during the show.

---

## 2. Physical Setup

- **1–2 large displays** — projector or TV at the front. Both show identical content via HDMI. Everyone — contestants and audience — watches the same screen at all times.
- **Operator laptop** — the laptop screen is the private control view. The extended display(s) show the game. Connected via HDMI screen extend.
- **Up to 12 tables**, each with one button unit: 4 RGB-LED buttons (A, B, C, D).
- **Teams of 2–4 people** per table share one button unit. One person presses on behalf of the team.
- **Handheld clicker** — the host's only control device.
  - Right click / forward = correct / next
  - Left click / back = wrong
- All button units connect over **WiFi** — no cables to tables.

---

## 3. Show Structure

| | |
|---|---|
| Rounds per show | 3–5 |
| Questions per round | 5–10 |
| Total show duration | 45 min – 1.5 hours |
| Tables | Up to 12, teams of 2–4 |

**Content types:**
- Question videos (music clip, photo, general knowledge)
- Dance break videos (between rounds — no interaction, plays through)
- Instructional videos (explain upcoming round rules — plays through)

---

## 4. Show Flow (Start to Finish)

### Step 1 — Landing Screen
The big screen shows a holding visual while the venue fills. The leaderboard can be toggled on here to show table numbers and names.

### Step 2 — Intro Video
Host triggers the intro. An energetic opener plays. During this, **all button units cycle through random colour patterns** — a light show signalling the show is starting. At the end of the intro, **all buttons switch off**.

### Step 3 — Questions
Repeated for each question. See **Section 5** for the full question flow.

### Step 4 — Leaderboard (host's discretion)
At any point the host can toggle the big screen to the **animated leaderboard** — after a question, between rounds, or to build tension. Toggle back when ready to continue.

### Step 5 — Dance Breaks & Instructional Videos
Between rounds. These play through completely with no pauses and no button interaction.

### Step 6 — End of Show
Host triggers the final leaderboard — a full animated ranking. Winner announced. Button units do a celebration colour sequence.

---

## 5. Question Flow (Per Question)

Every question video is made up of **five segments** that play in sequence. The video auto-pauses at two specific points — the host clicks the clicker to advance.

```
┌─────────────────────────────────┐
│  Segment 1: Category Reveal     │  "AUDIO QUESTION" / "PHOTO QUESTION" / "GENERAL KNOWLEDGE"
│  Buttons: off                   │
└──────────────┬──────────────────┘
               │
        ⏸ PAUSE 1 — host clicks to continue
               │
┌──────────────▼──────────────────┐
│  Segment 2: Question (~5 s)     │  Music clip / photo reveal / question text
│  Buttons: solid RED (not yet)   │
└──────────────┬──────────────────┘
               │  (no pause — flows directly into countdown)
┌──────────────▼──────────────────┐
│  Segment 3: Countdown (5 s*)    │  MC: A/B/C/D cards + timer  |  FF: "FASTEST FINGER!" + timer
│  Buttons: ARMED (see below)     │  * duration is configurable per question
└──────────────┬──────────────────┘
               │
        ⏸ PAUSE 2 — auto-pauses when timer hits zero
               │
┌──────────────▼──────────────────┐
│  Segment 4: Timeout Screen      │  "TIME'S UP!" — video paused here
│                                 │  MC: host clicks NEXT → auto-scores → answer plays
│                                 │  FF: host walks to buzzing table, hears answer,
│                                 │      clicks RIGHT (correct) or LEFT (wrong) → answer plays
└──────────────┬──────────────────┘
               │
┌──────────────▼──────────────────┐
│  Segment 5: Answer Reveal       │  Correct answer shown with confetti + celebration
│                                 │  FF: ✓ or ✗ symbol shown bottom-left of screen
│  Buttons: green (correct)       │
│           red (wrong)           │
└─────────────────────────────────┘
```

### Multiple Choice (MC)
- All tables press A/B/C/D simultaneously during the countdown
- System records every table's choice
- Points are awarded **automatically** when the answer reveals — no host action needed

### Fastest Finger (FF)
- No options shown — just a countdown
- First table to press any button wins the buzz
- **Their table name/number appears on the big screen** so everyone sees who buzzed first
- All other tables are locked out
- Host walks to that table, listens to verbal answer
- Host clicks **RIGHT = correct** or **LEFT = wrong**
- Points are awarded accordingly
- This is the **only moment** the host manually awards points — everything else is automatic

---

## 6. Button LED States

| Game State | LED Appearance | Meaning |
|---|---|---|
| Intro video | Random colour cycling | Show is starting |
| After intro | All off | Standby |
| Category reveal + question playing | All solid RED | Watch and listen — do not press yet |
| Countdown armed (MC) | A=green · B=blue · C=yellow · D=purple | Press your answer |
| Countdown armed (FF) | All same colour, pulsing | Press any button as fast as possible |
| First to buzz (FF) | That table pulses amber — others go dark | Your table buzzed first — answer verbally |
| Answer correct | Pressed button bright green | Correct — points awarded |
| Answer wrong | Pressed button red | Wrong — points deducted |
| End of show | Colour celebration sequence | Show over |

> **LED response must feel instant.** When a contestant presses a button the LED feedback must happen within a frame — no perceptible lag. This is the most tactile part of the experience.

---

## 7. Question Types

| Type | Answer Mode | Scoring |
|---|---|---|
| Music Clip — Multiple Choice | All tables press A/B/C/D simultaneously | Automatic |
| Photo / Visual — Multiple Choice | All tables press A/B/C/D simultaneously | Automatic |
| General Knowledge — Multiple Choice | All tables press A/B/C/D simultaneously | Automatic |
| General Knowledge — Fastest Finger | First buzz wins — verbal answer | Host clicks RIGHT/LEFT |
| Open Question | First buzz wins — verbal answer | Host clicks RIGHT/LEFT |
| Speed / Countdown Round | Multiple choice, rapid-fire | Automatic per question |

---

## 8. Scoring

| Situation | Points | How Applied |
|---|---|---|
| Correct multiple choice | +100 | Automatic on answer reveal |
| Wrong multiple choice | −100 | Automatic on answer reveal |
| No answer pressed | 0 | No change |
| Fastest finger — correct verbal | +100 | Host clicks RIGHT |
| Fastest finger — wrong verbal | −100 | Host clicks LEFT |

> **Manual scoring (fastest finger) is the only time the host awards points.** All other scoring is fully automatic.

---

## 9. The Big Screen

The big screen is always in one of three states:

| State | What It Shows | When |
|---|---|---|
| **Game Video** | Full-screen pre-produced question video | During every question |
| **Leaderboard** | Animated ranking — all tables, scores, positions animate smoothly | Host toggles manually at any time |
| **Landing / Holding** | Idle screen — show branding or pre-show visual | Before show starts, at host's discretion |

During a fastest finger question, when a table buzzes in, **their table name/number appears prominently on the big screen** — visible to the whole room while the host walks over to hear their answer.

---

## 10. The Host's Experience

The host runs the entire show from one laptop with one clicker:

- **Right click / forward** → advance (NEXT), or mark FF answer as **correct**
- **Left click / back** → mark FF answer as **wrong**
- Laptop screen shows a private control panel: table status, answers received, current game state, leaderboard toggle

> **The host must never need to touch the keyboard during a live show.** The system should be invisible — it just works. Reliability and simplicity come before every feature.

---

## 11. The Question Video Generator (Tooling)

All question videos are created in advance using a desktop tool: **`question_editor.py`** (in `10_FINAL_CURRENT_2026-04-to-present/`). No video editing software needed.

For each question, the host enters:
- Question type: Multiple Choice or Fastest Finger
- Media type: Text, Photo, or Audio
- Question text + four answer options (MC) with correct answer marked
- Optional embedded photo or audio file
- Countdown duration (default 5 seconds — configurable per question)
- Background music and sound effects (intro jingle, countdown tick, timeout ding)

The tool generates a fully animated MP4 video (5 segments, animated backgrounds, countdown ring, confetti on answer reveal) and saves it to `vid/vrae/`.

Each video also produces a **`.meta.json` sidecar file** with the exact pause timestamps for that video:

```json
{
  "mode": "MC",
  "pause_ms": [5000, 15800]
}
```

> **Developer note:** `video_player.py` needs to be updated to read each video's `.meta.json` sidecar for its pause timestamps, rather than using the current global config timing values.

---

## 12. Video Files

The question videos are **not included in this GitHub repo** (too large for git).

| Collection | Location | Videos | Size |
|---|---|---|---|
| Gen2 production library | `gamebegin/` on OneDrive | ~388 | ~25 GB |
| Gen1 archive | `gameshowold/` on OneDrive | ~130 | ~3.3 GB |
| Current active folder | `10_FINAL_CURRENT.../vid/vrae/` | 13 test files | ~14 MB |

Video folder structure the system expects:
```
vid/
├── vrae/        ← question videos  (A_name.mp4, B_name.mp4, F_name.mp4)
├── visual/      ← intro.mp4
└── countdown/   ← F_1.mp4, F_2.mp4 ...
```

Filename prefix encodes the correct answer and mode:
- `A_`, `B_`, `C_`, `D_` → multiple choice, correct answer is that letter
- `F_` → fastest finger (no correct-answer button, host judges verbally)
- `.Q_` anywhere in name → no pauses, plays straight through (bridge/transition video)

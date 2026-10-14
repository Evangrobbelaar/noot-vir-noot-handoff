# Installing the Noot-vir-Noot gameshow on a new laptop

Works on any Windows 10/11 laptop. No coding tools needed.

## 1. Install the software (one command)

1. Open **PowerShell** (Start menu, type `PowerShell`, press Enter). Normal or
   Administrator both work.
2. Copy **only this one line**, right-click in the PowerShell window to paste it,
   and press Enter:

```powershell
irm https://raw.githubusercontent.com/Evangrobbelaar/noot-vir-noot-handoff/gameshow-final/install_gameshow.ps1 | iex
```

Do **not** paste anything else (no `PS C:\...>` text, no lines from the script).
The installer shows 8 steps with a green `OK` each and ends with **KLAAR!**.
If a step fails it prints a red `FOUT:` message: take a photo of the screen.

If that line gives an error before step 1 starts, use this one instead (it saves
the installer to a file first and runs it from there):

```powershell
irm https://raw.githubusercontent.com/Evangrobbelaar/noot-vir-noot-handoff/gameshow-final/install_gameshow.ps1 -OutFile $env:TEMP\install_gameshow.ps1; powershell -NoProfile -ExecutionPolicy Bypass -File $env:TEMP\install_gameshow.ps1
```

It installs Python 3.12, VLC (64-bit), the gameshow and everything it needs into
`%USERPROFILE%\Gameshow`, and puts three shortcuts on the desktop. If winget
(Windows' app installer) doesn't work on the laptop, it downloads Python and VLC
directly from python.org and videolan.org instead.

| Shortcut | What it does |
| --- | --- |
| **Gameshow** | Starts the show (access code `00000`) |
| **Gameshow Netwerk** | Sets the laptop's cable port to `192.168.8.160` so the button units can connect |
| **Gameshow Videos** | Opens the folder where the videos go |

Windows may ask permission once while VLC installs. Takes about 5-10 minutes.
Running the same command again **updates** the software and keeps the videos and scores.

## 2. Add the videos

The videos are not part of the installer. Unzip the show's video zip and copy its
`vrae`, `countdown` and `visual` folders into **Gameshow Videos**.

The play order is stored in each video's *last modified* time: copy the folders as
they are (Explorer copy or unzip both keep it). Check the order in the control
panel's log when the show starts.

## 3. Connect the buttons

1. Switch on the GameShow router and plug a network cable from one of its **LAN**
   ports into the laptop.
2. Double-click **Gameshow Netwerk** and allow it (it needs admin to change the address).
   Wi-Fi is not touched, so the laptop keeps its normal internet.
3. Switch on the button units and give them about a minute.

## 4. Run the show

Double-click **Gameshow**, enter `00000`, tick the checklist, click **Launch**.

- **NEXT**: clicker forward / PageDown
- **L**: switch between show and scoreboard (show screen must be in front)
- Fastest finger: in the control panel, select the first buzzer under *Manual Points*, click + or -
- Use **Win + P -> Duplicate** so the projector shows the same picture as the laptop

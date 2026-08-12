"""
Gameshow launcher.
Auth → pre-launch checklist → start video_player.py + leaderboard.py → window switcher.
Run as: python main.py
"""

import os
import sys
import json
import time
import subprocess
import threading
import tkinter as tk
from tkinter import messagebox
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [MAIN] %(levelname)s %(message)s")
log = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")

with open(CONFIG_PATH) as f:
    CONFIG = json.load(f)

GAMESHOW_TITLE = "Gameshow Video Display"
LEADERBOARD_TITLE = "Dynamic Leaderboard"
TOGGLE_KEY = CONFIG["gameshow"]["toggle_key"]

DARK_BG = "#121212"
DARK_FG = "#E0E0E0"

# ---------------------------------------------------------------------------
# Auth dialog
# ---------------------------------------------------------------------------

def run_auth() -> bool:
    """Show password dialog. Returns True if authenticated."""
    correct_code = CONFIG["gameshow"]["access_code"]
    attempts = [0]
    result = [False]

    root = tk.Tk()
    root.title("Gameshow — Enter Access Code")
    root.configure(bg=DARK_BG)
    root.resizable(False, False)
    root.geometry("360x180")
    root.eval("tk::PlaceWindow . center")

    tk.Label(root, text="Enter Access Code", font=("Arial", 14, "bold"),
             bg=DARK_BG, fg=DARK_FG).pack(pady=(24, 8))

    entry = tk.Entry(root, show="*", font=("Arial", 14), bg="#2A2A2A", fg=DARK_FG,
                     insertbackground=DARK_FG, justify="center", relief=tk.FLAT)
    entry.pack(padx=40, fill=tk.X)
    entry.focus_set()

    err_lbl = tk.Label(root, text="", fg="#EF5350", bg=DARK_BG)
    err_lbl.pack(pady=4)

    def attempt():
        if entry.get() == correct_code:
            result[0] = True
            root.destroy()
        else:
            attempts[0] += 1
            remaining = 3 - attempts[0]
            if remaining <= 0:
                messagebox.showerror("Access Denied", "Too many failed attempts.")
                root.destroy()
            else:
                err_lbl.config(text=f"Incorrect code. {remaining} attempt(s) remaining.")
                entry.delete(0, tk.END)

    btn = tk.Button(root, text="Enter", command=attempt,
                    bg="#1565C0", fg=DARK_FG, relief=tk.FLAT,
                    activebackground="#1976D2", activeforeground=DARK_FG,
                    font=("Arial", 12), padx=20, pady=6)
    btn.pack(pady=8)
    entry.bind("<Return>", lambda e: attempt())

    root.mainloop()
    return result[0]


# ---------------------------------------------------------------------------
# Pre-launch checklist
# ---------------------------------------------------------------------------

def run_checklist() -> bool:
    """Show checklist dialog. Returns True if user clicked Launch."""
    result = [False]

    root = tk.Tk()
    root.title("Pre-Launch Checklist")
    root.configure(bg=DARK_BG)
    root.resizable(False, False)
    root.geometry("480x280")
    root.eval("tk::PlaceWindow . center")

    tk.Label(root, text="Pre-Launch Checklist", font=("Arial", 14, "bold"),
             bg=DARK_BG, fg=DARK_FG).pack(pady=(20, 12))

    checks = [
        tk.BooleanVar(),
        tk.BooleanVar(),
        tk.BooleanVar(),
    ]
    labels = [
        "Table button units are powered on and connected to the router",
        "PC is connected to the router",
        "Physical clicker is connected",
    ]

    launch_btn = None

    def on_check():
        if all(v.get() for v in checks):
            launch_btn.config(state=tk.NORMAL, bg="#1B5E20")
        else:
            launch_btn.config(state=tk.DISABLED, bg="#333")

    for var, text in zip(checks, labels):
        cb = tk.Checkbutton(
            root, text=text, variable=var, bg=DARK_BG, fg=DARK_FG,
            activebackground=DARK_BG, selectcolor="#333",
            font=("Arial", 10), command=on_check
        )
        cb.pack(anchor="w", padx=24, pady=2)

    def do_launch():
        result[0] = True
        root.destroy()

    launch_btn = tk.Button(
        root, text="Launch", command=do_launch,
        bg="#333", fg=DARK_FG, relief=tk.FLAT, state=tk.DISABLED,
        font=("Arial", 12, "bold"), padx=20, pady=8
    )
    launch_btn.pack(pady=16)

    root.mainloop()
    return result[0]


# ---------------------------------------------------------------------------
# Window switcher
# ---------------------------------------------------------------------------

showing_gameshow = True

def _find_window_by_title(title_substr: str):
    """Find window handle containing title_substr. Returns hwnd or None."""
    try:
        import win32gui

        result = [None]

        def enum_cb(hwnd, _):
            if title_substr.lower() in win32gui.GetWindowText(hwnd).lower():
                result[0] = hwnd

        win32gui.EnumWindows(enum_cb, None)
        return result[0]
    except ImportError:
        return None


def _show_window(hwnd):
    try:
        import win32gui
        import win32con
        win32gui.ShowWindow(hwnd, win32con.SW_SHOW)
        win32gui.BringWindowToTop(hwnd)
        win32gui.SetForegroundWindow(hwnd)
    except Exception as exc:
        log.warning("ShowWindow error: %s", exc)


def _hide_window(hwnd):
    try:
        import win32gui
        import win32con
        win32gui.ShowWindow(hwnd, win32con.SW_HIDE)
    except Exception as exc:
        log.warning("HideWindow error: %s", exc)


def _setup_toggle_key(toggle_key: str):
    """Set up global hotkey for window switching using the keyboard library."""
    global showing_gameshow
    try:
        import keyboard

        def on_toggle():
            global showing_gameshow
            gs_hwnd = _find_window_by_title(GAMESHOW_TITLE)
            lb_hwnd = _find_window_by_title(LEADERBOARD_TITLE)

            if showing_gameshow:
                if gs_hwnd:
                    _hide_window(gs_hwnd)
                if lb_hwnd:
                    _show_window(lb_hwnd)
                showing_gameshow = False
                log.info("Switched to Leaderboard")
            else:
                if lb_hwnd:
                    _hide_window(lb_hwnd)
                if gs_hwnd:
                    _show_window(gs_hwnd)
                showing_gameshow = True
                log.info("Switched to Gameshow")

        keyboard.add_hotkey(toggle_key, on_toggle, suppress=False)
        log.info("Toggle key '%s' registered", toggle_key)
    except ImportError:
        log.warning("keyboard library not installed — window toggle disabled")
    except Exception as exc:
        log.warning("Could not register toggle key: %s", exc)


def _setup_quit_key(procs: list[subprocess.Popen]):
    try:
        import keyboard

        def on_quit():
            log.info("Quit key pressed — terminating subprocesses")
            for p in procs:
                try:
                    p.terminate()
                except Exception:
                    pass
            sys.exit(0)

        keyboard.add_hotkey("q", on_quit, suppress=False)
    except ImportError:
        pass


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    # Auth
    if not run_auth():
        log.error("Authentication failed")
        sys.exit(1)

    # Checklist
    if not run_checklist():
        log.info("User cancelled at checklist")
        sys.exit(0)

    # Launch subprocesses
    flags = subprocess.CREATE_NEW_CONSOLE if sys.platform == "win32" else 0

    video_proc = subprocess.Popen(
        [sys.executable, os.path.join(BASE_DIR, "video_player.py")],
        creationflags=flags,
    )
    leaderboard_proc = subprocess.Popen(
        [sys.executable, os.path.join(BASE_DIR, "leaderboard.py")],
        creationflags=flags,
    )

    log.info("Subprocesses launched. Waiting for windows...")
    time.sleep(4)

    procs = [video_proc, leaderboard_proc]
    _setup_toggle_key(TOGGLE_KEY)
    _setup_quit_key(procs)

    log.info("Window switcher running. Toggle key: '%s'  |  Quit key: 'q'", TOGGLE_KEY)

    # Main monitor loop
    while True:
        time.sleep(0.5)

        # Check leaderboard
        if leaderboard_proc.poll() is not None:
            log.warning("Leaderboard process died — restarting")
            leaderboard_proc = subprocess.Popen(
                [sys.executable, os.path.join(BASE_DIR, "leaderboard.py")],
                creationflags=flags,
            )
            procs[1] = leaderboard_proc
            time.sleep(2)

        # Check video player — if it dies the show is over
        if video_proc.poll() is not None:
            log.info("video_player.py exited — show complete")
            try:
                leaderboard_proc.terminate()
            except Exception:
                pass
            sys.exit(0)


if __name__ == "__main__":
    main()

"""
Main gameshow application.
Imports GameServer, runs Tkinter + VLC, manages game state.
Run as: python video_player.py
"""

import os
import sys
import json
import queue
import threading
import logging
import tkinter as tk
from tkinter import scrolledtext, messagebox
from enum import Enum, auto

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [VP] %(levelname)s %(message)s",
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# VLC — must be imported after basic setup
# ---------------------------------------------------------------------------
try:
    import vlc
except ImportError:
    log.error("python-vlc not installed. Run: pip install python-vlc")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Local imports
# ---------------------------------------------------------------------------
from server import GameServer

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")
with open(CONFIG_PATH) as f:
    CONFIG = json.load(f)

VIDEO_FOLDER = os.path.join(
    os.path.dirname(__file__), CONFIG["gameshow"]["video_folder"]
)


# ---------------------------------------------------------------------------
# Network helpers
# ---------------------------------------------------------------------------
import socket as _socket  # noqa: E402


def _get_local_ip() -> str:
    """Return this machine's LAN IP by probing an outbound connection."""
    try:
        s = _socket.socket(_socket.AF_INET, _socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


# ---------------------------------------------------------------------------
# Game states
# ---------------------------------------------------------------------------
class State(Enum):
    LANDING = auto()
    INTRO = auto()
    WAITING_TO_START = auto()
    PLAYING = auto()
    COUNTDOWN = auto()


# ---------------------------------------------------------------------------
# Video file entry
# ---------------------------------------------------------------------------
class VideoEntry:
    def __init__(self, path: str, filename: str):
        self.path = path
        self.filename = filename
        stem = os.path.splitext(filename)[0]
        # Correct answer: first char before underscore
        if len(stem) >= 2 and stem[1] == "_" and stem[0].upper() in "ABCD":
            self.correct_answer = stem[0].upper()
            self.is_f_prefix = False
        elif len(stem) >= 2 and stem[0].upper() == "F" and stem[1] == "_":
            self.correct_answer = None
            self.is_f_prefix = True
        else:
            self.correct_answer = None
            self.is_f_prefix = False

        # .Q_ anywhere in filename: no pauses at all
        self.is_q_type = ".Q_" in filename

    def __repr__(self):
        return f"<VideoEntry {self.filename} ans={self.correct_answer} F={self.is_f_prefix} Q={self.is_q_type}>"


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------
class GameshowApp:
    def __init__(self):
        self.config = CONFIG
        self.event_bus: queue.Queue = queue.Queue()
        self.server = GameServer(self.config, self.event_bus)

        # Video lists
        self.intro_video: VideoEntry | None = None
        self.vrae_videos: list[VideoEntry] = []
        self.countdown_videos: list[VideoEntry] = []
        self.vrae_index = 0
        self.countdown_index = 0

        # Current video state
        self.current_video: VideoEntry | None = None
        self.current_answer: str | None = None
        self.answer_sent_this_video = False

        # Pause state (reset per video)
        self.pauses_triggered = 0  # how many pauses have fired this video
        self.at_video_end = False  # holding at end, waiting for NEXT
        self.answer_awarded = False  # MC auto-award already fired this video

        # Game state
        self.state = State.LANDING

        # Tkinter
        self.root = tk.Tk()
        self.root.title("Gameshow Video Display")
        self.root.configure(bg="black")
        self.root.attributes("-fullscreen", True)

        # VLC
        vlc_args = [
            "--no-xlib",
            "--aout=directsound",
            "--file-caching=1000",
            "--play-and-pause",
        ]
        self.vlc_instance = vlc.Instance(*vlc_args)
        self.media_player: vlc.MediaPlayer = self.vlc_instance.media_player_new()

        # VLC video frame embedded in Tkinter
        self.video_frame = tk.Frame(self.root, bg="black")
        self.video_frame.pack(fill=tk.BOTH, expand=True)

        # Bind VLC to frame after root is shown
        self.root.update_idletasks()
        self._bind_vlc_window()

        # Control panel
        self.control_panel: ControlPanel | None = None

        # Event manager callbacks
        self._vlc_events_attached = False

        # Setup
        self.server.start()
        self.load_video_files()
        self._build_control_panel()
        self._start_event_consumer()
        self._show_landing_screen()
        self._start_client_count_updater()
        self._setup_keyboard()

        self.root.mainloop()

    # ------------------------------------------------------------------
    # VLC window binding
    # ------------------------------------------------------------------

    def _bind_vlc_window(self):
        """Embed VLC into the Tkinter video frame."""
        handle = self.video_frame.winfo_id()
        if sys.platform == "win32":
            self.media_player.set_hwnd(handle)
        else:
            self.media_player.set_xwindow(handle)

    def _attach_vlc_events(self):
        if self._vlc_events_attached:
            return
        em = self.media_player.event_manager()
        em.event_attach(vlc.EventType.MediaPlayerTimeChanged, self._on_time_changed_vlc)
        em.event_attach(vlc.EventType.MediaPlayerEndReached, self._on_media_end_vlc)
        self._vlc_events_attached = True

    # ------------------------------------------------------------------
    # Video loading
    # ------------------------------------------------------------------

    def load_video_files(self):
        """Load video files from vid/ subfolders."""
        visual_dir = os.path.join(VIDEO_FOLDER, "visual")
        vrae_dir = os.path.join(VIDEO_FOLDER, "vrae")
        countdown_dir = os.path.join(VIDEO_FOLDER, "countdown")

        # Intro
        intro_path = os.path.join(visual_dir, "intro.mp4")
        if os.path.isfile(intro_path):
            self.intro_video = VideoEntry(intro_path, "intro.mp4")
        else:
            log.warning("intro.mp4 not found in vid/visual/")

        # VRAE videos
        if os.path.isdir(vrae_dir):
            files = sorted(
                f for f in os.listdir(vrae_dir) if f.lower().endswith(".mp4")
            )
            self.vrae_videos = [VideoEntry(os.path.join(vrae_dir, f), f) for f in files]
            log.info("Loaded %d VRAE videos", len(self.vrae_videos))
        else:
            log.warning("vid/vrae/ folder not found")

        # Countdown videos
        if os.path.isdir(countdown_dir):
            files = sorted(
                f for f in os.listdir(countdown_dir) if f.lower().endswith(".mp4")
            )
            self.countdown_videos = [
                VideoEntry(os.path.join(countdown_dir, f), f) for f in files
            ]
            log.info("Loaded %d countdown videos", len(self.countdown_videos))
        else:
            log.warning("vid/countdown/ folder not found")

    # ------------------------------------------------------------------
    # Screen helpers
    # ------------------------------------------------------------------

    def _clear_frame(self):
        for child in self.video_frame.winfo_children():
            child.destroy()

    def _show_landing_screen(self):
        self._clear_frame()
        lbl = tk.Label(
            self.video_frame,
            text="●",
            font=("Arial", 120),
            fg="#E0E0E0",
            bg="black",
        )
        lbl.place(relx=0.5, rely=0.5, anchor="center")

    def _show_waiting_screen(self):
        self._clear_frame()
        lbl = tk.Label(
            self.video_frame,
            text="Ready to Start",
            font=("Arial", 64, "bold"),
            fg="#E0E0E0",
            bg="black",
        )
        lbl.place(relx=0.5, rely=0.5, anchor="center")

    # ------------------------------------------------------------------
    # Video playback
    # ------------------------------------------------------------------

    def _reset_pause_flags(self):
        self.pauses_triggered = 0
        self.at_video_end = False
        self.answer_awarded = False
        self.answer_sent_this_video = False

    def _play_video(self, entry: VideoEntry):
        """Start playing a VideoEntry."""
        self._reset_pause_flags()
        self.current_video = entry
        self.current_answer = entry.correct_answer

        # Clear any landing/waiting widgets so VLC surface shows
        self._clear_frame()

        media = self.vlc_instance.media_new(entry.path)
        self.media_player.set_media(media)
        self._attach_vlc_events()
        self.media_player.play()

        log.info("Playing: %s", entry.filename)
        if self.control_panel:
            self.control_panel.update_video_label(entry.filename)
            self.control_panel.update_status(f"Playing: {entry.filename}")

    # ------------------------------------------------------------------
    # VLC event callbacks (fire on VLC thread — bridge to main thread)
    # ------------------------------------------------------------------

    def _on_time_changed_vlc(self, event):
        """VLC fires this on its own thread. Bridge to Tk main thread."""
        current_ms = self.media_player.get_time()
        self.root.after(0, lambda ms=current_ms: self._on_time_changed(ms))

    def _on_media_end_vlc(self, event):
        self.root.after(0, self._on_media_end)

    # ------------------------------------------------------------------
    # Pause timing helpers
    # ------------------------------------------------------------------

    def _get_pause_times(self) -> list:
        """Return the list of pause timestamps (ms) for the current video."""
        t = self.config.get("timing", {})
        defaults = {
            "mc_pause1_ms": 5000,
            "mc_pause2_ms": 12000,
            "mc_pause3_ms": 50000,
            "ff_pause1_ms": 5000,
            "ff_pause2_ms": 12000,
        }
        t = {**defaults, **t}
        if self.current_video and self.current_video.is_f_prefix:
            return [t["ff_pause1_ms"], t["ff_pause2_ms"]]
        return [t["mc_pause1_ms"], t["mc_pause2_ms"], t["mc_pause3_ms"]]

    def _on_pause_triggered(self, pause_num: int):
        """Side-effects when a numbered pause fires."""
        is_ff = self.current_video and self.current_video.is_f_prefix
        if pause_num == 1:
            # Clear answers and start tracking this round
            self.server.start_round()
            if self.current_video and self.current_video.correct_answer:
                self.server.correct_answer = self.current_video.correct_answer
            if self.control_panel:
                self.control_panel.clear_round_answers()
                self.control_panel.update_status(
                    "⏸ Pause 1 — press NEXT to arm buttons & show question"
                )
            log.info("Pause 1 — waiting to arm buttons")
        elif pause_num == 2:
            if self.control_panel:
                if is_ff:
                    self.control_panel.update_status(
                        "⏸ Pause 2 — question on screen — press NEXT for countdown"
                    )
                else:
                    self.control_panel.update_status(
                        "⏸ Pause 2 — question on screen — press NEXT for options"
                    )
            log.info("Pause 2")
        elif pause_num == 3:
            if self.control_panel:
                self.control_panel.update_status(
                    "⏸ Pause 3 — TIMEOUT — press NEXT to reveal answer & award points"
                )
            log.info("Pause 3 — waiting to reveal answer")

    def _auto_award_points(self):
        """Award points automatically (MC pause 3 → NEXT)."""
        if self.answer_awarded:
            return
        self.answer_awarded = True
        try:
            c_pts = (
                int(self.control_panel._correct_pts_var.get())
                if self.control_panel
                else self.config["game"]["correct_points"]
            )
            i_pts = (
                int(self.control_panel._incorrect_pts_var.get())
                if self.control_panel
                else self.config["game"]["incorrect_points"]
            )
        except (ValueError, AttributeError):
            c_pts = self.config["game"]["correct_points"]
            i_pts = self.config["game"]["incorrect_points"]
        result = self.server.award_points(c_pts, i_pts)
        if self.control_panel:
            self.control_panel._log(
                f"[AUTO-AWARD] ✔ {result['correct']}  ✘ {result['incorrect']}"
            )
        log.info(
            "Auto-award: correct=%s incorrect=%s",
            result["correct"],
            result["incorrect"],
        )

    # ------------------------------------------------------------------
    # Time-changed handler (runs on main thread)
    # ------------------------------------------------------------------

    def _on_time_changed(self, current_ms: int):
        if self.state == State.INTRO:
            return
        if self.current_video and self.current_video.is_q_type:
            return
        if self.at_video_end:
            return

        pause_times = self._get_pause_times()
        if self.pauses_triggered >= len(pause_times):
            return

        if current_ms >= pause_times[self.pauses_triggered]:
            self.pauses_triggered += 1
            self.media_player.pause()
            self._on_pause_triggered(self.pauses_triggered)

    # ------------------------------------------------------------------
    # Media end handler (runs on main thread)
    # ------------------------------------------------------------------

    def _on_media_end(self):
        log.info("Media ended. State=%s", self.state)

        if self.state == State.INTRO:
            self.server.stop_dance()
            self.server.broadcast_leds("X", 0, 0, 0)
            self._show_waiting_screen()
            self.state = State.WAITING_TO_START
            if self.control_panel:
                self.control_panel.update_status("Waiting to start — press NEXT")
            return

        if self.state == State.COUNTDOWN:
            self.countdown_index += 1
            if self.countdown_index < len(self.countdown_videos):
                self._play_video(self.countdown_videos[self.countdown_index])
            else:
                self._game_complete()
            return

        if self.state == State.PLAYING:
            if self.current_video and self.current_video.is_q_type:
                self.server.broadcast_leds("X", 0, 0, 0)
                self._advance_vrae()
            else:
                # Hold on last frame — operator presses NEXT to advance
                self.at_video_end = True
                if self.control_panel:
                    self.control_panel.update_status(
                        "End — press NEXT for next question"
                    )
                log.info("Video ended — holding, waiting for NEXT")

    def _advance_vrae(self):
        """Play next VRAE video or switch to COUNTDOWN."""
        self.vrae_index += 1
        if self.vrae_index < len(self.vrae_videos):
            self._play_video(self.vrae_videos[self.vrae_index])
        else:
            self._start_countdown()

    def _start_countdown(self):
        self.countdown_index = 0
        if not self.countdown_videos:
            messagebox.showinfo(
                "Game Complete", "All questions answered!\nNo countdown videos found."
            )
            self._game_complete()
            return
        self.state = State.COUNTDOWN
        if self.control_panel:
            self.control_panel.update_status("COUNTDOWN")
        self._play_video(self.countdown_videos[0])

    def _game_complete(self):
        self._show_waiting_screen()
        messagebox.showinfo("Game Complete", "The gameshow has ended!")
        log.info("Game complete.")
        if self.control_panel:
            self.control_panel.update_status("GAME COMPLETE")

    # ------------------------------------------------------------------
    # handle_next — main operator action
    # ------------------------------------------------------------------

    def handle_next(self, _event=None):
        if self.state == State.LANDING:
            self.state = State.INTRO
            self.server.start_dance()
            if self.intro_video:
                self._play_video(self.intro_video)
            else:
                # No intro — jump straight to waiting
                self.server.stop_dance()
                self._show_waiting_screen()
                self.state = State.WAITING_TO_START
            return

        if self.state == State.WAITING_TO_START:
            self.state = State.PLAYING
            self.vrae_index = 0
            if self.vrae_videos:
                self._play_video(self.vrae_videos[0])
            else:
                log.warning("No VRAE videos to play")
                messagebox.showwarning("No Videos", "No VRAE videos found in vid/vrae/")
            return

        if self.state in (State.PLAYING, State.COUNTDOWN):
            # Holding at end of video — advance to next question
            if self.at_video_end:
                self.at_video_end = False
                self._advance_vrae()
                return

            is_mc = (
                self.current_video is not None
                and not self.current_video.is_f_prefix
                and self.current_video.correct_answer is not None
            )

            if self.pauses_triggered == 1:
                # Arm buttons and resume — question is about to appear
                self.server.send_ready()
                self.server.broadcast_leds("X", 10, 0, 0)
                self.media_player.play()
                if self.control_panel:
                    self.control_panel.update_status(
                        "Buttons ARMED — question on screen"
                    )
                return

            if self.pauses_triggered == 2:
                # Resume — options / countdown about to appear
                self.media_player.play()
                if self.control_panel:
                    msg = (
                        "Countdown running"
                        if self.current_video and self.current_video.is_f_prefix
                        else "Options + countdown running"
                    )
                    self.control_panel.update_status(msg)
                return

            if self.pauses_triggered == 3 and is_mc:
                # Auto-award then reveal answer
                self._auto_award_points()
                self.media_player.play()
                if self.control_panel:
                    self.control_panel.update_status(
                        "Points awarded — answer revealing"
                    )
                return

            # Fallback: resume any unexpected pause
            self.media_player.play()
            if self.control_panel:
                self.control_panel.update_status("Resumed")

    # ------------------------------------------------------------------
    # Keyboard
    # ------------------------------------------------------------------

    def _setup_keyboard(self):
        """Bind keyboard shortcuts in Tkinter and pynput for global PageDown."""
        for key in (
            "<n>",
            "<Down>",
            "<Up>",
            "<Next>",
            "<Prior>",
            "<space>",
            "<Return>",
        ):
            try:
                self.root.bind(key, self.handle_next)
            except Exception:
                pass

        try:
            from pynput import keyboard as pynput_kb

            def on_press(key):
                try:
                    if key == pynput_kb.Key.page_down:
                        self.root.after(0, self.handle_next)
                except Exception:
                    pass

            listener = pynput_kb.Listener(on_press=on_press)
            listener.daemon = True
            listener.start()
        except ImportError:
            log.warning("pynput not installed — PageDown global listener disabled")

    # ------------------------------------------------------------------
    # Control panel
    # ------------------------------------------------------------------

    def _build_control_panel(self):
        self.control_panel = ControlPanel(self.root, self)

    # ------------------------------------------------------------------
    # Event consumer
    # ------------------------------------------------------------------

    def _start_event_consumer(self):
        t = threading.Thread(target=self._event_consumer_loop, daemon=True)
        t.start()

    def _event_consumer_loop(self):
        while True:
            try:
                event = self.event_bus.get(timeout=1)
                self.root.after(0, lambda e=event: self._dispatch_event(e))
            except queue.Empty:
                pass
            except Exception as exc:
                log.error("Event consumer error: %s", exc)

    def _dispatch_event(self, event: dict):
        t = event.get("type")
        if t == "answer":
            if self.control_panel:
                self.control_panel.log_answer(
                    event["table"], event["answer"], event["counter"]
                )
        elif t == "correct_answer_set":
            if self.control_panel:
                self.control_panel.set_correct_answer_display(event["answer"])
        elif t == "ready_sent":
            if self.control_panel:
                self.control_panel.update_status("READY sent")

    # ------------------------------------------------------------------
    # Client count updater
    # ------------------------------------------------------------------

    def _start_client_count_updater(self):
        def _update():
            if self.control_panel:
                count = self.server.client_count()
                self.control_panel.update_client_count(count)
            self.root.after(1000, _update)

        self.root.after(1000, _update)


# ---------------------------------------------------------------------------
# Control Panel — horizontal two-column layout
# ---------------------------------------------------------------------------

DARK_BG = "#121212"
HDR_BG = "#0D1117"
CTRL_BG = "#161B22"
PANEL_BG = "#1C2128"
DARK_FG = "#E6EDF3"
DIM_FG = "#8B949E"
ACCENT = "#1F6FEB"

ANSWER_COLOURS_HEX = {
    "A": "#2ECC71",
    "B": "#3498DB",
    "C": "#9B59B6",
    "D": "#E67E22",
}

STATE_COLOURS = {
    "LANDING": "#8B949E",
    "INTRO": "#F0883E",
    "WAITING_TO_START": "#58A6FF",
    "PLAYING": "#3FB950",
    "COUNTDOWN": "#FF7B72",
}


def _mk_label(parent, text, font=None, bg=None, fg=None, **kw):
    return tk.Label(
        parent,
        text=text,
        bg=bg or DARK_BG,
        fg=fg or DARK_FG,
        font=font or ("Segoe UI", 9),
        **kw,
    )


def _mk_btn(parent, text, command, bg="#21262D", fg=DARK_FG, font=None, **kw):
    return tk.Button(
        parent,
        text=text,
        command=command,
        bg=bg,
        fg=fg,
        activebackground="#30363D",
        activeforeground=DARK_FG,
        relief=tk.FLAT,
        bd=0,
        padx=8,
        pady=5,
        cursor="hand2",
        font=font or ("Segoe UI", 9),
        **kw,
    )


def _mk_entry(parent, textvariable=None, width=7, **kw):
    return tk.Entry(
        parent,
        textvariable=textvariable,
        width=width,
        bg="#21262D",
        fg=DARK_FG,
        insertbackground=DARK_FG,
        relief=tk.FLAT,
        bd=2,
        font=("Segoe UI", 9),
        **kw,
    )


# Keep old names as aliases so GameshowApp helper calls still work
def _label(parent, text, font=None, **kw):
    return _mk_label(parent, text, font=font, **kw)


def _button(parent, text, command, bg=None, **kw):
    return _mk_btn(parent, text, command, bg=bg or "#21262D", **kw)


class ControlPanel(tk.Toplevel):
    """
    Horizontal two-column operator panel.

    ┌─ HEADER: state badge │ video │ clients │ LED status │ status msg ─┐
    ├─ CONTROLS: [NEXT] [READY] [SKIP→CD] ──────────── Vol [────] ──────┤
    ├─────────────────────────┬───────────────────────────────────────────┤
    │  LEFT                   │  RIGHT                                    │
    │  ┌─ LED CONTROLS ─────┐ │  ┌─ ROUND ANSWERS ─────────────────────┐│
    │  │  · RED GREEN BLUE  │ │  │  T1 T2 T3 T4 T5 T6                  ││
    │  │  A  ●   ●    ●     │ │  │  T7 T8 T9 T10 T11 T12               ││
    │  │  B  ●   ●    ●     │ │  └─────────────────────────────────────┘│
    │  │  C  ●   ●    ●     │ │  ┌─ SCORING ───────────────────────────┐│
    │  │  D  ●   ●    ●     │ │  │  ○A ○B ○C ○D  Correct:[   ]        ││
    │  │ ALL  ●   ●    ●    │ │  │  Incorrect:[   ]   [AWARD POINTS]   ││
    │  │  [ ALL OFF ]       │ │  └─────────────────────────────────────┘│
    │  └────────────────────┘ │  ┌─ MANUAL POINTS ─────────────────────┐│
    │                         │  │  [1][2][3][4][5][6][7][8][9][10]... ││
    │                         │  │  [SelAll][ClrAll]  Pts:[   ]         ││
    │                         │  │  [+Pts] [−Pts]                       ││
    │                         │  │  Custom: [__________] [Send]         ││
    │                         │  └─────────────────────────────────────┘│
    ├─────────────────────────┴───────────────────────────────────────────┤
    │  LOG ──────────────────────────────────────────────── [Clear]       │
    └─────────────────────────────────────────────────────────────────────┘
    """

    def __init__(self, master, app: "GameshowApp"):
        super().__init__(master)
        self.app = app
        self.title("Game Control Panel")
        self.configure(bg=HDR_BG)
        self.attributes("-topmost", True)
        self.resizable(True, True)
        self.geometry("1100x720+10+10")
        self.minsize(900, 600)

        self.bind("<n>", app.handle_next)
        self.bind("<Down>", app.handle_next)
        self.bind("<Next>", app.handle_next)
        self.bind("<space>", app.handle_next)
        self.bind("<Return>", app.handle_next)

        self._correct_answer_var = tk.StringVar(value="")
        self._correct_pts_var = tk.StringVar(
            value=str(CONFIG["game"]["correct_points"])
        )
        self._incorrect_pts_var = tk.StringVar(
            value=str(CONFIG["game"]["incorrect_points"])
        )
        self._manual_pts_var = tk.StringVar(value="100")
        self._custom_cmd_var = tk.StringVar()

        _t = CONFIG.get("timing", {})
        self._mc_p1_var = tk.StringVar(value=str(_t.get("mc_pause1_ms", 5000)))
        self._mc_p2_var = tk.StringVar(value=str(_t.get("mc_pause2_ms", 12000)))
        self._mc_p3_var = tk.StringVar(value=str(_t.get("mc_pause3_ms", 50000)))
        self._ff_p1_var = tk.StringVar(value=str(_t.get("ff_pause1_ms", 5000)))
        self._ff_p2_var = tk.StringVar(value=str(_t.get("ff_pause2_ms", 12000)))

        self._table_toggle_vars: dict[int, bool] = {}
        self._table_toggle_btns: dict[int, tk.Button] = {}
        self._table_answer_btns: dict[int, tk.Button] = {}

        self._build_ui()

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def _lf(self, parent, title, bg=None):
        """Styled LabelFrame."""
        return tk.LabelFrame(
            parent,
            text=title,
            bg=bg or PANEL_BG,
            fg=DIM_FG,
            font=("Segoe UI", 9, "bold"),
            padx=6,
            pady=4,
            relief=tk.FLAT,
            bd=1,
            highlightthickness=1,
            highlightbackground="#30363D",
        )

    def _build_ui(self):
        self.rowconfigure(2, weight=1)
        self.columnconfigure(0, weight=1)

        self._build_header()
        self._build_controls()
        self._build_main()
        self._build_log()

    # ── Header ──────────────────────────────────────────────────────────

    def _build_header(self):
        hdr = tk.Frame(self, bg=HDR_BG, pady=6)
        hdr.grid(row=0, column=0, sticky="ew")
        hdr.columnconfigure(1, weight=1)

        # State badge
        self._state_badge = tk.Label(
            hdr,
            text="  LANDING  ",
            bg=STATE_COLOURS.get("LANDING", "#555"),
            fg="#000",
            font=("Segoe UI", 10, "bold"),
            padx=6,
            pady=2,
        )
        self._state_badge.grid(row=0, column=0, padx=(10, 6), pady=2)

        # Video name (truncated, expands)
        self._video_lbl = tk.Label(
            hdr,
            text="— no video —",
            bg=HDR_BG,
            fg=DARK_FG,
            font=("Segoe UI", 9),
            anchor="w",
        )
        self._video_lbl.grid(row=0, column=1, sticky="ew", padx=4)

        # Correct answer badge
        self._answer_badge = tk.Label(
            hdr,
            text="ANS: —",
            bg="#21262D",
            fg="#F0883E",
            font=("Segoe UI", 9, "bold"),
            padx=6,
            pady=2,
        )
        self._answer_badge.grid(row=0, column=2, padx=4)

        # Clients
        self._clients_lbl = tk.Label(
            hdr,
            text="0 clients",
            bg=HDR_BG,
            fg=DIM_FG,
            font=("Segoe UI", 9),
        )
        self._clients_lbl.grid(row=0, column=3, padx=6)

        # LED seq dot
        self._led_dot = tk.Label(
            hdr,
            text="● LED idle",
            bg=HDR_BG,
            fg="#30363D",
            font=("Segoe UI", 9),
        )
        self._led_dot.grid(row=0, column=4, padx=6)

        # Status text (right side, full second row)
        self._status_lbl = tk.Label(
            hdr,
            text="Ready",
            bg=HDR_BG,
            fg="#3FB950",
            font=("Segoe UI", 9, "italic"),
            anchor="w",
        )
        self._status_lbl.grid(
            row=1, column=0, columnspan=5, sticky="ew", padx=10, pady=(0, 2)
        )

        # Phone URL row
        url_row = tk.Frame(hdr, bg=HDR_BG)
        url_row.grid(row=2, column=0, columnspan=5, sticky="ew", padx=10, pady=(0, 4))
        http_port = self.app.config.get("web_client", {}).get("http_port", 8082)
        self._phone_ip_var = tk.StringVar(value=_get_local_ip())
        self._phone_url_lbl = tk.Label(
            url_row,
            text=f"📱 http://{self._phone_ip_var.get()}:{http_port}",
            bg=HDR_BG,
            fg="#58A6FF",
            font=("Consolas", 9),
            cursor="hand2",
        )
        self._phone_url_lbl.pack(side=tk.LEFT)
        self._phone_url_lbl.bind(
            "<Button-1>",
            lambda e: self._copy_url(f"http://{self._phone_ip_var.get()}:{http_port}"),
        )
        tk.Button(
            url_row,
            text="⧉ Copy",
            command=lambda: self._copy_url(
                f"http://{self._phone_ip_var.get()}:{http_port}"
            ),
            bg="#21262D",
            fg=DIM_FG,
            activebackground="#30363D",
            relief=tk.FLAT,
            bd=0,
            padx=6,
            pady=1,
            cursor="hand2",
            font=("Segoe UI", 8),
        ).pack(side=tk.LEFT, padx=(6, 0))
        tk.Button(
            url_row,
            text="↺ Refresh IP",
            command=lambda: self._refresh_ip(http_port),
            bg="#21262D",
            fg=DIM_FG,
            activebackground="#30363D",
            relief=tk.FLAT,
            bd=0,
            padx=6,
            pady=1,
            cursor="hand2",
            font=("Segoe UI", 8),
        ).pack(side=tk.LEFT, padx=4)

    # ── Controls bar ───────────────────────────────────────────────────

    def _build_controls(self):
        bar = tk.Frame(self, bg=CTRL_BG, pady=6)
        bar.grid(row=1, column=0, sticky="ew")
        bar.columnconfigure(4, weight=1)  # vol slider expands

        # Big NEXT
        tk.Button(
            bar,
            text="⏭  NEXT",
            command=self.app.handle_next,
            bg="#238636",
            fg="white",
            activebackground="#2EA043",
            font=("Segoe UI", 11, "bold"),
            relief=tk.FLAT,
            bd=0,
            padx=18,
            pady=8,
            cursor="hand2",
        ).grid(row=0, column=0, padx=(10, 4), pady=4)

        # SEND READY
        tk.Button(
            bar,
            text="✔ SEND READY",
            command=self.app.server.send_ready,
            bg="#1F6FEB",
            fg="white",
            activebackground="#388BFD",
            font=("Segoe UI", 10, "bold"),
            relief=tk.FLAT,
            bd=0,
            padx=12,
            pady=8,
            cursor="hand2",
        ).grid(row=0, column=1, padx=4, pady=4)

        # SKIP TO COUNTDOWN
        tk.Button(
            bar,
            text="⏩ Skip→CD",
            command=self._skip_to_countdown,
            bg="#6E40C9",
            fg="white",
            activebackground="#8957E5",
            font=("Segoe UI", 10),
            relief=tk.FLAT,
            bd=0,
            padx=10,
            pady=8,
            cursor="hand2",
        ).grid(row=0, column=2, padx=4, pady=4)

        # separator
        tk.Frame(bar, bg="#30363D", width=2).grid(
            row=0, column=3, padx=8, pady=4, sticky="ns"
        )

        # Volume
        tk.Label(bar, text="Vol", bg=CTRL_BG, fg=DIM_FG, font=("Segoe UI", 9)).grid(
            row=0, column=4, padx=(4, 0)
        )
        self._vol_slider = tk.Scale(
            bar,
            from_=0,
            to=100,
            orient=tk.HORIZONTAL,
            bg=CTRL_BG,
            fg=DARK_FG,
            troughcolor="#21262D",
            highlightthickness=0,
            showvalue=True,
            command=lambda v: self.app.media_player.audio_set_volume(int(v)),
        )
        self._vol_slider.set(80)
        self._vol_slider.grid(row=0, column=5, sticky="ew", padx=(2, 10), pady=4)
        bar.columnconfigure(5, weight=1)

    # ── Main two-column area ────────────────────────────────────────────

    def _build_main(self):
        paned = tk.PanedWindow(
            self,
            orient=tk.HORIZONTAL,
            bg="#30363D",
            sashwidth=4,
            sashrelief=tk.FLAT,
        )
        paned.grid(row=2, column=0, sticky="nsew", padx=2, pady=2)

        # LEFT pane
        left = tk.Frame(paned, bg=PANEL_BG, width=300)
        left.pack_propagate(False)
        paned.add(left, minsize=260)
        self._build_led_controls(left)
        self._build_timing(left)

        # RIGHT pane
        right = tk.Frame(paned, bg=PANEL_BG)
        paned.add(right, minsize=400)
        right.columnconfigure(0, weight=1)

        self._build_round_answers(right)
        self._build_scoring(right)
        self._build_manual_points(right)
        self._build_simulate(right)

    # ── LED Controls (left pane) ────────────────────────────────────────

    def _build_led_controls(self, parent):
        lf = self._lf(parent, "LED Controls")
        lf.pack(fill=tk.X, padx=6, pady=6)

        colour_defs = [
            ("RED", "#B71C1C", (10, 0, 0)),
            ("GRN", "#1B5E20", (0, 10, 0)),
            ("BLU", "#0D47A1", (0, 0, 10)),
        ]
        rows = [("A", "A"), ("B", "B"), ("C", "C"), ("D", "D"), ("ALL", "X")]

        # Header row
        tk.Label(lf, text="", bg=PANEL_BG, width=4).grid(row=0, column=0)
        for ci, (cname, cbg, _) in enumerate(colour_defs):
            tk.Label(
                lf,
                text=cname,
                bg=cbg,
                fg="white",
                font=("Segoe UI", 8, "bold"),
                width=5,
                pady=1,
            ).grid(row=0, column=ci + 1, padx=2, pady=(0, 3))

        for ri, (label, target) in enumerate(rows):
            tk.Label(
                lf,
                text=label,
                bg=PANEL_BG,
                fg=DARK_FG,
                font=("Segoe UI", 9, "bold"),
                width=4,
                anchor="w",
            ).grid(row=ri + 1, column=0, padx=(4, 2), pady=1)
            for ci, (cname, cbg, rgb) in enumerate(colour_defs):
                r, g, b = rgb
                tk.Button(
                    lf,
                    text="●",
                    command=lambda t=target, rv=r, gv=g, bv=b: (
                        self.app.server.broadcast_leds(t, rv, gv, bv)
                    ),
                    bg=cbg,
                    fg="white",
                    activebackground=cbg,
                    relief=tk.FLAT,
                    bd=0,
                    padx=6,
                    pady=3,
                    cursor="hand2",
                    font=("Segoe UI", 9),
                ).grid(row=ri + 1, column=ci + 1, padx=2, pady=1, sticky="ew")

        tk.Button(
            lf,
            text="ALL OFF",
            command=lambda: self.app.server.broadcast_leds("X", 0, 0, 0),
            bg="#21262D",
            fg="#FF7B72",
            activebackground="#30363D",
            activeforeground="#FF7B72",
            relief=tk.FLAT,
            bd=0,
            pady=5,
            cursor="hand2",
            font=("Segoe UI", 9, "bold"),
        ).grid(
            row=len(rows) + 1, column=0, columnspan=4, sticky="ew", padx=2, pady=(6, 2)
        )

        for c in range(4):
            lf.columnconfigure(c, weight=1)

    # ── Pause Timing (left pane, below LEDs) ───────────────────────────

    def _build_timing(self, parent):
        lf = self._lf(parent, "Pause Timing (ms)")
        lf.pack(fill=tk.X, padx=6, pady=(0, 6))

        fields = [
            ("MC Pause 1:", self._mc_p1_var),
            ("MC Pause 2:", self._mc_p2_var),
            ("MC Pause 3:", self._mc_p3_var),
            ("FF Pause 1:", self._ff_p1_var),
            ("FF Pause 2:", self._ff_p2_var),
        ]
        for i, (label, var) in enumerate(fields):
            row = tk.Frame(lf, bg=PANEL_BG)
            row.grid(row=i, column=0, sticky="ew", pady=1)
            tk.Label(
                row,
                text=label,
                bg=PANEL_BG,
                fg=DIM_FG,
                font=("Segoe UI", 9),
                width=11,
                anchor="w",
            ).pack(side=tk.LEFT)
            _mk_entry(row, textvariable=var, width=7).pack(side=tk.LEFT, padx=4)

        tk.Button(
            lf,
            text="Save Timing",
            command=self._save_timing,
            bg="#1F6FEB",
            fg="white",
            activebackground="#388BFD",
            relief=tk.FLAT,
            bd=0,
            pady=5,
            cursor="hand2",
            font=("Segoe UI", 9, "bold"),
        ).grid(row=len(fields), column=0, sticky="ew", pady=(6, 2))
        lf.columnconfigure(0, weight=1)

    def _save_timing(self):
        try:
            timing = {
                "mc_pause1_ms": int(self._mc_p1_var.get()),
                "mc_pause2_ms": int(self._mc_p2_var.get()),
                "mc_pause3_ms": int(self._mc_p3_var.get()),
                "ff_pause1_ms": int(self._ff_p1_var.get()),
                "ff_pause2_ms": int(self._ff_p2_var.get()),
            }
        except ValueError:
            messagebox.showerror(
                "Invalid", "All timing values must be integers (milliseconds)"
            )
            return
        self.app.config["timing"] = timing
        CONFIG["timing"] = timing
        try:
            with open(CONFIG_PATH, "w") as fh:
                json.dump(CONFIG, fh, indent=2)
            self._log("[TIMING] Saved timing config to disk")
        except Exception as exc:
            messagebox.showerror("Save failed", str(exc))

    # ── Round Answers (right pane, top) ────────────────────────────────

    def _build_round_answers(self, parent):
        lf = self._lf(parent, "Current Round Answers")
        lf.grid(row=0, column=0, sticky="ew", padx=6, pady=(6, 3))

        MAX = CONFIG["game"]["max_tables"]
        COLS = 6
        for i in range(1, MAX + 1):
            row, col = divmod(i - 1, COLS)
            btn = tk.Button(
                lf,
                text=f"T{i}\n—",
                bg="#21262D",
                fg=DIM_FG,
                activebackground="#30363D",
                relief=tk.FLAT,
                bd=0,
                width=5,
                height=2,
                font=("Segoe UI", 8),
                cursor="hand2",
            )
            btn.grid(row=row, column=col, padx=2, pady=2, sticky="ew")
            self._table_answer_btns[i] = btn
            lf.columnconfigure(col, weight=1)

    def log_answer(self, table: int, answer: str, counter: int):
        colour = ANSWER_COLOURS_HEX.get(answer, DARK_FG)
        btn = self._table_answer_btns.get(table)
        if btn:
            btn.config(text=f"T{table}\n{answer}", bg=colour, fg="#000000")
        self._log(f"[ANSWER] Table {table} → {answer}  (#{counter})")

    def clear_round_answers(self):
        for i, btn in self._table_answer_btns.items():
            btn.config(text=f"T{i}\n—", bg="#21262D", fg=DIM_FG)

    # ── Scoring (right pane, middle) ───────────────────────────────────

    def _build_scoring(self, parent):
        lf = self._lf(parent, "Scoring")
        lf.grid(row=1, column=0, sticky="ew", padx=6, pady=3)
        lf.columnconfigure(1, weight=1)

        # Row 0: Correct answer radios
        row0 = tk.Frame(lf, bg=PANEL_BG)
        row0.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(2, 4))
        tk.Label(
            row0, text="Correct:", bg=PANEL_BG, fg=DIM_FG, font=("Segoe UI", 9)
        ).pack(side=tk.LEFT, padx=(0, 6))
        for letter in "ABCD":
            clr = ANSWER_COLOURS_HEX[letter]
            rb = tk.Radiobutton(
                row0,
                text=f"  {letter}  ",
                variable=self._correct_answer_var,
                value=letter,
                bg=PANEL_BG,
                fg=clr,
                activebackground=PANEL_BG,
                selectcolor="#21262D",
                indicatoron=True,
                font=("Segoe UI", 10, "bold"),
                command=lambda l=letter: setattr(self.app.server, "correct_answer", l),
            )
            rb.pack(side=tk.LEFT, padx=2)

        # Row 1: Points entries
        row1 = tk.Frame(lf, bg=PANEL_BG)
        row1.grid(row=1, column=0, columnspan=2, sticky="ew", pady=2)
        tk.Label(
            row1, text="Correct pts:", bg=PANEL_BG, fg=DIM_FG, font=("Segoe UI", 9)
        ).pack(side=tk.LEFT)
        _mk_entry(row1, textvariable=self._correct_pts_var, width=6).pack(
            side=tk.LEFT, padx=4
        )
        tk.Label(
            row1, text="Incorrect pts:", bg=PANEL_BG, fg=DIM_FG, font=("Segoe UI", 9)
        ).pack(side=tk.LEFT, padx=(8, 0))
        _mk_entry(row1, textvariable=self._incorrect_pts_var, width=6).pack(
            side=tk.LEFT, padx=4
        )

        # Row 2: Award button
        tk.Button(
            lf,
            text="🏆  AWARD POINTS",
            command=self._award_points,
            bg="#B45309",
            fg="white",
            activebackground="#D97706",
            relief=tk.FLAT,
            bd=0,
            pady=7,
            cursor="hand2",
            font=("Segoe UI", 10, "bold"),
        ).grid(row=2, column=0, columnspan=2, sticky="ew", pady=(4, 2))

    def _award_points(self):
        try:
            c_pts = int(self._correct_pts_var.get())
            i_pts = int(self._incorrect_pts_var.get())
        except ValueError:
            messagebox.showerror("Invalid", "Points must be integers")
            return
        result = self.app.server.award_points(c_pts, i_pts)
        self._log(f"[POINTS] ✔ {result['correct']}  ✘ {result['incorrect']}")

    # ── Manual Points (right pane, bottom) ─────────────────────────────

    def _build_manual_points(self, parent):
        lf = self._lf(parent, "Manual Points")
        lf.grid(row=2, column=0, sticky="ew", padx=6, pady=(3, 6))

        # Table toggle grid (2 rows × 6)
        tgrid = tk.Frame(lf, bg=PANEL_BG)
        tgrid.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(2, 4))
        MAX = CONFIG["game"]["max_tables"]
        for i in range(1, MAX + 1):
            r, c = divmod(i - 1, 6)
            self._table_toggle_vars[i] = False
            btn = tk.Button(
                tgrid,
                text=str(i),
                command=lambda n=i: self._toggle_table(n),
                bg="#21262D",
                fg=DIM_FG,
                activebackground="#30363D",
                relief=tk.FLAT,
                bd=0,
                width=3,
                pady=3,
                font=("Segoe UI", 9),
                cursor="hand2",
            )
            btn.grid(row=r, column=c, padx=2, pady=1)
            self._table_toggle_btns[i] = btn
        for c in range(6):
            tgrid.columnconfigure(c, weight=1)

        # Select/Clear row
        selrow = tk.Frame(lf, bg=PANEL_BG)
        selrow.grid(row=1, column=0, columnspan=2, sticky="ew", pady=2)
        _mk_btn(selrow, "Sel All", self._select_all_tables).pack(
            side=tk.LEFT, padx=(0, 4)
        )
        _mk_btn(selrow, "Clr All", self._clear_all_tables).pack(side=tk.LEFT)

        # Points buttons row
        prow = tk.Frame(lf, bg=PANEL_BG)
        prow.grid(row=2, column=0, columnspan=2, sticky="ew", pady=4)
        tk.Label(prow, text="Pts:", bg=PANEL_BG, fg=DIM_FG, font=("Segoe UI", 9)).pack(
            side=tk.LEFT
        )
        _mk_entry(prow, textvariable=self._manual_pts_var, width=7).pack(
            side=tk.LEFT, padx=4
        )
        tk.Button(
            prow,
            text="+Pts",
            command=lambda: self._manual_points(1),
            bg="#238636",
            fg="white",
            activebackground="#2EA043",
            relief=tk.FLAT,
            bd=0,
            padx=10,
            pady=4,
            cursor="hand2",
            font=("Segoe UI", 9),
        ).pack(side=tk.LEFT, padx=2)
        tk.Button(
            prow,
            text="−Pts",
            command=lambda: self._manual_points(-1),
            bg="#B91C1C",
            fg="white",
            activebackground="#DC2626",
            relief=tk.FLAT,
            bd=0,
            padx=10,
            pady=4,
            cursor="hand2",
            font=("Segoe UI", 9),
        ).pack(side=tk.LEFT, padx=2)

        # Custom command row
        crow = tk.Frame(lf, bg=PANEL_BG)
        crow.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(2, 2))
        tk.Label(
            crow, text="Custom:", bg=PANEL_BG, fg=DIM_FG, font=("Segoe UI", 9)
        ).pack(side=tk.LEFT)
        _mk_entry(crow, textvariable=self._custom_cmd_var, width=16).pack(
            side=tk.LEFT, padx=4
        )
        _mk_btn(crow, "Send", self._send_custom_cmd).pack(side=tk.LEFT)
        tk.Label(
            crow, text="e.g. *1*2+100", bg=PANEL_BG, fg="#484F58", font=("Segoe UI", 8)
        ).pack(side=tk.LEFT, padx=6)

    # ── Simulate Answers (right pane, row 3) ────────────────────────────

    def _build_simulate(self, parent):
        lf = self._lf(parent, "Simulate Answers (no hardware needed)")
        lf.grid(row=3, column=0, sticky="ew", padx=6, pady=(3, 6))

        row0 = tk.Frame(lf, bg=PANEL_BG)
        row0.grid(row=0, column=0, sticky="ew", pady=(2, 4))

        tk.Label(
            row0, text="Table:", bg=PANEL_BG, fg=DIM_FG, font=("Segoe UI", 9)
        ).pack(side=tk.LEFT, padx=(0, 4))

        self._sim_table_var = tk.StringVar(value="1")
        table_spin = tk.Spinbox(
            row0,
            from_=1,
            to=CONFIG["game"]["max_tables"],
            textvariable=self._sim_table_var,
            width=4,
            bg="#21262D",
            fg=DARK_FG,
            buttonbackground="#21262D",
            relief=tk.FLAT,
            font=("Segoe UI", 9),
        )
        table_spin.pack(side=tk.LEFT, padx=(0, 12))

        for letter in "ABCD":
            clr = ANSWER_COLOURS_HEX[letter]
            tk.Button(
                row0,
                text=letter,
                command=lambda l=letter: self._simulate_press(l),
                bg=clr,
                fg="#000",
                activebackground=clr,
                relief=tk.FLAT,
                bd=0,
                width=3,
                pady=4,
                cursor="hand2",
                font=("Segoe UI", 11, "bold"),
            ).pack(side=tk.LEFT, padx=3)

        lf.columnconfigure(0, weight=1)

    def _simulate_press(self, button: str):
        try:
            table = int(self._sim_table_var.get())
        except ValueError:
            return
        self.app.server.simulate_button(table, button)
        self._log(f"[SIM] Table {table} → {button}")

    # ── Log (bottom, full width) ────────────────────────────────────────

    def _build_log(self):
        lf = tk.Frame(self, bg=HDR_BG)
        lf.grid(row=3, column=0, sticky="ew", padx=2, pady=(0, 2))
        lf.columnconfigure(0, weight=1)

        self._log_text = scrolledtext.ScrolledText(
            lf,
            height=5,
            bg="#0D1117",
            fg="#7D8590",
            font=("Consolas", 8),
            state=tk.DISABLED,
            insertbackground=DARK_FG,
            relief=tk.FLAT,
        )
        self._log_text.grid(row=0, column=0, sticky="ew", padx=4, pady=(4, 0))

        tk.Button(
            lf,
            text="Clear Log",
            command=self._clear_log,
            bg="#21262D",
            fg=DIM_FG,
            activebackground="#30363D",
            relief=tk.FLAT,
            bd=0,
            padx=8,
            pady=3,
            cursor="hand2",
            font=("Segoe UI", 8),
        ).grid(row=0, column=1, padx=(4, 6), pady=4, sticky="e")

    # ------------------------------------------------------------------
    # Public update methods (called by GameshowApp)
    # ------------------------------------------------------------------

    def update_status(self, msg: str):
        state_name = self.app.state.name
        colour = STATE_COLOURS.get(state_name, "#8B949E")
        self._state_badge.config(text=f"  {state_name}  ", bg=colour)
        self._status_lbl.config(text=msg)
        led_on = self.app.server.colour_sequence_active
        self._led_dot.config(
            text="● LED seq" if led_on else "● LED idle",
            fg="#F0883E" if led_on else "#30363D",
        )
        self._log(f"[STATUS] {msg}")

    def update_video_label(self, filename: str):
        self._video_lbl.config(text=filename)

    def update_client_count(self, count: int):
        self._clients_lbl.config(
            text=f"{count} client{'s' if count != 1 else ''}",
            fg="#3FB950" if count > 0 else DIM_FG,
        )

    def set_correct_answer_display(self, answer: str):
        clr = ANSWER_COLOURS_HEX.get(answer, "#F0883E")
        self._answer_badge.config(text=f"ANS: {answer}", fg=clr)
        self._correct_answer_var.set(answer)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _copy_url(self, url: str):
        self.clipboard_clear()
        self.clipboard_append(url)
        self._log(f"[URL] Copied: {url}")

    def _refresh_ip(self, http_port: int):
        ip = _get_local_ip()
        self._phone_ip_var.set(ip)
        self._phone_url_lbl.config(text=f"📱 http://{ip}:{http_port}")
        self._log(f"[URL] Refreshed IP → {ip}")

    def _skip_to_countdown(self):
        if self.app.state == State.PLAYING:
            self.app._start_countdown()

    def _toggle_table(self, n: int):
        self._table_toggle_vars[n] = not self._table_toggle_vars[n]
        active = self._table_toggle_vars[n]
        self._table_toggle_btns[n].config(
            bg=ACCENT if active else "#21262D",
            fg="white" if active else DIM_FG,
        )

    def _select_all_tables(self):
        for n in self._table_toggle_btns:
            self._table_toggle_vars[n] = True
            self._table_toggle_btns[n].config(bg=ACCENT, fg="white")

    def _clear_all_tables(self):
        for n in self._table_toggle_btns:
            self._table_toggle_vars[n] = False
            self._table_toggle_btns[n].config(bg="#21262D", fg=DIM_FG)

    def _manual_points(self, sign: int):
        selected = [n for n, v in self._table_toggle_vars.items() if v]
        if not selected:
            messagebox.showwarning("No tables", "Select at least one table first")
            return
        try:
            pts = abs(int(self._manual_pts_var.get())) * sign
        except ValueError:
            messagebox.showerror("Invalid", "Points must be an integer")
            return
        tables_str = "*" + "*".join(str(t) for t in selected)
        sign_char = "+" if pts >= 0 else "-"
        msg = f"{tables_str}{sign_char}{abs(pts)}"
        self.app.server.send_to_leaderboard(msg)
        self._log(f"[MANUAL] {msg}")

    def _send_custom_cmd(self):
        cmd = self._custom_cmd_var.get().strip()
        if cmd:
            self.app.server.send_to_leaderboard(cmd)
            self._log(f"[CUSTOM] {cmd}")

    def _log(self, msg: str):
        import datetime

        ts = datetime.datetime.now().strftime("%H:%M:%S")
        self._log_text.config(state=tk.NORMAL)
        self._log_text.insert(tk.END, f"[{ts}] {msg}\n")
        self._log_text.see(tk.END)
        self._log_text.config(state=tk.DISABLED)

    def _clear_log(self):
        self._log_text.config(state=tk.NORMAL)
        self._log_text.delete("1.0", tk.END)
        self._log_text.config(state=tk.DISABLED)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    GameshowApp()

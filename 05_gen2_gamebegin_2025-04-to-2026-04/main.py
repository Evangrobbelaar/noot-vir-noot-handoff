"""
main.py  —  Unified Gameshow Launcher
Replaces enter.py + toggler.py with a single entry point.

Master code : 00000  (always works, no need to pull access codes)
Regular code: gameshow123

Run this file instead of enter.py.
Press L or B to toggle display, Q to quit.
"""

import os
import sys
import subprocess
import threading
import hashlib
import time
import ctypes
import tkinter as tk
from tkinter import messagebox

# ── Optional Windows / keyboard libraries ────────────────────────────────────
try:
    import win32gui
    import win32con
    WIN32_AVAILABLE = True
except ImportError:
    WIN32_AVAILABLE = False

try:
    import keyboard as kb
    KEYBOARD_AVAILABLE = True
except ImportError:
    KEYBOARD_AVAILABLE = False

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

# ── Paths ─────────────────────────────────────────────────────────────────────
SCRIPT_DIR        = os.path.dirname(os.path.abspath(__file__))
BSD_SCRIPT        = os.path.join(SCRIPT_DIR, "bsd.py")
GAMESHOW_SCRIPT   = os.path.join(SCRIPT_DIR, "gameshow2.py")
LEADERBOARD_SCRIPT = os.path.join(SCRIPT_DIR, "leaderboard.py")

GAMESHOW_TITLE    = "Gameshow Video Display"
LEADERBOARD_TITLE = "Dynamic Leaderboard"

# ── Auth ──────────────────────────────────────────────────────────────────────
MASTER_CODE = "00000"   # hard-coded convenience code — always bypasses hashing

VALID_HASHES = {
    hashlib.sha256("gameshow123".encode()).hexdigest(),
}


def verify_password(password: str) -> bool:
    """Return True if the password/code is valid."""
    if password == MASTER_CODE:
        return True
    return hashlib.sha256(password.encode()).hexdigest() in VALID_HASHES


# ── Process manager ───────────────────────────────────────────────────────────
class ProcessManager:
    NAMES = ("bsd", "gameshow", "leaderboard")

    def __init__(self):
        self._procs: dict[str, subprocess.Popen | None] = {n: None for n in self.NAMES}
        self._scripts = {
            "bsd":         BSD_SCRIPT,
            "gameshow":    GAMESHOW_SCRIPT,
            "leaderboard": LEADERBOARD_SCRIPT,
        }
        self._cbs: list = []   # status-change callbacks: fn(name, alive)
        self._running = False  # monitor loop active

    def on_status_change(self, cb):
        self._cbs.append(cb)

    def _notify(self, name: str, alive: bool):
        for cb in self._cbs:
            try:
                cb(name, alive)
            except Exception:
                pass

    # ── internal process state ────────────────────────────────────────────────
    @staticmethod
    def _alive(proc) -> bool:
        if proc is None:
            return False
        if PSUTIL_AVAILABLE:
            try:
                return psutil.pid_exists(proc.pid) and psutil.Process(proc.pid).is_running()
            except psutil.NoSuchProcess:
                return False
        return proc.poll() is None

    # ── public API ────────────────────────────────────────────────────────────
    def is_alive(self, name: str) -> bool:
        return self._alive(self._procs.get(name))

    def start(self, name: str) -> bool:
        script = self._scripts[name]
        if not os.path.exists(script):
            print(f"[ProcessManager] Missing: {script}")
            return False
        proc = subprocess.Popen(
            [sys.executable, script],
            creationflags=subprocess.CREATE_NEW_CONSOLE,
        )
        self._procs[name] = proc
        self._notify(name, True)
        return True

    def stop(self, name: str):
        proc = self._procs.get(name)
        if proc and self._alive(proc):
            try:
                proc.terminate()
            except Exception:
                pass
        self._procs[name] = None
        self._notify(name, False)

    def start_all(self):
        """Launch BSD first (needs a moment to bind the port), then the rest."""
        self.start("bsd")
        time.sleep(2)          # give BSD time to open port 8080
        self.start("gameshow")
        self.start("leaderboard")

    def stop_all(self):
        for name in self.NAMES:
            self.stop(name)

    def restart(self, name: str):
        self.stop(name)
        time.sleep(0.6)
        return self.start(name)

    # ── background health monitor ──────────────────────────────────────────────
    def monitor_loop(self):
        """Runs in a daemon thread.  Polls health, notifies on change, auto-restarts leaderboard."""
        self._running = True
        prev = {n: False for n in self.NAMES}
        while self._running:
            for name in self.NAMES:
                alive = self.is_alive(name)
                if alive != prev[name]:
                    self._notify(name, alive)
                    prev[name] = alive
                # Auto-restart leaderboard when it dies (same as toggler.py did)
                if name == "leaderboard" and not alive and self._procs[name] is not None:
                    print("[Monitor] Leaderboard died — restarting …")
                    time.sleep(2)
                    self.start("leaderboard")
                    prev["leaderboard"] = True
            time.sleep(2)


# ── Window toggler ─────────────────────────────────────────────────────────────
class WindowToggler:
    """Mirrors the logic from toggler.py, but runs inside the main process."""

    def __init__(self):
        self.gameshow_hwnd = None
        self.leaderboard_hwnd = None
        self.gameshow_visible = True
        self.gameshow_placement = None
        self.leaderboard_placement = None
        self._wndproc_ref = None   # keep callback alive so GC doesn't eat it

    # ── window discovery ───────────────────────────────────────────────────────
    def find_windows(self):
        if not WIN32_AVAILABLE:
            return
        found_gs = found_lb = None

        def cb(hwnd, _):
            nonlocal found_gs, found_lb
            if win32gui.IsWindowVisible(hwnd) and win32gui.IsWindow(hwnd):
                title = win32gui.GetWindowText(hwnd)
                if title:
                    if GAMESHOW_TITLE in title and not found_gs:
                        found_gs = hwnd
                    elif LEADERBOARD_TITLE in title and not found_lb:
                        found_lb = hwnd
            return True

        win32gui.EnumWindows(cb, None)
        if found_gs:
            self.gameshow_hwnd = found_gs
        if found_lb:
            self.leaderboard_hwnd = found_lb

    # ── placement helpers ──────────────────────────────────────────────────────
    def _save(self, hwnd):
        try:
            return win32gui.GetWindowPlacement(hwnd)
        except Exception:
            return None

    def _restore(self, hwnd, placement):
        if placement:
            try:
                win32gui.SetWindowPlacement(hwnd, placement)
            except Exception:
                pass

    # ── show / hide ────────────────────────────────────────────────────────────
    def show_gameshow(self):
        if not WIN32_AVAILABLE:
            return
        if not self.gameshow_hwnd or not win32gui.IsWindow(self.gameshow_hwnd):
            self.find_windows()
        if self.gameshow_hwnd and win32gui.IsWindow(self.gameshow_hwnd):
            if self.gameshow_placement:
                self._restore(self.gameshow_hwnd, self.gameshow_placement)
            else:
                win32gui.ShowWindow(self.gameshow_hwnd, win32con.SW_SHOWNOACTIVATE)
            win32gui.BringWindowToTop(self.gameshow_hwnd)
            if self.leaderboard_hwnd and win32gui.IsWindow(self.leaderboard_hwnd):
                self.leaderboard_placement = self._save(self.leaderboard_hwnd)
                win32gui.SetWindowPos(
                    self.leaderboard_hwnd, win32con.HWND_NOTOPMOST,
                    0, 0, 0, 0,
                    win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_NOACTIVATE,
                )
                win32gui.ShowWindow(self.leaderboard_hwnd, win32con.SW_HIDE)
            self.gameshow_visible = True

    def show_leaderboard(self):
        if not WIN32_AVAILABLE:
            return
        if not self.leaderboard_hwnd or not win32gui.IsWindow(self.leaderboard_hwnd):
            self.find_windows()
        if self.leaderboard_hwnd and win32gui.IsWindow(self.leaderboard_hwnd):
            if self.leaderboard_placement:
                self._restore(self.leaderboard_hwnd, self.leaderboard_placement)
            else:
                win32gui.ShowWindow(self.leaderboard_hwnd, win32con.SW_SHOWNOACTIVATE)
            win32gui.SetWindowPos(
                self.leaderboard_hwnd, win32con.HWND_TOPMOST,
                0, 0, 0, 0,
                win32con.SWP_NOMOVE | win32con.SWP_NOSIZE,
            )
            win32gui.BringWindowToTop(self.leaderboard_hwnd)
            if self.gameshow_hwnd and win32gui.IsWindow(self.gameshow_hwnd):
                self.gameshow_placement = self._save(self.gameshow_hwnd)
                win32gui.ShowWindow(self.gameshow_hwnd, win32con.SW_HIDE)
            self.gameshow_visible = False

    def toggle(self):
        if self.gameshow_visible:
            self.show_leaderboard()
        else:
            self.show_gameshow()

    # ── leaderboard close-lock ─────────────────────────────────────────────────
    def lock_leaderboard(self):
        """Subclass leaderboard WndProc to block accidental WM_CLOSE."""
        if not WIN32_AVAILABLE or not self.leaderboard_hwnd:
            return
        if not win32gui.IsWindow(self.leaderboard_hwnd):
            return
        try:
            orig = win32gui.GetWindowLong(self.leaderboard_hwnd, win32con.GWL_WNDPROC)

            def _new_proc(hwnd, msg, wparam, lparam):
                if msg == win32con.WM_CLOSE:
                    print("[Toggler] Leaderboard close blocked.")
                    return 0
                return win32gui.CallWindowProc(orig, hwnd, msg, wparam, lparam)

            self._wndproc_ref = ctypes.WINFUNCTYPE(
                ctypes.c_long, ctypes.c_int, ctypes.c_uint,
                ctypes.c_wparam, ctypes.c_lparam,
            )(_new_proc)
            win32gui.SetWindowLong(
                self.leaderboard_hwnd,
                win32con.GWL_WNDPROC,
                ctypes.cast(self._wndproc_ref, ctypes.c_void_p).value,
            )
            print("[Toggler] Leaderboard window locked.")
        except Exception as e:
            print(f"[Toggler] lock_leaderboard error: {e}")

    # ── init after child processes have started ────────────────────────────────
    def init_windows(self):
        """Find both windows, save placements, lock leaderboard, show gameshow."""
        for attempt in range(8):
            self.find_windows()
            if self.gameshow_hwnd and self.leaderboard_hwnd:
                break
            time.sleep(1)
        if self.leaderboard_hwnd:
            self.lock_leaderboard()
            self.leaderboard_placement = self._save(self.leaderboard_hwnd)
        if self.gameshow_hwnd:
            self.gameshow_placement = self._save(self.gameshow_hwnd)
        self.show_gameshow()
        print("[Toggler] Windows initialised.")


# ── Mission Control UI ─────────────────────────────────────────────────────────
class MissionControl:
    BG  = "#1a1a2e"
    BG2 = "#16213e"
    FG  = "#e0e0e0"
    ACC = "#e94560"

    LABELS = {
        "bsd":         "BSD Server",
        "gameshow":    "Gameshow Player",
        "leaderboard": "Leaderboard",
    }

    def __init__(self, root: tk.Tk, pm: ProcessManager, tog: WindowToggler):
        self.root = root
        self.pm   = pm
        self.tog  = tog
        self._dots: dict[str, tk.Canvas] = {}
        self._build()
        pm.on_status_change(self._on_status_change)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _dot(self, alive: bool) -> str:
        return "#2ecc71" if alive else "#e74c3c"

    def _build(self):
        r = self.root
        r.title("Gameshow Control")
        r.geometry("360x370")
        r.configure(bg=self.BG)
        r.resizable(False, False)

        # ── header ─────────────────────────────────────────────────────────────
        tk.Label(r, text="GAMESHOW SYSTEM", font=("Arial", 15, "bold"),
                 fg=self.ACC, bg=self.BG).pack(pady=(14, 2))
        tk.Label(r, text="Mission Control", font=("Arial", 9),
                 fg="#666", bg=self.BG).pack(pady=(0, 8))

        # ── process status panel ───────────────────────────────────────────────
        panel = tk.Frame(r, bg=self.BG2, padx=14, pady=8)
        panel.pack(fill=tk.X, padx=16, pady=4)

        for name in ProcessManager.NAMES:
            row = tk.Frame(panel, bg=self.BG2)
            row.pack(fill=tk.X, pady=3)

            dot = tk.Canvas(row, width=16, height=16, bg=self.BG2,
                            highlightthickness=0)
            dot.create_oval(2, 2, 14, 14, fill="#888", tags="dot")
            dot.pack(side=tk.LEFT, padx=(0, 8))
            self._dots[name] = dot

            tk.Label(row, text=self.LABELS[name], font=("Segoe UI", 10),
                     fg=self.FG, bg=self.BG2, width=15,
                     anchor="w").pack(side=tk.LEFT)

            tk.Button(row, text="Restart", font=("Segoe UI", 8),
                      bg="#0f3460", fg=self.FG,
                      activebackground=self.ACC, activeforeground="#fff",
                      relief="flat", padx=7, pady=2,
                      command=lambda n=name: self._restart(n)).pack(side=tk.RIGHT)

        # ── display toggle controls ────────────────────────────────────────────
        tog_frame = tk.Frame(r, bg=self.BG, pady=6)
        tog_frame.pack(fill=tk.X, padx=16)

        for label, cmd in [
            ("Show Gameshow",    self.tog.show_gameshow),
            ("Show Leaderboard", self.tog.show_leaderboard),
            ("Toggle  (L)",      self.tog.toggle),
        ]:
            tk.Button(tog_frame, text=label, font=("Segoe UI", 9, "bold"),
                      bg="#0f3460", fg="#fff",
                      activebackground=self.ACC, activeforeground="#fff",
                      relief="flat", padx=8, pady=4,
                      command=cmd).pack(side=tk.LEFT, padx=3, pady=2)

        # ── hotkey reference ───────────────────────────────────────────────────
        hint_frame = tk.Frame(r, bg=self.BG2, padx=12, pady=8)
        hint_frame.pack(fill=tk.X, padx=16, pady=4)
        tk.Label(hint_frame, text="Hotkeys", font=("Segoe UI", 9, "bold"),
                 fg="#888", bg=self.BG2).pack(anchor="w")

        hints = [
            ("L  /  B",    "Toggle between gameshow & leaderboard"),
            ("Q",          "Quit all applications"),
            ("N / PageDn", "Next question (in gameshow window)"),
            ("S",          "Skip to countdown"),
            ("T",          "Send READY trigger"),
        ]
        for key, desc in hints:
            row = tk.Frame(hint_frame, bg=self.BG2)
            row.pack(fill=tk.X, pady=1)
            tk.Label(row, text=key, font=("Consolas", 9, "bold"),
                     fg=self.ACC, bg=self.BG2, width=11, anchor="w").pack(side=tk.LEFT)
            tk.Label(row, text=desc, font=("Segoe UI", 9),
                     fg="#999", bg=self.BG2).pack(side=tk.LEFT)

        # ── bottom bar ─────────────────────────────────────────────────────────
        bottom = tk.Frame(r, bg=self.BG, pady=8)
        bottom.pack(fill=tk.X, padx=16)
        tk.Button(bottom, text="Close All & Exit",
                  font=("Segoe UI", 10, "bold"),
                  bg="#c0392b", fg="#fff",
                  activebackground="#e74c3c", activeforeground="#fff",
                  relief="flat", padx=14, pady=6,
                  command=self._quit_all).pack(side=tk.RIGHT)

    # ── callbacks ──────────────────────────────────────────────────────────────
    def _on_status_change(self, name: str, alive: bool):
        """Called from background thread — schedule on main thread."""
        self.root.after(0, lambda n=name, a=alive: self._update_dot(n, a))

    def _update_dot(self, name: str, alive: bool):
        dot = self._dots.get(name)
        if dot:
            dot.itemconfig("dot", fill=self._dot(alive))

    def _restart(self, name: str):
        threading.Thread(target=self._do_restart, args=(name,), daemon=True).start()

    def _do_restart(self, name: str):
        self.pm.restart(name)
        if name == "leaderboard":
            time.sleep(3)
            self.tog.find_windows()
            if self.tog.leaderboard_hwnd:
                self.tog.lock_leaderboard()

    def _quit_all(self):
        self.pm.stop_all()
        self.root.after(300, lambda: os._exit(0))

    def _on_close(self):
        if messagebox.askyesno("Exit", "Close all gameshow applications and exit?",
                               parent=self.root):
            self._quit_all()

    # ── background threads started from main() ────────────────────────────────
    def start_background_threads(self):
        threading.Thread(target=self.pm.monitor_loop,   daemon=True).start()
        threading.Thread(target=self._hotkey_thread,    daemon=True).start()
        threading.Thread(target=self._window_init_thread, daemon=True).start()

    def _hotkey_thread(self):
        """Global hotkeys — same keys as toggler.py (L, B, Q)."""
        if not KEYBOARD_AVAILABLE:
            print("[Hotkeys] 'keyboard' library not available — hotkeys disabled.")
            return

        def _handler(event):
            if event.event_type != kb.KEY_DOWN:
                return
            if event.name in ('l', 'b'):
                self.tog.toggle()
            elif event.name == 'q':
                self.root.after(0, self._quit_all)

        kb.hook(_handler)
        # keep thread alive — hook is still active
        while True:
            time.sleep(1)

    def _window_init_thread(self):
        """Wait for child processes to open their windows before toggling."""
        time.sleep(5)   # processes need a few seconds to show windows
        self.tog.init_windows()


# ── Login window ───────────────────────────────────────────────────────────────
class LoginWindow:
    BG = "#222222"

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Gameshow Login")
        self.root.geometry("320x210")
        self.root.resizable(False, False)
        self.root.configure(bg=self.BG)
        self._center(320, 210)
        self._build()
        self.success = False

    def _center(self, w: int, h: int):
        self.root.update_idletasks()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        self.root.geometry(f"+{(sw - w) // 2}+{(sh - h) // 2}")

    def _build(self):
        tk.Label(self.root, text="GAMESHOW LOGIN",
                 font=("Arial", 16, "bold"), fg="#fff", bg=self.BG).pack(pady=(18, 6))
        tk.Label(self.root,
                 text="Enter password  (master code: 00000)",
                 font=("Arial", 9), fg="#888", bg=self.BG).pack(pady=(0, 8))

        frame = tk.Frame(self.root, bg=self.BG, padx=30)
        frame.pack(fill=tk.X)

        tk.Label(frame, text="Password / Code:", font=("Arial", 11),
                 fg="#fff", bg=self.BG, anchor="w").pack(fill=tk.X)

        self._pwd = tk.StringVar()
        entry = tk.Entry(frame, textvariable=self._pwd, show="•",
                         font=("Arial", 13), bd=0,
                         highlightthickness=1, highlightbackground="#555",
                         highlightcolor="#3498db",
                         bg="#333", fg="#fff", insertbackground="#fff")
        entry.pack(fill=tk.X, ipady=4, pady=(4, 14))
        entry.focus_set()
        self.root.bind("<Return>", lambda _: self._verify())

        btns = tk.Frame(frame, bg=self.BG)
        btns.pack(fill=tk.X)
        tk.Button(btns, text="Login", command=self._verify,
                  bg="#3498db", fg="#fff", font=("Arial", 11, "bold"),
                  activebackground="#2980b9", bd=0,
                  padx=16, pady=5).pack(side=tk.LEFT, padx=(0, 10))
        tk.Button(btns, text="Cancel", command=self.root.destroy,
                  bg="#e74c3c", fg="#fff", font=("Arial", 11),
                  activebackground="#c0392b", bd=0,
                  padx=10, pady=5).pack(side=tk.LEFT)

    def _verify(self):
        pwd = self._pwd.get().strip()
        if not pwd:
            messagebox.showerror("Error", "Please enter a password or code",
                                 parent=self.root)
            return
        if verify_password(pwd):
            self.success = True
            self.root.destroy()
        else:
            messagebox.showerror("Access Denied", "Incorrect password or code",
                                 parent=self.root)
            self._pwd.set("")

    def run(self) -> bool:
        self.root.mainloop()
        return self.success


# ── Entry point ───────────────────────────────────────────────────────────────
def main():
    # Sanity check — make sure the component scripts exist
    missing = [s for s in (BSD_SCRIPT, GAMESHOW_SCRIPT, LEADERBOARD_SCRIPT)
               if not os.path.exists(s)]
    if missing:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            "Missing Files",
            "Required component files not found:\n" +
            "\n".join(f"  {os.path.basename(s)}" for s in missing),
        )
        root.destroy()
        return

    # ── Login ─────────────────────────────────────────────────────────────────
    login = LoginWindow()
    if not login.run():
        return   # user cancelled

    # ── Build system ──────────────────────────────────────────────────────────
    pm  = ProcessManager()
    tog = WindowToggler()

    # ── Mission Control window ────────────────────────────────────────────────
    root = tk.Tk()
    mc   = MissionControl(root, pm, tog)
    mc.start_background_threads()

    # ── Start processes in background so the UI appears immediately ───────────
    threading.Thread(target=pm.start_all, daemon=True).start()

    root.mainloop()


if __name__ == "__main__":
    main()

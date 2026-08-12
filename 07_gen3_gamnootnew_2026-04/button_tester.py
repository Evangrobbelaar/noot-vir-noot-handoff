"""
Button Tester — automated test suite that exercises every LED command and
server-side feature by connecting as a client to bsd.py.

Tests:
  1. Connection handshake
  2. Individual LED commands  (A/B/C/D × Red/Green/Blue/Off)
  3. All-LEDs command         (X × Red/Green/Blue/Off)
  4. Answer submission        (@TABLE:ANSWER format)
  5. DASHBOARD-READY-TRIGGER  (sends ready signal to server)
  6. Dance-lights start/stop
  7. Disconnection
"""
import socket
import threading
import time
import tkinter as tk
from tkinter import scrolledtext

SERVER_IP   = "127.0.0.1"
SERVER_PORT = 8080

LED_COMMANDS = (
    # (description, command)
    ("A  — RED",    "EMS-LEDS-A|10|0|0|"),
    ("A  — GREEN",  "EMS-LEDS-A|0|10|0|"),
    ("A  — BLUE",   "EMS-LEDS-A|0|0|10|"),
    ("A  — OFF",    "EMS-LEDS-A|0|0|0|"),
    ("B  — RED",    "EMS-LEDS-B|10|0|0|"),
    ("B  — GREEN",  "EMS-LEDS-B|0|10|0|"),
    ("B  — BLUE",   "EMS-LEDS-B|0|0|10|"),
    ("B  — OFF",    "EMS-LEDS-B|0|0|0|"),
    ("C  — RED",    "EMS-LEDS-C|10|0|0|"),
    ("C  — GREEN",  "EMS-LEDS-C|0|10|0|"),
    ("C  — BLUE",   "EMS-LEDS-C|0|0|10|"),
    ("C  — OFF",    "EMS-LEDS-C|0|0|0|"),
    ("D  — RED",    "EMS-LEDS-D|10|0|0|"),
    ("D  — GREEN",  "EMS-LEDS-D|0|10|0|"),
    ("D  — BLUE",   "EMS-LEDS-D|0|0|10|"),
    ("D  — OFF",    "EMS-LEDS-D|0|0|0|"),
    ("ALL — RED",   "EMS-LEDS-X|10|0|0|"),
    ("ALL — GREEN", "EMS-LEDS-X|0|10|0|"),
    ("ALL — BLUE",  "EMS-LEDS-X|0|0|10|"),
    ("ALL — OFF",   "EMS-LEDS-X|0|0|0|"),
)

ANSWER_TESTS = [
    ("Table 1 answers A", "@1:A"),
    ("Table 2 answers B", "@2:B"),
    ("Table 3 answers C", "@3:C"),
    ("Table 4 answers D", "@4:D"),
]


class ButtonTesterApp:
    def __init__(self, root: tk.Tk):
        self.root  = root
        self.root.title("Button Tester")
        self.root.configure(bg="#121212")
        self.sock  = None
        self._recv_buf = ""
        self._lock = threading.Lock()
        self._build_ui()

    def _build_ui(self):
        top = tk.Frame(self.root, bg="#121212")
        top.pack(fill=tk.X, padx=10, pady=8)

        tk.Label(top, text="IP:", bg="#121212", fg="#e0e0e0",
                 font=("Segoe UI", 10)).pack(side=tk.LEFT)
        self.ip_var = tk.StringVar(value=SERVER_IP)
        tk.Entry(top, textvariable=self.ip_var, width=14,
                 bg="#2d2d2d", fg="#e0e0e0", insertbackground="#e0e0e0",
                 relief="flat").pack(side=tk.LEFT, padx=4)

        tk.Label(top, text="Port:", bg="#121212", fg="#e0e0e0",
                 font=("Segoe UI", 10)).pack(side=tk.LEFT)
        self.port_var = tk.StringVar(value=str(SERVER_PORT))
        tk.Entry(top, textvariable=self.port_var, width=6,
                 bg="#2d2d2d", fg="#e0e0e0", insertbackground="#e0e0e0",
                 relief="flat").pack(side=tk.LEFT, padx=4)

        tk.Label(top, text="Delay (ms):", bg="#121212", fg="#e0e0e0",
                 font=("Segoe UI", 10)).pack(side=tk.LEFT, padx=(8, 0))
        self.delay_var = tk.StringVar(value="300")
        tk.Entry(top, textvariable=self.delay_var, width=5,
                 bg="#2d2d2d", fg="#e0e0e0", insertbackground="#e0e0e0",
                 relief="flat").pack(side=tk.LEFT, padx=4)

        btn_frame = tk.Frame(self.root, bg="#121212")
        btn_frame.pack(fill=tk.X, padx=10, pady=4)

        self._btn(btn_frame, "Run All Tests", "#2980b9", "#3498db",
                  self._run_all).pack(side=tk.LEFT, padx=4)
        self._btn(btn_frame, "Test LEDs Only", "#27ae60", "#2ecc71",
                  self._run_leds).pack(side=tk.LEFT, padx=4)
        self._btn(btn_frame, "Test Answers Only", "#8e44ad", "#9b59b6",
                  self._run_answers).pack(side=tk.LEFT, padx=4)
        self._btn(btn_frame, "Send READY Trigger", "#c0392b", "#e74c3c",
                  self._send_ready).pack(side=tk.LEFT, padx=4)
        self._btn(btn_frame, "Dance Lights (3s)", "#7d3c98", "#8e44ad",
                  self._run_dance).pack(side=tk.LEFT, padx=4)
        self._btn(btn_frame, "Clear Log", "#333333", "#444444",
                  self._clear_log).pack(side=tk.RIGHT, padx=4)

        summary_frame = tk.Frame(self.root, bg="#121212")
        summary_frame.pack(fill=tk.X, padx=10, pady=(0, 4))
        self.summary_lbl = tk.Label(
            summary_frame, text="No tests run yet.",
            bg="#121212", fg="#aaaaaa", font=("Segoe UI", 10),
        )
        self.summary_lbl.pack(side=tk.LEFT)

        log_frame = tk.LabelFrame(self.root, text="Test Log",
                                  bg="#121212", fg="#e0e0e0",
                                  font=("Segoe UI", 10, "bold"))
        log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        self.log_box = scrolledtext.ScrolledText(
            log_frame, bg="#1a1a1a", fg="#cccccc",
            font=("Consolas", 9), state="disabled",
        )
        self.log_box.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        # colour tags
        self.log_box.tag_config("pass",  foreground="#2ecc71")
        self.log_box.tag_config("fail",  foreground="#e74c3c")
        self.log_box.tag_config("info",  foreground="#3498db")
        self.log_box.tag_config("warn",  foreground="#f39c12")
        self.log_box.tag_config("plain", foreground="#cccccc")

    # ── helpers ────────────────────────────────────────────────────────────

    @staticmethod
    def _btn(parent, text, color, hover, cmd):
        b = tk.Button(parent, text=text, bg=color, fg="#ffffff",
                      font=("Segoe UI", 9, "bold"),
                      activebackground=hover, relief="flat", bd=0,
                      padx=8, pady=4, command=cmd)
        b.bind("<Enter>", lambda _: b.config(bg=hover))
        b.bind("<Leave>", lambda _: b.config(bg=color))
        return b

    def _log(self, text: str, tag: str = "plain"):
        def _do():
            self.log_box.config(state="normal")
            self.log_box.insert("end", text + "\n", tag)
            self.log_box.see("end")
            self.log_box.config(state="disabled")
        self.root.after(0, _do)

    def _clear_log(self):
        self.log_box.config(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.config(state="disabled")

    def _set_summary(self, passed: int, failed: int):
        color = "#2ecc71" if failed == 0 else "#e74c3c"
        msg   = f"Results: {passed} passed, {failed} failed"
        self.root.after(0, lambda: self.summary_lbl.config(
            text=msg, fg=color))

    def _connect(self) -> bool:
        try:
            ip   = self.ip_var.get().strip()
            port = int(self.port_var.get().strip())
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(4)
            self.sock.connect((ip, port))
            greeting = self.sock.recv(64).decode("utf-8", errors="replace").strip()
            if "Connected" not in greeting:
                raise ConnectionError(f"Bad greeting: {greeting!r}")
            self._log(f"✓ Connected to {ip}:{port}", "pass")
            threading.Thread(target=self._recv_loop, daemon=True).start()
            return True
        except Exception as e:
            self._log(f"✗ Connection failed: {e}", "fail")
            self.sock = None
            return False

    def _disconnect(self):
        try:
            if self.sock:
                self.sock.close()
        except Exception:
            pass
        self.sock = None
        self._log("◦ Disconnected", "info")

    def _send(self, cmd: str) -> bool:
        if not self.sock:
            return False
        try:
            self.sock.sendall((cmd + "\r\n").encode("utf-8"))
            return True
        except Exception as e:
            self._log(f"  send error: {e}", "fail")
            return False

    def _recv_loop(self):
        while self.sock:
            try:
                data = self.sock.recv(256)
                if not data:
                    break
                with self._lock:
                    self._recv_buf += data.decode("utf-8", errors="replace")
            except Exception:
                break

    def _delay(self):
        try:
            ms = max(50, int(self.delay_var.get()))
        except ValueError:
            ms = 300
        time.sleep(ms / 1000)

    # ── test runners ───────────────────────────────────────────────────────

    def _run_all(self):
        threading.Thread(target=self._all_tests, daemon=True).start()

    def _run_leds(self):
        threading.Thread(target=self._led_tests, daemon=True).start()

    def _run_answers(self):
        threading.Thread(target=self._answer_tests, daemon=True).start()

    def _send_ready(self):
        threading.Thread(target=self._ready_test, daemon=True).start()

    def _run_dance(self):
        threading.Thread(target=self._dance_test, daemon=True).start()

    def _all_tests(self):
        passed = failed = 0
        self._log("═══ Full Test Suite ═══", "info")
        if not self._connect():
            self._set_summary(0, 1)
            return
        passed, failed = self._led_tests_inner(passed, failed)
        passed, failed = self._answer_tests_inner(passed, failed)
        passed, failed = self._ready_test_inner(passed, failed)
        passed, failed = self._dance_test_inner(passed, failed)
        self._disconnect()
        self._log(f"═══ Done: {passed} passed, {failed} failed ═══", "info")
        self._set_summary(passed, failed)

    def _led_tests(self):
        passed = failed = 0
        self._log("═══ LED Tests ═══", "info")
        if not self._connect():
            self._set_summary(0, 1)
            return
        passed, failed = self._led_tests_inner(passed, failed)
        self._disconnect()
        self._log(f"═══ Done: {passed} passed, {failed} failed ═══", "info")
        self._set_summary(passed, failed)

    def _led_tests_inner(self, passed, failed):
        for desc, cmd in LED_COMMANDS:
            ok = self._send(cmd)
            tag = "pass" if ok else "fail"
            sym = "✓" if ok else "✗"
            self._log(f"  {sym} LED {desc}", tag)
            if ok:
                passed += 1
            else:
                failed += 1
            self._delay()
        return passed, failed

    def _answer_tests(self):
        passed = failed = 0
        self._log("═══ Answer Tests ═══", "info")
        if not self._connect():
            self._set_summary(0, 1)
            return
        passed, failed = self._answer_tests_inner(passed, failed)
        self._disconnect()
        self._log(f"═══ Done: {passed} passed, {failed} failed ═══", "info")
        self._set_summary(passed, failed)

    def _answer_tests_inner(self, passed, failed):
        for desc, cmd in ANSWER_TESTS:
            ok = self._send(cmd)
            tag = "pass" if ok else "fail"
            sym = "✓" if ok else "✗"
            self._log(f"  {sym} Answer — {desc}", tag)
            if ok:
                passed += 1
            else:
                failed += 1
            self._delay()
        return passed, failed

    def _ready_test(self):
        passed = failed = 0
        self._log("═══ READY Trigger Test ═══", "info")
        if not self._connect():
            self._set_summary(0, 1)
            return
        passed, failed = self._ready_test_inner(passed, failed)
        self._disconnect()
        self._set_summary(passed, failed)

    def _ready_test_inner(self, passed, failed):
        ok = self._send("DASHBOARD-READY-TRIGGER")
        tag = "pass" if ok else "fail"
        sym = "✓" if ok else "✗"
        self._log(f"  {sym} READY trigger sent", tag)
        return (passed + 1, failed) if ok else (passed, failed + 1)

    def _dance_test(self):
        passed = failed = 0
        self._log("═══ Dance Lights Test (3 s) ═══", "info")
        if not self._connect():
            self._set_summary(0, 1)
            return
        passed, failed = self._dance_test_inner(passed, failed)
        self._disconnect()
        self._set_summary(passed, failed)

    def _dance_test_inner(self, passed, failed):
        ok1 = self._send("DANCE-LIGHTS-START")
        self._log(f"  {'✓' if ok1 else '✗'} Dance lights START", "pass" if ok1 else "fail")
        time.sleep(3)
        ok2 = self._send("DANCE-LIGHTS-STOP")
        self._log(f"  {'✓' if ok2 else '✗'} Dance lights STOP", "pass" if ok2 else "fail")
        p = (1 if ok1 else 0) + (1 if ok2 else 0)
        f = (0 if ok1 else 1) + (0 if ok2 else 1)
        return passed + p, failed + f


if __name__ == "__main__":
    root = tk.Tk()
    app  = ButtonTesterApp(root)
    root.geometry("760x520")
    root.mainloop()

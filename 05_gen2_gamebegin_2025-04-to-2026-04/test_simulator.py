"""
test_simulator.py  —  Gameshow System Test & Simulation Suite
=============================================================

Simulates all external components so you can verify the full system
works WITHOUT needing the physical EMS hardware present.

What it tests / simulates
──────────────────────────
  1. BSD Server TCP connection
       – Connects on port 8080 (or custom port)
       – Expects "Connected" greeting from BSD
  2. Gameshow → BSD link
       – Sends  awns_B\\r\\n             (video player sends correct answer)
       – Sends  DASHBOARD-READY-TRIGGER  (video player arms buzzers)
  3. EMS Hardware (buttons / IP gateway)
       – Sends  @TABLE:ANSWER\\r\\n      (legacy buzzer format)
       – Sends  |EMS|TABLE|ANSWER|QUESTION|\\r\\n  (current firmware format)
       – NOTE: The firmware adds a single non-UTF-8 prefix byte before
               |EMS|…  When BSD decodes with errors='replace' that byte
               becomes \\ufffd (shown as ?).  This simulator sends the
               message without the prefix so you can verify TCP delivery;
               the EMS-specific code path in BSD is tested via the legacy
               @TABLE:ANSWER format which uses the same routing internally.
  4. Leaderboard named pipe
       – Sends score commands  *1*2+100
       – Sends answer display  @3:A
       – Sends bulk answers    ANSWERS:1:A,2:B,3:C,4:D

All results are shown live in the GUI log.
"""

import socket
import threading
import time
import tkinter as tk
from tkinter import scrolledtext, ttk, messagebox
import win32pipe
import win32file
import pywintypes

# ── Config defaults ────────────────────────────────────────────────────────────
BSD_HOST_DEFAULT  = "127.0.0.1"
BSD_PORT_DEFAULT  = 8080
PIPE_NAME         = r'\\.\pipe\gameshow_pipe'

# ─────────────────────────────────────────────────────────────────────────────
# Low-level helpers
# ─────────────────────────────────────────────────────────────────────────────

def tcp_send(host: str, port: int, messages: list[str],
             timeout: float = 3.0) -> tuple[bool, str]:
    """
    Open a TCP connection, send each message, read whatever BSD replies,
    then return (success, log_text).
    """
    log = []
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        s.connect((host, port))
        log.append(f"  ✓ Connected to {host}:{port}")

        # Read greeting
        try:
            greeting = s.recv(256).decode("utf-8", errors="replace").strip()
            log.append(f"  → BSD says: '{greeting}'")
        except socket.timeout:
            log.append("  (no greeting within timeout — continuing)")

        for msg in messages:
            s.send(msg.encode("utf-8"))
            display = msg.replace("\r\n", "\\r\\n")
            log.append(f"  ↑ Sent: {display}")
            time.sleep(0.2)

        s.close()
        return True, "\n".join(log)
    except ConnectionRefusedError:
        log.append(f"  ✗ Connection refused — is BSD server running on {host}:{port}?")
        return False, "\n".join(log)
    except Exception as e:
        log.append(f"  ✗ Error: {e}")
        return False, "\n".join(log)


def pipe_send(messages: list[str]) -> tuple[bool, str]:
    """
    Send each message to the leaderboard via the Windows named pipe.
    Returns (success, log_text).
    """
    log = []
    all_ok = True
    for msg in messages:
        try:
            pipe = win32file.CreateFile(
                PIPE_NAME,
                win32file.GENERIC_WRITE,
                0, None,
                win32file.OPEN_EXISTING,
                0, None,
            )
            win32file.WriteFile(pipe, msg.encode("utf-8"))
            win32file.CloseHandle(pipe)
            log.append(f"  ✓ Pipe sent: {msg}")
            time.sleep(0.3)
        except pywintypes.error as e:
            log.append(f"  ✗ Pipe error for '{msg}': {e}")
            all_ok = False
        except Exception as e:
            log.append(f"  ✗ Unexpected error for '{msg}': {e}")
            all_ok = False
    return all_ok, "\n".join(log)


# ─────────────────────────────────────────────────────────────────────────────
# Individual test suites
# ─────────────────────────────────────────────────────────────────────────────

def test_bsd_connection(host: str, port: int) -> tuple[bool, str]:
    """Test 1 — just connect and verify BSD responds."""
    ok, log = tcp_send(host, port, [], timeout=3)
    return ok, f"[Test 1] BSD Connection\n{log}"


def test_gameshow_to_bsd(host: str, port: int) -> tuple[bool, str]:
    """Test 2 — simulate gameshow2.py sending awns_ and DASHBOARD-READY-TRIGGER."""
    msgs = [
        "awns_B\r\n",
        "DASHBOARD-READY-TRIGGER\r\n",
    ]
    ok, log = tcp_send(host, port, msgs)
    return ok, f"[Test 2] Gameshow → BSD (awns_ / READY trigger)\n{log}"


def test_ems_legacy(host: str, port: int, table: int = 2,
                    answer: str = "B") -> tuple[bool, str]:
    """Test 3a — legacy @TABLE:ANSWER buzzer format."""
    msg = f"@{table}:{answer}\r\n"
    ok, log = tcp_send(host, port, [msg])
    return ok, f"[Test 3a] EMS Legacy format (@TABLE:ANSWER)\n{log}"


def test_ems_firmware(host: str, port: int, table: int = 3,
                      answer: str = "C", question: int = 7199) -> tuple[bool, str]:
    """
    Test 3b — simulate EMS firmware message.
    The firmware sends a non-UTF-8 byte before |EMS|…  BSD decodes it with
    errors='replace', turning the prefix into \\ufffd.  We replicate that
    here so the startswith check in BSD matches correctly.
    """
    prefix = "\ufffd"   # the replacement char BSD sees from the firmware's prefix byte
    raw = f"{prefix}|EMS|{table}|{answer}|{question}|\r\n"
    ok, log = tcp_send(host, port, [raw])
    return ok, f"[Test 3b] EMS Firmware format (\\ufffd|EMS|TABLE|ANSWER|QUESTION|)\n{log}"


def test_multi_table_answers(host: str, port: int) -> tuple[bool, str]:
    """Test 4 — simulate multiple tables buzzing in sequentially."""
    msgs = []
    scenario = [(1, "A"), (2, "B"), (3, "A"), (4, "C"), (5, "D"), (6, "A")]
    for table, ans in scenario:
        msgs.append(f"@{table}:{ans}\r\n")

    ok, log = tcp_send(host, port, msgs, timeout=5)
    lines = [f"[Test 4] Multi-table answers (6 tables)"]
    lines.append(f"  Scenario: { {t:a for t,a in scenario} }")
    lines.append(log)
    return ok, "\n".join(lines)


def test_pipe_scores() -> tuple[bool, str]:
    """Test 5 — send score updates to the leaderboard via named pipe."""
    msgs = [
        "*1*2*3+100",     # tables 1,2,3 get +100
        "*4*5-50",        # tables 4,5 lose 50
        "*1+50",          # table 1 gets bonus
    ]
    ok, log = pipe_send(msgs)
    return ok, f"[Test 5] Leaderboard pipe — score updates\n{log}"


def test_pipe_answers() -> tuple[bool, str]:
    """Test 6 — send answer indicators to the leaderboard."""
    msgs = [
        "@1:A",
        "@2:B",
        "@3:C",
        "@4:D",
        "ANSWERS:1:A,2:B,3:C,4:A,5:D,6:B",
    ]
    ok, log = pipe_send(msgs)
    return ok, f"[Test 6] Leaderboard pipe — answer display\n{log}"


def run_full_suite(host: str, port: int,
                   log_fn) -> None:
    """Run all tests in sequence and report via log_fn(text)."""
    tests = [
        lambda: test_bsd_connection(host, port),
        lambda: test_gameshow_to_bsd(host, port),
        lambda: test_ems_legacy(host, port),
        lambda: test_ems_firmware(host, port),
        lambda: test_multi_table_answers(host, port),
        lambda: test_pipe_scores(),
        lambda: test_pipe_answers(),
    ]
    passed = 0
    for i, t in enumerate(tests, 1):
        log_fn(f"\n{'─'*50}")
        try:
            ok, text = t()
            log_fn(text)
            status = "PASS ✓" if ok else "FAIL ✗"
            log_fn(f"  Result: {status}")
            if ok:
                passed += 1
        except Exception as e:
            log_fn(f"  EXCEPTION: {e}")
        time.sleep(0.4)

    log_fn(f"\n{'═'*50}")
    log_fn(f"SUITE COMPLETE — {passed}/{len(tests)} tests passed")
    log_fn(f"{'═'*50}")


# ─────────────────────────────────────────────────────────────────────────────
# GUI
# ─────────────────────────────────────────────────────────────────────────────

class SimulatorApp:
    BG  = "#1a1a2e"
    BG2 = "#16213e"
    FG  = "#e0e0e0"
    ACC = "#e94560"

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Gameshow System — Test Simulator")
        self.root.geometry("720x660")
        self.root.configure(bg=self.BG)
        self._build()

    # ── UI construction ────────────────────────────────────────────────────────
    def _build(self):
        r = self.root

        # ── header
        tk.Label(r, text="GAMESHOW SYSTEM TEST SIMULATOR",
                 font=("Arial", 14, "bold"), fg=self.ACC,
                 bg=self.BG).pack(pady=(12, 2))
        tk.Label(r,
                 text="Simulates EMS hardware, WiFi gateway, and leaderboard pipe "
                      "— no physical hardware needed",
                 font=("Arial", 9), fg="#888", bg=self.BG).pack(pady=(0, 8))

        # ── connection settings
        cfg = tk.Frame(r, bg=self.BG2, padx=12, pady=8)
        cfg.pack(fill=tk.X, padx=14, pady=4)
        tk.Label(cfg, text="BSD Host:", fg=self.FG, bg=self.BG2,
                 font=("Segoe UI", 10)).grid(row=0, column=0, sticky="w", padx=(0, 6))
        self._host = tk.StringVar(value=BSD_HOST_DEFAULT)
        tk.Entry(cfg, textvariable=self._host, width=16, bg="#2d2d2d", fg=self.FG,
                 insertbackground=self.FG, relief="flat",
                 font=("Consolas", 10)).grid(row=0, column=1, padx=(0, 14))

        tk.Label(cfg, text="Port:", fg=self.FG, bg=self.BG2,
                 font=("Segoe UI", 10)).grid(row=0, column=2, sticky="w", padx=(0, 6))
        self._port = tk.StringVar(value=str(BSD_PORT_DEFAULT))
        tk.Entry(cfg, textvariable=self._port, width=7, bg="#2d2d2d", fg=self.FG,
                 insertbackground=self.FG, relief="flat",
                 font=("Consolas", 10)).grid(row=0, column=3)

        # ── individual test buttons
        btn_frame = tk.Frame(r, bg=self.BG, pady=4)
        btn_frame.pack(fill=tk.X, padx=14)

        tests = [
            ("1 · BSD Connection",          self._t1),
            ("2 · Gameshow → BSD",          self._t2),
            ("3a · EMS Legacy (@TABLE:ANS)", self._t3a),
            ("3b · EMS Firmware format",    self._t3b),
            ("4 · Multi-table Answers",     self._t4),
            ("5 · Leaderboard Scores",      self._t5),
            ("6 · Leaderboard Answers",     self._t6),
        ]

        for row_i in range(0, len(tests), 4):
            row = tk.Frame(btn_frame, bg=self.BG)
            row.pack(fill=tk.X, pady=2)
            for label, cmd in tests[row_i:row_i + 4]:
                tk.Button(row, text=label, font=("Segoe UI", 9),
                          bg="#0f3460", fg="#fff",
                          activebackground=self.ACC, activeforeground="#fff",
                          relief="flat", padx=8, pady=4,
                          command=cmd).pack(side=tk.LEFT, padx=3)

        # ── manual EMS simulator
        manual_frame = tk.LabelFrame(r, text="Manual EMS Button Simulator",
                                     bg=self.BG2, fg=self.FG,
                                     font=("Segoe UI", 10, "bold"),
                                     padx=10, pady=8)
        manual_frame.pack(fill=tk.X, padx=14, pady=4)

        row1 = tk.Frame(manual_frame, bg=self.BG2)
        row1.pack(fill=tk.X, pady=2)
        tk.Label(row1, text="Table:", fg=self.FG, bg=self.BG2,
                 font=("Segoe UI", 10)).pack(side=tk.LEFT, padx=(0, 4))
        self._man_table = tk.StringVar(value="1")
        ttk.Combobox(row1, textvariable=self._man_table, width=4,
                     values=[str(i) for i in range(1, 16)],
                     state="readonly").pack(side=tk.LEFT, padx=(0, 14))
        tk.Label(row1, text="Answer:", fg=self.FG, bg=self.BG2,
                 font=("Segoe UI", 10)).pack(side=tk.LEFT, padx=(0, 4))
        self._man_ans = tk.StringVar(value="A")
        ttk.Combobox(row1, textvariable=self._man_ans, width=4,
                     values=["A", "B", "C", "D"],
                     state="readonly").pack(side=tk.LEFT, padx=(0, 14))
        tk.Label(row1, text="Question ID:", fg=self.FG, bg=self.BG2,
                 font=("Segoe UI", 10)).pack(side=tk.LEFT, padx=(0, 4))
        self._man_qid = tk.StringVar(value="7199")
        tk.Entry(row1, textvariable=self._man_qid, width=7, bg="#2d2d2d", fg=self.FG,
                 insertbackground=self.FG, relief="flat",
                 font=("Consolas", 10)).pack(side=tk.LEFT, padx=(0, 14))

        row2 = tk.Frame(manual_frame, bg=self.BG2)
        row2.pack(fill=tk.X, pady=4)
        for label, fmt in [
            ("Send Legacy (@TABLE:ANS)",       "legacy"),
            ("Send Firmware (EMS format)",     "firmware"),
            ("Rapid Fire (all 12 tables → A)", "rapid"),
        ]:
            tk.Button(row2, text=label, font=("Segoe UI", 9),
                      bg="#0f3460", fg="#fff",
                      activebackground=self.ACC, activeforeground="#fff",
                      relief="flat", padx=8, pady=4,
                      command=lambda f=fmt: self._manual_send(f)).pack(side=tk.LEFT, padx=3)

        # ── leaderboard pipe controls
        lb_frame = tk.LabelFrame(r, text="Leaderboard Pipe — Direct Control",
                                 bg=self.BG2, fg=self.FG,
                                 font=("Segoe UI", 10, "bold"),
                                 padx=10, pady=8)
        lb_frame.pack(fill=tk.X, padx=14, pady=4)

        lb_row = tk.Frame(lb_frame, bg=self.BG2)
        lb_row.pack(fill=tk.X, pady=2)
        tk.Label(lb_row, text="Pipe command:", fg=self.FG, bg=self.BG2,
                 font=("Segoe UI", 10)).pack(side=tk.LEFT, padx=(0, 6))
        self._pipe_cmd = tk.StringVar(value="*1*2+100")
        tk.Entry(lb_row, textvariable=self._pipe_cmd, width=22, bg="#2d2d2d", fg=self.FG,
                 insertbackground=self.FG, relief="flat",
                 font=("Consolas", 10)).pack(side=tk.LEFT, padx=(0, 8))
        tk.Button(lb_row, text="Send to Leaderboard",
                  font=("Segoe UI", 9),
                  bg="#27ae60", fg="#fff",
                  activebackground="#2ecc71", activeforeground="#fff",
                  relief="flat", padx=8, pady=4,
                  command=self._send_pipe_manual).pack(side=tk.LEFT)
        tk.Label(lb_row,
                 text="  Formats: *1*2+100  |  @3:B  |  ANSWERS:1:A,2:B",
                 fg="#666", bg=self.BG2, font=("Segoe UI", 8)).pack(side=tk.LEFT, padx=8)

        # ── full suite button
        suite_row = tk.Frame(r, bg=self.BG, pady=6)
        suite_row.pack(fill=tk.X, padx=14)
        tk.Button(suite_row, text="▶  Run Full Test Suite",
                  font=("Segoe UI", 11, "bold"),
                  bg="#8e44ad", fg="#fff",
                  activebackground="#9b59b6", activeforeground="#fff",
                  relief="flat", padx=14, pady=6,
                  command=self._full_suite).pack(side=tk.LEFT)
        tk.Button(suite_row, text="Clear Log",
                  font=("Segoe UI", 10),
                  bg="#333", fg="#fff",
                  activebackground="#555", activeforeground="#fff",
                  relief="flat", padx=10, pady=6,
                  command=self._clear).pack(side=tk.LEFT, padx=8)

        # ── log
        log_frame = tk.Frame(r, bg=self.BG)
        log_frame.pack(fill=tk.BOTH, expand=True, padx=14, pady=(0, 10))
        self.log = scrolledtext.ScrolledText(
            log_frame, height=10,
            font=("Consolas", 9),
            bg="#0d0d1a", fg="#d0d0d0",
            insertbackground="#fff",
        )
        self.log.pack(fill=tk.BOTH, expand=True)
        self._write("Gameshow Test Simulator ready.\n"
                    "Make sure BSD is running and the leaderboard is open before testing.\n")

    # ── helpers ────────────────────────────────────────────────────────────────
    def _write(self, text: str):
        self.log.insert(tk.END, text + "\n")
        self.log.see(tk.END)

    def _clear(self):
        self.log.delete("1.0", tk.END)

    def _get_host_port(self):
        try:
            return self._host.get().strip(), int(self._port.get().strip())
        except ValueError:
            messagebox.showerror("Bad port", "Port must be a number", parent=self.root)
            return None, None

    def _run_async(self, fn):
        threading.Thread(target=fn, daemon=True).start()

    # ── individual test dispatchers ────────────────────────────────────────────
    def _t1(self): self._run_async(lambda: self._exec(test_bsd_connection, *self._get_hp()))
    def _t2(self): self._run_async(lambda: self._exec(test_gameshow_to_bsd, *self._get_hp()))
    def _t3a(self): self._run_async(lambda: self._exec(test_ems_legacy, *self._get_hp()))
    def _t3b(self): self._run_async(lambda: self._exec(test_ems_firmware, *self._get_hp()))
    def _t4(self): self._run_async(lambda: self._exec(test_multi_table_answers, *self._get_hp()))
    def _t5(self): self._run_async(lambda: self._exec_pipe(test_pipe_scores))
    def _t6(self): self._run_async(lambda: self._exec_pipe(test_pipe_answers))

    def _get_hp(self):
        return self._get_host_port()

    def _exec(self, fn, host, port):
        if host is None:
            return
        ok, text = fn(host, port)
        self.root.after(0, lambda: self._write(text))

    def _exec_pipe(self, fn):
        ok, text = fn()
        self.root.after(0, lambda: self._write(text))

    # ── manual EMS send ────────────────────────────────────────────────────────
    def _manual_send(self, fmt: str):
        host, port = self._get_host_port()
        if host is None:
            return
        table  = self._man_table.get()
        answer = self._man_ans.get()
        qid    = self._man_qid.get()

        def _do():
            if fmt == "legacy":
                ok, text = tcp_send(host, port, [f"@{table}:{answer}\r\n"])
                self.root.after(0, lambda: self._write(
                    f"[Manual Legacy] @{table}:{answer}\n{text}"))
            elif fmt == "firmware":
                ok, text = test_ems_firmware(host, port,
                                             int(table), answer, int(qid))
                self.root.after(0, lambda: self._write(text))
            elif fmt == "rapid":
                # Simulate all 12 tables buzzing answer A
                msgs = [f"@{t}:A\r\n" for t in range(1, 13)]
                ok, text = tcp_send(host, port, msgs, timeout=8)
                self.root.after(0, lambda: self._write(
                    f"[Rapid Fire] 12 tables → A\n{text}"))

        self._run_async(_do)

    def _send_pipe_manual(self):
        cmd = self._pipe_cmd.get().strip()
        if not cmd:
            return

        def _do():
            ok, text = pipe_send([cmd])
            self.root.after(0, lambda: self._write(
                f"[Pipe Manual]\n{text}"))

        self._run_async(_do)

    # ── full suite ─────────────────────────────────────────────────────────────
    def _full_suite(self):
        host, port = self._get_host_port()
        if host is None:
            return
        self._write("\n" + "═" * 50)
        self._write("STARTING FULL TEST SUITE")
        self._write("═" * 50)

        def _do():
            run_full_suite(host, port,
                           lambda t: self.root.after(0, lambda txt=t: self._write(txt)))

        self._run_async(_do)

    def run(self):
        self.root.mainloop()


# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    SimulatorApp().run()

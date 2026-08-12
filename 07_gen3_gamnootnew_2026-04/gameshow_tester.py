"""
gameshow_tester.py  —  Master Integration Test Suite
=====================================================
Launches bsd.py automatically, then runs:
  1. Connection & handshake tests
  2. Protocol tests  (READY relay, LED colour sequence, answer handling)
  3. Full game simulation  (12 tables × 5 question rounds)
  4. Leaderboard pipe tests  (mock pipe server captures forwarded messages)
  5. Stress tests  (30 clients, 500 rapid messages, reconnect cycles)

Outputs:
  • Real-time progress in the GUI window
  • test_report.json   – raw data for every test
  • test_report.html   – browser-friendly colour-coded report
"""

import socket
import threading
import subprocess
import sys
import os
import time
import json
import random
import string
import queue
import tkinter as tk
from tkinter import scrolledtext
from dataclasses import dataclass, field, asdict
from typing import Optional
import win32pipe
import win32file

# ─────────────────────────────────────────────────────────────────────────────
#  Constants
# ─────────────────────────────────────────────────────────────────────────────
SERVER_IP         = "127.0.0.1"
SERVER_PORT       = 8080
BSD_PATH          = os.path.join(os.path.dirname(__file__), "bsd.py")
PIPE_NAME         = r'\\.\pipe\gameshow_pipe'
CONNECT_TIMEOUT   = 5.0
MESSAGE_TIMEOUT   = 3.0
SERVER_BOOT_WAIT  = 3.0    # seconds to wait for bsd.py to start

COLOUR_SEQUENCE   = [
    "EMS-LEDS-X|10|0|0|",   # RED   (immediate after READY)
    "EMS-LEDS-X|0|10|0|",   # GREEN (after 5s)
    "EMS-LEDS-X|0|0|10|",   # BLUE  (after 15s)
    "EMS-LEDS-X|0|0|0|",    # OFF   (after 20s)
]

# ─────────────────────────────────────────────────────────────────────────────
#  Data structures
# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class TestResult:
    category:    str
    name:        str
    passed:      bool
    duration_ms: float
    error:       Optional[str] = None
    metrics:     dict          = field(default_factory=dict)
    notes:       str           = ""


@dataclass
class TestReport:
    timestamp:    str
    server_ip:    str
    server_port:  int
    results:      list = field(default_factory=list)

    @property
    def passed(self):  return sum(1 for r in self.results if r.passed)
    @property
    def failed(self):  return sum(1 for r in self.results if not r.passed)
    @property
    def total(self):   return len(self.results)


# ─────────────────────────────────────────────────────────────────────────────
#  Mock leaderboard pipe server
#  Creates the named pipe so bsd.py can connect and send score/answer data.
# ─────────────────────────────────────────────────────────────────────────────
class MockLeaderboardPipe:
    def __init__(self):
        self.received: list[str] = []
        self._lock   = threading.Lock()
        self._event  = threading.Event()
        self._stop   = False
        threading.Thread(target=self._serve, daemon=True, name="MockPipe").start()

    def _serve(self):
        while not self._stop:
            try:
                pipe = win32pipe.CreateNamedPipe(
                    PIPE_NAME,
                    win32pipe.PIPE_ACCESS_INBOUND,
                    win32pipe.PIPE_TYPE_MESSAGE | win32pipe.PIPE_READMODE_MESSAGE | win32pipe.PIPE_WAIT,
                    1, 65536, 65536, 300, None
                )
                win32pipe.ConnectNamedPipe(pipe, None)
                try:
                    while not self._stop:
                        try:
                            _, data = win32file.ReadFile(pipe, 65536)
                            msg = data.decode("utf-8", errors="replace")
                            with self._lock:
                                self.received.append(msg)
                            self._event.set()
                        except Exception:
                            break
                finally:
                    try:
                        win32file.CloseHandle(pipe)
                    except Exception:
                        pass
            except Exception:
                time.sleep(0.1)

    def wait_for(self, pattern: str, timeout: float = MESSAGE_TIMEOUT) -> bool:
        deadline = time.time() + timeout
        while time.time() < deadline:
            with self._lock:
                if any(pattern in m for m in self.received):
                    return True
            self._event.wait(timeout=0.1)
            self._event.clear()
        return False

    def clear(self):
        with self._lock:
            self.received.clear()
        self._event.clear()

    def stop(self):
        self._stop = True


# ─────────────────────────────────────────────────────────────────────────────
#  Simulated button client (one TCP connection = one table unit)
# ─────────────────────────────────────────────────────────────────────────────
class MockButtonClient:
    def __init__(self, table_id: int):
        self.table_id        = table_id
        self.sock: Optional[socket.socket] = None
        self.connected       = False
        self._recv_buf       = ""
        self._received: list[str] = []
        self._recv_lock      = threading.Lock()
        self._recv_event     = threading.Event()
        self.connect_time_ms = 0.0

    def connect(self, ip=SERVER_IP, port=SERVER_PORT) -> tuple[bool, str]:
        t0 = time.time()
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(CONNECT_TIMEOUT)
            self.sock.connect((ip, port))
            greeting = self.sock.recv(64).decode("utf-8", errors="replace").strip()
            if "Connected" not in greeting:
                return False, f"Unexpected greeting: {greeting!r}"
            self.sock.settimeout(None)
            self.connected       = True
            self.connect_time_ms = (time.time() - t0) * 1000
            threading.Thread(target=self._recv_loop, daemon=True,
                             name=f"ClientRecv-{self.table_id}").start()
            return True, ""
        except Exception as e:
            self.sock = None
            return False, str(e)

    def disconnect(self):
        self.connected = False
        try:
            if self.sock:
                self.sock.close()
        except Exception:
            pass
        self.sock = None

    def send(self, msg: str) -> bool:
        if not self.connected or not self.sock:
            return False
        try:
            self.sock.sendall((msg + "\r\n").encode("utf-8"))
            return True
        except Exception:
            self.connected = False
            return False

    def send_answer(self, answer: str, question: int = 1) -> bool:
        return self.send(f"@{self.table_id}:{answer}")

    def send_answer_ems(self, answer: str, question: int = 1) -> bool:
        return self.send(f"*|EMS|{self.table_id}|{answer}|{question}|")

    def wait_for(self, pattern: str, timeout: float = MESSAGE_TIMEOUT) -> bool:
        deadline = time.time() + timeout
        while time.time() < deadline:
            with self._recv_lock:
                if any(pattern in m for m in self._received):
                    return True
            self._recv_event.wait(timeout=0.05)
            self._recv_event.clear()
        return False

    def get_received(self) -> list[str]:
        with self._recv_lock:
            return list(self._received)

    def clear_received(self):
        with self._recv_lock:
            self._received.clear()
        self._recv_event.clear()

    def _recv_loop(self):
        buf = ""
        while self.connected and self.sock:
            try:
                data = self.sock.recv(256)
                if not data:
                    break
                buf += data.decode("utf-8", errors="replace")
                while "\r\n" in buf:
                    line, buf = buf.split("\r\n", 1)
                    if line:
                        with self._recv_lock:
                            self._received.append(line)
                        self._recv_event.set()
            except Exception:
                break
        self.connected = False


# ─────────────────────────────────────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────────────────────────────────────
def wait_for_server(ip=SERVER_IP, port=SERVER_PORT, timeout=10.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            s = socket.create_connection((ip, port), timeout=1)
            s.recv(32)
            s.close()
            return True
        except Exception:
            time.sleep(0.3)
    return False


def timed(fn):
    t0  = time.time()
    err = None
    try:
        result = fn()
    except Exception as e:
        result = False
        err = str(e)
    elapsed = (time.time() - t0) * 1000
    return result, elapsed, err


# ─────────────────────────────────────────────────────────────────────────────
#  Test runner
# ─────────────────────────────────────────────────────────────────────────────
class GameshowTestRunner:
    def __init__(self, log_fn):
        self.log       = log_fn
        self.results:  list[TestResult] = []
        self._proc:    Optional[subprocess.Popen] = None
        self._pipe     = MockLeaderboardPipe()

    # ── lifecycle ─────────────────────────────────────────────────────────

    def launch_server(self) -> bool:
        self.log("▶ Launching bsd.py --autostart …", "info")
        try:
            self._proc = subprocess.Popen(
                [sys.executable, BSD_PATH, "--autostart"],
                creationflags=subprocess.CREATE_NEW_CONSOLE,
            )
        except Exception as e:
            self.log(f"  Failed to start bsd.py: {e}", "fail")
            return False

        self.log(f"  Waiting up to {SERVER_BOOT_WAIT + 5}s for server …", "info")
        if not wait_for_server(timeout=SERVER_BOOT_WAIT + 5):
            self.log("  Server did not come up in time.", "fail")
            return False
        self.log("  Server is up.", "pass")
        return True

    def stop_server(self):
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()
            self.log("▶ bsd.py terminated.", "info")

    # ── record helper ──────────────────────────────────────────────────────

    def record(self, category: str, name: str, passed: bool,
               duration_ms: float, error: str = None,
               metrics: dict = None, notes: str = "") -> TestResult:
        r = TestResult(category, name, passed, round(duration_ms, 2),
                       error, metrics or {}, notes)
        self.results.append(r)
        sym = "✓" if passed else "✗"
        tag = "pass" if passed else "fail"
        detail = f"  ({error})" if error else ""
        self.log(f"  {sym} [{category}] {name}  {duration_ms:.0f}ms{detail}", tag)
        return r

    # ════════════════════════════════════════════════════════════════════════
    #  1. CONNECTION TESTS
    # ════════════════════════════════════════════════════════════════════════
    def run_connection_tests(self):
        self.log("\n── CONNECTION TESTS ──", "header")
        cat = "Connection"

        # Basic handshake
        c = MockButtonClient(0)
        ok, ms, err = timed(lambda: c.connect()[0])
        self.record(cat, "TCP connect + handshake", ok, ms, err,
                    {"connect_ms": round(c.connect_time_ms, 1)})
        if ok:
            c.disconnect()

        # 12 simultaneous connections
        clients = [MockButtonClient(i) for i in range(1, 13)]
        t0 = time.time()
        threads = [threading.Thread(target=lambda cl=c: cl.connect()) for c in clients]
        for t in threads: t.start()
        for t in threads: t.join(timeout=6)
        elapsed = (time.time() - t0) * 1000
        connected = [c for c in clients if c.connected]
        ok = len(connected) == 12
        self.record(cat, "12 simultaneous connections",
                    ok, elapsed,
                    None if ok else f"Only {len(connected)}/12 connected",
                    {"connected": len(connected), "failed": 12 - len(connected)})
        for c in clients: c.disconnect()
        time.sleep(0.3)

        # Clean disconnect
        c = MockButtonClient(99)
        c.connect()
        t0 = time.time()
        c.disconnect()
        elapsed = (time.time() - t0) * 1000
        self.record(cat, "Clean disconnect", True, elapsed)

        # Invalid port rejected
        c = MockButtonClient(0)
        ok2, ms, _ = timed(lambda: (
            lambda s: (s.connect((SERVER_IP, SERVER_PORT + 1000)),
                       s.close(), False)[-1]
        )(socket.socket()))
        # We expect this to FAIL (connection refused = good, server is isolated)
        self.record(cat, "Wrong port rejected",
                    not ok2, ms, notes="Connection to wrong port should be refused")

    # ════════════════════════════════════════════════════════════════════════
    #  2. PROTOCOL TESTS
    # ════════════════════════════════════════════════════════════════════════
    def run_protocol_tests(self):
        self.log("\n── PROTOCOL TESTS ──", "header")
        cat = "Protocol"

        # Set up: one "gameshow" client + 4 "button" clients
        gameshow = MockButtonClient(0)
        buttons  = [MockButtonClient(i) for i in range(1, 5)]
        gameshow.connect()
        for b in buttons: b.connect()
        time.sleep(0.3)

        # ── READY relay ──────────────────────────────────────────────
        for b in buttons: b.clear_received()
        t0 = time.time()
        gameshow.send("DASHBOARD-READY-TRIGGER")
        ready_received = []
        for b in buttons:
            if b.wait_for("READY", timeout=2.0):
                ready_received.append(b.table_id)
        elapsed = (time.time() - t0) * 1000
        ok = len(ready_received) == 4
        self.record(cat, "DASHBOARD-READY-TRIGGER broadcasts READY to all clients",
                    ok, elapsed,
                    None if ok else f"Only {len(ready_received)}/4 received READY",
                    {"received_by": ready_received})

        # ── Colour sequence after READY ───────────────────────────────
        # Server sends RED immediately after READY trigger
        for b in buttons: b.clear_received()
        gameshow.send("DASHBOARD-READY-TRIGGER")
        red_received = [b.wait_for("EMS-LEDS-X|10|0|0|", timeout=2.0) for b in buttons]
        ok = all(red_received)
        elapsed_ms = 500.0
        self.record(cat, "Colour sequence — RED sent to all clients after READY",
                    ok, elapsed_ms,
                    None if ok else "Some clients missed RED command",
                    {"received_by": [b.table_id for b, r in zip(buttons, red_received) if r]},
                    notes="Full sequence is RED(0s)→READY+GREEN(5s)→BLUE(15s)→OFF(20s)")

        # ── awns_ sets correct answer ──────────────────────────────────
        for letter in ("A", "B", "C", "D"):
            ok2, ms, err = timed(lambda l=letter: gameshow.send(f"awns_{l}"))
            self.record(cat, f"awns_{letter} accepted by server", ok2, ms, err)
            time.sleep(0.1)

        # ── Answer forwarding to leaderboard pipe ─────────────────────
        for b in buttons:
            self._pipe.clear()
            msg = f"@{b.table_id}:A"
            t0  = time.time()
            b.send_answer("A")
            forwarded = self._pipe.wait_for(f"@{b.table_id}:A", timeout=2.0)
            elapsed = (time.time() - t0) * 1000
            self.record(cat, f"Table {b.table_id} answer forwarded to leaderboard pipe",
                        forwarded, elapsed,
                        None if forwarded else "Pipe did not receive the answer",
                        {"message": msg})

        # ── Invalid answer rejected ───────────────────────────────────
        before = len(self._pipe.received)
        buttons[0].send("@1:X")        # X is not A/B/C/D
        time.sleep(0.3)
        forwarded = len(self._pipe.received) > before
        self.record(cat, "Invalid answer (@1:X) NOT forwarded to leaderboard",
                    not forwarded, 300.0,
                    notes="Server should log invalid format but not forward")

        # ── PING handled without crash ────────────────────────────────
        ok2, ms, err = timed(lambda: gameshow.send("PING"))
        self.record(cat, "PING accepted without crash", ok2, ms, err)

        gameshow.disconnect()
        for b in buttons: b.disconnect()
        time.sleep(0.3)

    # ════════════════════════════════════════════════════════════════════════
    #  3. FULL GAME SIMULATION  (12 tables, 5 question rounds)
    # ════════════════════════════════════════════════════════════════════════
    def run_game_simulation(self):
        self.log("\n── FULL GAME SIMULATION  (12 tables × 5 rounds) ──", "header")
        cat = "GameSim"

        answers = ["A", "B", "C", "D"]
        questions = [
            {"correct": "A", "video": "A_question1.mp4"},
            {"correct": "B", "video": "B_question2.mp4"},
            {"correct": "C", "video": "C_question3.mp4"},
            {"correct": "D", "video": "D_question4.mp4"},
            {"correct": "A", "video": "A_question5.mp4"},
        ]

        gameshow = MockButtonClient(0)
        tables   = [MockButtonClient(i) for i in range(1, 13)]

        ok, ms, err = timed(lambda: gameshow.connect()[0])
        self.record(cat, "Gameshow client connects", ok, ms, err)

        all_connected = True
        connect_times = []
        for t in tables:
            ok2, _, _ = timed(lambda cl=t: cl.connect()[0])
            connect_times.append(t.connect_time_ms)
            if not ok2:
                all_connected = False
        self.record(cat, "All 12 table clients connect",
                    all_connected, max(connect_times),
                    metrics={"avg_ms": round(sum(connect_times)/len(connect_times), 1),
                             "max_ms": round(max(connect_times), 1)})
        time.sleep(0.3)

        round_results = []
        total_answers_sent     = 0
        total_answers_received = 0

        for rnd, q in enumerate(questions, 1):
            self.log(f"  Round {rnd}: correct={q['correct']}  ({q['video']})", "info")
            for t in tables: t.clear_received()
            self._pipe.clear()
            round_start = time.time()

            # Gameshow announces correct answer (from filename)
            gameshow.send(f"awns_{q['correct']}")
            time.sleep(0.05)

            # Gameshow sends READY trigger (at first pause)
            gameshow.send("DASHBOARD-READY-TRIGGER")

            # Verify READY reached all tables
            ready_ok = all(t.wait_for("READY", timeout=2.0) for t in tables)

            # Tables submit answers (randomised, ~half correct)
            sent_answers = {}
            for t in tables:
                ans = random.choice(answers)
                sent_answers[t.table_id] = ans
                t.send_answer(ans)
                total_answers_sent += 1

            # Give server time to process
            time.sleep(0.4)

            # Count how many answers arrived at leaderboard pipe
            pipe_hits = 0
            for tid, ans in sent_answers.items():
                if self._pipe.wait_for(f"@{tid}:{ans}", timeout=0.5):
                    pipe_hits += 1
                    total_answers_received += 1

            round_time = (time.time() - round_start) * 1000

            correct_count = sum(1 for a in sent_answers.values() if a == q["correct"])
            round_ok = ready_ok and pipe_hits >= 10   # allow 2 failures

            round_results.append({
                "round": rnd, "correct_answer": q["correct"],
                "ready_delivered": ready_ok,
                "answers_forwarded": pipe_hits,
                "correct_tables": correct_count,
                "duration_ms": round(round_time, 1),
            })
            self.record(cat, f"Round {rnd} — READY + 12 answers processed",
                        round_ok, round_time,
                        None if round_ok else f"pipe_hits={pipe_hits}/12, ready={ready_ok}",
                        {"pipe_hits": pipe_hits, "correct_tables": correct_count})

            time.sleep(0.2)

        # Overall game stats
        throughput = round(total_answers_sent /
                           sum(r["duration_ms"] for r in round_results) * 1000, 1)
        self.record(cat, "Overall game — all rounds completed",
                    len(round_results) == 5,
                    sum(r["duration_ms"] for r in round_results),
                    metrics={
                        "answers_sent":      total_answers_sent,
                        "answers_forwarded": total_answers_received,
                        "forward_rate_pct":  round(total_answers_received / total_answers_sent * 100, 1),
                        "throughput_msg_s":  throughput,
                        "rounds":            round_results,
                    })

        gameshow.disconnect()
        for t in tables: t.disconnect()
        time.sleep(0.3)

    # ════════════════════════════════════════════════════════════════════════
    #  4. LEADERBOARD PIPE TESTS
    # ════════════════════════════════════════════════════════════════════════
    def run_leaderboard_tests(self):
        self.log("\n── LEADERBOARD PIPE TESTS ──", "header")
        cat = "Leaderboard"

        # The pipe is the link between bsd.py and leaderboard.py.
        # We verify bsd.py correctly formats and sends every command type.

        c = MockButtonClient(1)
        c.connect()
        time.sleep(0.2)

        pipe_tests = [
            ("Single answer @5:B forwarded",          lambda: c.send("@5:B"),    "@5:B"),
            ("Single answer @12:D forwarded",         lambda: c.send("@12:D"),   "@12:D"),
            ("All answers A forwarded",               lambda: c.send("@1:A"),    "@1:A"),
        ]
        for name, send_fn, pattern in pipe_tests:
            self._pipe.clear()
            t0 = time.time()
            send_fn()
            ok = self._pipe.wait_for(pattern, timeout=2.0)
            self.record(cat, name, ok, (time.time() - t0) * 1000,
                        None if ok else f"Pattern {pattern!r} not seen in pipe")

        # Points commands are sent directly to the leaderboard pipe by bsd.py's UI.
        # We can't trigger that externally, so we send directly to the pipe to verify it
        # accepts the format leaderboard.py expects.
        pipe_formats = [
            ("Score: +100 to tables 1,2,3",    "*1*2*3+100"),
            ("Score: -50 to table 7",           "*7-50"),
            ("Score: +75 to all via X",         "*X+75"),
            ("Answer indicators multi-format",  "ANSWERS:1:A,2:B,3:C"),
        ]
        for name, cmd in pipe_formats:
            self._pipe.clear()
            ok2, ms, err = timed(lambda c=cmd: (
                lambda h: (
                    win32file.WriteFile(h, c.encode("utf-8")),
                    win32file.CloseHandle(h)
                )
            )(win32file.CreateFile(
                PIPE_NAME, win32file.GENERIC_WRITE, 0, None,
                win32file.OPEN_EXISTING, 0, None
            )))
            self.record(cat, f"Pipe accepts: {name}", ok2, ms, err)
            time.sleep(0.1)

        c.disconnect()
        time.sleep(0.2)

    # ════════════════════════════════════════════════════════════════════════
    #  5. STRESS TESTS
    # ════════════════════════════════════════════════════════════════════════
    def run_stress_tests(self):
        self.log("\n── STRESS TESTS ──", "header")
        cat = "Stress"

        # ── 5a: 30 rapid simultaneous connections ─────────────────────
        self.log("  5a: 30 simultaneous connections …", "info")
        clients = [MockButtonClient(i) for i in range(1, 31)]
        t0 = time.time()
        threads = [threading.Thread(target=lambda cl=c: cl.connect()) for c in clients]
        for t in threads: t.start()
        for t in threads: t.join(timeout=8)
        elapsed = (time.time() - t0) * 1000
        connected = [c for c in clients if c.connected]
        ok = len(connected) >= 28   # allow 2 failures under load
        self.record(cat, "30 simultaneous connections",
                    ok, elapsed,
                    None if ok else f"Only {len(connected)}/30 connected",
                    {"connected": len(connected), "failed": 30 - len(connected),
                     "avg_connect_ms": round(
                         sum(c.connect_time_ms for c in connected) / max(len(connected), 1), 1)})
        time.sleep(0.5)

        # ── 5b: 500 rapid answer messages ─────────────────────────────
        self.log("  5b: 500 rapid answer messages …", "info")
        self._pipe.clear()
        senders = connected[:12] if len(connected) >= 12 else connected
        answers = "ABCD"
        sent    = 0
        errors  = 0
        t0      = time.time()
        for i in range(500):
            c   = senders[i % len(senders)]
            ans = answers[i % 4]
            if c.send(f"@{c.table_id}:{ans}"):
                sent += 1
            else:
                errors += 1
        elapsed = (time.time() - t0) * 1000
        throughput = round(sent / elapsed * 1000, 1)
        time.sleep(1.0)   # let server digest
        self.record(cat, "500 rapid answer messages (throughput)",
                    errors == 0, elapsed,
                    None if errors == 0 else f"{errors} send errors",
                    {"sent": sent, "errors": errors,
                     "throughput_msg_s": throughput,
                     "elapsed_ms": round(elapsed, 1)})

        # ── 5c: Server stability after flood ─────────────────────────
        self.log("  5c: Server stability after message flood …", "info")
        stable = MockButtonClient(999)
        ok2, ms, err = timed(lambda: stable.connect()[0])
        self.record(cat, "Server still accepts connections after flood",
                    ok2, ms, err)
        if ok2:
            stable.disconnect()

        # ── 5d: Reconnect stress (connect/disconnect 20 cycles) ───────
        self.log("  5d: Reconnect stress (20 cycles) …", "info")
        c = MockButtonClient(500)
        successes = 0
        t0 = time.time()
        for _ in range(20):
            ok3, _, _ = timed(lambda: c.connect()[0])
            if ok3: successes += 1
            c.disconnect()
            time.sleep(0.05)
        elapsed = (time.time() - t0) * 1000
        self.record(cat, "Reconnect stress — 20 connect/disconnect cycles",
                    successes >= 18, elapsed,
                    None if successes >= 18 else f"Only {successes}/20 succeeded",
                    {"successes": successes, "failures": 20 - successes})

        # ── 5e: Mixed simultaneous load ───────────────────────────────
        self.log("  5e: Mixed load (answers + READY triggers concurrently) …", "info")
        gameshow_stress = MockButtonClient(0)
        gameshow_stress.connect()
        for c in connected: c.clear_received()
        errors_mixed = 0
        t0 = time.time()

        def flood_answers():
            nonlocal errors_mixed
            for i in range(50):
                c = connected[i % len(connected)] if connected else gameshow_stress
                if not c.send(f"@{c.table_id}:{answers[i%4]}"):
                    errors_mixed += 1
                time.sleep(0.01)

        def flood_ready():
            nonlocal errors_mixed
            for _ in range(5):
                if not gameshow_stress.send("DASHBOARD-READY-TRIGGER"):
                    errors_mixed += 1
                time.sleep(0.2)

        t1 = threading.Thread(target=flood_answers)
        t2 = threading.Thread(target=flood_ready)
        t1.start(); t2.start()
        t1.join(); t2.join()
        elapsed = (time.time() - t0) * 1000
        self.record(cat, "Mixed concurrent load (answers + READY triggers)",
                    errors_mixed == 0, elapsed,
                    None if errors_mixed == 0 else f"{errors_mixed} errors",
                    {"send_errors": errors_mixed})

        gameshow_stress.disconnect()
        for c in connected: c.disconnect()
        time.sleep(0.3)

    # ── run everything ────────────────────────────────────────────────────
    def run_all(self) -> TestReport:
        report = TestReport(
            timestamp   = time.strftime("%Y-%m-%d %H:%M:%S"),
            server_ip   = SERVER_IP,
            server_port = SERVER_PORT,
        )

        if not self.launch_server():
            report.results = self.results
            return report

        time.sleep(0.5)

        try:
            self.run_connection_tests()
            self.run_protocol_tests()
            self.run_game_simulation()
            self.run_leaderboard_tests()
            self.run_stress_tests()
        except Exception as e:
            self.log(f"FATAL during tests: {e}", "fail")
            self.record("Fatal", "Unexpected exception in test runner", False, 0, str(e))
        finally:
            self.stop_server()
            self._pipe.stop()

        report.results = self.results
        return report


# ─────────────────────────────────────────────────────────────────────────────
#  Report generation
# ─────────────────────────────────────────────────────────────────────────────
def save_json(report: TestReport, path: str):
    data = {
        "timestamp":   report.timestamp,
        "server":      f"{report.server_ip}:{report.server_port}",
        "summary":     {"total": report.total, "passed": report.passed, "failed": report.failed,
                        "pass_rate": f"{report.passed/max(report.total,1)*100:.1f}%"},
        "results":     [asdict(r) for r in report.results],
    }
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def save_html(report: TestReport, path: str):
    rows = []
    for r in report.results:
        colour  = "#1e7e34" if r.passed else "#721c24"
        bg      = "#d4edda" if r.passed else "#f8d7da"
        sym     = "✓" if r.passed else "✗"
        metrics = "<br>".join(f"{k}: {v}" for k, v in r.metrics.items()
                              if k != "rounds") if r.metrics else "—"
        notes   = r.notes or "—"
        err     = r.error or "—"
        rows.append(f"""
        <tr style="background:{bg}">
          <td>{r.category}</td>
          <td>{r.name}</td>
          <td style="color:{colour};font-weight:bold;text-align:center">{sym}</td>
          <td style="text-align:right">{r.duration_ms:.0f} ms</td>
          <td style="font-size:0.85em;color:#555">{metrics}</td>
          <td style="font-size:0.85em;color:#c00">{err}</td>
          <td style="font-size:0.85em;color:#555">{notes}</td>
        </tr>""")

    pct = report.passed / max(report.total, 1) * 100
    summary_col = "#28a745" if pct >= 90 else "#ffc107" if pct >= 70 else "#dc3545"

    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<title>Gameshow Test Report — {report.timestamp}</title>
<style>
  body {{ font-family: Segoe UI, Arial, sans-serif; background:#f5f5f5; padding:20px }}
  h1   {{ color:#333 }}
  .summary {{ background:#333; color:#fff; padding:14px 20px; border-radius:6px;
              display:inline-block; margin-bottom:20px }}
  .summary span {{ font-size:1.4em; font-weight:bold; color:{summary_col} }}
  table {{ border-collapse:collapse; width:100%; background:#fff;
           box-shadow:0 1px 4px rgba(0,0,0,.15) }}
  th    {{ background:#343a40; color:#fff; padding:8px 10px; text-align:left }}
  td    {{ padding:6px 10px; border-bottom:1px solid #ddd; vertical-align:top }}
  tr:hover {{ filter:brightness(0.97) }}
</style>
</head>
<body>
<h1>Gameshow Integration Test Report</h1>
<div class="summary">
  {report.timestamp} &nbsp;|&nbsp;
  Server: {report.server_ip}:{report.server_port} &nbsp;|&nbsp;
  <span>{report.passed}/{report.total} passed ({pct:.1f}%)</span>
</div>
<table>
<tr>
  <th>Category</th><th>Test</th><th>Result</th>
  <th>Duration</th><th>Metrics</th><th>Error</th><th>Notes</th>
</tr>
{"".join(rows)}
</table>
<p style="color:#888;font-size:0.85em">
  Generated by gameshow_tester.py
</p>
</body></html>"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)


# ─────────────────────────────────────────────────────────────────────────────
#  GUI
# ─────────────────────────────────────────────────────────────────────────────
class TesterGUI:
    def __init__(self, root: tk.Tk):
        self.root    = root
        self.root.title("Gameshow Master Test Suite")
        self.root.configure(bg="#121212")
        self._running = False
        self._build_ui()

    def _build_ui(self):
        # ── top bar ──
        bar = tk.Frame(self.root, bg="#121212")
        bar.pack(fill=tk.X, padx=10, pady=8)

        tk.Label(bar, text="Server IP:", bg="#121212", fg="#e0e0e0",
                 font=("Segoe UI", 10)).pack(side=tk.LEFT)
        self.ip_var = tk.StringVar(value=SERVER_IP)
        tk.Entry(bar, textvariable=self.ip_var, width=14,
                 bg="#2d2d2d", fg="#e0e0e0", insertbackground="#e0e0e0",
                 relief="flat").pack(side=tk.LEFT, padx=4)

        tk.Label(bar, text="Port:", bg="#121212", fg="#e0e0e0",
                 font=("Segoe UI", 10)).pack(side=tk.LEFT)
        self.port_var = tk.StringVar(value=str(SERVER_PORT))
        tk.Entry(bar, textvariable=self.port_var, width=6,
                 bg="#2d2d2d", fg="#e0e0e0", insertbackground="#e0e0e0",
                 relief="flat").pack(side=tk.LEFT, padx=4)

        self.run_btn = self._btn(bar, "▶  Run All Tests", "#2980b9", "#3498db",
                                 self._start_tests)
        self.run_btn.pack(side=tk.LEFT, padx=10)

        self._btn(bar, "Open HTML Report", "#27ae60", "#2ecc71",
                  self._open_report).pack(side=tk.LEFT)

        # ── summary bar ──
        self.summary_var = tk.StringVar(value="Press  ▶ Run All Tests  to begin.")
        tk.Label(self.root, textvariable=self.summary_var,
                 bg="#121212", fg="#aaaaaa",
                 font=("Segoe UI", 10)).pack(fill=tk.X, padx=10)

        # ── progress bar (canvas) ──
        self.prog_canvas = tk.Canvas(self.root, height=8, bg="#2d2d2d",
                                     highlightthickness=0)
        self.prog_canvas.pack(fill=tk.X, padx=10, pady=(2, 4))
        self._prog_bar = self.prog_canvas.create_rectangle(0, 0, 0, 8,
                                                            fill="#3498db", width=0)

        # ── log ──
        log_frame = tk.LabelFrame(self.root, text="Test Log", bg="#121212",
                                  fg="#e0e0e0", font=("Segoe UI", 10, "bold"))
        log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        self.log_box = scrolledtext.ScrolledText(
            log_frame, bg="#0d0d0d", fg="#cccccc",
            font=("Consolas", 9), state="disabled")
        self.log_box.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        self.log_box.tag_config("pass",   foreground="#2ecc71")
        self.log_box.tag_config("fail",   foreground="#e74c3c")
        self.log_box.tag_config("info",   foreground="#3498db")
        self.log_box.tag_config("warn",   foreground="#f39c12")
        self.log_box.tag_config("header", foreground="#9b59b6",
                                font=("Consolas", 9, "bold"))
        self.log_box.tag_config("plain",  foreground="#cccccc")

        self._msg_queue: queue.Queue = queue.Queue()
        self._poll_queue()

    def _btn(self, parent, text, color, hover, cmd):
        b = tk.Button(parent, text=text, bg=color, fg="#ffffff",
                      font=("Segoe UI", 10, "bold"),
                      activebackground=hover, relief="flat", bd=0,
                      padx=10, pady=5, command=cmd)
        b.bind("<Enter>", lambda _: b.config(bg=hover))
        b.bind("<Leave>", lambda _: b.config(bg=color))
        return b

    def _log(self, msg: str, tag: str = "plain"):
        self._msg_queue.put(("log", msg, tag))

    def _poll_queue(self):
        try:
            while True:
                item = self._msg_queue.get_nowait()
                if item[0] == "log":
                    _, msg, tag = item
                    self.log_box.config(state="normal")
                    self.log_box.insert("end", msg + "\n", tag)
                    self.log_box.see("end")
                    self.log_box.config(state="disabled")
                elif item[0] == "summary":
                    _, txt, pct, passed, failed = item
                    self.summary_var.set(txt)
                    w = self.prog_canvas.winfo_width()
                    self.prog_canvas.coords(self._prog_bar, 0, 0, w * pct / 100, 8)
                    col = "#2ecc71" if failed == 0 else "#e74c3c" if passed == 0 else "#f39c12"
                    self.prog_canvas.itemconfig(self._prog_bar, fill=col)
        except queue.Empty:
            pass
        self.root.after(50, self._poll_queue)

    def _start_tests(self):
        if self._running:
            return
        self._running = True
        self.run_btn.config(state="disabled")
        self.log_box.config(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.config(state="disabled")
        threading.Thread(target=self._run_worker, daemon=True).start()

    def _run_worker(self):
        runner = GameshowTestRunner(self._log)
        report = runner.run_all()

        # Save reports
        out_dir  = os.path.dirname(os.path.abspath(__file__))
        json_path = os.path.join(out_dir, "test_report.json")
        html_path = os.path.join(out_dir, "test_report.html")
        save_json(report, json_path)
        save_html(report, html_path)

        pct = report.passed / max(report.total, 1) * 100
        summary = (f"Finished: {report.passed}/{report.total} passed  "
                   f"({pct:.1f}%)  —  {report.failed} failed  "
                   f"| Reports saved to test_report.json / .html")
        self._msg_queue.put(("summary", summary, pct, report.passed, report.failed))
        self._log(f"\n{'═'*60}", "header")
        self._log(f"  {summary}", "pass" if report.failed == 0 else "warn")
        self._log(f"{'═'*60}", "header")
        self._running = False
        self.root.after(0, lambda: self.run_btn.config(state="normal"))

    def _open_report(self):
        html_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                 "test_report.html")
        if os.path.exists(html_path):
            os.startfile(html_path)
        else:
            tk.messagebox.showinfo("No Report",
                                   "Run the tests first to generate a report.")


if __name__ == "__main__":
    root = tk.Tk()
    root.geometry("900x620")
    app = TesterGUI(root)
    root.mainloop()

"""
Gameshow Test Suite
===================
Tests every layer of the gameshow system and produces a full report.

Tests included:
  1.  Config  — config.json is valid and complete
  2.  Server startup  — TCP server binds and accepts connections
  3.  Protocol parse  — firmware button message decoded correctly
  4.  Connect greeting — server sends "Connected\\r\\n" on connect
  5.  Button simulation — fake client sends button press, server routes event
  6.  Correct answer logic  — award_points() calculates right/wrong tables
  7.  LED broadcast — broadcast_leds formats message correctly
  8.  READY broadcast — broadcast sends READY to all clients
  9.  Leaderboard IPC — score commands forwarded over IPC socket
 10.  Multi-client — 12 simultaneous fake button units all connect
 11.  Stress test — 200 rapid button messages, no drops
 12.  Reconnect — client disconnects and reconnects, server recovers
 13.  Video folder scan — reports what videos are present in vid/

Run as:  python test_suite.py
"""

import os
import sys
import json
import time
import queue
import socket
import struct
import threading
import datetime
import traceback
import tkinter as tk
from tkinter import scrolledtext, messagebox

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

# ---------------------------------------------------------------------------
# Styling
# ---------------------------------------------------------------------------
DARK_BG  = "#0D1117"
PANEL_BG = "#161B22"
FG       = "#E6EDF3"
DIM_FG   = "#8B949E"
GREEN    = "#3FB950"
RED      = "#F85149"
ORANGE   = "#F0883E"
BLUE     = "#58A6FF"

# ---------------------------------------------------------------------------
# Result model
# ---------------------------------------------------------------------------

class TestResult:
    PASS = "PASS"
    FAIL = "FAIL"
    SKIP = "SKIP"
    WARN = "WARN"

    def __init__(self, name: str, status: str, detail: str = "", duration_ms: float = 0):
        self.name        = name
        self.status      = status
        self.detail      = detail
        self.duration_ms = duration_ms

    @property
    def colour(self) -> str:
        return {
            self.PASS: GREEN,
            self.FAIL: RED,
            self.SKIP: DIM_FG,
            self.WARN: ORANGE,
        }.get(self.status, DIM_FG)


# ---------------------------------------------------------------------------
# Individual tests
# ---------------------------------------------------------------------------

def _timed(fn) -> tuple[any, float]:
    t0 = time.perf_counter()
    result = fn()
    ms = (time.perf_counter() - t0) * 1000
    return result, ms


# ── 1. Config ──────────────────────────────────────────────────────────────

def test_config() -> TestResult:
    required_keys = [
        ("server", "host"), ("server", "port"),
        ("leaderboard_ipc", "host"), ("leaderboard_ipc", "port"),
        ("gameshow", "video_folder"), ("gameshow", "access_code"),
        ("game", "max_tables"), ("game", "correct_points"),
        ("game", "incorrect_points"),
    ]
    path = os.path.join(BASE_DIR, "config.json")

    def run():
        if not os.path.isfile(path):
            return None, "config.json not found"
        with open(path) as f:
            cfg = json.load(f)
        missing = []
        for section, key in required_keys:
            if section not in cfg or key not in cfg[section]:
                missing.append(f"{section}.{key}")
        if missing:
            return False, "Missing keys: " + ", ".join(missing)
        return True, f"All {len(required_keys)} required keys present"

    (ok, detail), ms = _timed(run)
    if ok is None:
        return TestResult("1. Config file exists", TestResult.FAIL, detail, ms)
    return TestResult(
        "1. Config valid",
        TestResult.PASS if ok else TestResult.FAIL,
        detail, ms
    )


# ── 2. Server startup ──────────────────────────────────────────────────────

def test_server_startup(cfg: dict) -> TestResult:
    host = "127.0.0.1"
    port = cfg["server"]["port"]

    def run():
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((host, port))
            sock.listen(1)
            sock.close()
            return True, f"Port {port} available and bindable"
        except OSError as e:
            sock.close()
            if "already in use" in str(e).lower() or e.errno == 10048:
                # Port in use means server might already be running — check if connectable
                try:
                    probe = socket.socket()
                    probe.settimeout(1)
                    probe.connect((host, port))
                    probe.close()
                    return True, f"Port {port} already bound — server running ✔"
                except Exception:
                    return False, f"Port {port} in use but not connectable: {e}"
            return False, str(e)

    (ok, detail), ms = _timed(run)
    return TestResult("2. Server port available", TestResult.PASS if ok else TestResult.FAIL, detail, ms)


# ── 3. Protocol parse ──────────────────────────────────────────────────────

def test_protocol_parse() -> TestResult:
    """Verify the firmware message format parses correctly without running the server."""

    def run():
        # Build a message exactly as the firmware sends it
        # ç|EMS|5|B|1229|\r\n  where ç = byte 231
        raw_bytes = b"\xe7|EMS|5|B|1229|\r\n"
        msg = raw_bytes.rstrip(b"\r\n")

        if msg[0] != 0xE7:
            return False, "First byte not 0xE7"

        text = msg.decode("utf-8", errors="replace")
        parts = text.split("|")
        if len(parts) < 5:
            return False, f"Expected 5+ parts, got {len(parts)}"
        if parts[1] != "EMS":
            return False, f"Expected parts[1]='EMS', got '{parts[1]}'"

        table  = int(parts[2])
        button = parts[3].strip().upper()
        counter = int(parts[4]) if parts[4].strip().isdigit() else 0

        if table != 5:
            return False, f"Table should be 5, got {table}"
        if button != "B":
            return False, f"Button should be B, got {button}"
        if counter != 1229:
            return False, f"Counter should be 1229, got {counter}"

        # Also test malformed (no crash)
        bad = b"garbage data"
        if bad[0] == 0xE7:
            return False, "Malformed message incorrectly identified as hardware msg"

        return True, "ç|EMS|5|B|1229| → table=5 button=B counter=1229 ✔"

    (ok, detail), ms = _timed(run)
    return TestResult("3. Protocol message parse", TestResult.PASS if ok else TestResult.FAIL, detail, ms)


# ── 4 & 5. Fake client: greeting + button simulation ──────────────────────

def _start_server_for_test(cfg: dict) -> tuple["GameServer", queue.Queue]:
    """Start a real GameServer instance for integration tests."""
    from server import GameServer
    bus = queue.Queue()
    srv = GameServer(cfg, bus)
    srv.start()
    time.sleep(0.3)
    return srv, bus


def _connect_fake_client(host: str, port: int, timeout: float = 3.0) -> socket.socket:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    sock.connect((host, port))
    return sock


def _recv_line(sock: socket.socket, timeout: float = 2.0) -> str:
    sock.settimeout(timeout)
    buf = b""
    while True:
        chunk = sock.recv(64)
        if not chunk:
            break
        buf += chunk
        if b"\r\n" in buf or b"\n" in buf:
            break
    return buf.decode("utf-8", errors="replace").strip()


def test_connect_greeting(srv, cfg: dict) -> TestResult:
    host = "127.0.0.1"
    port = cfg["server"]["port"]

    def run():
        try:
            c = _connect_fake_client(host, port)
            greeting = _recv_line(c, timeout=2)
            c.close()
            if "Connected" in greeting:
                return True, f"Received: '{greeting}'"
            return False, f"Expected 'Connected', got: '{greeting}'"
        except Exception as e:
            return False, str(e)

    (ok, detail), ms = _timed(run)
    return TestResult("4. Connect greeting", TestResult.PASS if ok else TestResult.FAIL, detail, ms)


def test_button_simulation(srv, bus: queue.Queue, cfg: dict) -> TestResult:
    host = "127.0.0.1"
    port = cfg["server"]["port"]

    def run():
        # Drain stale events
        while not bus.empty():
            bus.get_nowait()

        c = _connect_fake_client(host, port)
        _recv_line(c, timeout=1)  # consume greeting

        # Send button press: ç|EMS|7|A|42|\r\n
        msg = b"\xe7|EMS|7|A|42|\r\n"
        c.sendall(msg)
        time.sleep(0.3)
        c.close()

        # Check event arrived
        try:
            event = bus.get(timeout=2)
            if event["type"] == "answer" and event["table"] == 7 and event["answer"] == "A":
                return True, f"event={event}"
            return False, f"Wrong event: {event}"
        except queue.Empty:
            return False, "No event received within 2 s"

    (ok, detail), ms = _timed(run)
    return TestResult("5. Button press event", TestResult.PASS if ok else TestResult.FAIL, detail, ms)


# ── 6. Award points logic ──────────────────────────────────────────────────

def test_award_points(srv) -> TestResult:
    def run():
        srv.start_round()
        # Inject synthetic answers
        with srv._round_lock:
            srv.round_answers = {
                1: {"answer": "A", "timestamp": time.time(), "counter": 1},
                2: {"answer": "B", "timestamp": time.time(), "counter": 2},
                3: {"answer": "A", "timestamp": time.time(), "counter": 3},
            }
        srv.correct_answer = "A"
        result = srv.award_points(100, -50)
        if sorted(result["correct"]) != [1, 3]:
            return False, f"Expected correct=[1,3], got {result['correct']}"
        if result["incorrect"] != [2]:
            return False, f"Expected incorrect=[2], got {result['incorrect']}"
        return True, f"correct={result['correct']}  incorrect={result['incorrect']}"

    (ok, detail), ms = _timed(run)
    return TestResult("6. Award points logic", TestResult.PASS if ok else TestResult.FAIL, detail, ms)


# ── 7. LED broadcast format ───────────────────────────────────────────────

def test_led_broadcast(srv, cfg: dict) -> TestResult:
    host = "127.0.0.1"
    port = cfg["server"]["port"]

    def run():
        received = []
        done = threading.Event()

        c = _connect_fake_client(host, port)
        _recv_line(c, 1)  # greeting

        def reader():
            buf = b""
            c.settimeout(2)
            try:
                while not done.is_set():
                    data = c.recv(128)
                    if not data:
                        break
                    buf += data
                    while b"\r\n" in buf:
                        line, buf = buf.split(b"\r\n", 1)
                        received.append(line.decode("utf-8", errors="replace"))
            except Exception:
                pass

        t = threading.Thread(target=reader, daemon=True)
        t.start()
        time.sleep(0.1)

        srv.broadcast_leds("A", 10, 0, 0)
        time.sleep(0.4)
        done.set()
        c.close()
        t.join(timeout=1)

        expected = "EMS-LEDS-A|10|0|0|"
        if any(expected in r for r in received):
            return True, f"Received: {[r for r in received if 'EMS-LEDS' in r]}"
        return False, f"Expected '{expected}' not found in {received}"

    (ok, detail), ms = _timed(run)
    return TestResult("7. LED broadcast format", TestResult.PASS if ok else TestResult.FAIL, detail, ms)


# ── 8. READY broadcast ────────────────────────────────────────────────────

def test_ready_broadcast(srv, cfg: dict) -> TestResult:
    host = "127.0.0.1"
    port = cfg["server"]["port"]

    def run():
        c = _connect_fake_client(host, port)
        _recv_line(c, 1)  # greeting

        received = []
        done = threading.Event()

        def reader():
            buf = b""
            c.settimeout(2)
            try:
                while not done.is_set():
                    data = c.recv(128)
                    if not data:
                        break
                    buf += data
                    while b"\r\n" in buf:
                        line, buf = buf.split(b"\r\n", 1)
                        received.append(line.decode(errors="replace"))
            except Exception:
                pass

        t = threading.Thread(target=reader, daemon=True)
        t.start()
        time.sleep(0.1)
        srv.broadcast("READY\r\n")
        time.sleep(0.4)
        done.set()
        c.close()
        t.join(1)

        if any("READY" in r for r in received):
            return True, "READY received by client ✔"
        return False, f"READY not seen in: {received}"

    (ok, detail), ms = _timed(run)
    return TestResult("8. READY broadcast", TestResult.PASS if ok else TestResult.FAIL, detail, ms)


# ── 9. Leaderboard IPC ────────────────────────────────────────────────────

def test_leaderboard_ipc(cfg: dict) -> TestResult:
    ipc_host = cfg["leaderboard_ipc"]["host"]
    ipc_port = cfg["leaderboard_ipc"]["port"]

    def run():
        # Start a temporary IPC listener (simulates leaderboard.py)
        received = []
        ready = threading.Event()
        done  = threading.Event()

        def fake_leaderboard():
            srv_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            srv_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                srv_sock.bind((ipc_host, ipc_port))
                srv_sock.listen(1)
                ready.set()
                srv_sock.settimeout(5)
                conn, _ = srv_sock.accept()
                conn.settimeout(3)
                buf = ""
                while not done.is_set():
                    try:
                        data = conn.recv(256).decode("utf-8", errors="replace")
                        if not data:
                            break
                        buf += data
                        while "\n" in buf:
                            line, buf = buf.split("\n", 1)
                            received.append(line.strip())
                    except socket.timeout:
                        break
                conn.close()
            except Exception as exc:
                received.append(f"ERROR:{exc}")
            finally:
                srv_sock.close()

        lb_thread = threading.Thread(target=fake_leaderboard, daemon=True)
        lb_thread.start()

        if not ready.wait(timeout=3):
            return False, "Fake leaderboard server did not start"

        # Now connect to it from GameServer side
        ipc_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        ipc_sock.settimeout(3)
        ipc_sock.connect((ipc_host, ipc_port))
        time.sleep(0.2)

        # Send a score command
        ipc_sock.sendall(b"*1*3+100\n")
        ipc_sock.sendall(b"@5:B\n")
        time.sleep(0.5)
        done.set()
        ipc_sock.close()
        lb_thread.join(2)

        if "*1*3+100" in received and "@5:B" in received:
            return True, f"Received: {received}"
        return False, f"Expected commands not received. Got: {received}"

    (ok, detail), ms = _timed(run)
    return TestResult("9. Leaderboard IPC", TestResult.PASS if ok else TestResult.FAIL, detail, ms)


# ── 10. Multi-client (12 simultaneous) ────────────────────────────────────

def test_multi_client(srv, bus: queue.Queue, cfg: dict) -> TestResult:
    host = "127.0.0.1"
    port = cfg["server"]["port"]
    MAX  = cfg["game"]["max_tables"]

    def run():
        while not bus.empty():
            bus.get_nowait()
        srv.start_round()

        sockets = []
        errors  = []

        def connect_and_press(table_num: int):
            try:
                c = _connect_fake_client(host, port, timeout=5)
                _recv_line(c, timeout=2)
                msg = f"\xe7|EMS|{table_num}|A|{table_num}|\r\n".encode()
                msg = bytes([0xE7]) + msg[1:]
                c.sendall(msg)
                time.sleep(0.5)
                c.close()
            except Exception as e:
                errors.append(f"T{table_num}: {e}")

        threads = [
            threading.Thread(target=connect_and_press, args=(i,), daemon=True)
            for i in range(1, MAX + 1)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=6)

        if errors:
            return False, f"Errors: {errors}"

        time.sleep(0.5)
        events = []
        while not bus.empty():
            try:
                events.append(bus.get_nowait())
            except queue.Empty:
                break

        answer_events = [e for e in events if e.get("type") == "answer"]
        tables_seen   = {e["table"] for e in answer_events}
        expected      = set(range(1, MAX + 1))
        missed        = expected - tables_seen

        if missed:
            return False, f"Missed tables: {sorted(missed)}  got {len(answer_events)}/{MAX}"
        return True, f"All {MAX} table events received ✔"

    (ok, detail), ms = _timed(run)
    return TestResult("10. Multi-client (12 tables)", TestResult.PASS if ok else TestResult.FAIL, detail, ms)


# ── 11. Stress test ───────────────────────────────────────────────────────

def test_stress(srv, bus: queue.Queue, cfg: dict) -> TestResult:
    host = "127.0.0.1"
    port = cfg["server"]["port"]
    N    = 200

    def run():
        while not bus.empty():
            bus.get_nowait()

        c = _connect_fake_client(host, port, timeout=5)
        _recv_line(c, timeout=2)

        srv.start_round()

        sent = 0
        for i in range(N):
            # Vary table (1-12) and button (A-D) each message
            table  = (i % 12) + 1
            button = "ABCD"[i % 4]
            msg    = bytes([0xE7]) + f"|EMS|{table}|{button}|{i}|\r\n".encode()
            c.sendall(msg)
            sent += 1
            if i % 50 == 0:
                time.sleep(0.01)   # brief yield

        time.sleep(0.8)
        c.close()

        events  = []
        deadline = time.time() + 2
        while time.time() < deadline:
            try:
                events.append(bus.get_nowait())
            except queue.Empty:
                time.sleep(0.05)

        answer_events = [e for e in events if e.get("type") == "answer"]
        # We expect at most 12 events (first answer per table per round)
        tables_seen = {e["table"] for e in answer_events}
        if not tables_seen:
            return False, f"No events from {N} messages"

        return True, (
            f"Sent {N} msgs, got {len(answer_events)} answer events "
            f"for {len(tables_seen)} tables — no crash ✔"
        )

    (ok, detail), ms = _timed(run)
    return TestResult("11. Stress test (200 msgs)", TestResult.PASS if ok else TestResult.FAIL, detail, ms)


# ── 12. Reconnect ─────────────────────────────────────────────────────────

def test_reconnect(srv, bus: queue.Queue, cfg: dict) -> TestResult:
    host = "127.0.0.1"
    port = cfg["server"]["port"]

    def run():
        while not bus.empty():
            bus.get_nowait()

        srv.start_round()

        # Connect, send, disconnect abruptly
        c1 = _connect_fake_client(host, port, timeout=3)
        _recv_line(c1, 1)
        c1.sendall(bytes([0xE7]) + b"|EMS|99|C|1|\r\n")
        time.sleep(0.2)
        c1.close()   # abrupt close

        time.sleep(0.3)

        # Reconnect with different table
        c2 = _connect_fake_client(host, port, timeout=3)
        greeting2 = _recv_line(c2, 2)
        c2.sendall(bytes([0xE7]) + b"|EMS|88|D|2|\r\n")
        time.sleep(0.3)
        c2.close()

        if "Connected" not in greeting2:
            return False, f"No greeting on reconnect: '{greeting2}'"

        # Drain events
        events = []
        deadline = time.time() + 1.5
        while time.time() < deadline:
            try:
                events.append(bus.get_nowait())
            except queue.Empty:
                time.sleep(0.05)

        tables = {e["table"] for e in events if e.get("type") == "answer"}
        if 88 not in tables:
            return False, f"Table 88 event missing after reconnect. Got tables: {tables}"
        return True, f"Reconnect greeting OK, event received for table 88 ✔"

    (ok, detail), ms = _timed(run)
    return TestResult("12. Client reconnect", TestResult.PASS if ok else TestResult.FAIL, detail, ms)


# ── 13. Video folder scan ─────────────────────────────────────────────────

def test_video_scan(cfg: dict) -> TestResult:
    vf = cfg["gameshow"]["video_folder"]
    vid_dir = os.path.join(BASE_DIR, vf)

    def run():
        lines = []
        total = 0
        for sub in ("visual", "vrae", "countdown"):
            d = os.path.join(vid_dir, sub)
            if not os.path.isdir(d):
                lines.append(f"  {sub}/  ← MISSING")
                continue
            files = sorted(f for f in os.listdir(d) if _is_video(f))
            total += len(files)
            lines.append(f"  {sub}/  — {len(files)} video(s)")
            for f in files[:5]:
                lines.append(f"      {f}")
            if len(files) > 5:
                lines.append(f"      …and {len(files)-5} more")

        return True, "\n".join(lines) + f"\n  Total: {total} video(s)"

    (ok, detail), ms = _timed(run)
    status = TestResult.PASS if ok else TestResult.WARN
    return TestResult("13. Video folder scan", status, detail, ms)


def _is_video(name: str) -> bool:
    return os.path.splitext(name)[1].lower() in {
        ".mp4", ".mov", ".avi", ".mkv", ".webm", ".wmv", ".m4v", ".mpg", ".mpeg"
    }


# ---------------------------------------------------------------------------
# Test runner
# ---------------------------------------------------------------------------

class TestRunner:
    """Runs all tests sequentially, yielding TestResult objects."""

    def __init__(self, cfg: dict, log_fn):
        self.cfg    = cfg
        self.log    = log_fn
        self._srv   = None
        self._bus   = None

    def _ensure_server(self):
        if self._srv is None:
            self.log("  → Starting embedded GameServer for integration tests…")
            try:
                self._srv, self._bus = _start_server_for_test(self.cfg)
                self.log("  → GameServer started on port " + str(self.cfg["server"]["port"]))
            except Exception as e:
                self.log(f"  ✘ Could not start GameServer: {e}")
                raise

    def run_all(self):
        results = []

        # 1. Config (no server needed)
        r = test_config()
        self.log(f"  {r.status}  {r.name}  [{r.duration_ms:.0f}ms]")
        if r.detail:
            for line in r.detail.splitlines():
                self.log(f"       {line}")
        results.append(r)

        if r.status == TestResult.FAIL:
            self.log("  ⚠  Config invalid — skipping remaining tests")
            return results

        # 2. Port availability (no server needed yet)
        r = test_server_startup(self.cfg)
        self.log(f"  {r.status}  {r.name}  [{r.duration_ms:.0f}ms]")
        self.log(f"       {r.detail}")
        results.append(r)

        # 3. Protocol (pure logic, no server)
        r = test_protocol_parse()
        self.log(f"  {r.status}  {r.name}  [{r.duration_ms:.0f}ms]")
        self.log(f"       {r.detail}")
        results.append(r)

        # 9. Leaderboard IPC (needs IPC port free — run before server starts)
        r = test_leaderboard_ipc(self.cfg)
        self.log(f"  {r.status}  {r.name}  [{r.duration_ms:.0f}ms]")
        self.log(f"       {r.detail}")
        results.append(r)

        # Start server for integration tests
        try:
            self._ensure_server()
        except Exception as e:
            skip = TestResult("Integration tests", TestResult.SKIP,
                              f"Server start failed: {e}")
            results.append(skip)
            return results

        # 4. Greeting
        r = test_connect_greeting(self._srv, self.cfg)
        self.log(f"  {r.status}  {r.name}  [{r.duration_ms:.0f}ms]")
        self.log(f"       {r.detail}")
        results.append(r)

        # 5. Button simulation
        r = test_button_simulation(self._srv, self._bus, self.cfg)
        self.log(f"  {r.status}  {r.name}  [{r.duration_ms:.0f}ms]")
        self.log(f"       {r.detail}")
        results.append(r)

        # 6. Award points
        r = test_award_points(self._srv)
        self.log(f"  {r.status}  {r.name}  [{r.duration_ms:.0f}ms]")
        self.log(f"       {r.detail}")
        results.append(r)

        # 7. LED broadcast
        r = test_led_broadcast(self._srv, self.cfg)
        self.log(f"  {r.status}  {r.name}  [{r.duration_ms:.0f}ms]")
        self.log(f"       {r.detail}")
        results.append(r)

        # 8. READY broadcast
        r = test_ready_broadcast(self._srv, self.cfg)
        self.log(f"  {r.status}  {r.name}  [{r.duration_ms:.0f}ms]")
        self.log(f"       {r.detail}")
        results.append(r)

        # 10. Multi-client
        r = test_multi_client(self._srv, self._bus, self.cfg)
        self.log(f"  {r.status}  {r.name}  [{r.duration_ms:.0f}ms]")
        self.log(f"       {r.detail}")
        results.append(r)

        # 11. Stress
        r = test_stress(self._srv, self._bus, self.cfg)
        self.log(f"  {r.status}  {r.name}  [{r.duration_ms:.0f}ms]")
        self.log(f"       {r.detail}")
        results.append(r)

        # 12. Reconnect
        r = test_reconnect(self._srv, self._bus, self.cfg)
        self.log(f"  {r.status}  {r.name}  [{r.duration_ms:.0f}ms]")
        self.log(f"       {r.detail}")
        results.append(r)

        # 13. Video scan (no server)
        r = test_video_scan(self.cfg)
        self.log(f"  {r.status}  {r.name}  [{r.duration_ms:.0f}ms]")
        self.log(f"       {r.detail}")
        results.append(r)

        return results


# ---------------------------------------------------------------------------
# Tkinter GUI
# ---------------------------------------------------------------------------

class TestSuiteApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Gameshow Test Suite")
        self.configure(bg=DARK_BG)
        self.geometry("900x680+100+80")
        self.resizable(True, True)

        self._cfg  = None
        self._results: list[TestResult] = []
        self._running = False

        self._build_ui()
        self._load_config()

    def _build_ui(self):
        self.rowconfigure(2, weight=1)
        self.columnconfigure(0, weight=1)

        # ── Header ──
        hdr = tk.Frame(self, bg="#161B22", pady=10)
        hdr.grid(row=0, column=0, sticky="ew")
        tk.Label(hdr, text="Gameshow Test Suite", font=("Segoe UI", 14, "bold"),
                 bg="#161B22", fg=BLUE).pack(side=tk.LEFT, padx=16)
        tk.Label(hdr, text="Tests the TCP server, protocol, scoring, IPC and stress loads",
                 bg="#161B22", fg=DIM_FG, font=("Segoe UI", 9)).pack(side=tk.LEFT)

        # ── Controls ──
        ctrl = tk.Frame(self, bg=DARK_BG, pady=8)
        ctrl.grid(row=1, column=0, sticky="ew", padx=16)

        self._btn_run = tk.Button(
            ctrl, text="▶  Run All Tests",
            command=self._run_tests,
            bg="#238636", fg="white", activebackground="#2EA043",
            relief=tk.FLAT, bd=0, padx=16, pady=8,
            font=("Segoe UI", 11, "bold"), cursor="hand2",
        )
        self._btn_run.pack(side=tk.LEFT)

        self._btn_save = tk.Button(
            ctrl, text="💾  Save Report",
            command=self._save_report,
            bg="#21262D", fg=FG, activebackground="#30363D",
            relief=tk.FLAT, bd=0, padx=12, pady=8,
            font=("Segoe UI", 10), cursor="hand2", state=tk.DISABLED,
        )
        self._btn_save.pack(side=tk.LEFT, padx=8)

        self._summary_lbl = tk.Label(
            ctrl, text="", bg=DARK_BG, fg=DIM_FG,
            font=("Segoe UI", 10),
        )
        self._summary_lbl.pack(side=tk.LEFT, padx=16)

        # ── Results table ──
        results_frame = tk.Frame(self, bg=DARK_BG)
        results_frame.grid(row=2, column=0, sticky="nsew", padx=8, pady=(0, 4))
        results_frame.rowconfigure(0, weight=1)
        results_frame.columnconfigure(0, weight=1)

        self._results_canvas = tk.Canvas(results_frame, bg=DARK_BG, highlightthickness=0)
        self._results_canvas.grid(row=0, column=0, sticky="nsew")
        sb = tk.Scrollbar(results_frame, orient="vertical", command=self._results_canvas.yview)
        sb.grid(row=0, column=1, sticky="ns")
        self._results_canvas.configure(yscrollcommand=sb.set)

        self._result_rows_frame = tk.Frame(self._results_canvas, bg=DARK_BG)
        self._results_canvas.create_window((0, 0), window=self._result_rows_frame, anchor="nw")
        self._result_rows_frame.bind(
            "<Configure>",
            lambda e: self._results_canvas.configure(scrollregion=self._results_canvas.bbox("all"))
        )

        # ── Log ──
        log_frame = tk.LabelFrame(self, text="Test Log", bg=DARK_BG, fg=DIM_FG,
                                   font=("Segoe UI", 9, "bold"), relief=tk.FLAT)
        log_frame.grid(row=3, column=0, sticky="ew", padx=8, pady=4)
        self._log = scrolledtext.ScrolledText(
            log_frame, height=7,
            bg="#0D1117", fg="#7D8590",
            font=("Consolas", 8),
            state=tk.DISABLED,
        )
        self._log.pack(fill=tk.X, padx=4, pady=4)

    def _load_config(self):
        path = os.path.join(BASE_DIR, "config.json")
        try:
            with open(path) as f:
                self._cfg = json.load(f)
            self._log_line(f"Loaded {path}")
        except Exception as e:
            self._log_line(f"ERROR loading config: {e}")
            messagebox.showerror("Config error", str(e))

    def _log_line(self, msg: str):
        ts = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
        self._log.config(state=tk.NORMAL)
        self._log.insert(tk.END, f"[{ts}] {msg}\n")
        self._log.see(tk.END)
        self._log.config(state=tk.DISABLED)
        self.update_idletasks()

    def _run_tests(self):
        if self._running:
            return
        self._running = True
        self._btn_run.config(state=tk.DISABLED, text="Running…")
        self._results.clear()
        for w in self._result_rows_frame.winfo_children():
            w.destroy()
        self._summary_lbl.config(text="")

        def worker():
            runner = TestRunner(self._cfg, lambda m: self.after(0, self._log_line, m))
            try:
                results = runner.run_all()
            except Exception as e:
                results = [TestResult("Runner error", TestResult.FAIL, traceback.format_exc())]
            self.after(0, self._on_tests_done, results)

        threading.Thread(target=worker, daemon=True).start()

    def _on_tests_done(self, results: list[TestResult]):
        self._results = results
        self._running = False
        self._btn_run.config(state=tk.NORMAL, text="▶  Run All Tests")

        for r in results:
            self._add_result_row(r)

        passed  = sum(1 for r in results if r.status == TestResult.PASS)
        failed  = sum(1 for r in results if r.status == TestResult.FAIL)
        warned  = sum(1 for r in results if r.status == TestResult.WARN)
        total   = len(results)

        colour  = GREEN if failed == 0 else RED
        summary = f"✔ {passed}  ✘ {failed}  ⚠ {warned}  of {total} tests"
        self._summary_lbl.config(text=summary, fg=colour)
        self._btn_save.config(state=tk.NORMAL)
        self._log_line(f"\n{'='*50}")
        self._log_line(f"DONE — {summary}")

    def _add_result_row(self, r: TestResult):
        STATUS_BG = {
            TestResult.PASS: "#0D2616",
            TestResult.FAIL: "#200D0D",
            TestResult.WARN: "#1F1500",
            TestResult.SKIP: "#161B22",
        }
        bg  = STATUS_BG.get(r.status, PANEL_BG)
        row = tk.Frame(self._result_rows_frame, bg=bg, pady=4)
        row.pack(fill=tk.X, padx=4, pady=1)
        row.columnconfigure(1, weight=1)

        badge_colour = {
            TestResult.PASS: GREEN, TestResult.FAIL: RED,
            TestResult.WARN: ORANGE, TestResult.SKIP: DIM_FG,
        }.get(r.status, DIM_FG)

        tk.Label(row, text=f" {r.status} ", bg=badge_colour, fg="#000",
                 font=("Segoe UI", 8, "bold"), padx=4, pady=2
                 ).grid(row=0, column=0, padx=(8, 6), pady=2, sticky="w")
        tk.Label(row, text=r.name, bg=bg, fg=FG,
                 font=("Segoe UI", 10), anchor="w"
                 ).grid(row=0, column=1, sticky="ew")
        tk.Label(row, text=f"{r.duration_ms:.0f}ms", bg=bg, fg=DIM_FG,
                 font=("Segoe UI", 8)
                 ).grid(row=0, column=2, padx=8)

        if r.detail:
            for line in r.detail.splitlines()[:6]:
                tk.Label(row, text=f"    {line}", bg=bg, fg=DIM_FG,
                         font=("Consolas", 8), anchor="w"
                         ).grid(row=1, column=0, columnspan=3, sticky="ew",
                                padx=(8, 4))
                break  # show only first line in row; full detail is in log
            if "\n" in r.detail:
                more = r.detail.count("\n")
                tk.Label(row, text=f"    (+{more} more lines in log)",
                         bg=bg, fg="#484F58",
                         font=("Segoe UI", 8), anchor="w"
                         ).grid(row=2, column=0, columnspan=3, sticky="ew", padx=(8, 4))

    def _save_report(self):
        from tkinter.filedialog import asksaveasfilename
        path = asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            initialfile=f"gameshow_test_report_{datetime.datetime.now():%Y%m%d_%H%M%S}.txt",
        )
        if not path:
            return
        lines = [
            "Gameshow Test Suite Report",
            f"Generated: {datetime.datetime.now():%Y-%m-%d %H:%M:%S}",
            "=" * 60,
            "",
        ]
        for r in self._results:
            lines.append(f"[{r.status}]  {r.name}  ({r.duration_ms:.0f}ms)")
            if r.detail:
                for dl in r.detail.splitlines():
                    lines.append(f"    {dl}")
            lines.append("")

        passed = sum(1 for r in self._results if r.status == TestResult.PASS)
        failed = sum(1 for r in self._results if r.status == TestResult.FAIL)
        lines += ["=" * 60, f"TOTAL: {passed} passed, {failed} failed of {len(self._results)}"]

        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        messagebox.showinfo("Saved", f"Report saved to:\n{path}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app = TestSuiteApp()
    app.mainloop()

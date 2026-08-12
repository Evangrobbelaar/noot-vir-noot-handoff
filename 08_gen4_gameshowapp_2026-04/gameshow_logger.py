"""
╔══════════════════════════════════════════════════════════════╗
║         GAMESHOW SYSTEM MONITOR  —  Full Diagnostic GUI      ║
╚══════════════════════════════════════════════════════════════╝

Captures EVERYTHING happening across:
  • BSD TCP server (port 8080) — all raw bytes in/out
  • Named pipe  \\.\pipe\gameshow_pipe  (BSD → Leaderboard)
  • access_codes.db — every read / write / delete
  • Process health — BSD, Gameshow, Leaderboard, Toggler
  • Network sockets — every connection attempt, IP, port, latency
  • Message parsing — EMS firmware, legacy, LED commands, READY
  • Leaderboard score & answer state reconstruction
  • Timeline of all events with microsecond timestamps

Also runs the full test suite from test_simulator.py inline.

Usage:
  python gameshow_monitor.py

Run BEFORE (or alongside) the rest of the suite.
Pipe interception requires pywin32.
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog, messagebox
import threading
import socket
import time
import datetime
import os
import sys
import json
import csv
import io
import re
import sqlite3
import queue
import hashlib
from collections import defaultdict, deque
from dataclasses import dataclass, field, asdict
from typing import Optional

# ── Optional Windows imports ──────────────────────────────────────────────────
try:
    import win32pipe, win32file, pywintypes
    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

# ══════════════════════════════════════════════════════════════════════════════
#  DATA STRUCTURES
# ══════════════════════════════════════════════════════════════════════════════

EVENT_CATEGORIES = {
    "TCP_CONNECT":    "#00ff9f",
    "TCP_DISCONNECT": "#ff4444",
    "TCP_RECV":       "#00cfff",
    "TCP_SEND":       "#ffaa00",
    "PIPE_RECV":      "#ff66ff",
    "PIPE_SEND":      "#cc44cc",
    "DB_READ":        "#66ff66",
    "DB_WRITE":       "#ff9944",
    "DB_DELETE":      "#ff4444",
    "PARSE_ANSWER":   "#00ff9f",
    "PARSE_SCORE":    "#ffff44",
    "PARSE_LED":      "#44aaff",
    "PARSE_READY":    "#ffffff",
    "PARSE_PING":     "#888888",
    "PARSE_UNKNOWN":  "#666666",
    "PROC_ALIVE":     "#00ff9f",
    "PROC_DEAD":      "#ff4444",
    "TEST_PASS":      "#00ff9f",
    "TEST_FAIL":      "#ff4444",
    "TEST_INFO":      "#aaaaaa",
    "ERROR":          "#ff0000",
    "SYSTEM":         "#888888",
}

@dataclass
class Event:
    ts: str
    ts_raw: float
    category: str
    source: str
    direction: str        # IN / OUT / INTERNAL
    raw: str
    parsed_type: str
    parsed_detail: str
    extra: dict = field(default_factory=dict)

    def to_dict(self):
        d = asdict(self)
        d.pop("ts_raw", None)
        return d


# ══════════════════════════════════════════════════════════════════════════════
#  CENTRAL EVENT BUS
# ══════════════════════════════════════════════════════════════════════════════

class EventBus:
    def __init__(self):
        self._listeners = []
        self._events: list[Event] = []
        self._lock = threading.Lock()
        self._stats = defaultdict(int)

    def subscribe(self, fn):
        self._listeners.append(fn)

    def emit(self, event: Event):
        with self._lock:
            self._events.append(event)
            self._stats[event.category] += 1
        for fn in self._listeners:
            try:
                fn(event)
            except Exception:
                pass

    def all_events(self):
        with self._lock:
            return list(self._events)

    def stats(self):
        with self._lock:
            return dict(self._stats)

    def clear(self):
        with self._lock:
            self._events.clear()
            self._stats.clear()


BUS = EventBus()

def emit(category: str, source: str, direction: str,
         raw: str, parsed_type: str = "", parsed_detail: str = "",
         extra: dict = None):
    now = time.time()
    ts  = datetime.datetime.fromtimestamp(now).strftime("%H:%M:%S.%f")[:-3]
    BUS.emit(Event(
        ts=ts, ts_raw=now,
        category=category, source=source, direction=direction,
        raw=raw, parsed_type=parsed_type, parsed_detail=parsed_detail,
        extra=extra or {},
    ))


# ══════════════════════════════════════════════════════════════════════════════
#  MESSAGE PARSER
# ══════════════════════════════════════════════════════════════════════════════

def parse_message(raw: str, source: str, direction: str = "IN"):
    """Decode every known wire format and emit a structured event."""
    s = raw.strip()

    # PING keepalive
    if s == "PING":
        emit("PARSE_PING", source, direction, raw, "PING", "keepalive heartbeat")
        return

    # DASHBOARD-READY-TRIGGER
    if s.startswith("DASHBOARD-READY-TRIGGER"):
        emit("PARSE_READY", source, direction, raw, "READY_TRIGGER",
             "Gameshow arms buzzers → BSD will broadcast READY to all clients")
        return

    # READY broadcast (BSD → clients)
    if s == "READY":
        emit("PARSE_READY", source, direction, raw, "READY_BROADCAST",
             "BSD broadcasts READY to all connected clients")
        return

    # awns_X  — correct answer from gameshow
    if s.lower().startswith("awns_"):
        answer = s.split("_", 1)[1].strip().upper() if "_" in s else "?"
        emit("PARSE_ANSWER", source, direction, raw, "CORRECT_ANSWER",
             f"Correct answer set to [{answer}]", {"answer": answer})
        return

    # EMS firmware format  \xae|EMS|TABLE|ANSWER|QUESTION|
    if "|EMS|" in s:
        parts = s.split("|")
        if len(parts) >= 5:
            table = parts[2]; answer = parts[3].upper(); qid = parts[4]
            emit("PARSE_ANSWER", source, direction, raw, "EMS_FIRMWARE",
                 f"Table {table} answered [{answer}] on Q#{qid}",
                 {"table": table, "answer": answer, "question": qid, "format": "EMS_FIRMWARE"})
            return

    # Legacy @TABLE:ANSWER
    if s.startswith("@") and ":" in s:
        parts = s.split(":")
        table = parts[0][1:]; answer = parts[1].strip().upper() if len(parts) > 1 else "?"
        emit("PARSE_ANSWER", source, direction, raw, "LEGACY_ANSWER",
             f"Table {table} answered [{answer}]",
             {"table": table, "answer": answer, "format": "LEGACY"})
        return

    # ANSWERS: bulk
    if s.startswith("ANSWERS:"):
        payload = s[8:]
        emit("PARSE_ANSWER", source, direction, raw, "BULK_ANSWERS",
             f"Bulk answer update: {payload}", {"payload": payload})
        return

    # Score commands  *1*2+100  or  *1-50
    if s.startswith("*") or re.match(r"^\*[\d\*]+[+-]\d+$", s):
        op = "+" if "+" in s else "-"
        parts = s.split(op)
        tables = [t for t in parts[0].split("*") if t.isdigit()]
        pts = parts[1] if len(parts) > 1 else "?"
        emit("PARSE_SCORE", source, direction, raw, "SCORE_UPDATE",
             f"Tables {tables} {op}{pts} points",
             {"tables": tables, "op": op, "points": pts})
        return

    # LED commands
    if s.startswith("EMS-LEDS"):
        parts = s.split("|")
        target = parts[0].replace("EMS-LEDS-", "") if len(parts) >= 1 else "?"
        rgb = parts[1:4] if len(parts) >= 4 else []
        color_name = "OFF"
        if rgb:
            r, g, b = (int(x) for x in rgb[:3]) if all(x.isdigit() for x in rgb[:3]) else (0,0,0)
            color_name = "RED" if r > 0 else "GREEN" if g > 0 else "BLUE" if b > 0 else "OFF"
        emit("PARSE_LED", source, direction, raw, "LED_COMMAND",
             f"LEDs [{target}] → {color_name}  raw:{s}",
             {"target": target, "color": color_name, "raw_cmd": s})
        return

    # Dance lights
    if s.startswith("DANCE-LIGHTS"):
        action = "START" if "START" in s else "STOP"
        emit("PARSE_LED", source, direction, raw, "DANCE_LIGHTS",
             f"Dance lights {action}")
        return

    # Connected greeting
    if "Connected" in s:
        emit("TCP_CONNECT", source, direction, raw, "HANDSHAKE",
             "BSD confirmed connection")
        return

    # Unknown
    emit("PARSE_UNKNOWN", source, direction, raw, "UNKNOWN",
         f"Unrecognised: {repr(s[:80])}")


# ══════════════════════════════════════════════════════════════════════════════
#  TCP INTERCEPT SERVER
# ══════════════════════════════════════════════════════════════════════════════

class TCPInterceptServer:
    def __init__(self, port: int = 8080):
        self.port = port
        self.running = False
        self._sock = None
        self._clients: list = []
        self._lock = threading.Lock()
        self._connection_count = 0

    def start(self):
        self.running = True
        threading.Thread(target=self._listen, daemon=True, name="TCPServer").start()

    def stop(self):
        self.running = False
        if self._sock:
            try: self._sock.close()
            except: pass

    def broadcast(self, data: bytes, exclude=None):
        with self._lock:
            dead = []
            for c in self._clients:
                if c is exclude:
                    continue
                try:
                    c.send(data)
                    parse_message(data.decode("utf-8", errors="replace").strip(),
                                  "SERVER→CLIENT", "OUT")
                except:
                    dead.append(c)
            for c in dead:
                self._clients.remove(c)

    def _listen(self):
        try:
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._sock.bind(("0.0.0.0", self.port))
            self._sock.listen(30)
            emit("SYSTEM", "TCPServer", "INTERNAL", f"Listening on 0.0.0.0:{self.port}",
                 "SERVER_START", f"TCP intercept server bound to port {self.port}")
        except OSError as e:
            emit("ERROR", "TCPServer", "INTERNAL", str(e),
                 "BIND_ERROR",
                 f"Cannot bind port {self.port}. Is bsd.py already running? "
                 f"Start gameshow_monitor.py FIRST, then bsd.py will fail to bind "
                 f"(or change its port). Alternatively run monitor in passive mode.")
            return

        while self.running:
            try:
                client, addr = self._sock.accept()
                self._connection_count += 1
                ip, port = addr
                t_connect = time.time()
                emit("TCP_CONNECT", f"{ip}:{port}", "IN",
                     f"TCP connection from {ip}:{port}",
                     "NEW_CONNECTION",
                     f"Client #{self._connection_count}  IP={ip}  Port={port}",
                     {"ip": ip, "port": port, "conn_num": self._connection_count})
                try:
                    client.send("Connected\r\n".encode("utf-8"))
                    emit("TCP_SEND", f"SERVER→{ip}:{port}", "OUT",
                         "Connected\r\n", "HANDSHAKE", "Sent Connected greeting")
                except:
                    pass
                with self._lock:
                    self._clients.append(client)
                threading.Thread(
                    target=self._handle_client,
                    args=(client, ip, port, t_connect),
                    daemon=True,
                    name=f"Client-{ip}:{port}"
                ).start()
            except socket.error as e:
                if self.running:
                    emit("ERROR", "TCPServer", "INTERNAL", str(e), "ACCEPT_ERROR", str(e))
                break

    def _handle_client(self, client, ip, port, t_connect):
        source = f"{ip}:{port}"
        buf = ""
        bytes_in = 0
        msg_count = 0
        try:
            while self.running:
                data = client.recv(4096)
                if not data:
                    break
                bytes_in += len(data)
                raw_hex = data.hex()
                raw_str = data.decode("utf-8", errors="replace")
                buf += raw_str
                # Emit raw bytes event
                emit("TCP_RECV", source, "IN",
                     raw_str.strip(),
                     "RAW_BYTES",
                     f"{len(data)} bytes  hex={raw_hex[:64]}{'...' if len(raw_hex)>64 else ''}",
                     {"bytes": len(data), "hex_preview": raw_hex[:64], "ip": ip, "port": port})

                # Process line-delimited messages
                while "\r\n" in buf:
                    line, buf = buf.split("\r\n", 1)
                    if not line:
                        continue
                    msg_count += 1
                    parse_message(line, source, "IN")
        except ConnectionError:
            pass
        except Exception as e:
            emit("ERROR", source, "INTERNAL", str(e), "CLIENT_READ_ERROR", str(e))
        finally:
            with self._lock:
                if client in self._clients:
                    self._clients.remove(client)
            try: client.close()
            except: pass
            duration = time.time() - t_connect
            emit("TCP_DISCONNECT", source, "IN",
                 f"Client {source} disconnected",
                 "DISCONNECTED",
                 f"Session: {duration:.2f}s  bytes_in={bytes_in}  messages={msg_count}",
                 {"duration_s": round(duration, 3), "bytes_in": bytes_in,
                  "messages": msg_count, "ip": ip, "port": port})


# ══════════════════════════════════════════════════════════════════════════════
#  NAMED PIPE INTERCEPTOR
# ══════════════════════════════════════════════════════════════════════════════

class PipeInterceptor:
    PIPE_NAME = r"\\.\pipe\gameshow_pipe"

    def __init__(self):
        self.running = False

    def start(self):
        if not HAS_WIN32:
            emit("SYSTEM", "PipeInterceptor", "INTERNAL",
                 "pywin32 not installed — pipe monitoring disabled",
                 "PIPE_SKIP", "Install pywin32 to enable named-pipe monitoring")
            return
        self.running = True
        threading.Thread(target=self._serve, daemon=True, name="PipeServer").start()
        emit("SYSTEM", "PipeInterceptor", "INTERNAL",
             f"Pipe interceptor active on {self.PIPE_NAME}",
             "PIPE_START", "Named pipe interceptor listening")

    def stop(self):
        self.running = False

    def _serve(self):
        while self.running:
            try:
                pipe = win32pipe.CreateNamedPipe(
                    self.PIPE_NAME,
                    win32pipe.PIPE_ACCESS_DUPLEX,
                    win32pipe.PIPE_TYPE_MESSAGE | win32pipe.PIPE_READMODE_MESSAGE | win32pipe.PIPE_WAIT,
                    win32pipe.PIPE_UNLIMITED_INSTANCES,
                    65536, 65536, 0, None,
                )
            except Exception as e:
                emit("ERROR", "PipeServer", "INTERNAL", str(e), "PIPE_CREATE_ERROR", str(e))
                time.sleep(1)
                continue

            def handle(p):
                try:
                    win32pipe.ConnectNamedPipe(p, None)
                    # Immediately create a new instance so next caller isn't blocked
                    threading.Thread(target=self._new_instance, daemon=True).start()
                    while True:
                        try:
                            _, raw = win32file.ReadFile(p, 64 * 1024)
                            data = raw.decode("utf-8", errors="replace")
                            emit("PIPE_RECV", "BSD→LEADERBOARD", "IN",
                                 data, "PIPE_DATA",
                                 f"Pipe payload: {repr(data[:80])}",
                                 {"length": len(data), "hex": raw.hex()[:64]})
                            parse_message(data, "PIPE:BSD→LB", "IN")
                            # Relay to real leaderboard pipe if it exists
                            self._relay(raw)
                        except pywintypes.error:
                            break
                finally:
                    try: win32file.CloseHandle(p)
                    except: pass

            threading.Thread(target=handle, args=(pipe,), daemon=True).start()
            break   # first instance spawned; _new_instance handles the rest

    def _new_instance(self):
        """Keep a fresh pipe instance always available."""
        if not self.running:
            return
        try:
            pipe = win32pipe.CreateNamedPipe(
                self.PIPE_NAME,
                win32pipe.PIPE_ACCESS_DUPLEX,
                win32pipe.PIPE_TYPE_MESSAGE | win32pipe.PIPE_READMODE_MESSAGE | win32pipe.PIPE_WAIT,
                win32pipe.PIPE_UNLIMITED_INSTANCES,
                65536, 65536, 0, None,
            )
            win32pipe.ConnectNamedPipe(pipe, None)
            threading.Thread(target=self._new_instance, daemon=True).start()
            while True:
                try:
                    _, raw = win32file.ReadFile(pipe, 64 * 1024)
                    data = raw.decode("utf-8", errors="replace")
                    emit("PIPE_RECV", "BSD→LEADERBOARD", "IN", data, "PIPE_DATA",
                         f"Pipe payload: {repr(data[:80])}", {"length": len(data)})
                    parse_message(data, "PIPE:BSD→LB", "IN")
                    self._relay(raw)
                except pywintypes.error:
                    break
            try: win32file.CloseHandle(pipe)
            except: pass
        except Exception as e:
            emit("ERROR", "PipeServer", "INTERNAL", str(e), "PIPE_INSTANCE_ERROR", str(e))

    def _relay(self, raw_bytes: bytes):
        """Optionally relay to a 'real' leaderboard pipe (if it exists)."""
        try:
            relay = win32file.CreateFile(
                r"\\.\pipe\gameshow_pipe_real",
                win32file.GENERIC_WRITE, 0, None,
                win32file.OPEN_EXISTING, 0, None,
            )
            win32file.WriteFile(relay, raw_bytes)
            win32file.CloseHandle(relay)
        except:
            pass   # no relay target — silent


# ══════════════════════════════════════════════════════════════════════════════
#  DATABASE WATCHER
# ══════════════════════════════════════════════════════════════════════════════

class DatabaseWatcher:
    def __init__(self, db_path: str = "access_codes.db"):
        self.db_path = db_path
        self._known: set = set()
        self._last_mtime = 0.0
        self._running = False
        self._read_count = 0
        self._write_count = 0
        self._delete_count = 0

    def start(self):
        self._running = True
        self._snapshot()
        threading.Thread(target=self._watch, daemon=True, name="DBWatcher").start()
        emit("SYSTEM", "DBWatcher", "INTERNAL",
             f"Watching: {self.db_path}",
             "DB_WATCH_START",
             f"Monitoring access_codes.db at {os.path.abspath(self.db_path)}")

    def stop(self):
        self._running = False

    def _snapshot(self):
        if not os.path.exists(self.db_path):
            return
        try:
            conn = sqlite3.connect(self.db_path)
            rows = conn.execute("SELECT code FROM access_codes").fetchall()
            conn.close()
            self._known = {r[0] for r in rows}
            emit("DB_READ", "DB", "INTERNAL",
                 f"Initial snapshot: {len(self._known)} codes",
                 "DB_SNAPSHOT",
                 f"Database loaded: {len(self._known)} access codes present")
        except Exception as e:
            emit("ERROR", "DB", "INTERNAL", str(e), "DB_SNAPSHOT_ERROR", str(e))

    def _watch(self):
        while self._running:
            time.sleep(0.5)
            if not os.path.exists(self.db_path):
                continue
            try:
                mtime = os.path.getmtime(self.db_path)
                if mtime == self._last_mtime:
                    continue
                self._last_mtime = mtime
                size = os.path.getsize(self.db_path)

                conn = sqlite3.connect(self.db_path)
                rows = conn.execute("SELECT code FROM access_codes").fetchall()
                conn.close()
                current = {r[0] for r in rows}

                added   = current - self._known
                removed = self._known - current

                for code in added:
                    self._write_count += 1
                    emit("DB_WRITE", "DB:access_codes", "INTERNAL",
                         f"INSERT code='{code}'",
                         "CODE_ADDED",
                         f"Access code added: '{code}'  (total: {len(current)})",
                         {"code": code, "total_codes": len(current), "db_size_bytes": size})

                for code in removed:
                    self._delete_count += 1
                    emit("DB_DELETE", "DB:access_codes", "INTERNAL",
                         f"DELETE code='{code}'",
                         "CODE_USED",
                         f"Access code used/removed: '{code}'  (remaining: {len(current)})",
                         {"code": code, "remaining_codes": len(current), "db_size_bytes": size})

                self._known = current
            except Exception as e:
                emit("ERROR", "DB", "INTERNAL", str(e), "DB_WATCH_ERROR", str(e))


# ══════════════════════════════════════════════════════════════════════════════
#  PROCESS MONITOR
# ══════════════════════════════════════════════════════════════════════════════

WATCH_PROCESSES = {
    "bsd.py":         "BSD Server",
    "gameshow2.py":   "Gameshow Player",
    "leaderboard.py": "Leaderboard",
    "toggler.py":     "Toggler",
    "main.py":        "Mission Control",
}

class ProcessMonitor:
    def __init__(self):
        self._prev: dict = {}
        self._running = False

    def start(self):
        if not HAS_PSUTIL:
            emit("SYSTEM", "ProcMonitor", "INTERNAL",
                 "psutil not installed — process monitoring disabled",
                 "PROC_SKIP", "Install psutil to enable process health monitoring")
            return
        self._running = True
        threading.Thread(target=self._watch, daemon=True, name="ProcMonitor").start()
        emit("SYSTEM", "ProcMonitor", "INTERNAL",
             "Process monitor started", "PROC_START",
             f"Watching: {list(WATCH_PROCESSES.keys())}")

    def stop(self):
        self._running = False

    def _watch(self):
        while self._running:
            time.sleep(2)
            try:
                found = {}
                for proc in psutil.process_iter(["pid", "name", "cmdline",
                                                  "cpu_percent", "memory_info",
                                                  "status", "create_time"]):
                    try:
                        cmd = " ".join(proc.info["cmdline"] or [])
                        for script, label in WATCH_PROCESSES.items():
                            if script in cmd:
                                found[script] = {
                                    "pid":     proc.pid,
                                    "cpu":     proc.info["cpu_percent"],
                                    "mem_mb":  round(proc.info["memory_info"].rss / 1024 / 1024, 1),
                                    "status":  proc.info["status"],
                                    "label":   label,
                                }
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass

                for script, label in WATCH_PROCESSES.items():
                    was_alive = script in self._prev
                    is_alive  = script in found
                    if is_alive and not was_alive:
                        info = found[script]
                        emit("PROC_ALIVE", f"PROC:{label}", "INTERNAL",
                             f"{label} started (PID {info['pid']})",
                             "PROC_STARTED",
                             f"{label} is running  PID={info['pid']}  "
                             f"RAM={info['mem_mb']}MB  CPU={info['cpu']}%",
                             info)
                    elif was_alive and not is_alive:
                        emit("PROC_DEAD", f"PROC:{label}", "INTERNAL",
                             f"{label} stopped",
                             "PROC_STOPPED",
                             f"{label} is NO LONGER RUNNING  (was PID {self._prev[script]['pid']})",
                             {"script": script, "last_pid": self._prev[script]["pid"]})

                self._prev = found
            except Exception as e:
                emit("ERROR", "ProcMonitor", "INTERNAL", str(e), "PROC_WATCH_ERROR", str(e))


# ══════════════════════════════════════════════════════════════════════════════
#  INLINE TEST RUNNER  (mirrors test_simulator.py logic)
# ══════════════════════════════════════════════════════════════════════════════

def tcp_send_test(host, port, messages, timeout=3.0):
    log = []
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        t0 = time.time()
        s.connect((host, port))
        latency = (time.time() - t0) * 1000
        log.append(f"  ✓ Connected to {host}:{port}  latency={latency:.1f}ms")
        emit("TCP_CONNECT", f"TEST→{host}:{port}", "OUT",
             f"Test connection to {host}:{port}",
             "TEST_CONNECT",
             f"Connected  latency={latency:.1f}ms", {"latency_ms": round(latency, 1)})
        try:
            greeting = s.recv(256).decode("utf-8", errors="replace").strip()
            log.append(f"  → BSD replied: '{greeting}'")
            emit("TCP_RECV", f"TEST←{host}:{port}", "IN", greeting, "TEST_RECV", greeting)
        except socket.timeout:
            log.append("  (no greeting)")
        for msg in messages:
            s.send(msg.encode("utf-8"))
            log.append(f"  ↑ Sent: {repr(msg.strip())}")
            emit("TCP_SEND", f"TEST→{host}:{port}", "OUT", msg.strip(),
                 "TEST_SEND", repr(msg.strip()))
            time.sleep(0.15)
        s.close()
        return True, "\n".join(log)
    except ConnectionRefusedError:
        msg = f"  ✗ Connection refused — is BSD server running on {host}:{port}?"
        emit("ERROR", f"TEST→{host}:{port}", "OUT", msg, "TEST_CONN_REFUSED", msg)
        return False, msg
    except Exception as e:
        msg = f"  ✗ Error: {e}"
        emit("ERROR", f"TEST→{host}:{port}", "OUT", str(e), "TEST_ERROR", str(e))
        return False, msg


def pipe_send_test(messages):
    if not HAS_WIN32:
        return False, "  ✗ pywin32 not available — pipe tests skipped"
    log = []
    ok = True
    for msg in messages:
        try:
            pipe = win32file.CreateFile(
                r"\\.\pipe\gameshow_pipe",
                win32file.GENERIC_WRITE, 0, None,
                win32file.OPEN_EXISTING, 0, None,
            )
            win32file.WriteFile(pipe, msg.encode("utf-8"))
            win32file.CloseHandle(pipe)
            log.append(f"  ✓ Pipe sent: {msg}")
            emit("PIPE_SEND", "TEST→LEADERBOARD", "OUT", msg, "TEST_PIPE_SEND",
                 f"Sent to leaderboard pipe: {msg}")
            time.sleep(0.2)
        except Exception as e:
            log.append(f"  ✗ Pipe error '{msg}': {e}")
            emit("ERROR", "TEST→PIPE", "OUT", str(e), "TEST_PIPE_ERROR", str(e))
            ok = False
    return ok, "\n".join(log)


def run_test_suite(host, port, log_cb):
    """Run all 8 test categories and report via log_cb."""

    def section(title):
        log_cb(f"\n{'─'*55}")
        log_cb(f"  {title}")
        log_cb(f"{'─'*55}")
        emit("TEST_INFO", "TestSuite", "INTERNAL", title, "TEST_SECTION", title)

    def result(label, ok, detail):
        sym = "PASS ✓" if ok else "FAIL ✗"
        cat = "TEST_PASS" if ok else "TEST_FAIL"
        log_cb(f"  [{sym}]  {label}")
        if detail:
            log_cb(detail)
        emit(cat, "TestSuite", "INTERNAL", label, sym, f"{label}: {detail[:120]}")

    passed = failed = 0

    # ── T1: BSD Connection ────────────────────────────────────────────────────
    section("T1 · BSD TCP Connection + Handshake")
    ok, text = tcp_send_test(host, port, [])
    result("BSD Connection", ok, text)
    if ok: passed += 1
    else: failed += 1

    # ── T2: Gameshow → BSD ───────────────────────────────────────────────────
    section("T2 · Gameshow → BSD  (awns_ + READY trigger)")
    ok, text = tcp_send_test(host, port, ["awns_B\r\n", "DASHBOARD-READY-TRIGGER\r\n"])
    result("Gameshow→BSD messages", ok, text)
    if ok: passed += 1
    else: failed += 1

    # ── T3: PING keepalive ───────────────────────────────────────────────────
    section("T3 · PING keepalive")
    ok, text = tcp_send_test(host, port, ["PING\r\n"])
    result("PING keepalive", ok, text)
    if ok: passed += 1
    else: failed += 1

    # ── T4a: Legacy answer ───────────────────────────────────────────────────
    section("T4a · EMS Legacy Answer  (@TABLE:ANSWER)")
    ok, text = tcp_send_test(host, port, ["@2:B\r\n", "@5:A\r\n", "@12:D\r\n"])
    result("Legacy answer format", ok, text)
    if ok: passed += 1
    else: failed += 1

    # ── T4b: EMS firmware ───────────────────────────────────────────────────
    section("T4b · EMS Firmware Answer  (\\ufffd|EMS|TABLE|ANS|QID|)")
    prefix = "\ufffd"
    msgs = [
        f"{prefix}|EMS|3|C|7199|\r\n",
        f"{prefix}|EMS|7|A|7199|\r\n",
    ]
    ok, text = tcp_send_test(host, port, msgs)
    result("EMS firmware format", ok, text)
    if ok: passed += 1
    else: failed += 1

    # ── T5: Multi-table rapid fire ───────────────────────────────────────────
    section("T5 · Rapid-fire: 12 tables all answer simultaneously")
    msgs = [f"@{t}:{'ABCD'[(t-1)%4]}\r\n" for t in range(1, 13)]
    ok, text = tcp_send_test(host, port, msgs, timeout=8)
    result("12-table rapid fire", ok, text)
    if ok: passed += 1
    else: failed += 1

    # ── T6: LED commands ─────────────────────────────────────────────────────
    section("T6 · LED Commands  (RED / GREEN / BLUE / OFF / DANCE)")
    led_cmds = [
        "EMS-LEDS-X|10|0|0|\r\n",
        "EMS-LEDS-X|0|10|0|\r\n",
        "EMS-LEDS-X|0|0|10|\r\n",
        "EMS-LEDS-X|0|0|0|\r\n",
        "EMS-LEDS-A|10|0|0|\r\n",
        "EMS-LEDS-B|0|10|0|\r\n",
        "DANCE-LIGHTS-START\r\n",
        "DANCE-LIGHTS-STOP\r\n",
    ]
    ok, text = tcp_send_test(host, port, led_cmds, timeout=5)
    result("LED command suite", ok, text)
    if ok: passed += 1
    else: failed += 1

    # ── T7: Leaderboard pipe ──────────────────────────────────────────────────
    section("T7 · Leaderboard Named Pipe  (scores + answers + bulk)")
    pipe_msgs = [
        "*1*2*3+100",
        "*4*5+200",
        "*1-50",
        "@1:A",
        "@2:B",
        "@3:C",
        "@4:D",
        "ANSWERS:1:A,2:B,3:C,4:D,5:A,6:B,7:C,8:D",
        "*1*2*3*4*5*6*7*8+100",
    ]
    ok, text = pipe_send_test(pipe_msgs)
    result("Leaderboard pipe suite", ok, text)
    if ok: passed += 1
    else: failed += 1

    # ── Summary ───────────────────────────────────────────────────────────────
    total = passed + failed
    log_cb(f"\n{'═'*55}")
    log_cb(f"  SUITE COMPLETE  —  {passed}/{total} PASSED  {'✓' if failed==0 else '✗'}")
    log_cb(f"{'═'*55}")
    emit("TEST_PASS" if failed==0 else "TEST_FAIL",
         "TestSuite", "INTERNAL",
         f"Suite: {passed}/{total} passed",
         "SUITE_RESULT",
         f"{passed}/{total} tests passed, {failed} failed")


# ══════════════════════════════════════════════════════════════════════════════
#  GUI
# ══════════════════════════════════════════════════════════════════════════════

class MonitorGUI:
    # Colour palette — dark terminal aesthetic
    BG       = "#0a0a0f"
    BG2      = "#111118"
    BG3      = "#1a1a24"
    FG       = "#c8d0e0"
    FG_DIM   = "#606878"
    ACC      = "#00d4ff"
    ACC2     = "#ff3366"
    ACC3     = "#00ff9f"
    BORDER   = "#2a2a3a"
    FONT_MONO = ("Consolas", 9)
    FONT_UI   = ("Segoe UI", 9)
    FONT_H    = ("Segoe UI", 10, "bold")

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("GAMESHOW SYSTEM MONITOR")
        self.root.geometry("1400x900")
        self.root.configure(bg=self.BG)
        self.root.minsize(1100, 700)

        # Services
        self.tcp_server  = TCPInterceptServer(port=8080)
        self.pipe        = PipeInterceptor()
        self.db_watcher  = DatabaseWatcher()
        self.proc_mon    = ProcessMonitor()

        # State
        self._event_queue: queue.Queue = queue.Queue()
        self._filter_var  = tk.StringVar(value="ALL")
        self._search_var  = tk.StringVar()
        self._paused      = tk.BooleanVar(value=False)
        self._autoscroll  = tk.BooleanVar(value=True)
        self._event_rows  = []   # (tag, text) for filtered display
        self._leaderboard = {i: {"score": 0, "answer": None} for i in range(1, 13)}
        self._score_labels = {}
        self._answer_labels = {}
        self._proc_dots   = {}
        self._stat_vars   = {}

        BUS.subscribe(self._on_event)
        self._build_ui()
        self._start_services()
        self._gui_poll()

    # ── UI construction ────────────────────────────────────────────────────────

    def _build_ui(self):
        r = self.root
        r.protocol("WM_DELETE_WINDOW", self._on_close)

        # ── Header bar ───────────────────────────────────────────────────────
        header = tk.Frame(r, bg="#05050a", height=44)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        tk.Label(header, text="⬡ GAMESHOW SYSTEM MONITOR",
                 font=("Consolas", 14, "bold"),
                 fg=self.ACC, bg="#05050a").pack(side=tk.LEFT, padx=16, pady=8)
        self._status_label = tk.Label(header, text="● STARTING",
                                       font=("Consolas", 10, "bold"),
                                       fg="#ffaa00", bg="#05050a")
        self._status_label.pack(side=tk.LEFT, padx=8)
        tk.Label(header,
                 text="Full-spectrum diagnostics — every byte, pipe command, DB op, and process event",
                 font=self.FONT_UI, fg=self.FG_DIM, bg="#05050a").pack(side=tk.LEFT, padx=12)

        # ── Top control strip ──────────────────────────────────────────────
        ctrl = tk.Frame(r, bg=self.BG2, pady=5)
        ctrl.pack(fill=tk.X, padx=6)

        tk.Label(ctrl, text="Filter:", fg=self.FG_DIM, bg=self.BG2,
                 font=self.FONT_UI).pack(side=tk.LEFT, padx=(6, 3))
        filters = ["ALL", "TCP", "PIPE", "DB", "PROC", "PARSE", "TEST", "ERROR"]
        for f in filters:
            rb = tk.Radiobutton(ctrl, text=f, variable=self._filter_var, value=f,
                                command=self._apply_filter,
                                bg=self.BG2, fg=self.FG, selectcolor=self.BG3,
                                activebackground=self.BG2, activeforeground=self.ACC,
                                font=self.FONT_UI, bd=0)
            rb.pack(side=tk.LEFT, padx=2)

        tk.Label(ctrl, text="Search:", fg=self.FG_DIM, bg=self.BG2,
                 font=self.FONT_UI).pack(side=tk.LEFT, padx=(12, 3))
        search_entry = tk.Entry(ctrl, textvariable=self._search_var, width=20,
                                bg=self.BG3, fg=self.FG, insertbackground=self.FG,
                                relief="flat", font=self.FONT_MONO)
        search_entry.pack(side=tk.LEFT, padx=(0, 8))
        self._search_var.trace_add("write", lambda *a: self._apply_filter())

        tk.Checkbutton(ctrl, text="Pause", variable=self._paused,
                       bg=self.BG2, fg=self.FG, selectcolor=self.BG3,
                       activebackground=self.BG2, font=self.FONT_UI).pack(side=tk.LEFT, padx=4)
        tk.Checkbutton(ctrl, text="Auto-scroll", variable=self._autoscroll,
                       bg=self.BG2, fg=self.FG, selectcolor=self.BG3,
                       activebackground=self.BG2, font=self.FONT_UI).pack(side=tk.LEFT, padx=4)

        tk.Button(ctrl, text="Clear", font=self.FONT_UI,
                  bg=self.BG3, fg=self.FG, relief="flat", padx=8, pady=2,
                  command=self._clear_log).pack(side=tk.LEFT, padx=4)
        tk.Button(ctrl, text="📥 Export CSV", font=self.FONT_UI,
                  bg="#0f3460", fg="#fff", relief="flat", padx=10, pady=2,
                  command=self._export_csv).pack(side=tk.LEFT, padx=4)
        tk.Button(ctrl, text="📥 Export JSON", font=self.FONT_UI,
                  bg="#0f3460", fg="#fff", relief="flat", padx=10, pady=2,
                  command=self._export_json).pack(side=tk.LEFT, padx=4)
        tk.Button(ctrl, text="📄 Export Full Log", font=self.FONT_UI,
                  bg="#0f3460", fg="#fff", relief="flat", padx=10, pady=2,
                  command=self._export_txt).pack(side=tk.LEFT, padx=4)

        # ── Main paned layout ──────────────────────────────────────────────
        paned = tk.PanedWindow(r, orient=tk.HORIZONTAL, bg=self.BG,
                                sashwidth=5, sashrelief="flat")
        paned.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        # ── LEFT COLUMN: sidebar panels ──────────────────────────────────
        left = tk.Frame(paned, bg=self.BG, width=320)
        paned.add(left, minsize=260)

        self._build_stats_panel(left)
        self._build_proc_panel(left)
        self._build_leaderboard_panel(left)
        self._build_test_panel(left)

        # ── RIGHT COLUMN: tabbed log ──────────────────────────────────────
        right = tk.Frame(paned, bg=self.BG)
        paned.add(right, minsize=600)

        # Notebook tabs
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Dark.TNotebook",
                        background=self.BG, borderwidth=0)
        style.configure("Dark.TNotebook.Tab",
                        background=self.BG3, foreground=self.FG_DIM,
                        padding=[10, 4], font=self.FONT_UI)
        style.map("Dark.TNotebook.Tab",
                  background=[("selected", self.BG2)],
                  foreground=[("selected", self.ACC)])

        nb = ttk.Notebook(right, style="Dark.TNotebook")
        nb.pack(fill=tk.BOTH, expand=True)

        # Tab 1: All events
        self._log_text = self._make_log_tab(nb, "All Events")

        # Tab 2: TCP only
        self._tcp_text = self._make_log_tab(nb, "TCP Traffic")

        # Tab 3: Pipe only
        self._pipe_text = self._make_log_tab(nb, "Pipe Traffic")

        # Tab 4: Parsed messages
        self._parsed_text = self._make_log_tab(nb, "Parsed Messages")

        # Tab 5: Test output
        self._test_text = self._make_log_tab(nb, "Test Output")

        # Tab 6: Errors
        self._err_text = self._make_log_tab(nb, "⚠ Errors")

        # ── Status bar ────────────────────────────────────────────────────
        statusbar = tk.Frame(r, bg="#05050a", height=22)
        statusbar.pack(fill=tk.X, side=tk.BOTTOM)
        statusbar.pack_propagate(False)
        self._sb_label = tk.Label(statusbar, text="Ready.",
                                   font=("Consolas", 8), fg=self.FG_DIM, bg="#05050a",
                                   anchor="w")
        self._sb_label.pack(side=tk.LEFT, padx=8)
        self._event_count_label = tk.Label(statusbar, text="Events: 0",
                                            font=("Consolas", 8), fg=self.FG_DIM,
                                            bg="#05050a", anchor="e")
        self._event_count_label.pack(side=tk.RIGHT, padx=8)

        # Register tag colours in all text widgets
        for tw in [self._log_text, self._tcp_text, self._pipe_text,
                   self._parsed_text, self._test_text, self._err_text]:
            for cat, color in EVENT_CATEGORIES.items():
                tw.tag_configure(cat, foreground=color)
            tw.tag_configure("TIMESTAMP", foreground="#445566")
            tw.tag_configure("SOURCE",    foreground="#6688aa")
            tw.tag_configure("DIM",       foreground="#404050")
            tw.tag_configure("SEP",       foreground="#222233")

    def _make_log_tab(self, parent, title):
        frame = tk.Frame(parent, bg=self.BG)
        parent.add(frame, text=f"  {title}  ")
        tw = scrolledtext.ScrolledText(
            frame,
            font=self.FONT_MONO,
            bg=self.BG, fg=self.FG,
            insertbackground=self.FG,
            selectbackground="#223355",
            relief="flat",
            state="disabled",
        )
        tw.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
        return tw

    def _build_stats_panel(self, parent):
        f = tk.LabelFrame(parent, text=" Event Statistics ",
                          bg=self.BG2, fg=self.ACC,
                          font=self.FONT_H, padx=8, pady=6, bd=1,
                          relief="flat", highlightthickness=1,
                          highlightbackground=self.BORDER)
        f.pack(fill=tk.X, padx=6, pady=4)

        categories = [
            ("TCP_CONNECT",   "TCP Connects"),
            ("TCP_RECV",      "TCP Recv"),
            ("TCP_SEND",      "TCP Send"),
            ("PIPE_RECV",     "Pipe Recv"),
            ("PARSE_ANSWER",  "Answers"),
            ("PARSE_SCORE",   "Score Cmds"),
            ("PARSE_LED",     "LED Cmds"),
            ("DB_WRITE",      "DB Writes"),
            ("DB_DELETE",     "DB Deletes"),
            ("ERROR",         "Errors"),
        ]

        grid = tk.Frame(f, bg=self.BG2)
        grid.pack(fill=tk.X)
        for i, (cat, label) in enumerate(categories):
            row, col = divmod(i, 2)
            var = tk.StringVar(value="0")
            self._stat_vars[cat] = var
            color = EVENT_CATEGORIES.get(cat, self.FG)
            tk.Label(grid, text=label+":", fg=self.FG_DIM, bg=self.BG2,
                     font=("Consolas", 8), anchor="w", width=12).grid(
                     row=row, column=col*2, sticky="w", padx=2, pady=1)
            tk.Label(grid, textvariable=var, fg=color, bg=self.BG2,
                     font=("Consolas", 8, "bold"), anchor="e", width=5).grid(
                     row=row, column=col*2+1, sticky="e", padx=(0,10), pady=1)

    def _build_proc_panel(self, parent):
        f = tk.LabelFrame(parent, text=" Process Health ",
                          bg=self.BG2, fg=self.ACC,
                          font=self.FONT_H, padx=8, pady=6, bd=1,
                          relief="flat", highlightthickness=1,
                          highlightbackground=self.BORDER)
        f.pack(fill=tk.X, padx=6, pady=4)

        for script, label in WATCH_PROCESSES.items():
            row = tk.Frame(f, bg=self.BG2)
            row.pack(fill=tk.X, pady=1)
            dot = tk.Canvas(row, width=12, height=12, bg=self.BG2, highlightthickness=0)
            dot.create_oval(2, 2, 10, 10, fill="#444455", tags="dot")
            dot.pack(side=tk.LEFT, padx=(0, 6))
            self._proc_dots[script] = dot
            tk.Label(row, text=label, fg=self.FG_DIM, bg=self.BG2,
                     font=("Consolas", 8)).pack(side=tk.LEFT)

    def _build_leaderboard_panel(self, parent):
        f = tk.LabelFrame(parent, text=" Leaderboard State ",
                          bg=self.BG2, fg=self.ACC,
                          font=self.FONT_H, padx=8, pady=6, bd=1,
                          relief="flat", highlightthickness=1,
                          highlightbackground=self.BORDER)
        f.pack(fill=tk.X, padx=6, pady=4)

        grid = tk.Frame(f, bg=self.BG2)
        grid.pack(fill=tk.X)

        tk.Label(grid, text="Tbl", fg=self.FG_DIM, bg=self.BG2,
                 font=("Consolas", 8), width=3).grid(row=0, column=0)
        tk.Label(grid, text="Score", fg=self.FG_DIM, bg=self.BG2,
                 font=("Consolas", 8), width=6).grid(row=0, column=1)
        tk.Label(grid, text="Ans", fg=self.FG_DIM, bg=self.BG2,
                 font=("Consolas", 8), width=4).grid(row=0, column=2)

        answer_colors = {"A": "#2ecc71", "B": "#3498db", "C": "#9b59b6", "D": "#e67e22"}

        for i in range(1, 13):
            sv = tk.StringVar(value="0")
            av = tk.StringVar(value="-")
            self._score_labels[i] = sv
            self._answer_labels[i] = av
            tk.Label(grid, text=f"{i:2d}", fg=self.FG_DIM, bg=self.BG2,
                     font=("Consolas", 8), width=3).grid(row=i, column=0, sticky="w")
            tk.Label(grid, textvariable=sv, fg=self.ACC3, bg=self.BG2,
                     font=("Consolas", 8, "bold"), width=6).grid(row=i, column=1)
            al = tk.Label(grid, textvariable=av, fg=self.FG_DIM, bg=self.BG2,
                          font=("Consolas", 8, "bold"), width=4)
            al.grid(row=i, column=2)

    def _build_test_panel(self, parent):
        f = tk.LabelFrame(parent, text=" Test Runner ",
                          bg=self.BG2, fg=self.ACC,
                          font=self.FONT_H, padx=8, pady=6, bd=1,
                          relief="flat", highlightthickness=1,
                          highlightbackground=self.BORDER)
        f.pack(fill=tk.X, padx=6, pady=4)

        cfg = tk.Frame(f, bg=self.BG2)
        cfg.pack(fill=tk.X, pady=2)
        tk.Label(cfg, text="Host:", fg=self.FG_DIM, bg=self.BG2,
                 font=self.FONT_UI).pack(side=tk.LEFT)
        self._test_host = tk.StringVar(value="127.0.0.1")
        tk.Entry(cfg, textvariable=self._test_host, width=12,
                 bg=self.BG3, fg=self.FG, insertbackground=self.FG,
                 relief="flat", font=self.FONT_MONO).pack(side=tk.LEFT, padx=4)
        tk.Label(cfg, text="Port:", fg=self.FG_DIM, bg=self.BG2,
                 font=self.FONT_UI).pack(side=tk.LEFT)
        self._test_port = tk.StringVar(value="8080")
        tk.Entry(cfg, textvariable=self._test_port, width=6,
                 bg=self.BG3, fg=self.FG, insertbackground=self.FG,
                 relief="flat", font=self.FONT_MONO).pack(side=tk.LEFT, padx=4)

        btns = tk.Frame(f, bg=self.BG2)
        btns.pack(fill=tk.X, pady=4)

        tests = [
            ("T1 BSD Conn",       lambda: self._run_test_async("T1 BSD Connection", lambda h,p: tcp_send_test(h,p,[]))),
            ("T2 Gameshow→BSD",   lambda: self._run_test_async("T2 Gameshow→BSD",   lambda h,p: tcp_send_test(h,p,["awns_B\r\n","DASHBOARD-READY-TRIGGER\r\n"]))),
            ("T3 PING",           lambda: self._run_test_async("T3 PING",           lambda h,p: tcp_send_test(h,p,["PING\r\n"]))),
            ("T4a Legacy Ans",    lambda: self._run_test_async("T4a Legacy",        lambda h,p: tcp_send_test(h,p,["@2:B\r\n","@5:A\r\n"]))),
            ("T4b EMS Firmware",  lambda: self._run_test_async("T4b EMS FW",        lambda h,p: tcp_send_test(h,p,["\ufffd|EMS|3|C|7199|\r\n"]))),
            ("T5 12-tbl Rapid",   lambda: self._run_test_async("T5 Rapid",          lambda h,p: tcp_send_test(h,p,[f"@{t}:{'ABCD'[(t-1)%4]}\r\n" for t in range(1,13)],8))),
            ("T6 LED Suite",      lambda: self._run_test_async("T6 LEDs",           lambda h,p: tcp_send_test(h,p,["EMS-LEDS-X|10|0|0|\r\n","EMS-LEDS-X|0|10|0|\r\n","EMS-LEDS-X|0|0|0|\r\n","DANCE-LIGHTS-START\r\n","DANCE-LIGHTS-STOP\r\n"],5))),
            ("T7 Pipe Scores",    lambda: self._run_test_async("T7 Pipe",           lambda h,p: pipe_send_test(["*1*2+100","*3-50","@1:A","ANSWERS:1:A,2:B,3:C,4:D"]))),
        ]

        for i, (label, cmd) in enumerate(tests):
            row, col = divmod(i, 2)
            tk.Button(btns, text=label, font=("Consolas", 8),
                      bg=self.BG3, fg=self.FG,
                      activebackground=self.ACC, activeforeground="#000",
                      relief="flat", padx=4, pady=2,
                      command=cmd).grid(row=row, column=col, padx=2, pady=2, sticky="ew")
        btns.columnconfigure(0, weight=1)
        btns.columnconfigure(1, weight=1)

        tk.Button(f, text="▶▶  RUN FULL TEST SUITE",
                  font=("Consolas", 9, "bold"),
                  bg="#1a0a2e", fg=self.ACC,
                  activebackground=self.ACC, activeforeground="#000",
                  relief="flat", padx=10, pady=5,
                  command=self._run_full_suite).pack(fill=tk.X, pady=4)

    # ── Event handling ────────────────────────────────────────────────────────

    def _on_event(self, event: Event):
        """Called from any thread — queue for GUI thread."""
        self._event_queue.put(event)

    def _gui_poll(self):
        """Drain event queue on the GUI thread every 50 ms."""
        MAX_PER_POLL = 100
        count = 0
        while not self._event_queue.empty() and count < MAX_PER_POLL:
            try:
                event = self._event_queue.get_nowait()
                if not self._paused.get():
                    self._render_event(event)
                    self._update_sidebar(event)
                count += 1
            except queue.Empty:
                break

        # Update counters
        stats = BUS.stats()
        total = sum(stats.values())
        self._event_count_label.config(text=f"Events: {total}")
        for cat, var in self._stat_vars.items():
            var.set(str(stats.get(cat, 0)))

        self.root.after(50, self._gui_poll)

    def _render_event(self, e: Event):
        """Write one event line to the appropriate log panes."""
        cat = e.category
        color = EVENT_CATEGORIES.get(cat, self.FG)
        filt  = self._filter_var.get()
        search = self._search_var.get().lower()

        # Format the log line
        direction_sym = {"IN": "←", "OUT": "→", "INTERNAL": "·"}.get(e.direction, " ")
        line = (f"[{e.ts}] [{cat:<16s}] [{e.direction:<8s}] "
                f"{direction_sym} {e.source:<28s}  "
                f"{e.parsed_type:<20s}  {e.parsed_detail[:90]}")
        raw_line = f"          raw={e.raw[:100]}" if e.raw else ""

        # Determine which panes to write to
        panes_to_write = [self._log_text]  # always write to All Events

        if cat.startswith("TCP"):
            panes_to_write.append(self._tcp_text)
        if cat.startswith("PIPE"):
            panes_to_write.append(self._pipe_text)
        if cat.startswith("PARSE") or cat in ("PARSE_ANSWER","PARSE_SCORE","PARSE_LED"):
            panes_to_write.append(self._parsed_text)
        if cat.startswith("TEST"):
            panes_to_write.append(self._test_text)
        if cat == "ERROR":
            panes_to_write.append(self._err_text)

        # Filter check (only affects All Events tab scroll/highlight, other tabs always show their own)
        show_in_all = True
        if filt != "ALL":
            prefix_map = {
                "TCP": "TCP", "PIPE": "PIPE", "DB": "DB",
                "PROC": "PROC", "PARSE": "PARSE", "TEST": "TEST", "ERROR": "ERROR"
            }
            show_in_all = cat.startswith(prefix_map.get(filt, filt))
        if search and search not in line.lower() and search not in e.raw.lower():
            show_in_all = False

        def append_to(tw, show):
            tw.config(state="normal")
            tw.insert(tk.END, line + "\n", cat)
            if e.raw and cat in ("TCP_RECV", "TCP_SEND", "PIPE_RECV", "PIPE_SEND"):
                tw.insert(tk.END, raw_line + "\n", "DIM")
            if self._autoscroll.get() and show:
                tw.see(tk.END)
            tw.config(state="disabled")

        for tw in panes_to_write:
            is_all = tw is self._log_text
            append_to(tw, show_in_all if is_all else True)

    def _update_sidebar(self, e: Event):
        """Update live panels based on event content."""
        # Process dots
        for script in WATCH_PROCESSES:
            label = WATCH_PROCESSES[script]
            if e.source == f"PROC:{label}":
                dot = self._proc_dots.get(script)
                if dot:
                    color = "#00ff9f" if e.category == "PROC_ALIVE" else "#ff4444"
                    dot.itemconfig("dot", fill=color)

        # Leaderboard reconstruction
        if e.category == "PARSE_SCORE":
            tables = e.extra.get("tables", [])
            op     = e.extra.get("op", "+")
            pts    = e.extra.get("points", "0")
            try:
                delta = int(pts) * (1 if op == "+" else -1)
                for t in tables:
                    idx = int(t)
                    if 1 <= idx <= 12:
                        self._leaderboard[idx]["score"] += delta
                        sv = self._score_labels.get(idx)
                        if sv:
                            sv.set(str(self._leaderboard[idx]["score"]))
            except:
                pass

        if e.category == "PARSE_ANSWER":
            t = e.extra.get("table")
            a = e.extra.get("answer")
            ptype = e.extra.get("format", e.parsed_type)
            if t and a:
                try:
                    idx = int(t)
                    if 1 <= idx <= 12:
                        self._leaderboard[idx]["answer"] = a
                        av = self._answer_labels.get(idx)
                        if av:
                            av.set(a)
                except:
                    pass

        # Status bar
        self._sb_label.config(text=f"[{e.ts}] {e.source}: {e.parsed_detail[:100]}")

    # ── Test helpers ──────────────────────────────────────────────────────────

    def _run_test_async(self, name, fn):
        host = self._test_host.get()
        try:
            port = int(self._test_port.get())
        except ValueError:
            messagebox.showerror("Bad port", "Port must be a number")
            return
        def _do():
            ok, text = fn(host, port)
            sym = "PASS ✓" if ok else "FAIL ✗"
            self._append_test(f"\n[{name}] {sym}\n{text}\n")
        threading.Thread(target=_do, daemon=True).start()

    def _run_full_suite(self):
        host = self._test_host.get()
        try:
            port = int(self._test_port.get())
        except ValueError:
            messagebox.showerror("Bad port", "Port must be a number")
            return
        def _do():
            self._append_test("\n" + "═"*55 + "\n  FULL TEST SUITE STARTING\n" + "═"*55)
            run_test_suite(host, port, self._append_test)
        threading.Thread(target=_do, daemon=True).start()

    def _append_test(self, text):
        self.root.after(0, lambda t=text: self._do_append_test(t))

    def _do_append_test(self, text):
        tw = self._test_text
        tw.config(state="normal")
        for line in text.splitlines():
            tag = "TEST_PASS" if "PASS" in line or "✓" in line else \
                  "TEST_FAIL" if "FAIL" in line or "✗" in line else "TEST_INFO"
            tw.insert(tk.END, line + "\n", tag)
        if self._autoscroll.get():
            tw.see(tk.END)
        tw.config(state="disabled")

    # ── Filter ────────────────────────────────────────────────────────────────

    def _apply_filter(self):
        """Re-render all events through the current filter into All Events tab."""
        tw = self._log_text
        tw.config(state="normal")
        tw.delete("1.0", tk.END)
        tw.config(state="disabled")
        filt = self._filter_var.get()
        search = self._search_var.get().lower()
        prefix_map = {
            "TCP": "TCP", "PIPE": "PIPE", "DB": "DB",
            "PROC": "PROC", "PARSE": "PARSE", "TEST": "TEST", "ERROR": "ERROR"
        }
        for e in BUS.all_events():
            if filt != "ALL":
                if not e.category.startswith(prefix_map.get(filt, filt)):
                    continue
            if search:
                line_check = f"{e.source} {e.parsed_type} {e.parsed_detail} {e.raw}".lower()
                if search not in line_check:
                    continue
            self._render_event(e)

    # ── Clear ────────────────────────────────────────────────────────────────

    def _clear_log(self):
        BUS.clear()
        for tw in [self._log_text, self._tcp_text, self._pipe_text,
                   self._parsed_text, self._test_text, self._err_text]:
            tw.config(state="normal")
            tw.delete("1.0", tk.END)
            tw.config(state="disabled")
        # Reset leaderboard display
        for i in range(1, 13):
            self._leaderboard[i] = {"score": 0, "answer": None}
            self._score_labels[i].set("0")
            self._answer_labels[i].set("-")

    # ── Export ────────────────────────────────────────────────────────────────

    def _export_csv(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv"), ("All", "*.*")],
            initialfile=f"gameshow_log_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            title="Export CSV"
        )
        if not path:
            return
        events = BUS.all_events()
        try:
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=[
                    "ts", "category", "source", "direction",
                    "parsed_type", "parsed_detail", "raw", "extra"
                ])
                writer.writeheader()
                for e in events:
                    d = e.to_dict()
                    d["extra"] = json.dumps(d.get("extra", {}))
                    writer.writerow(d)
            messagebox.showinfo("Export", f"Exported {len(events)} events to:\n{path}")
        except Exception as ex:
            messagebox.showerror("Export Error", str(ex))

    def _export_json(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON", "*.json"), ("All", "*.*")],
            initialfile=f"gameshow_log_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            title="Export JSON"
        )
        if not path:
            return
        events = BUS.all_events()
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump({
                    "session_start": datetime.datetime.now().isoformat(),
                    "total_events": len(events),
                    "stats": BUS.stats(),
                    "leaderboard_final": {
                        str(k): v for k, v in self._leaderboard.items()
                    },
                    "events": [e.to_dict() for e in events],
                }, f, indent=2)
            messagebox.showinfo("Export", f"Exported {len(events)} events to:\n{path}")
        except Exception as ex:
            messagebox.showerror("Export Error", str(ex))

    def _export_txt(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".log",
            filetypes=[("Log", "*.log"), ("Text", "*.txt"), ("All", "*.*")],
            initialfile=f"gameshow_full_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.log",
            title="Export Full Log"
        )
        if not path:
            return
        events = BUS.all_events()
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(f"# GAMESHOW SYSTEM MONITOR — Full Log\n")
                f.write(f"# Exported: {datetime.datetime.now().isoformat()}\n")
                f.write(f"# Total events: {len(events)}\n")
                f.write(f"# Stats: {json.dumps(BUS.stats())}\n\n")
                f.write("# Leaderboard final state:\n")
                for i in range(1, 13):
                    lb = self._leaderboard[i]
                    f.write(f"#   Table {i:2d}: score={lb['score']:6d}  last_answer={lb['answer']}\n")
                f.write("\n" + "═"*80 + "\n\n")
                for e in events:
                    dir_sym = {"IN":"←","OUT":"→","INTERNAL":"·"}.get(e.direction," ")
                    f.write(f"[{e.ts}] [{e.category:<16}] [{e.direction:<8}] {dir_sym} "
                            f"{e.source:<30}  {e.parsed_type:<20}  {e.parsed_detail}\n")
                    if e.raw:
                        f.write(f"         raw: {e.raw[:200]}\n")
                    if e.extra:
                        f.write(f"         extra: {json.dumps(e.extra)}\n")
                    f.write("\n")
            messagebox.showinfo("Export", f"Exported {len(events)} events to:\n{path}")
        except Exception as ex:
            messagebox.showerror("Export Error", str(ex))

    # ── Startup ───────────────────────────────────────────────────────────────

    def _start_services(self):
        emit("SYSTEM", "Monitor", "INTERNAL",
             "Gameshow Monitor starting up",
             "STARTUP",
             "Initialising TCP intercept, pipe monitor, DB watcher, process monitor")
        self.tcp_server.start()
        self.pipe.start()
        self.db_watcher.start()
        self.proc_mon.start()
        self._status_label.config(text="● MONITORING", fg=self.ACC3)

    def _on_close(self):
        self.tcp_server.stop()
        self.pipe.stop()
        self.db_watcher.stop()
        self.proc_mon.stop()
        self.root.destroy()

    def run(self):
        self.root.mainloop()


# ══════════════════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("""
╔══════════════════════════════════════════════════════════════╗
║         GAMESHOW SYSTEM MONITOR  v2.0                        ║
╠══════════════════════════════════════════════════════════════╣
║  Captures:                                                   ║
║    • TCP traffic (port 8080) — every byte in/out             ║
║    • Named pipe BSD→Leaderboard — all commands               ║
║    • access_codes.db — every read/write/delete               ║
║    • Process health — all 5 scripts watched live             ║
║    • Message parsing — EMS, legacy, LED, READY, scores       ║
║    • Leaderboard state reconstruction in real-time           ║
║    • Full test suite with 8 test categories                  ║
╠══════════════════════════════════════════════════════════════╣
║  IMPORTANT: Run this FIRST, then start the rest of the       ║
║  suite. The monitor owns port 8080 as the TCP server.        ║
║  Export buttons save CSV / JSON / full text log.             ║
╚══════════════════════════════════════════════════════════════╝
""")
    MonitorGUI().run()
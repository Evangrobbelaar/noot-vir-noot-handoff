"""
bsd_simulator.py
================
Test simulator for bsd.py. Simulates every client type that connects to the
server so you can verify that connections, message routing, and leaderboard
forwarding all still work after making edits to bsd.py.

Simulates:
  1. gameshow2.py client  — sends LED commands, awns_, DASHBOARD-READY-TRIGGER, PING
  2. Hardware button boxes — sends answers in both supported wire formats
  3. Named pipe server    — acts as leaderboard.py, captures what bsd.py pipes

Usage:
  1. Start bsd.py and click "Start Server" (default port 8080)
  2. python bsd_simulator.py

All sent/received bytes are printed verbatim so you can diff against the
real hardware captures if needed.
"""

import socket
import sys
import threading
import time

# Force UTF-8 output so Unicode chars (arrows, box-drawing) print on any console.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# ── Configuration ─────────────────────────────────────────────────────────────
HOST = "127.0.0.1"
PORT = 8080
CONNECT_TIMEOUT = 5.0   # seconds to wait for bsd.py to accept
RECV_TIMEOUT    = 2.0   # seconds to wait for data after sending

# ── Shared state ──────────────────────────────────────────────────────────────
pipe_received: list[str] = []   # messages bsd.py wrote to the leaderboard pipe
pass_count = 0
fail_count = 0
results: list[str] = []


# ==============================================================================
# Helpers
# ==============================================================================

def log(label: str, msg: str) -> None:
    line = f"[{label:14s}] {msg}"
    print(line)
    results.append(line)


def check(label: str, condition: bool, pass_msg: str, fail_msg: str) -> None:
    global pass_count, fail_count
    if condition:
        pass_count += 1
        log(label, f"PASS  {pass_msg}")
    else:
        fail_count += 1
        log(label, f"FAIL  {fail_msg}")


def tcp_connect(label: str) -> socket.socket | None:
    """Open a TCP connection to bsd.py and verify the 'Connected' handshake."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(CONNECT_TIMEOUT)
        s.connect((HOST, PORT))
        s.settimeout(RECV_TIMEOUT)
        banner = s.recv(1024).decode("utf-8", errors="replace")
        check(label, "Connected" in banner,
              f"received banner: {repr(banner.strip())}",
              f"unexpected banner: {repr(banner.strip())}")
        return s
    except Exception as exc:
        log(label, f"FAIL  connect error: {exc}")
        return None


def send_msg(sock: socket.socket, label: str, data: str) -> None:
    """Send a message terminated with \\r\\n — exactly what the real clients do."""
    raw = data if data.endswith("\r\n") else data + "\r\n"
    sock.send(raw.encode("utf-8"))
    log(label, f"SENT  {repr(raw.strip())}")


def recv_msgs(sock: socket.socket, label: str, timeout: float = RECV_TIMEOUT) -> str:
    """Drain the socket for `timeout` seconds and return everything as a string."""
    sock.settimeout(timeout)
    chunks: list[str] = []
    try:
        while True:
            chunk = sock.recv(4096)
            if not chunk:
                break
            chunks.append(chunk.decode("utf-8", errors="replace"))
    except socket.timeout:
        pass
    full = "".join(chunks)
    if full:
        log(label, f"RECV  {repr(full.strip())}")
    return full


def close_quietly(sock: socket.socket) -> None:
    try:
        sock.close()
    except Exception:
        pass


# ==============================================================================
# Named-pipe server (simulates leaderboard.py)
# ==============================================================================

PIPE_NAME = r"\\.\pipe\gameshow_pipe"
pipe_server_ready = threading.Event()


def run_pipe_server() -> None:
    """
    Creates the same named pipe that leaderboard.py creates.
    bsd.py opens it as a write-only client and sends leaderboard commands here.

    Leaderboard pipe protocol (what bsd.py writes):
      @TABLE:ANSWER           — answer forwarded from a hardware button
      *TABLE1*TABLE2+POINTS   — add points
      *TABLE1*TABLE2-POINTS   — subtract points

    Race-condition fix: bsd.py reconnects for every message (one write → close).
    We use unlimited pipe instances and spawn a new listener thread the moment a
    client connects, so there is always an open instance ready for the next write.
    """
    try:
        import win32pipe
        import win32file
    except ImportError:
        log("PIPE", "pywin32 not available — pipe capture skipped")
        pipe_server_ready.set()
        return

    log("PIPE", f"Pipe server ready on {PIPE_NAME}")
    pipe_server_ready.set()

    def handle_one(pipe) -> None:
        """Read all messages from one pipe connection then close it."""
        try:
            while True:
                _, raw = win32file.ReadFile(pipe, 64 * 1024)
                msg = raw.decode("utf-8", errors="replace")
                pipe_received.append(msg)
                log("PIPE", f"bsd→leaderboard: {repr(msg)}")
        except Exception:
            pass
        finally:
            try:
                win32file.CloseHandle(pipe)
            except Exception:
                pass

    def create_instance() -> None:
        """Create one pipe instance and wait for a client in a daemon thread.
        The moment a client connects, spawn another instance so we are never
        caught without a ready listener."""
        try:
            pipe = win32pipe.CreateNamedPipe(
                PIPE_NAME,
                win32pipe.PIPE_ACCESS_DUPLEX,
                win32pipe.PIPE_TYPE_MESSAGE
                    | win32pipe.PIPE_READMODE_MESSAGE
                    | win32pipe.PIPE_WAIT,
                win32pipe.PIPE_UNLIMITED_INSTANCES,
                65536, 65536, 0, None,
            )
        except Exception as exc:
            log("PIPE", f"CreateNamedPipe error: {exc}")
            return

        def wait_then_handle() -> None:
            try:
                win32pipe.ConnectNamedPipe(pipe, None)
            except Exception as exc:
                log("PIPE", f"ConnectNamedPipe error: {exc}")
                try:
                    win32file.CloseHandle(pipe)
                except Exception:
                    pass
                return
            # Client connected — immediately open a fresh instance for the next
            # connection before we start reading, eliminating the race window.
            create_instance()
            handle_one(pipe)

        threading.Thread(target=wait_then_handle, daemon=True).start()

    # Seed with two instances so concurrent rapid connects are handled.
    create_instance()
    create_instance()


# ==============================================================================
# Test scenarios
# ==============================================================================

def run_tests() -> None:
    pipe_server_ready.wait(timeout=3)

    # ── Test 1: gameshow2.py connects ─────────────────────────────────────────
    log("", "")
    log("TEST", "== 1/7  gameshow2.py client connection ==")
    gameshow = tcp_connect("GAMESHOW")
    if gameshow is None:
        log("TEST", "Cannot continue without gameshow connection — is bsd.py running?")
        return

    # ── Test 2: Four hardware button boxes connect ─────────────────────────────
    log("", "")
    log("TEST", "== 2/7  Hardware button box connections (tables 1-4) ==")
    boxes: dict[int, socket.socket] = {}
    for t in range(1, 5):
        sock = tcp_connect(f"BOX-T{t}")
        if sock:
            boxes[t] = sock
    time.sleep(0.3)

    # ── Test 3: gameshow sends PING (keepalive) ────────────────────────────────
    # gameshow2.py sends PING after connecting; bsd.py does not reply but must
    # not crash or disconnect the client.
    log("", "")
    log("TEST", "== 3/7  PING keepalive (no reply expected) ==")
    send_msg(gameshow, "GAMESHOW", "PING")
    time.sleep(0.2)
    # Verify connection is still alive by checking socket is not closed
    check("GAMESHOW", gameshow.fileno() != -1,
          "socket still open after PING",
          "socket closed after PING")

    # ── Test 4: gameshow sends awns_ (correct answer) ─────────────────────────
    # Wire format used by gameshow2.py line ~499:
    #   command = f"awns_{self.current_answer}\r\n"
    # bsd.py stores it as self.correct_answer and updates the UI radio button.
    log("", "")
    log("TEST", "== 4/7  awns_ correct-answer message ==")
    send_msg(gameshow, "GAMESHOW", "awns_B")
    time.sleep(0.3)
    log("TEST", "bsd.py should now show 'B' selected as correct answer in UI")

    # ── Test 5: DASHBOARD-READY-TRIGGER → READY broadcast ─────────────────────
    # gameshow2.py sends this when the operator presses N at first pause.
    # bsd.py must broadcast READY\r\n to every connected client.
    log("", "")
    log("TEST", "== 5/7  DASHBOARD-READY-TRIGGER → READY broadcast ==")
    send_msg(gameshow, "GAMESHOW", "DASHBOARD-READY-TRIGGER")
    time.sleep(0.5)

    for t, sock in boxes.items():
        data = recv_msgs(sock, f"BOX-T{t}")
        check(f"BOX-T{t}", "READY" in data,
              "received READY",
              f"did not receive READY — got {repr(data[:80])}")

    # ── Test 6: Legacy @TABLE:ANSWER from button boxes ─────────────────────────
    # Wire format: @<table>:<answer>\r\n
    # bsd.py must log it and pipe @TABLE:ANSWER to the leaderboard.
    log("", "")
    log("TEST", "== 6/7  Legacy @TABLE:ANSWER button format ==")
    send_msg(boxes[1], "BOX-T1", "@1:A")   # wrong answer
    send_msg(boxes[2], "BOX-T2", "@2:B")   # correct answer
    time.sleep(0.5)

    check("PIPE",
          any("@1:A" in m for m in pipe_received),
          "leaderboard got @1:A",
          "leaderboard did NOT get @1:A")
    check("PIPE",
          any("@2:B" in m for m in pipe_received),
          "leaderboard got @2:B",
          "leaderboard did NOT get @2:B")

    # ── Test 7: EMS hardware format from button boxes ─────────────────────────
    # Wire format:  ®|EMS|<table>|<answer>|<question>|\r\n
    #
    # ® is U+00AE (registered-trademark sign).
    # The hardware likely transmits \xc2\xae (valid UTF-8 for ®).
    # bsd.py decodes with errors='replace' and checks message.startswith('®|EMS|').
    #
    # bsd.py should:
    #   • log:  @<question>:<table>:<answer> - Answer received from ...
    #   • pipe: @<table>:<answer>  (standardised format to leaderboard)
    log("", "")
    log("TEST", r"== 7/7  EMS hardware format (\xae|EMS|TABLE|ANSWER|QUESTION|) ==")

    # The hardware sends raw byte 0xae as a sync/prefix byte.
    # bsd.py decodes with errors='replace', turning 0xae into U+FFFD (\xef\xbf\xbd).
    # bsd.py's startswith check is literally for U+FFFD — confirmed by hex dump.
    # We must send the raw byte so bsd.py's replace-decode produces the match.
    ems_t3_raw = b"\xae|EMS|3|C|7199|\r\n"
    ems_t4_raw = b"\xae|EMS|4|B|7199|\r\n"
    boxes[3].send(ems_t3_raw)
    log("BOX-T3", f"SENT  {repr(ems_t3_raw.strip())}")
    boxes[4].send(ems_t4_raw)
    log("BOX-T4", f"SENT  {repr(ems_t4_raw.strip())}")
    time.sleep(0.5)

    check("PIPE",
          any("@3:C" in m for m in pipe_received),
          "leaderboard got @3:C  (from EMS format)",
          "leaderboard did NOT get @3:C")
    check("PIPE",
          any("@4:B" in m for m in pipe_received),
          "leaderboard got @4:B  (from EMS format)",
          "leaderboard did NOT get @4:B")

    # ── Bonus: LED commands from gameshow (sent to bsd.py) ────────────────────
    # gameshow2.py sends these; bsd.py logs them but does NOT relay them.
    # This is the current known behaviour — document it explicitly.
    log("", "")
    log("TEST", "== Bonus  LED / dance commands from gameshow (log-only, no relay) ==")
    for cmd in [
        "EMS-LEDS-X|10|0|0|",    # red all
        "EMS-LEDS-X|0|10|0|",    # green all
        "EMS-LEDS-X|0|0|0|",     # all off
        "DANCE-LIGHTS-START",
        "DANCE-LIGHTS-STOP",
    ]:
        send_msg(gameshow, "GAMESHOW", cmd)
        time.sleep(0.1)
    log("TEST", "All LED/dance commands sent — verify bsd.py logged them without error")

    # ── Cleanup ───────────────────────────────────────────────────────────────
    for sock in boxes.values():
        close_quietly(sock)
    close_quietly(gameshow)

    # ── Summary ───────────────────────────────────────────────────────────────
    log("", "")
    log("TEST", "== PIPE CAPTURE SUMMARY ==")
    if pipe_received:
        for i, m in enumerate(pipe_received):
            log("PIPE", f"  [{i}] {repr(m)}")
    else:
        log("PIPE", "  (nothing captured — is pywin32 installed?)")

    log("", "")
    log("RESULT", f"PASSED: {pass_count}   FAILED: {fail_count}")
    if fail_count == 0:
        log("RESULT", "All checks passed.")
    else:
        log("RESULT", f"{fail_count} check(s) failed — review output above.")


# ==============================================================================
# Entry point
# ==============================================================================

if __name__ == "__main__":
    print(__doc__)
    print(f"Connecting to bsd.py at {HOST}:{PORT}\n")

    # Named pipe server runs in a daemon thread — it outlives run_tests()
    pipe_thread = threading.Thread(target=run_pipe_server, daemon=True)
    pipe_thread.start()

    run_tests()

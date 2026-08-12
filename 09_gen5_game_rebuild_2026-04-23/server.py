"""
GameServer - TCP server for physical button units.
Imported by video_player.py; runs in daemon threads.
Protocol matches GameController_00c.cpp exactly.
"""

import socket
import threading
import time
import queue
import random
import logging

log = logging.getLogger(__name__)

# Byte value 231 (0xE7) that the firmware prefixes every button message with
HARDWARE_MSG_BYTE = 0xE7


class GameServer:
    def __init__(self, config: dict, event_bus: queue.Queue):
        self.config = config
        self.event_bus = event_bus

        self.clients: list[socket.socket] = []
        self.client_lock = threading.Lock()

        self.correct_answer: str | None = None
        # {table_number: {"answer": str, "timestamp": float, "counter": int}}
        self.round_answers: dict = {}
        self._round_lock = threading.Lock()

        self.leaderboard_socket: socket.socket | None = None
        self.leaderboard_lock = threading.Lock()

        self.dance_active = False
        self._dance_timer: threading.Timer | None = None

        self.colour_sequence_active = False
        self._colour_timer: threading.Timer | None = None

        self._server_sock: socket.socket | None = None

    # ------------------------------------------------------------------
    # Start
    # ------------------------------------------------------------------

    def start(self):
        """Start TCP accept loop and leaderboard connector in daemon threads."""
        t_accept = threading.Thread(target=self._accept_loop, daemon=True)
        t_accept.start()

        t_lb = threading.Thread(target=self._leaderboard_connector, daemon=True)
        t_lb.start()

    # ------------------------------------------------------------------
    # TCP accept loop
    # ------------------------------------------------------------------

    def _accept_loop(self):
        host = self.config["server"]["host"]
        port = self.config["server"]["port"]

        self._server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server_sock.bind((host, port))
        self._server_sock.listen(20)
        log.info("TCP server listening on %s:%d", host, port)

        while True:
            try:
                conn, addr = self._server_sock.accept()
                log.info("Button unit connected from %s", addr)
                with self.client_lock:
                    self.clients.append(conn)
                # Firmware expects "Connected\r\n" immediately on connect
                self._send_to_sock(conn, "Connected\r\n")
                t = threading.Thread(
                    target=self._client_read_loop,
                    args=(conn,),
                    daemon=True,
                )
                t.start()
            except Exception as exc:
                log.error("Accept loop error: %s", exc)
                time.sleep(1)

    def _client_read_loop(self, sock: socket.socket):
        """Buffer incoming bytes, split on \\r\\n, process each message."""
        buf = b""
        while True:
            try:
                data = sock.recv(256)
                if not data:
                    break
                buf += data
                # Split on \r\n - firmware always terminates with \r\n
                while b"\r\n" in buf:
                    line, buf = buf.split(b"\r\n", 1)
                    if line:
                        try:
                            self.process_message(sock, line)
                        except Exception as exc:
                            log.error("process_message error: %s", exc)
            except Exception as exc:
                log.warning("Client read error: %s", exc)
                break

        log.info("Button unit disconnected")
        with self.client_lock:
            if sock in self.clients:
                self.clients.remove(sock)
        try:
            sock.close()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Message processing
    # ------------------------------------------------------------------

    def process_message(self, sock: socket.socket, raw: bytes):
        """
        Handle one complete message from a button unit.
        raw is bytes (no trailing \\r\\n).
        """
        # Hardware button message: first byte is 0xE7 (ç)
        if raw[0] == HARDWARE_MSG_BYTE:
            # Decode, replacing any undecodeable bytes
            text = raw.decode("utf-8", errors="replace")
            parts = text.split("|")
            # Expected: ç|EMS|<SerialNo>|<Button>|<CounterValue>|
            # parts[0] = 'ç', parts[1] = 'EMS', parts[2] = table, parts[3] = button, parts[4] = counter
            if len(parts) >= 5 and parts[1] == "EMS":
                try:
                    table = int(parts[2])
                    button = parts[3].strip().upper()
                    counter = int(parts[4]) if parts[4].strip().isdigit() else 0
                except (ValueError, IndexError):
                    log.warning("Malformed EMS message: %r", raw)
                    return

                ts = time.time()
                with self._round_lock:
                    if table not in self.round_answers:
                        self.round_answers[table] = {
                            "answer": button,
                            "timestamp": ts,
                            "counter": counter,
                        }
                        log.info("Table %d answered %s (counter=%d)", table, button, counter)

                self.event_bus.put(
                    {"type": "answer", "table": table, "answer": button, "counter": counter}
                )
                # Notify leaderboard of this answer
                self.send_to_leaderboard(f"@{table}:{button}\n")
            return

        # Text-based internal commands (sent from video_player via internal calls,
        # but also handle if somehow received over TCP)
        try:
            text = raw.decode("utf-8", errors="replace").strip()
        except Exception:
            return

        if text == "DASHBOARD-READY-TRIGGER":
            self.broadcast("READY\r\n")
            self.event_bus.put({"type": "ready_sent"})
            self._start_colour_sequence()

        elif text in ("awns_A", "awns_B", "awns_C", "awns_D"):
            letter = text[-1].upper()
            self.correct_answer = letter
            self.event_bus.put({"type": "correct_answer_set", "answer": letter})

        elif text == "PING":
            pass  # Silently ignore

        else:
            log.debug("Unhandled message: %r", text)

    # ------------------------------------------------------------------
    # Broadcast helpers
    # ------------------------------------------------------------------

    def broadcast(self, message: str):
        """Send message string to all connected button units. Thread-safe."""
        data = message.encode("utf-8")
        dead = []
        with self.client_lock:
            for sock in self.clients:
                if not self._send_to_sock(sock, data):
                    dead.append(sock)
            for sock in dead:
                self.clients.remove(sock)
                try:
                    sock.close()
                except Exception:
                    pass

    def _send_to_sock(self, sock: socket.socket, data) -> bool:
        """Send bytes or str to a socket. Returns False if failed."""
        if isinstance(data, str):
            data = data.encode("utf-8")
        try:
            sock.sendall(data)
            return True
        except Exception as exc:
            log.warning("Send error: %s", exc)
            return False

    def broadcast_leds(self, target: str, r: int, g: int, b: int):
        """
        Broadcast LED command to all button units.
        target: A / B / C / D / X (all)
        r, g, b: each 0 or 10
        """
        self.broadcast(f"EMS-LEDS-{target}|{r}|{g}|{b}|\r\n")

    # ------------------------------------------------------------------
    # Game control
    # ------------------------------------------------------------------

    def send_ready(self):
        """Broadcast READY, fire ready_sent event, start colour sequence."""
        self.broadcast("READY\r\n")
        self.event_bus.put({"type": "ready_sent"})
        self._start_colour_sequence()

    def start_round(self):
        """Clear answers for a new question round."""
        with self._round_lock:
            self.round_answers.clear()
        self.correct_answer = None
        self.send_to_leaderboard("CLEAR_ANSWERS\n")
        log.info("Round started - answers cleared")

    def award_points(self, correct_pts: int, incorrect_pts: int) -> dict:
        """
        Award points based on correct_answer and round_answers.
        Returns {"correct": [table,...], "incorrect": [table,...]}.
        """
        if self.correct_answer is None:
            log.warning("award_points called but correct_answer is None")
            return {"correct": [], "incorrect": []}

        correct_tables = []
        incorrect_tables = []

        with self._round_lock:
            for table, info in self.round_answers.items():
                if info["answer"] == self.correct_answer:
                    correct_tables.append(table)
                else:
                    incorrect_tables.append(table)

        if correct_tables:
            tables_str = "*" + "*".join(str(t) for t in correct_tables)
            sign = "+" if correct_pts >= 0 else "-"
            msg = f"{tables_str}{sign}{abs(correct_pts)}\n"
            self.send_to_leaderboard(msg)
            log.info("Correct tables %s: %+d pts", correct_tables, correct_pts)

        if incorrect_tables:
            tables_str = "*" + "*".join(str(t) for t in incorrect_tables)
            sign = "+" if incorrect_pts >= 0 else "-"
            msg = f"{tables_str}{sign}{abs(incorrect_pts)}\n"
            self.send_to_leaderboard(msg)
            log.info("Incorrect tables %s: %+d pts", incorrect_tables, incorrect_pts)

        return {"correct": correct_tables, "incorrect": incorrect_tables}

    # ------------------------------------------------------------------
    # Leaderboard IPC
    # ------------------------------------------------------------------

    def _leaderboard_connector(self):
        """Persistently connect to leaderboard IPC server. Retries every 5s."""
        host = self.config["leaderboard_ipc"]["host"]
        port = self.config["leaderboard_ipc"]["port"]
        while True:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.connect((host, port))
                log.info("Connected to leaderboard IPC at %s:%d", host, port)
                with self.leaderboard_lock:
                    self.leaderboard_socket = sock
                # Block here until the connection dies (detect by empty recv)
                while True:
                    try:
                        data = sock.recv(64)
                        if not data:
                            break
                    except Exception:
                        break
                log.warning("Leaderboard IPC connection dropped, reconnecting...")
                with self.leaderboard_lock:
                    self.leaderboard_socket = None
                try:
                    sock.close()
                except Exception:
                    pass
            except Exception as exc:
                log.debug("Leaderboard IPC connect failed: %s", exc)
            time.sleep(5)

    def send_to_leaderboard(self, message: str):
        """Thread-safe send to leaderboard IPC socket."""
        if not message.endswith("\n"):
            message += "\n"
        with self.leaderboard_lock:
            sock = self.leaderboard_socket
        if sock is None:
            return
        try:
            sock.sendall(message.encode("utf-8"))
        except Exception as exc:
            log.warning("Leaderboard IPC send error: %s", exc)
            with self.leaderboard_lock:
                self.leaderboard_socket = None

    # ------------------------------------------------------------------
    # Colour sequence (RED -> GREEN -> BLUE -> OFF)
    # ------------------------------------------------------------------

    def _start_colour_sequence(self):
        """Start the post-READY LED colour sequence. Cancels any running sequence."""
        if self._colour_timer is not None:
            self._colour_timer.cancel()
        self.colour_sequence_active = True
        # Step 1: immediate RED all
        self.broadcast_leds("X", 10, 0, 0)
        self._colour_timer = threading.Timer(5.0, self._colour_step_green)
        self._colour_timer.daemon = True
        self._colour_timer.start()

    def _colour_step_green(self):
        self.broadcast("READY\r\n")
        self.broadcast_leds("X", 0, 10, 0)
        self._colour_timer = threading.Timer(10.0, self._colour_step_blue)
        self._colour_timer.daemon = True
        self._colour_timer.start()

    def _colour_step_blue(self):
        self.broadcast_leds("X", 0, 0, 10)
        self._colour_timer = threading.Timer(5.0, self._colour_step_off)
        self._colour_timer.daemon = True
        self._colour_timer.start()

    def _colour_step_off(self):
        self.broadcast_leds("X", 0, 0, 0)
        self.colour_sequence_active = False

    # ------------------------------------------------------------------
    # Dance lights
    # ------------------------------------------------------------------

    def start_dance(self):
        """Start random LED dance pattern."""
        self.dance_active = True
        self._dance_beat()

    def stop_dance(self):
        """Stop dance and turn all LEDs off."""
        self.dance_active = False
        if self._dance_timer is not None:
            self._dance_timer.cancel()
            self._dance_timer = None
        self.broadcast_leds("X", 0, 0, 0)

    def _dance_beat(self):
        if not self.dance_active:
            return

        pattern = random.randint(1, 5)
        rows = ["A", "B", "C", "D"]
        colours = [(10, 0, 0), (0, 10, 0), (0, 0, 10)]  # red, green, blue

        if pattern == 1:
            row = random.choice(rows)
            r, g, b = random.choice(colours)
            self.broadcast_leds(row, r, g, b)

        elif pattern == 2:
            r, g, b = random.choice(colours)
            self.broadcast_leds("X", r, g, b)

        elif pattern == 3:
            c1 = random.choice(colours)
            c2 = random.choice([c for c in colours if c != c1])
            self.broadcast_leds("A", *c1)
            self.broadcast_leds("C", *c1)
            self.broadcast_leds("B", *c2)
            self.broadcast_leds("D", *c2)

        elif pattern == 4:
            self.broadcast_leds("X", 0, 0, 0)

        else:  # pattern == 5
            for row in rows:
                choice = random.choice(colours + [(0, 0, 0)])
                self.broadcast_leds(row, *choice)

        interval = self.config["game"]["dance_lights_interval_ms"] / 1000.0
        self._dance_timer = threading.Timer(interval, self._dance_beat)
        self._dance_timer.daemon = True
        self._dance_timer.start()

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def client_count(self) -> int:
        """Return number of currently connected button units."""
        with self.client_lock:
            return len(self.clients)

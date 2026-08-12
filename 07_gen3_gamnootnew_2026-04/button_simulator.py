"""
Button Simulator — simulates physical gameshow button units connecting to bsd.py.
Each table appears as a panel with A/B/C/D answer buttons and an LED status display.
The simulator connects all tables as separate TCP clients to the game server.
"""
import socket
import threading
import tkinter as tk
from tkinter import ttk, messagebox
import time

SERVER_IP   = "127.0.0.1"
SERVER_PORT = 8080
NUM_TABLES  = 12

LED_COLORS = {
    "red":   "#e74c3c",
    "green": "#2ecc71",
    "blue":  "#3498db",
    "off":   "#2d2d2d",
}

ANSWER_COLORS = {
    "A": "#2ecc71",
    "B": "#3498db",
    "C": "#9b59b6",
    "D": "#e67e22",
}


class TableUnit:
    """One simulated button unit (one table)."""

    def __init__(self, table_id: int, frame: tk.Frame, log_fn):
        self.table_id  = table_id
        self.log       = log_fn
        self.sock      = None
        self.connected = False
        self.ready     = False
        self.leds      = {"A": "off", "B": "off", "C": "off", "D": "off"}
        self._build_ui(frame)

    def _build_ui(self, parent):
        self.frame = tk.LabelFrame(
            parent, text=f"Table {self.table_id}",
            bg="#1a1a1a", fg="#ffffff",
            font=("Segoe UI", 9, "bold"),
        )

        # Status / LED row
        top = tk.Frame(self.frame, bg="#1a1a1a")
        top.pack(fill=tk.X, padx=4, pady=(2, 0))

        self.conn_dot = tk.Canvas(top, width=12, height=12,
                                  bg="#1a1a1a", highlightthickness=0)
        self.conn_dot.create_oval(1, 1, 11, 11, fill="#555555", tags="dot")
        self.conn_dot.pack(side=tk.LEFT, padx=(0, 4))

        self.ready_lbl = tk.Label(top, text="—", width=5,
                                  bg="#1a1a1a", fg="#555555",
                                  font=("Segoe UI", 8))
        self.ready_lbl.pack(side=tk.RIGHT)

        # LED indicators
        led_row = tk.Frame(self.frame, bg="#1a1a1a")
        led_row.pack(fill=tk.X, padx=4, pady=1)
        self.led_labels = {}
        for ch in ("A", "B", "C", "D"):
            lbl = tk.Label(led_row, text=ch, width=3,
                           bg=LED_COLORS["off"], fg="#ffffff",
                           font=("Segoe UI", 8, "bold"), relief="flat")
            lbl.pack(side=tk.LEFT, padx=1)
            self.led_labels[ch] = lbl

        # Answer buttons
        btn_row = tk.Frame(self.frame, bg="#1a1a1a")
        btn_row.pack(fill=tk.X, padx=4, pady=(1, 4))
        for ch in ("A", "B", "C", "D"):
            btn = tk.Button(
                btn_row, text=ch, width=3,
                bg=ANSWER_COLORS[ch], fg="#ffffff",
                font=("Segoe UI", 9, "bold"),
                activebackground=ANSWER_COLORS[ch],
                relief="flat", bd=0,
                command=lambda c=ch: self.press(c),
            )
            btn.pack(side=tk.LEFT, padx=1)

    def connect(self, ip: str, port: int):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(3)
            self.sock.connect((ip, port))
            self.sock.settimeout(None)
            greeting = self.sock.recv(64).decode("utf-8", errors="replace").strip()
            if "Connected" not in greeting:
                raise ConnectionError(f"Unexpected greeting: {greeting}")
            self.connected = True
            self._set_dot("#2ecc71")
            threading.Thread(target=self._recv_loop, daemon=True).start()
            self.log(f"Table {self.table_id}: connected")
        except Exception as e:
            self.connected = False
            self._set_dot("#e74c3c")
            self.log(f"Table {self.table_id}: connect failed — {e}")

    def disconnect(self):
        self.connected = False
        self.ready     = False
        try:
            if self.sock:
                self.sock.close()
        except Exception:
            pass
        self.sock = None
        self._set_dot("#555555")
        self._set_ready(False)
        self.log(f"Table {self.table_id}: disconnected")

    def press(self, answer: str):
        if not self.connected:
            self.log(f"Table {self.table_id}: not connected — cannot send answer")
            return
        if not self.ready:
            self.log(f"Table {self.table_id}: not READY yet — buzzer locked")
            return
        msg = f"@{self.table_id}:{answer}\r\n"
        try:
            self.sock.sendall(msg.encode("utf-8"))
            self.ready = False
            self._set_ready(False)
            self.log(f"Table {self.table_id}: sent answer {answer}")
        except Exception as e:
            self.log(f"Table {self.table_id}: send error — {e}")
            self.disconnect()

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
                    self._handle_cmd(line.strip())
            except Exception:
                break
        self.connected = False
        self.frame.after(0, lambda: self._set_dot("#e74c3c"))

    def _handle_cmd(self, cmd: str):
        if not cmd:
            return
        if cmd.startswith("EMS-LEDS-"):
            # EMS-LEDS-A|10|0|0|  or  EMS-LEDS-X|...
            parts = cmd.split("|")
            if len(parts) < 4:
                return
            target = parts[0].split("-")[-1]   # A/B/C/D/X
            r, g, b = int(parts[1]), int(parts[2]), int(parts[3])
            color = "red" if r else "green" if g else "blue" if b else "off"
            channels = ["A", "B", "C", "D"] if target == "X" else [target]
            for ch in channels:
                if ch in self.led_labels:
                    self.leds[ch] = color
                    self.frame.after(0, lambda lbl=self.led_labels[ch], c=color:
                                     lbl.config(bg=LED_COLORS[c]))
        elif cmd == "READY":
            self.ready = True
            self.frame.after(0, lambda: self._set_ready(True))
        elif cmd == "DANCE-LIGHTS-START":
            self.log(f"Table {self.table_id}: dance lights ON")
        elif cmd == "DANCE-LIGHTS-STOP":
            self.log(f"Table {self.table_id}: dance lights OFF")

    def _set_dot(self, color: str):
        self.conn_dot.itemconfig("dot", fill=color)

    def _set_ready(self, ready: bool):
        if ready:
            self.ready_lbl.config(text="READY", fg="#2ecc71")
        else:
            self.ready_lbl.config(text="—", fg="#555555")


class ButtonSimulatorApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Button Simulator")
        self.root.configure(bg="#121212")
        self.tables: list[TableUnit] = []
        self._build_ui()

    def _build_ui(self):
        # ── Top bar ──────────────────────────────────────────────
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

        tk.Label(bar, text="Tables:", bg="#121212", fg="#e0e0e0",
                 font=("Segoe UI", 10)).pack(side=tk.LEFT, padx=(8, 0))
        self.num_var = tk.StringVar(value=str(NUM_TABLES))
        tk.Entry(bar, textvariable=self.num_var, width=4,
                 bg="#2d2d2d", fg="#e0e0e0", insertbackground="#e0e0e0",
                 relief="flat").pack(side=tk.LEFT, padx=4)

        self._btn(bar, "Connect All", "#27ae60", "#2ecc71",
                  self.connect_all).pack(side=tk.LEFT, padx=6)
        self._btn(bar, "Disconnect All", "#c0392b", "#e74c3c",
                  self.disconnect_all).pack(side=tk.LEFT)

        # ── Quick-answer row ──────────────────────────────────────
        qa = tk.Frame(self.root, bg="#121212")
        qa.pack(fill=tk.X, padx=10, pady=(0, 6))
        tk.Label(qa, text="All tables answer:", bg="#121212", fg="#aaaaaa",
                 font=("Segoe UI", 9)).pack(side=tk.LEFT)
        for ch in ("A", "B", "C", "D"):
            self._btn(qa, ch, ANSWER_COLORS[ch], ANSWER_COLORS[ch],
                      lambda c=ch: self._all_answer(c)
                      ).pack(side=tk.LEFT, padx=3)

        # ── Table grid ───────────────────────────────────────────
        self.grid_frame = tk.Frame(self.root, bg="#121212")
        self.grid_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=4)

        # ── Log area ─────────────────────────────────────────────
        log_frame = tk.LabelFrame(self.root, text="Log", bg="#121212",
                                  fg="#e0e0e0", font=("Segoe UI", 9, "bold"))
        log_frame.pack(fill=tk.X, padx=10, pady=(4, 8))
        self.log_text = tk.Text(log_frame, height=6, bg="#1a1a1a", fg="#cccccc",
                                font=("Consolas", 8), state="disabled")
        self.log_text.pack(fill=tk.X, padx=4, pady=4)
        self._btn(log_frame, "Clear", "#333333", "#444444",
                  lambda: (self.log_text.config(state="normal"),
                           self.log_text.delete("1.0", "end"),
                           self.log_text.config(state="disabled"))
                  ).pack(anchor="e", padx=4, pady=(0, 4))

        self._rebuild_grid()

    def _rebuild_grid(self):
        for w in self.grid_frame.winfo_children():
            w.destroy()
        self.tables.clear()
        try:
            n = int(self.num_var.get())
        except ValueError:
            n = NUM_TABLES
        cols = 4
        for i in range(n):
            t = TableUnit(i + 1, self.grid_frame, self.log)
            t.frame.grid(row=i // cols, column=i % cols,
                         padx=4, pady=4, sticky="nsew")
            self.grid_frame.columnconfigure(i % cols, weight=1)
            self.tables.append(t)

    def connect_all(self):
        self._rebuild_grid()
        ip   = self.ip_var.get().strip()
        port = int(self.port_var.get().strip())
        for t in self.tables:
            threading.Thread(target=t.connect, args=(ip, port), daemon=True).start()
            time.sleep(0.05)

    def disconnect_all(self):
        for t in self.tables:
            threading.Thread(target=t.disconnect, daemon=True).start()

    def _all_answer(self, answer: str):
        for t in self.tables:
            t.press(answer)

    def log(self, msg: str):
        def _do():
            self.log_text.config(state="normal")
            self.log_text.insert("end", msg + "\n")
            self.log_text.see("end")
            self.log_text.config(state="disabled")
        self.root.after(0, _do)

    @staticmethod
    def _btn(parent, text, color, hover, cmd):
        b = tk.Button(parent, text=text, bg=color, fg="#ffffff",
                      font=("Segoe UI", 9, "bold"),
                      activebackground=hover, relief="flat", bd=0,
                      padx=8, pady=3, command=cmd)
        b.bind("<Enter>", lambda _: b.config(bg=hover))
        b.bind("<Leave>", lambda _: b.config(bg=color))
        return b


if __name__ == "__main__":
    root = tk.Tk()
    app  = ButtonSimulatorApp(root)
    root.mainloop()

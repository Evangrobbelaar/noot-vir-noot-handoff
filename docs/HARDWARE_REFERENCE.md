# Janus Button Unit — Hardware Reference for Claude Code Sessions

Attach this document to any new Claude Code session when building software for this
hardware system. It describes exactly how the physical button units communicate,
what messages they send and expect, and how to set up the PC network to reach them.

---

## What is the Hardware?

Each "table unit" is an **ESP32 microcontroller** with a companion sub-board.
The sub-board has **4 physical press buttons** labelled A, B, C, D and **4 LED
indicators** (also labelled A, B, C, D). The ESP32 connects to your PC over a
**local WiFi router** via a persistent **TCP socket**.

Up to **12 units** can be in use simultaneously, each identified by a unique
**Serial Number (1–12)** stored in the unit's flash memory.

---

## Physical Hardware Details

| Component | ESP32 Pin | Description |
|-----------|-----------|-------------|
| `LED_HB` | GPIO 16 | Heartbeat LED — blinks every second |
| `LED_A` | GPIO 33 | Indicator LED for button A |
| `LED_B` | GPIO 25 | Indicator LED for button B |
| `LED_C` | GPIO 26 | Indicator LED for button C |
| `LED_D` | GPIO 27 | Indicator LED for button D |
| `LED_MAIN` | GPIO 12 | Main status LED — ON when connected to server |
| `LED_BACK_LIGHT` | GPIO 4 | Screen backlight |
| `TOUCH_IRQ` | GPIO 5 | Touch screen interrupt |
| `ACTIVATE_BLUETOOTH` | GPIO 35 | Held LOW to enter Bluetooth config mode |
| `USART_1_RXD` | GPIO 14 | Serial receive from sub-board |
| `USART_1_TXD` | GPIO 13 | Serial transmit to sub-board |

**Sub-board baud rate:** 9600, 8N1

The **sub-board** detects physical button presses and sends messages to the
ESP32 over USART_1 (hardware serial). The ESP32 then forwards them to the server
over TCP. All LED colour commands from the server travel the same path in
reverse: server → TCP → ESP32 → USART_1 → sub-board → LEDs.

---

## Button Press Flow (complete path)

```
Player presses button
        ↓
Sub-board detects press, sends USART_1 message to ESP32:
    ç|EMS|<Key>|<Button>|<Counter>|
    (ç = byte 0xE7 = 231, Key = sub-board key field, Button = A/B/C/D)

        ↓
ESP32 receives from sub-board, checks byte[6] to control its own LEDs:
    - If byte[6] == 'A' → turn LED_A ON
    - If byte[6] == 'B' → turn LED_B ON
    - If byte[6] == 'C' → turn LED_C ON
    - If byte[6] == 'D' → turn LED_D ON

        ↓
ESP32 builds TCP message and sends to server:
    ç|EMS|<SerialNo>|<Button>|<Counter>|<CR><LF>

        ↓
Server receives, parses, handles in software
```

---

## TCP Protocol — EXACT Message Formats

**All TCP messages are terminated with `\r\n` (CRLF).
This is fixed in firmware and cannot be changed.**

### Unit → Server (button press)

```
<0xE7>|EMS|<SerialNo>|<Button>|<Counter>|\r\n
```

| Field | Type | Example | Notes |
|-------|------|---------|-------|
| `0xE7` | byte | `ç` | Byte value 231. Always the first byte. |
| `EMS` | literal | `EMS` | Fixed identifier string |
| `SerialNo` | integer | `5` | Table number 1–12, set at unit config time |
| `Button` | char | `A` | One of: `A` `B` `C` `D` (uppercase) |
| `Counter` | integer | `1229` | Incrementing counter from sub-board, resets at power cycle |

**Full example received bytes:**
```
\xe7|EMS|5|B|1229|\r\n
```

**How to parse it in Python:**
```python
HARDWARE_MSG_BYTE = 0xE7

def parse_button_message(raw: bytes) -> dict | None:
    """raw is the message bytes WITHOUT the trailing \r\n."""
    if not raw or raw[0] != HARDWARE_MSG_BYTE:
        return None
    text = raw.decode("utf-8", errors="replace")
    parts = text.split("|")
    # parts: ['ç', 'EMS', '5', 'B', '1229', '']
    if len(parts) < 5 or parts[1] != "EMS":
        return None
    return {
        "table":   int(parts[2]),
        "button":  parts[3].strip().upper(),   # 'A', 'B', 'C', or 'D'
        "counter": int(parts[4]) if parts[4].strip().isdigit() else 0,
    }
```

---

### Server → Unit (all commands)

All commands the server sends are forwarded raw through the ESP32 to the
sub-board via USART_1. The ESP32 also checks for the substring `"READY"` in
any incoming message and if found turns all four indicator LEDs off.

| Command | Format | Effect on unit |
|---------|--------|---------------|
| **Greeting** | `Connected\r\n` | Must be sent immediately on TCP connect. Tells unit server is ready. |
| **Ready** | `READY\r\n` | Turns OFF all four indicator LEDs (A, B, C, D). Sub-board also receives it. |
| **LED colour** | `EMS-LEDS-<Target>\|<R>\|<G>\|<B>\|\r\n` | Sets LED row colour on sub-board. See LED section below. |
| **Correct answer** | `awns_<Letter>\r\n` | Broadcasts correct answer. Forwarded to sub-board (e.g. `awns_A`). |

**Critical:** The unit reads server messages using `client.readStringUntil('\n')`,
so it reads until `\n`. The `\r` before it is included in the string but harmless.
Always send `\r\n` terminated messages.

---

## LED Colour Control

LED commands control the physical **colour LEDs on the sub-board** (not the
ESP32 on-board indicator LEDs). The sub-board supports RGB colour mixing.

**Format:**
```
EMS-LEDS-<Target>|<R>|<G>|<B>|\r\n
```

| Field | Values | Notes |
|-------|--------|-------|
| `Target` | `A` `B` `C` `D` `X` | Row A/B/C/D individually, or `X` for ALL rows at once |
| `R` | `0` or `10` | Red channel — 0 = off, 10 = full on |
| `G` | `0` or `10` | Green channel — 0 = off, 10 = full on |
| `B` | `0` or `10` | Blue channel — 0 = off, 10 = full on |

**Only one colour channel should be non-zero at a time** (the sub-board
interprets these as discrete colour states, not mixed RGB).

**Examples:**
```
EMS-LEDS-X|10|0|0|\r\n    →  ALL rows RED
EMS-LEDS-A|0|10|0|\r\n    →  Row A only GREEN
EMS-LEDS-B|0|0|10|\r\n    →  Row B only BLUE
EMS-LEDS-X|0|0|0|\r\n     →  ALL rows OFF
```

**Python helper:**
```python
def led_command(target: str, r: int, g: int, b: int) -> bytes:
    """target: 'A','B','C','D', or 'X' for all. r/g/b: 0 or 10."""
    return f"EMS-LEDS-{target}|{r}|{g}|{b}|\r\n".encode("utf-8")
```

---

## TCP Connection Management

### On Connect
The server **must** send `Connected\r\n` immediately after accepting the TCP
connection. The unit does not send any button presses until after this greeting.

```python
def on_new_connection(conn: socket.socket):
    conn.sendall(b"Connected\r\n")
```

### Buffering and Splitting
The unit sends one message per button press. Messages are `\r\n` terminated.
Buffer incoming bytes and split on `\r\n`:

```python
buf = b""
while True:
    data = conn.recv(256)
    if not data:
        break
    buf += data
    while b"\r\n" in buf:
        line, buf = buf.split(b"\r\n", 1)
        if line:
            handle_message(line)   # line has NO trailing \r\n
```

### Reconnection
The unit **automatically reconnects** if the TCP connection drops. Your server
must always be listening and must send `Connected\r\n` on each new connection.
Each reconnect is a fresh TCP connection — there is no session state on the unit.

### Port
Default port: **8080** (configurable per unit via Bluetooth).

---

## Unit Configuration (Bluetooth)

Units are configured via Bluetooth serial before a session. Use any Bluetooth
terminal app (e.g. "Serial Bluetooth Terminal" on Android).

**Bluetooth device name:** `ESP32-Config`

**Commands:**
```
SSID:your_router_name          → Set WiFi network name
PASS:your_wifi_password        → Set WiFi password
SERVER:192.168.x.x             → Set PC IP address on the router's network
PORT:8080                      → Set TCP port (default 8080)
SN:1                           → Set this unit's table number (1–12)
STATUS                         → Show current saved config
SAVE                           → Save to flash and restart unit
RESET                          → Clear all config and restart
HELP                           → Show command list
```

To enter Bluetooth config mode at any time: **hold the ACTIVATE_BLUETOOTH
button (GPIO 35) LOW** while the unit is running. It will restart and advertise
as `ESP32-Config`.

---

## Network Setup — PC Side

The PC must be on the **same local network** as the router the button units
connect to. This often means switching the PC's WiFi adapter from your normal
home/office DHCP network to a static IP on the gameshow router's subnet.

**The script `set_network.py` in the project folder handles this automatically.**

Run it as Administrator:
```
python set_network.py
```

First-time setup:
1. Select your WiFi adapter from the dropdown
2. Enter the **static IP** you want to assign to the PC (e.g. `192.168.4.100`)
3. Enter the **subnet mask** (e.g. `255.255.255.0`)
4. Enter the **gateway** (the router's IP, e.g. `192.168.4.1`)
5. Enter a **DNS** (e.g. `8.8.8.8`)
6. Click **Save Settings** — these are stored in `network_profile.json`

Every session:
- Click **Switch to GAMESHOW** → applies static IP, PC joins the button unit network
- Click **Restore NORMAL (DHCP)** → reverts to your normal internet connection

Under the hood, `set_network.py` runs:
```
netsh interface ip set address "Wi-Fi" static 192.168.4.100 255.255.255.0 192.168.4.1
netsh interface ip set dns "Wi-Fi" static 8.8.8.8
```
and to restore:
```
netsh interface ip set address "Wi-Fi" dhcp
netsh interface ip set dns "Wi-Fi" dhcp
```

**After switching to GAMESHOW**, verify the PC has joined the router's network
before starting the server. The units will then connect automatically.

---

## Naming Conventions

| Name | Meaning |
|------|---------|
| `SerialNo` | The table number (integer, 1–12). Set per unit in Bluetooth config. |
| `table` | Same as SerialNo — used in server-side code. |
| `button` | The letter pressed: `'A'`, `'B'`, `'C'`, or `'D'` (always uppercase string). |
| `counter` | An incrementing integer from the sub-board. Monotonically increasing per unit per power cycle. Useful for deduplication and ordering. |
| `0xE7` / `231` / `ç` | The magic first byte that identifies a hardware button message. Always check `raw[0] == 0xE7`. |
| `EMS` | The fixed protocol identifier string in every button message. |
| `target` | Which LED row(s) to control: `'A'`, `'B'`, `'C'`, `'D'`, or `'X'` (all). |
| `USART_1` | The ESP32 serial port connected to the sub-board (GPIO 13/14). |
| `client` | The Arduino `WiFiClient` object — the TCP connection to the server. |
| `config.SerialNo` | The unit's table number stored in ESP32 flash via `Preferences`. |

---

## Minimal Python Server Template

This is the smallest correct server that these units can connect to:

```python
import socket
import threading

HARDWARE_MSG_BYTE = 0xE7
HOST = "0.0.0.0"
PORT = 8080


def handle_client(conn: socket.socket, addr):
    print(f"Unit connected from {addr}")
    conn.sendall(b"Connected\r\n")   # ← required greeting

    buf = b""
    while True:
        try:
            data = conn.recv(256)
            if not data:
                break
            buf += data
            while b"\r\n" in buf:
                line, buf = buf.split(b"\r\n", 1)
                if line and line[0] == HARDWARE_MSG_BYTE:
                    text = line.decode("utf-8", errors="replace")
                    parts = text.split("|")
                    if len(parts) >= 5 and parts[1] == "EMS":
                        table   = int(parts[2])
                        button  = parts[3].strip().upper()
                        counter = int(parts[4]) if parts[4].strip().isdigit() else 0
                        on_button_press(conn, table, button, counter)
        except Exception as e:
            print(f"Client error: {e}")
            break
    conn.close()
    print(f"Unit {addr} disconnected")


def on_button_press(conn: socket.socket, table: int, button: str, counter: int):
    """Called when a button is pressed. table=1-12, button='A'/'B'/'C'/'D'."""
    print(f"Table {table} pressed {button} (counter={counter})")
    # Your game logic here


def broadcast(clients: list, message: str):
    """Send a message to all connected units."""
    data = message.encode("utf-8")
    dead = []
    for c in clients:
        try:
            c.sendall(data)
        except Exception:
            dead.append(c)
    for c in dead:
        clients.remove(c)


if __name__ == "__main__":
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, PORT))
    server.listen(20)
    print(f"Listening on {HOST}:{PORT}")
    clients = []
    while True:
        conn, addr = server.accept()
        clients.append(conn)
        threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()
```

---

## Common Mistakes to Avoid

1. **Do not skip the `Connected\r\n` greeting.** The unit will not send button
   presses until it receives it. Connection will appear to work but no messages
   will arrive.

2. **Always check `raw[0] == 0xE7` before parsing.** The unit can send garbage
   during startup. This byte is your only reliable message boundary marker.

3. **Do not split on `\n` alone.** Always split on `\r\n`. The firmware sends
   `\r\n` and the bytes are distinct — splitting on `\n` only can leave `\r`
   characters in your parsed strings.

4. **LED values are 0 or 10 — not 0 or 1, not 0 or 255.** The sub-board
   expects exactly these values. `EMS-LEDS-X|1|0|0|` will not work; use `10`.

5. **The unit auto-reconnects — your server's accept loop must never stop.**
   Run it in a daemon thread and keep it alive for the entire session.

6. **`SerialNo` is the table number.** Do not confuse it with a MAC address
   or hardware serial number. It is a user-assigned integer (1–12).

7. **The PC must be on the router's subnet before starting the server.** Run
   `set_network.py → Switch to GAMESHOW` first, verify ping to the router,
   then start the server.

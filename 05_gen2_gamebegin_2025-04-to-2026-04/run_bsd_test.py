"""
run_bsd_test.py
===============
Launches bsd.py with --autostart, waits for port 8080 to open,
then runs bsd_simulator.py — all hands-free.

Usage:
  python run_bsd_test.py
"""

import os
import sys
import socket
import subprocess
import threading
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BSD_PATH   = os.path.join(SCRIPT_DIR, "bsd.py")

HOST       = "127.0.0.1"
PORT       = 8080
PORT_WAIT  = 15   # seconds to wait for port 8080 to open


def port_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=1):
            return True
    except OSError:
        return False


def main() -> None:
    # ── 1. Launch bsd.py with auto-start flag ─────────────────────────────────
    print("[LAUNCHER] Starting bsd.py --autostart ...")
    bsd_proc = subprocess.Popen(
        [sys.executable, BSD_PATH, "--autostart"],
        cwd=SCRIPT_DIR,
    )

    # ── 2. Wait for port 8080 to open ─────────────────────────────────────────
    print(f"[LAUNCHER] Waiting for port {PORT} (up to {PORT_WAIT}s) ...")
    deadline = time.time() + PORT_WAIT
    while time.time() < deadline:
        if port_open(HOST, PORT):
            break
        time.sleep(0.3)

    if not port_open(HOST, PORT):
        print(f"[LAUNCHER] FAIL — port {PORT} never opened.")
        bsd_proc.terminate()
        sys.exit(1)

    print(f"[LAUNCHER] Port {PORT} is open. Running tests ...\n")
    print("=" * 60)

    # ── 3. Run the simulator in-process ───────────────────────────────────────
    sys.path.insert(0, SCRIPT_DIR)
    import bsd_simulator

    pipe_thread = threading.Thread(target=bsd_simulator.run_pipe_server, daemon=True)
    pipe_thread.start()

    bsd_simulator.run_tests()

    # ── 4. Teardown ───────────────────────────────────────────────────────────
    print("=" * 60)
    print("[LAUNCHER] Tests done. Closing bsd.py ...")
    bsd_proc.terminate()
    try:
        bsd_proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        bsd_proc.kill()
    print("[LAUNCHER] Done.")


if __name__ == "__main__":
    main()

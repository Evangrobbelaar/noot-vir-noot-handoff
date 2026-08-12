"""
run_gameshow2_test.py — one-shot launcher for gameshow2 regression tests

No manual steps: just run this file.
gameshow2.py is NOT started as a subprocess; tests mock all dependencies
(vlc, tkinter, pynput) and exercise the logic directly.
"""

import subprocess
import sys
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SIM_PATH   = os.path.join(SCRIPT_DIR, "gameshow2_simulator.py")

result = subprocess.run(
    [sys.executable, SIM_PATH],
    cwd=SCRIPT_DIR,
)
sys.exit(result.returncode)

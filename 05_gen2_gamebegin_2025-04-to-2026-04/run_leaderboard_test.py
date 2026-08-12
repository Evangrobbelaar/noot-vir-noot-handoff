"""
run_leaderboard_test.py — one-shot launcher for leaderboard regression tests

No manual steps: just run this file and the tests execute automatically.
leaderboard.py is NOT started as a subprocess because the tests mock pygame
and exercise process_command() directly — no display needed.
"""

import subprocess
import sys
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SIM_PATH = os.path.join(SCRIPT_DIR, "leaderboard_simulator.py")

result = subprocess.run(
    [sys.executable, SIM_PATH],
    cwd=SCRIPT_DIR,
)
sys.exit(result.returncode)

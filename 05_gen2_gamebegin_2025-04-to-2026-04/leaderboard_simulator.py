"""
leaderboard_simulator.py — regression tests for leaderboard.py

Tests all pipe command formats that bsd.py sends to leaderboard.py.
Mocks pygame so no display or window is needed.  Imports GameshowLeaderboard
directly and exercises process_command() against every supported format.
"""

import sys
import os
from unittest.mock import MagicMock, patch

sys.stdout.reconfigure(encoding="utf-8")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

# ---------------------------------------------------------------------------
# Mock pygame before importing leaderboard (no display required)
# ---------------------------------------------------------------------------
_pygame = MagicMock()
_pygame.font.Font.return_value = MagicMock()
_pygame.display.Info.return_value = MagicMock(current_w=1920, current_h=1080)
_pygame.display.set_mode.return_value = MagicMock()

# Patch pygame in sys.modules and suppress the background pipe thread
with patch.dict("sys.modules", {"pygame": _pygame}):
    import leaderboard as _lb

# Create board instance without launching the real pipe server
with patch.object(_lb.GameshowLeaderboard, "start_pipe_server"):
    board = _lb.GameshowLeaderboard()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
PASS_COUNT = 0
FAIL_COUNT = 0


def check(label: str, condition: bool) -> None:
    global PASS_COUNT, FAIL_COUNT
    if condition:
        PASS_COUNT += 1
        print(f"  [PASS] {label}")
    else:
        FAIL_COUNT += 1
        print(f"  [FAIL] {label}")


def reset_board() -> None:
    """Return all tables to zero score / no answer."""
    for table in board.tables:
        table.score = 0
        table.last_answer = None
        table.previous_position = -1
        table.current_position = -1
        table.position_change = _lb.PositionChange.SAME


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------

def test_score_add_single_table():
    print("\n[1] Score addition — single table (*1+100)")
    reset_board()
    board.process_command("*1+100")
    check("Table 1 score == 100", board.tables[0].score == 100)
    check("Table 2 score unchanged (0)", board.tables[1].score == 0)


def test_score_add_multiple_tables():
    print("\n[2] Score addition — multiple tables (*1*2*3+200)")
    reset_board()
    board.process_command("*1*2*3+200")
    check("Table 1 score == 200", board.tables[0].score == 200)
    check("Table 2 score == 200", board.tables[1].score == 200)
    check("Table 3 score == 200", board.tables[2].score == 200)
    check("Table 4 score unchanged (0)", board.tables[3].score == 0)


def test_score_subtract():
    print("\n[3] Score subtraction (*1-50)")
    reset_board()
    board.tables[0].score = 200
    board.process_command("*1-50")
    check("Table 1 score == 150 after -50", board.tables[0].score == 150)


def test_single_answer():
    print("\n[4] Single answer update (@3:B)")
    reset_board()
    board.process_command("@3:B")
    check("Table 3 last_answer == 'B'", board.tables[2].last_answer == "B")
    check("Table 1 last_answer still None", board.tables[0].last_answer is None)


def test_single_answer_uppercase_normalization():
    print("\n[5] Answer letter normalised to uppercase (@2:a -> 'A')")
    reset_board()
    board.process_command("@2:a")
    check("Table 2 last_answer == 'A'", board.tables[1].last_answer == "A")


def test_single_answer_all_letters():
    print("\n[6] All valid answer letters (A, B, C, D)")
    reset_board()
    for idx, letter in enumerate(["A", "B", "C", "D"], start=1):
        board.process_command(f"@{idx}:{letter}")
    check("Table 1 answer == 'A'", board.tables[0].last_answer == "A")
    check("Table 2 answer == 'B'", board.tables[1].last_answer == "B")
    check("Table 3 answer == 'C'", board.tables[2].last_answer == "C")
    check("Table 4 answer == 'D'", board.tables[3].last_answer == "D")


def test_invalid_answer_letter_ignored():
    print("\n[7] Invalid answer letter ignored (@1:Z leaves existing answer)")
    reset_board()
    board.tables[0].last_answer = "A"
    board.process_command("@1:Z")
    check("Table 1 answer unchanged ('A')", board.tables[0].last_answer == "A")


def test_multiple_answers_command():
    print("\n[8] Multiple answers (ANSWERS:1:A,2:B,3:C,4:D)")
    reset_board()
    board.process_command("ANSWERS:1:A,2:B,3:C,4:D")
    check("Table 1 answer == 'A'", board.tables[0].last_answer == "A")
    check("Table 2 answer == 'B'", board.tables[1].last_answer == "B")
    check("Table 3 answer == 'C'", board.tables[2].last_answer == "C")
    check("Table 4 answer == 'D'", board.tables[3].last_answer == "D")
    check("Table 5 answer still None", board.tables[4].last_answer is None)


def test_multiple_answers_resets_stale():
    print("\n[9] ANSWERS: clears previous answers not in new batch")
    reset_board()
    board.tables[5].last_answer = "C"   # Table 6 had an old answer
    board.process_command("ANSWERS:1:B")
    check("Table 6 old answer cleared", board.tables[5].last_answer is None)
    check("Table 1 new answer == 'B'",  board.tables[0].last_answer == "B")


def test_position_tracking_after_score():
    print("\n[10] Position tracking after score update")
    reset_board()
    board.update_scores([1], 500)
    check("Table 1 is rank 0 (first place)", board.tables[0].current_position == 0)


def test_cumulative_scores():
    print("\n[11] Cumulative score updates")
    reset_board()
    board.process_command("*1+100")
    board.process_command("*1+100")
    board.process_command("*2+300")
    check("Table 1 cumulative == 200", board.tables[0].score == 200)
    check("Table 2 cumulative == 300", board.tables[1].score == 300)


def test_invalid_commands_no_crash():
    print("\n[12] Garbage input does not crash process_command")
    reset_board()
    try:
        board.process_command("GARBAGE_XYZ")
        board.process_command("")
        board.process_command("*notanumber+100")
        check("No exception raised for invalid input", True)
    except Exception as exc:
        check(f"No exception raised (got: {exc})", False)


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def run_tests() -> bool:
    print("=" * 60)
    print("leaderboard.py  pipe command regression tests")
    print("=" * 60)

    test_score_add_single_table()
    test_score_add_multiple_tables()
    test_score_subtract()
    test_single_answer()
    test_single_answer_uppercase_normalization()
    test_single_answer_all_letters()
    test_invalid_answer_letter_ignored()
    test_multiple_answers_command()
    test_multiple_answers_resets_stale()
    test_position_tracking_after_score()
    test_cumulative_scores()
    test_invalid_commands_no_crash()

    total = PASS_COUNT + FAIL_COUNT
    print("\n" + "=" * 60)
    print(f"Results: {PASS_COUNT}/{total} passed")
    if FAIL_COUNT:
        print(f"FAILED:  {FAIL_COUNT}")
        return False
    print("All tests passed!")
    return True


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)

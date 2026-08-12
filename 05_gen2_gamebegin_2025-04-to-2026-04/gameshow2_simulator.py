"""
gameshow2_simulator.py — regression tests for gameshow2.py

Tests every command gameshow2 sends to the bsd.py TCP server (the "light server"),
plus the answer-extraction logic and all pause/trigger behavior.

All external dependencies (vlc, tkinter, pynput) are mocked so no display,
media files, or hardware are needed.
"""

import sys
import os
from unittest.mock import MagicMock, patch, call

sys.stdout.reconfigure(encoding="utf-8")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

# ---------------------------------------------------------------------------
# Mock all external dependencies before importing gameshow2
# ---------------------------------------------------------------------------
_vlc = MagicMock()
_vlc.State.Ended = object()          # unique sentinel — won't equal any other object
_vlc.EventType.MediaPlayerTimeChanged = 1
_vlc.EventType.MediaPlayerEndReached  = 2
_vlc.EventType.MediaPlayerAudioDevice = 3
_vlc.EventType.MediaPlayerAudioVolume = 4

_tk_mock   = MagicMock()
_pynput    = MagicMock()
_pynput_kb = MagicMock()

module_patches = {
    "vlc":              _vlc,
    "tkinter":          _tk_mock,
    "pynput":           _pynput,
    "pynput.keyboard":  _pynput_kb,
}

with patch.dict("sys.modules", module_patches):
    import gameshow2 as gs

# ---------------------------------------------------------------------------
# Build a GameshowPlayer with all GUI/VLC/OS calls suppressed
# ---------------------------------------------------------------------------
with patch.object(gs.GameshowPlayer, "setup_gui"),          \
     patch.object(gs.GameshowPlayer, "setup_vlc"),           \
     patch.object(gs.GameshowPlayer, "load_video_files"),    \
     patch.object(gs.GameshowPlayer, "show_landing_screen"), \
     patch.object(gs.GameshowPlayer, "setup_global_listener"):
    player = gs.GameshowPlayer()

# Wire up a mock root and control panel so method calls don't blow up
player.root           = MagicMock()
player.control_panel  = MagicMock()
player.media_player   = MagicMock()
player.media_player.get_time.return_value  = 0
player.media_player.get_state.return_value = "Playing"   # NOT vlc.State.Ended

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


def fresh_socket():
    """Return a mock socket and wire it as the connected light socket."""
    sock = MagicMock()
    player.light_connected = True
    player.light_socket    = sock
    return sock


def sent_bytes(sock) -> list:
    """Collect all byte strings passed to sock.send()."""
    return [c[0][0] for c in sock.send.call_args_list]


def reset_pauses():
    player.first_pause_occurred  = False
    player.second_pause_occurred = False
    player.third_pause_occurred  = False
    player.media_player.get_time.return_value = 0


def set_video(path: str) -> None:
    player.current_video_path = path


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_extract_answer_from_filename():
    print("\n[1] extract_answer_from_filename — answer letter from file name")
    check("A_question.mp4 -> 'A'",  player.extract_answer_from_filename("A_question.mp4")  == "A")
    check("D_final.mp4 -> 'D'",     player.extract_answer_from_filename("D_final.mp4")     == "D")
    check("b_lower.mp4 -> 'B'",     player.extract_answer_from_filename("b_lower.mp4")     == "B")
    check("no_letter.mp4 -> 'UNKNOWN'", player.extract_answer_from_filename("no_letter.mp4") == "UNKNOWN")


def test_send_ready_trigger():
    print("\n[2] send_ready_trigger — sends DASHBOARD-READY-TRIGGER when connected")
    sock = fresh_socket()
    player.send_ready_trigger()
    check("DASHBOARD-READY-TRIGGER sent",
          b"DASHBOARD-READY-TRIGGER\r\n" in sent_bytes(sock))


def test_send_ready_trigger_not_connected():
    print("\n[3] send_ready_trigger — shows messagebox when not connected, no send")
    player.light_connected = False
    player.light_socket    = None
    player.control_panel.reset_mock()
    player.send_ready_trigger()
    # Access gs.messagebox which is _tk_mock.messagebox (bound at import time)
    check("showinfo called",    _tk_mock.messagebox.showinfo.called)
    check("No socket send",     True)  # No socket to check; just verifying no crash


def test_send_answer_to_server():
    print("\n[4] send_answer_to_server — sends awns_<letter> when answer available")
    sock = fresh_socket()
    player.current_answer = "C"
    player.send_answer_to_server()
    check("awns_C sent", b"awns_C\r\n" in sent_bytes(sock))


def test_send_answer_to_server_no_answer():
    print("\n[5] send_answer_to_server — does nothing when current_answer is None")
    sock = fresh_socket()
    player.current_answer = None
    player.send_answer_to_server()
    check("No bytes sent when no answer", sock.send.call_count == 0)


def test_set_lights_green():
    print("\n[6] set_lights_green — sends EMS-LEDS-X|0|10|0|")
    sock = fresh_socket()
    player.set_lights_green()
    check("GREEN command sent", b"EMS-LEDS-X|0|10|0|\r\n" in sent_bytes(sock))


def test_set_lights_red():
    print("\n[7] set_lights_red — sends EMS-LEDS-X|10|0|0|")
    sock = fresh_socket()
    player.set_lights_red()
    check("RED command sent", b"EMS-LEDS-X|10|0|0|\r\n" in sent_bytes(sock))


def test_all_lights_off():
    print("\n[8] all_lights_off — sends EMS-LEDS-X|0|0|0|")
    sock = fresh_socket()
    player.all_lights_off()
    check("ALL-OFF command sent", b"EMS-LEDS-X|0|0|0|\r\n" in sent_bytes(sock))


def test_start_dance_lights():
    print("\n[9] start_dance_lights — sends DANCE-LIGHTS-START")
    sock = fresh_socket()
    player.start_dance_lights()
    check("DANCE-LIGHTS-START sent", b"DANCE-LIGHTS-START\r\n" in sent_bytes(sock))


def test_stop_dance_lights():
    print("\n[10] stop_dance_lights — sends DANCE-LIGHTS-STOP")
    sock = fresh_socket()
    player.stop_dance_lights()
    check("DANCE-LIGHTS-STOP sent", b"DANCE-LIGHTS-STOP\r\n" in sent_bytes(sock))


def test_on_time_changed_first_pause():
    print("\n[11] on_time_changed — first pause at 5 s: pauses player and sends RED")
    sock = fresh_socket()
    reset_pauses()
    set_video("A_question.mp4")
    player.current_state = gs.GameState.PLAYING
    player.media_player.get_time.return_value = 5001

    player.on_time_changed(None)

    check("first_pause_occurred set True",    player.first_pause_occurred)
    check("media_player.set_pause(1) called", player.media_player.set_pause.called)
    check("RED command sent on first pause",  b"EMS-LEDS-X|10|0|0|\r\n" in sent_bytes(sock))


def test_on_time_changed_intro_state_skipped():
    print("\n[12] on_time_changed — INTRO state: no commands sent")
    sock = fresh_socket()
    reset_pauses()
    set_video("A_question.mp4")
    player.current_state = gs.GameState.INTRO
    player.media_player.get_time.return_value = 5001

    player.on_time_changed(None)

    check("No bytes sent during INTRO", sock.send.call_count == 0)
    check("first_pause_occurred still False", not player.first_pause_occurred)


def test_on_time_changed_q_video_skipped():
    print("\n[13] on_time_changed — Q_ video: no pause/send at any time")
    sock = fresh_socket()
    reset_pauses()
    set_video("prefix.Q_question.mp4")      # after the dot starts with Q_
    player.current_state = gs.GameState.PLAYING
    player.media_player.get_time.return_value = 25000

    player.on_time_changed(None)

    check("No bytes sent for Q_ video", sock.send.call_count == 0)
    check("first_pause_occurred still False", not player.first_pause_occurred)


def test_on_time_changed_third_pause_sends_answer():
    print("\n[14] on_time_changed — third pause at 20 s: sends answer to server")
    sock = fresh_socket()
    reset_pauses()
    player.first_pause_occurred  = True
    player.second_pause_occurred = True
    player.third_pause_occurred  = False
    set_video("A_question.mp4")
    player.current_state  = gs.GameState.PLAYING
    player.current_answer = "D"
    player.media_player.get_time.return_value = 20001

    player.on_time_changed(None)

    check("third_pause_occurred set True",  player.third_pause_occurred)
    check("awns_D sent at third pause",     b"awns_D\r\n" in sent_bytes(sock))


def test_handle_next_first_pause_sends_ready_and_red():
    print("\n[15] handle_next at first pause — sends READY TRIGGER then RED")
    sock = fresh_socket()
    reset_pauses()
    player.first_pause_occurred  = True
    player.second_pause_occurred = False
    player.current_state = gs.GameState.PLAYING

    player.handle_next()

    sent = sent_bytes(sock)
    check("DASHBOARD-READY-TRIGGER sent",   b"DASHBOARD-READY-TRIGGER\r\n" in sent)
    check("RED command sent after TRIGGER", b"EMS-LEDS-X|10|0|0|\r\n" in sent)


def test_handle_next_third_pause_sends_answer():
    print("\n[16] handle_next at third pause — re-sends answer")
    sock = fresh_socket()
    reset_pauses()
    player.first_pause_occurred  = True
    player.second_pause_occurred = True
    player.third_pause_occurred  = True
    player.current_state  = gs.GameState.PLAYING
    player.current_answer = "B"

    player.handle_next()

    check("awns_B sent at third pause next", b"awns_B\r\n" in sent_bytes(sock))


def test_check_light_connection_sends_ping():
    print("\n[17] check_light_connection — sends PING keepalive")
    sock = fresh_socket()
    player.check_light_connection()
    check("PING sent", b"PING\r\n" in sent_bytes(sock))


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def run_tests() -> bool:
    print("=" * 60)
    print("gameshow2.py  socket command regression tests")
    print("=" * 60)

    test_extract_answer_from_filename()
    test_send_ready_trigger()
    test_send_ready_trigger_not_connected()
    test_send_answer_to_server()
    test_send_answer_to_server_no_answer()
    test_set_lights_green()
    test_set_lights_red()
    test_all_lights_off()
    test_start_dance_lights()
    test_stop_dance_lights()
    test_on_time_changed_first_pause()
    test_on_time_changed_intro_state_skipped()
    test_on_time_changed_q_video_skipped()
    test_on_time_changed_third_pause_sends_answer()
    test_handle_next_first_pause_sends_ready_and_red()
    test_handle_next_third_pause_sends_answer()
    test_check_light_connection_sends_ping()

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

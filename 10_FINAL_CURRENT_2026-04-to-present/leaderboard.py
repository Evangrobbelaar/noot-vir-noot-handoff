"""
Leaderboard display - standalone pygame application.
Receives IPC commands over a persistent TCP connection from video_player/server.py.
Run as: python leaderboard.py
"""

import os
import re
import sys
import socket
import threading
import time
import json
import math
import logging

os.environ["SDL_VIDEO_MINIMIZE_ON_FOCUS_LOSS"] = "0"

import pygame

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [LB] %(levelname)s %(message)s"
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")
with open(CONFIG_PATH) as f:
    CONFIG = json.load(f)

IPC_HOST = CONFIG["leaderboard_ipc"]["host"]
IPC_PORT = CONFIG["leaderboard_ipc"]["port"]
MAX_TABLES = CONFIG["game"]["max_tables"]

# ---------------------------------------------------------------------------
# Colours
# ---------------------------------------------------------------------------
BG_COLOUR = (44, 62, 80)
TEXT_COLOUR = (236, 240, 241)
TITLE_COLOUR = (241, 196, 15)
ROW_BG_EVEN = (52, 73, 94)
ROW_BG_ODD = (44, 62, 80)
SCORE_COLOUR = (46, 204, 113)

ANSWER_COLOURS = {
    "A": (46, 204, 113),  # green
    "B": (52, 152, 219),  # blue
    "C": (155, 89, 182),  # purple
    "D": (230, 126, 34),  # orange
}

ARROW_UP_COLOUR = (46, 204, 113)
ARROW_DOWN_COLOUR = (231, 76, 60)
ARROW_SAME_COLOUR = (127, 140, 141)

# ---------------------------------------------------------------------------
# Table data
# ---------------------------------------------------------------------------


class TableEntry:
    def __init__(self, number: int):
        self.number = number
        self.score = 0
        self.last_answer: str | None = None
        self.display_y: float = 0.0  # current interpolated y position
        self.target_y: float = 0.0  # target y position after re-sort
        self.prev_rank: int = number - 1
        self.rank: int = number - 1


tables: list[TableEntry] = [TableEntry(i + 1) for i in range(MAX_TABLES)]

# ---------------------------------------------------------------------------
# IPC server (receives from video_player/GameServer)
# ---------------------------------------------------------------------------

_ipc_buf = ""
_ipc_lock = threading.Lock()
_pending_commands: list[str] = []


def _ipc_server_thread():
    """Listen for one persistent connection at a time on IPC_PORT."""
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((IPC_HOST, IPC_PORT))
    srv.listen(5)
    log.info("IPC server listening on %s:%d", IPC_HOST, IPC_PORT)

    while True:
        try:
            conn, addr = srv.accept()
            log.info("IPC connection from %s", addr)
            buf = ""
            while True:
                try:
                    data = conn.recv(256)
                    if not data:
                        break
                    buf += data.decode("utf-8", errors="replace")
                    while "\n" in buf:
                        line, buf = buf.split("\n", 1)
                        line = line.strip()
                        if line:
                            with _ipc_lock:
                                _pending_commands.append(line)
                except Exception as exc:
                    log.warning("IPC recv error: %s", exc)
                    break
            log.info("IPC connection closed")
            try:
                conn.close()
            except Exception:
                pass
        except Exception as exc:
            log.error("IPC accept error: %s", exc)
            time.sleep(1)


def _process_ipc_commands():
    """Drain pending IPC commands and apply to table state. Called from pygame main loop."""
    global tables
    with _ipc_lock:
        commands = _pending_commands[:]
        _pending_commands.clear()

    changed = False
    for cmd in commands:
        # Answer indicator: @5:B
        if cmd.startswith("@") and ":" in cmd:
            try:
                rest = cmd[1:]
                table_str, answer = rest.split(":", 1)
                table_num = int(table_str)
                for t in tables:
                    if t.number == table_num:
                        t.last_answer = answer.strip().upper()
                        break
                changed = True
            except Exception as exc:
                log.warning("Bad answer command %r: %s", cmd, exc)

        # Clear answers: CLEAR_ANSWERS
        elif cmd == "CLEAR_ANSWERS":
            for t in tables:
                t.last_answer = None
            changed = True

        # Score update: *1*3+100 or *2*4-50
        # Format: *<t1>*<t2>...[+|-]<points>
        elif cmd.startswith("*"):
            try:
                m = re.match(r"^(\*[\d*]+)([+-])(\d+)$", cmd)
                if not m:
                    log.warning("Unrecognised score command %r", cmd)
                else:
                    tables_part = m.group(1)  # e.g. "*1*3"
                    sign = 1 if m.group(2) == "+" else -1
                    points = int(m.group(3)) * sign
                    table_nums = [
                        int(x) for x in tables_part.split("*") if x.strip().isdigit()
                    ]
                    for table_num in table_nums:
                        for t in tables:
                            if t.number == table_num:
                                t.score += points
                                break
                    changed = True
                    log.info("Points applied: tables=%s pts=%+d", table_nums, points)
            except Exception as exc:
                log.warning("Bad score command %r: %s", cmd, exc)

    if changed:
        _recalculate_ranks()

    return changed


def _recalculate_ranks():
    """Sort tables by score descending and update rank/target_y."""
    sorted_tables = sorted(tables, key=lambda t: t.score, reverse=True)
    for new_rank, t in enumerate(sorted_tables):
        t.prev_rank = t.rank
        t.rank = new_rank


# ---------------------------------------------------------------------------
# Drawing helpers
# ---------------------------------------------------------------------------


def _draw_arrow(
    surf: pygame.Surface, x: int, y: int, size: int, direction: int, colour
):
    """direction: 1=up, -1=down, 0=same (dash)"""
    if direction == 0:
        pygame.draw.rect(surf, colour, (x - size // 2, y - 2, size, 4))
    elif direction == 1:
        points = [
            (x, y - size // 2),
            (x - size // 2, y + size // 2),
            (x + size // 2, y + size // 2),
        ]
        pygame.draw.polygon(surf, colour, points)
    else:
        points = [
            (x, y + size // 2),
            (x - size // 2, y - size // 2),
            (x + size // 2, y - size // 2),
        ]
        pygame.draw.polygon(surf, colour, points)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    pygame.init()
    pygame.display.set_caption("Dynamic Leaderboard")

    W, H = 1200, 680
    screen = pygame.display.set_mode((W, H), pygame.RESIZABLE)
    fullscreen = False
    clock = pygame.time.Clock()

    font_title = pygame.font.SysFont("Arial", 48, bold=True)
    font_row = pygame.font.SysFont("Arial", 28)
    font_small = pygame.font.SysFont("Arial", 20)

    # Start IPC listener
    t = threading.Thread(target=_ipc_server_thread, daemon=True)
    t.start()

    # Animation: interpolate display_y toward target_y
    ANIM_FRAMES = 20
    anim_progress: dict[int, float] = {}  # table number -> frame counter

    # Initial y positions
    def _compute_row_targets(w: int, h: int) -> dict[int, float]:
        """Return {table_number: target_y} based on current ranks."""
        title_h = 80
        usable_h = h - title_h - 20
        rows_per_col = math.ceil(MAX_TABLES / 2)
        row_h = usable_h / rows_per_col
        targets = {}
        sorted_tables = sorted(tables, key=lambda t: t.rank)
        for t in sorted_tables:
            col = t.rank // rows_per_col
            row_in_col = t.rank % rows_per_col
            y = title_h + row_in_col * row_h
            targets[t.number] = y
        return targets

    # Initialise display_y for all tables
    w, h = screen.get_size()
    targets = _compute_row_targets(w, h)
    for t in tables:
        t.display_y = targets.get(t.number, 0.0)
        t.target_y = t.display_y

    last_rank_snapshot = {t.number: t.rank for t in tables}

    running = True
    while running:
        changed = _process_ipc_commands()
        w, h = screen.get_size()

        # Detect rank changes → start animations
        targets = _compute_row_targets(w, h)
        for t in tables:
            new_target = targets.get(t.number, t.target_y)
            if abs(new_target - t.target_y) > 1:
                t.target_y = new_target
                anim_progress[t.number] = 0.0

        # Advance animations
        for t in tables:
            if t.number in anim_progress:
                prog = anim_progress[t.number]
                prog += 1.0
                if prog >= ANIM_FRAMES:
                    t.display_y = t.target_y
                    del anim_progress[t.number]
                else:
                    anim_progress[t.number] = prog
                    alpha = prog / ANIM_FRAMES
                    # smooth step
                    alpha = alpha * alpha * (3 - 2 * alpha)
                    start_y = t.display_y
                    t.display_y = start_y + (t.target_y - start_y) * (
                        1.0 / (ANIM_FRAMES - prog + 1)
                    )
            else:
                t.display_y = t.target_y

        # Events
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_f:
                    fullscreen = not fullscreen
                    if fullscreen:
                        screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
                    else:
                        screen = pygame.display.set_mode((W, H), pygame.RESIZABLE)

        # Draw
        screen.fill(BG_COLOUR)
        w, h = screen.get_size()

        # Title
        title_surf = font_title.render("Leaderboard", True, TITLE_COLOUR)
        screen.blit(title_surf, (w // 2 - title_surf.get_width() // 2, 15))

        title_h = 80
        usable_h = h - title_h - 20
        rows_per_col = math.ceil(MAX_TABLES / 2)
        row_h = usable_h / rows_per_col
        col_w = w // 2

        sorted_tables = sorted(tables, key=lambda t: t.rank)

        for idx, t in enumerate(sorted_tables):
            col = idx // rows_per_col
            x_offset = col * col_w

            y = int(t.display_y)
            rh = int(row_h) - 4

            # Row background
            bg = ROW_BG_EVEN if idx % 2 == 0 else ROW_BG_ODD
            pygame.draw.rect(
                screen, bg, (x_offset + 4, y + 2, col_w - 8, rh), border_radius=6
            )

            cx = x_offset + 30
            cy = y + rh // 2

            # Arrow
            if t.rank < t.prev_rank:
                direction, colour = 1, ARROW_UP_COLOUR
            elif t.rank > t.prev_rank:
                direction, colour = -1, ARROW_DOWN_COLOUR
            else:
                direction, colour = 0, ARROW_SAME_COLOUR
            _draw_arrow(screen, cx, cy, 16, direction, colour)

            # Table name
            name_surf = font_row.render(f"Table {t.number}", True, TEXT_COLOUR)
            screen.blit(name_surf, (x_offset + 55, cy - name_surf.get_height() // 2))

            # Score (right-aligned in column)
            score_surf = font_row.render(str(t.score), True, SCORE_COLOUR)
            score_x = x_offset + col_w - 70
            screen.blit(
                score_surf,
                (score_x - score_surf.get_width(), cy - score_surf.get_height() // 2),
            )

            # Answer indicator circle
            if t.last_answer and t.last_answer in ANSWER_COLOURS:
                circle_x = x_offset + col_w - 40
                circle_colour = ANSWER_COLOURS[t.last_answer]
                pygame.draw.circle(screen, circle_colour, (circle_x, cy), 14)
                ans_surf = font_small.render(t.last_answer, True, (255, 255, 255))
                screen.blit(
                    ans_surf,
                    (
                        circle_x - ans_surf.get_width() // 2,
                        cy - ans_surf.get_height() // 2,
                    ),
                )

        pygame.display.flip()
        clock.tick(60)

    pygame.quit()
    sys.exit(0)


if __name__ == "__main__":
    main()

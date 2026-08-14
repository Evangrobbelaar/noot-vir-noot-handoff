import pygame
import sys
import math
import os
import json
import win32pipe, win32file, pywintypes
from threading import Thread
from enum import Enum
from typing import List, Optional

SCORES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scores.json")

class PositionChange(Enum):
    UP = "up"
    DOWN = "down"
    SAME = "same"

class TableData:
    def __init__(self, name: str, initial_score: int = 0):
        self.name = name
        self.score = initial_score
        self.previous_position = -1
        self.current_position = -1
        self.last_answer: Optional[str] = None
        self.position_change = PositionChange.SAME

class GameshowLeaderboard:
    def __init__(self):
        # Set environment variables to prevent window minimization
        os.environ['SDL_VIDEO_MINIMIZE_ON_FOCUS_LOSS'] = '0'
        os.environ['SDL_VIDEO_WINDOW_POS'] = 'centered'
        
        pygame.init()
        self.WIDTH, self.HEIGHT = 1200, 680
        # Get the current display info
        self.display_info = pygame.display.Info()
        self.SCREEN = pygame.display.set_mode((self.WIDTH, self.HEIGHT))
        pygame.display.set_caption("Dynamic Leaderboard")
        self.is_fullscreen = False

        # Colors
        self.WHITE = (255, 255, 255)
        self.BLACK = (0, 0, 0)
        self.GREEN = (41, 128, 85)
        self.RED = (185, 41, 41)
        self.DARK_BLUE = (44, 62, 80)
        
        # Answer colors
        self.ANSWER_COLORS = {
            'A': (46, 204, 113),   # Emerald Green
            'B': (52, 152, 219),   # Blue
            'C': (155, 89, 182),   # Purple
            'D': (230, 126, 34)    # Orange
        }

        # Fonts
        self.TITLE_FONT = pygame.font.Font(None, 72)
        self.TABLE_FONT = pygame.font.Font(None, 48)
        self.SCORE_FONT = pygame.font.Font(None, 42)
        self.ANSWER_FONT = pygame.font.Font(None, 36)

        # Animation
        self.ANIMATION_SPEED = 0.05
        self.animation_progress = [0]
        
        # Game Data
        self.tables = [TableData(f"Table {i+1}") for i in range(12)]
        self.table_positions = []
        self.load_scores()

        self.start_pipe_server()

    def load_scores(self):
        """Restore scores from disk so a restarted leaderboard resumes with
        correct standings instead of zeros (see docs/proposals/nootvirnoot/
        01-scoreboard-bug-investigation.md #6.1)."""
        if not os.path.exists(SCORES_FILE):
            return
        try:
            with open(SCORES_FILE, "r") as f:
                saved = json.load(f)
            for i, score in enumerate(saved.get("scores", [])):
                if i < len(self.tables):
                    self.tables[i].score = score
            self.update_positions()
            print(f"Restored scores from {SCORES_FILE}")
        except Exception as e:
            print(f"Could not load saved scores ({e}); starting from zero")

    def save_scores(self):
        """Persist current scores so a leaderboard restart doesn't reset the
        board to zero."""
        try:
            with open(SCORES_FILE, "w") as f:
                json.dump({"scores": [t.score for t in self.tables]}, f)
        except Exception as e:
            print(f"Could not save scores: {e}")

    def toggle_fullscreen(self):
        if self.is_fullscreen:
            self.SCREEN = pygame.display.set_mode((self.WIDTH, self.HEIGHT))
        else:
            # Use FULLSCREEN with DOUBLEBUF to try to prevent minimization behavior
            self.SCREEN = pygame.display.set_mode(
                (self.display_info.current_w, self.display_info.current_h),
                pygame.FULLSCREEN | pygame.DOUBLEBUF
            )
        self.is_fullscreen = not self.is_fullscreen

    def start_pipe_server(self):
        server_thread = Thread(target=self.create_pipe_server)
        server_thread.daemon = True
        server_thread.start()

    def create_pipe_server(self):
        PIPE_NAME = r'\\.\pipe\gameshow_pipe'
        while True:
            try:
                pipe = win32pipe.CreateNamedPipe(
                    PIPE_NAME,
                    win32pipe.PIPE_ACCESS_DUPLEX,
                    win32pipe.PIPE_TYPE_MESSAGE | win32pipe.PIPE_READMODE_MESSAGE | win32pipe.PIPE_WAIT,
                    1, 65536, 65536, 0, None
                )
                win32pipe.ConnectNamedPipe(pipe, None)
                try:
                    while True:
                        resp = win32file.ReadFile(pipe, 64*1024)
                        data = resp[1].decode()
                        self.process_command(data)
                except pywintypes.error:
                    pass
                finally:
                    win32file.CloseHandle(pipe)
            except Exception as e:
                print(f"Pipe error: {e}")

    def process_command(self, data: str):
        try:
            # Handle score updates
            if "*" in data:
                parts = data.split("+") if "+" in data else data.split("-")
                if len(parts) == 2:
                    table_numbers_str, points_str = parts
                    table_numbers = [int(num) for num in table_numbers_str.split("*")[1:]]
                    points = int(points_str)
                    if "-" in data:
                        points = -points
                    self.update_scores(table_numbers, points)
            
            # Handle answer updates (@1:A for Table 1 answering A)
            elif data.startswith("@"):
                table_num, answer = data[1:].strip().split(":")
                self.update_answer(int(table_num), answer.upper())
                
            # Handle multiple table answers (format: "ANSWERS:1:A,2:B,3:C,4:D,5:A")
            elif data.startswith("ANSWERS:"):
                answers_data = data[8:].strip()  # Remove "ANSWERS:" prefix
                self.process_multiple_answers(answers_data)
                
        except ValueError as e:
            print(f"Invalid command: {data}, Error: {e}")

    def process_multiple_answers(self, answers_data: str):
        # Reset all answers first
        for table in self.tables:
            table.last_answer = None
            
        # Split by comma to get individual table:answer pairs
        answer_pairs = answers_data.split(',')
        
        for pair in answer_pairs:
            # Skip empty entries
            if not pair.strip():
                continue
                
            # Split by colon to get table number and answer
            try:
                parts = pair.strip().split(':')
                if len(parts) != 2:
                    print(f"Invalid answer pair format: {pair}")
                    continue
                    
                table_num_str, answer = parts
                
                # Validate and convert table number
                if not table_num_str.isdigit():
                    print(f"Invalid table number: {table_num_str}")
                    continue
                    
                table_num = int(table_num_str)
                
                # Validate answer
                answer = answer.strip().upper()
                if answer not in self.ANSWER_COLORS:
                    print(f"Invalid answer: {answer}")
                    continue
                
                # Update the table's answer if valid
                if 1 <= table_num <= len(self.tables):
                    self.tables[table_num - 1].last_answer = answer
                else:
                    print(f"Table number out of range: {table_num}")
                    
            except Exception as e:
                print(f"Error processing answer pair '{pair}': {e}")
                continue

    def update_scores(self, table_numbers: List[int], points: int):
        # Store previous positions
        self.store_previous_positions()
        
        # Update scores
        for table_num in table_numbers:
            if 0 < table_num <= len(self.tables):
                self.tables[table_num - 1].score += points

        # Reset animation and update positions
        self.animation_progress[0] = 0
        self.update_positions()
        self.save_scores()

    def update_answer(self, table_num: int, answer: str):
        if 0 < table_num <= len(self.tables) and answer in self.ANSWER_COLORS:
            self.tables[table_num - 1].last_answer = answer

    def store_previous_positions(self):
        # Store current positions as previous
        sorted_tables = sorted(enumerate(self.tables), key=lambda x: x[1].score, reverse=True)
        for pos, (idx, _) in enumerate(sorted_tables):
            self.tables[idx].previous_position = pos

    def update_positions(self):
        # Update current positions and determine changes
        sorted_tables = sorted(enumerate(self.tables), key=lambda x: x[1].score, reverse=True)
        for new_pos, (idx, table) in enumerate(sorted_tables):
            table.current_position = new_pos
            if table.previous_position == -1:
                table.position_change = PositionChange.SAME
            elif new_pos < table.previous_position:
                table.position_change = PositionChange.UP
            elif new_pos > table.previous_position:
                table.position_change = PositionChange.DOWN
            else:
                table.position_change = PositionChange.SAME

    def draw_position_arrow(self, surface: pygame.Surface, x: int, y: int, change: PositionChange):
        arrow_color = {
            PositionChange.UP: (46, 204, 113),    # Green
            PositionChange.DOWN: (231, 76, 60),   # Red
            PositionChange.SAME: (149, 165, 166)  # Gray
        }[change]

        if change == PositionChange.SAME:
            # Draw horizontal line for no change
            pygame.draw.line(surface, arrow_color, (x, y), (x + 20, y), 3)
        else:
            # Draw arrow
            points = []
            if change == PositionChange.UP:
                points = [(x + 10, y - 10), (x + 20, y), (x, y)]
            else:  # DOWN
                points = [(x + 10, y + 10), (x + 20, y), (x, y)]
            pygame.draw.polygon(surface, arrow_color, points)

    def draw_answer_indicator(self, surface: pygame.Surface, answer: str, x: int, y: int):
        if answer in self.ANSWER_COLORS:
            color = self.ANSWER_COLORS[answer]
            pygame.draw.circle(surface, color, (x, y), 15)
            text = self.ANSWER_FONT.render(answer, True, self.WHITE)
            text_rect = text.get_rect(center=(x, y))
            surface.blit(text, text_rect)

    def draw_gradient_rect(self, surface, color, rect):
        color1 = color
        color2 = [max(0, c - 50) for c in color]
        for i in range(rect.height):
            factor = i / rect.height
            gradient_color = [int(color1[j] * (1 - factor) + color2[j] * factor) for j in range(3)]
            pygame.draw.line(surface, gradient_color, (rect.left, rect.top + i), (rect.right, rect.top + i))

    def draw_ui(self):
        self.SCREEN.fill(self.DARK_BLUE)
        
        # Draw title
        title = self.TITLE_FONT.render("Leaderboard", True, self.WHITE)
        self.SCREEN.blit(title, (self.SCREEN.get_width() // 2 - title.get_width() // 2, 20))
        
        # Sort tables by score
        sorted_table_data = sorted(enumerate(self.tables), key=lambda x: x[1].score, reverse=True)
        num_tables = len(sorted_table_data)
        tables_per_side = math.ceil(num_tables / 2)
        table_width = (self.SCREEN.get_width() - 60) // 2
        table_height = (self.SCREEN.get_height() - 100) // tables_per_side
        
        # Ensure table_positions list is initialized
        while len(self.table_positions) < num_tables:
            self.table_positions.append((0, 0))

        for i, (orig_idx, table) in enumerate(sorted_table_data):
            column = 0 if i < tables_per_side else 1
            row = i % tables_per_side
            
            target_x = 20 + column * (table_width + 20)
            target_y = 80 + row * table_height
            
            current_x, current_y = self.table_positions[i]
            new_x = current_x + (target_x - current_x) * self.animation_progress[0]
            new_y = current_y + (target_y - current_y) * self.animation_progress[0]
            self.table_positions[i] = (new_x, new_y)
            
            # Draw table background with gradient
            table_rect = pygame.Rect(new_x, new_y, table_width, table_height - 10)
            self.draw_gradient_rect(self.SCREEN, self.GREEN if column == 0 else self.RED, table_rect)
            pygame.draw.rect(self.SCREEN, self.WHITE, table_rect, 2)
            
            # Draw position change arrow
            self.draw_position_arrow(self.SCREEN, new_x + 20, 
                                  new_y + table_height // 2, 
                                  table.position_change)
            
            # Draw table name and score
            name_text = self.TABLE_FONT.render(table.name, True, self.WHITE)
            score_text = self.SCORE_FONT.render(str(table.score), True, self.WHITE)
            
            # Position text with space for arrow and answer indicator
            self.SCREEN.blit(name_text, (new_x + 50, new_y + table_height // 2 - name_text.get_height() // 2))
            self.SCREEN.blit(score_text, (new_x + table_width - score_text.get_width() - 50, 
                                        new_y + table_height // 2 - score_text.get_height() // 2))
            
            # Draw answer indicator if available
            if table.last_answer:
                self.draw_answer_indicator(self.SCREEN, 
                                        table.last_answer,
                                        new_x + table_width - 25,
                                        new_y + table_height // 2)

        pygame.display.update()

    def run(self):
        clock = pygame.time.Clock()
        running = True
        
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    # Only quit on window close events when not in fullscreen
                    if not self.is_fullscreen:
                        running = False
                elif event.type == pygame.ACTIVEEVENT:
                    # Prevent minimization in fullscreen mode
                    if self.is_fullscreen and hasattr(event, 'gain') and event.gain == 0:
                        # Window lost focus - ignore this to prevent minimization
                        pass
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        running = False
                    elif event.key == pygame.K_f:  # Press F to toggle fullscreen
                        self.toggle_fullscreen()
            
            self.animation_progress[0] = min(1, self.animation_progress[0] + self.ANIMATION_SPEED)
            self.draw_ui()
            clock.tick(60)

        pygame.quit()
        sys.exit()

if __name__ == "__main__":
    leaderboard = GameshowLeaderboard()
    leaderboard.run()
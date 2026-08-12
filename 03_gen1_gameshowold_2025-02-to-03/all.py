import socket
import threading
import pygame
import sys
import math
from datetime import datetime
from typing import Dict, Tuple, List
from dataclasses import dataclass

@dataclass
class GameState:
    current_answers: Dict[str, str] = None
    scores: Dict[str, int] = None
    last_results: Dict[str, bool] = None
    table_positions: Dict[str, Tuple[float, float]] = None

    def __post_init__(self):
        self.current_answers = {}
        self.scores = {f"Table {i}": 0 for i in range(1, 16)}
        self.last_results = {}
        self.table_positions = {}

    def clear_state(self):
        self.current_answers.clear()
        self.last_results.clear()
        self.scores = {f"Table {i}": 0 for i in range(1, 16)}

class Constants:
    WIDTH, HEIGHT = 1200, 800
    WHITE = (255, 255, 255)
    BLACK = (20, 20, 20)
    GREEN = (46, 204, 113)
    RED = (231, 76, 60)
    DARK_BLUE = (44, 62, 80)
    YELLOW = (241, 196, 15)
    BACKGROUND = (36, 47, 61)
    CARD_BG = (52, 73, 94)
    ANIMATION_SPEED = 0.08
    POINTS_CORRECT = 10
    POINTS_INCORRECT = -10

class GameServer:
    def __init__(self, game_state: GameState, host="127.0.0.1", port=8089):
        self.game_state = game_state
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self.server_socket.bind((host, port))
            self.server_socket.listen(5)
            print(f"Server listening on {host}:{port}")
        except OSError as e:
            print(f"Failed to bind to {host}:{port}: {e}")
            sys.exit(1)

    def start(self):
        server_thread = threading.Thread(target=self.listen_for_connections, daemon=True)
        server_thread.start()

    def handle_client(self, client_socket: socket.socket):
        try:
            with client_socket:
                while True:
                    data = client_socket.recv(1024).decode("utf-8")
                    if not data:
                        break

                    try:
                        table, sub, answer = data.split("|")
                        table_id = f"Table {table}{sub}"
                        self.game_state.current_answers[table_id] = answer
                        print(f"Received answer '{answer}' from {table_id}")
                    except ValueError:
                        print(f"Malformed data received: {data}")
        except Exception as e:
            print(f"Error handling client: {e}")

    def listen_for_connections(self):
        while True:
            try:
                client_socket, client_address = self.server_socket.accept()
                print(f"Connection established with {client_address}")
                threading.Thread(target=self.handle_client, args=(client_socket,), daemon=True).start()
            except Exception as e:
                print(f"Error accepting connection: {e}")

class GameUI:
    def __init__(self, game_state: GameState):
        pygame.init()
        self.game_state = game_state
        self.screen = pygame.display.set_mode((Constants.WIDTH, Constants.HEIGHT))
        pygame.display.set_caption("Game Show Leaderboard")
        
        # Load fonts with fallbacks
        try:
            self.title_font = pygame.font.Font("arial.ttf", 72)
        except:
            self.title_font = pygame.font.Font(None, 72)
        try:
            self.table_font = pygame.font.Font("arial.ttf", 36)
        except:
            self.table_font = pygame.font.Font(None, 36)

    def draw_rounded_rect(self, surface, rect, color, corner_radius):
        """Draw a rounded rectangle"""
        pygame.draw.rect(surface, color, rect, border_radius=corner_radius)

    def draw(self, animation_progress: float):
        self.screen.fill(Constants.BACKGROUND)
        
        # Draw title with shadow
        title = "Game Show Leaderboard"
        shadow = self.title_font.render(title, True, Constants.BLACK)
        text = self.title_font.render(title, True, Constants.WHITE)
        title_pos = (Constants.WIDTH // 2 - text.get_width() // 2, 30)
        self.screen.blit(shadow, (title_pos[0] + 2, title_pos[1] + 2))
        self.screen.blit(text, title_pos)
        
        # Sort tables by score
        sorted_tables = sorted(self.game_state.scores.items(), key=lambda x: (-x[1], x[0]))
        
        # Calculate layout
        tables_per_side = math.ceil(len(sorted_tables) / 2)
        padding = 40
        table_width = (Constants.WIDTH - padding * 3) // 2
        table_height = (Constants.HEIGHT - 150 - padding * (tables_per_side + 1)) // tables_per_side
        
        self._draw_tables(sorted_tables, tables_per_side, table_width, table_height, 
                         padding, animation_progress)
        pygame.display.update()

    def _draw_tables(self, sorted_tables, tables_per_side, table_width, table_height, 
                    padding, animation_progress):
        for i, (table_id, score) in enumerate(sorted_tables):
            column = 0 if i < tables_per_side else 1
            row = i % tables_per_side
            
            target_x = padding + column * (table_width + padding)
            target_y = 120 + row * (table_height + padding)
            
            # Initialize position if not exists
            if table_id not in self.game_state.table_positions:
                self.game_state.table_positions[table_id] = (target_x, target_y)
            
            current_x, current_y = self.game_state.table_positions[table_id]
            new_x = current_x + (target_x - current_x) * animation_progress
            new_y = current_y + (target_y - current_y) * animation_progress
            self.game_state.table_positions[table_id] = (new_x, new_y)
            
            # Draw card background with rank indicator
            card_rect = pygame.Rect(new_x, new_y, table_width, table_height)
            rank_width = 60
            
            # Draw rank indicator
            rank_rect = pygame.Rect(new_x, new_y, rank_width, table_height)
            rank_color = self._get_rank_color(i + 1)
            self.draw_rounded_rect(self.screen, rank_rect, rank_color, 10)
            
            # Draw rank number
            rank_text = self.table_font.render(f"#{i+1}", True, Constants.WHITE)
            rank_pos = (new_x + rank_width//2 - rank_text.get_width()//2, 
                       new_y + table_height//2 - rank_text.get_height()//2)
            self.screen.blit(rank_text, rank_pos)
            
            # Draw main card
            main_card_rect = pygame.Rect(new_x + rank_width, new_y, 
                                       table_width - rank_width, table_height)
            card_color = self._get_table_color(table_id)
            self.draw_rounded_rect(self.screen, main_card_rect, card_color, 10)
            
            # Draw content
            self._draw_table_content(table_id, score, new_x + rank_width, new_y, 
                                   table_width - rank_width, table_height)

    def _get_rank_color(self, rank: int) -> Tuple[int, int, int]:
        if rank == 1:
            return (212, 175, 55)  # Gold
        elif rank == 2:
            return (192, 192, 192)  # Silver
        elif rank == 3:
            return (205, 127, 50)  # Bronze
        return Constants.CARD_BG

    def _get_table_color(self, table_id: str) -> Tuple[int, int, int]:
        if table_id in self.game_state.last_results and self.game_state.last_results[table_id]:
            return Constants.GREEN
        elif table_id in self.game_state.current_answers:
            return Constants.YELLOW
        return Constants.CARD_BG

    def _draw_table_content(self, table_id: str, score: int, x: float, y: float, 
                          width: int, height: int):
        # Draw table name
        name_text = self.table_font.render(table_id, True, Constants.WHITE)
        self.screen.blit(name_text, (x + 20, y + height//4))
        
        # Draw score
        score_text = self.table_font.render(f"Score: {score}", True, Constants.WHITE)
        self.screen.blit(score_text, (x + 20, y + height//2))
        
        # Draw current answer if available
        if table_id in self.game_state.current_answers:
            answer = self.game_state.current_answers[table_id]
            answer_text = self.table_font.render(f"Answer: {answer}", True, Constants.WHITE)
            self.screen.blit(answer_text, (x + 20, y + height*3//4))

class GameController:
    def __init__(self, game_state: GameState):
        self.game_state = game_state

    def process_correct_answer(self, answer: str):
        if not self.game_state.current_answers:
            print("No answers received yet!")
            return

        self.game_state.last_results.clear()
        
        for table_id, submitted_answer in self.game_state.current_answers.items():
            is_correct = submitted_answer.strip().upper() == answer.strip().upper()
            self.game_state.last_results[table_id] = is_correct
            
            current_score = self.game_state.scores.get(table_id, 0)
            if is_correct:
                self.game_state.scores[table_id] = current_score + Constants.POINTS_CORRECT
                print(f"{table_id} correct! +10 points (submitted: {submitted_answer})")
            else:
                self.game_state.scores[table_id] = current_score + Constants.POINTS_INCORRECT
                print(f"{table_id} incorrect! -10 points (submitted: {submitted_answer})")
        
        self.game_state.current_answers.clear()
        print("Scores updated and ready for next question!")

def main():
    game_state = GameState()
    game_server = GameServer(game_state)
    game_ui = GameUI(game_state)
    game_controller = GameController(game_state)
    
    game_server.start()
    
    clock = pygame.time.Clock()
    animation_progress = 0
    running = True
    print("Game system ready! Waiting for answers...")
    
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_c:
                game_state.clear_state()
                print("Scores cleared!")
        
        animation_progress = min(1, animation_progress + Constants.ANIMATION_SPEED)
        game_ui.draw(animation_progress)
        
        try:
            command = input("Enter correct answer or command (or 'quit' to exit): ").strip()
            if command.lower() == 'quit':
                running = False
            elif command.lower() == 'clear':
                game_state.clear_state()
                print("Scores cleared!")
            else:
                game_controller.process_correct_answer(command)
                animation_progress = 0
        except KeyboardInterrupt:
            running = False
        except Exception as e:
            print(f"Error processing command: {e}")
        
        clock.tick(60)

    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()
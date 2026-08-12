import vlc
import tkinter as tk
from tkinter import ttk, messagebox
import os
import socket
import re
from typing import List, Optional, Dict
from enum import Enum
from itertools import cycle
from pynput import keyboard  # Added for global key listening

class GameState(Enum):
    LANDING = "landing"
    INTRO = "intro"
    WAITING_TO_START = "waiting_to_start"
    PLAYING = "playing"
    COUNTDOWN = "countdown"

class QuestionCategory(Enum):
    VRAE = "vrae"
    VISUAL = "visual"
    COUNTDOWN = "countdown"

class ControlPanel(tk.Toplevel):
    def __init__(self, parent, player):
        super().__init__(parent)
        self.player = player
        self.title("Gameshow Control Panel")
        self.geometry("300x300")
        self.configure(bg="#121212")
        self.resizable(True, True)
        self.minsize(250, 250)
        self.create_styles()
        self.setup_ui()

    def create_styles(self):
        style = ttk.Style()
        style.configure(".", 
            background="#121212",
            foreground="#ffffff",
            fieldbackground="#1e1e1e",
            troughcolor="#2a2a2a"
        )
        style.configure("Primary.TButton", background="#121212", foreground="#00b2ff", bordercolor="#00b2ff", font=('Arial', 14, 'bold'), padding=8)
        style.configure("Secondary.TButton", background="#121212", foreground="#00ff7f", bordercolor="#00ff7f", font=('Arial', 11), padding=5)
        style.configure("Accent.TButton", background="#121212", foreground="#ff0066", bordercolor="#ff0066", font=('Arial', 11, 'bold'), padding=5)
        style.configure("Connect.TButton", background="#121212", foreground="#ffaa00", bordercolor="#ffaa00", font=('Arial', 10, 'bold'), padding=3)
        style.configure("TFrame", background="#121212")
        style.configure("Status.TLabel", background="#121212", foreground="#aaaaaa", font=('Arial', 9))
        style.configure("StatusActive.TLabel", background="#121212", foreground="#00ff7f", font=('Arial', 9, 'bold'))
        style.configure("TileFrame.TFrame", background="#181818", relief="raised", borderwidth=1)
        style.configure("Header.TLabel", background="#121212", foreground="#ffffff", font=('Arial', 11, 'bold'))
        style.configure("TScale", background="#121212", troughcolor="#1e1e1e", sliderrelief="flat")

    def setup_ui(self):
        main_frame = ttk.Frame(self, style="TFrame")
        main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        main_frame.columnconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        
        status_header = ttk.Label(main_frame, text="GAMESHOW CONTROL", style="Header.TLabel")
        status_header.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 5))
        
        status_frame = ttk.Frame(main_frame, style="TileFrame.TFrame")
        status_frame.grid(row=1, column=0, columnspan=2, sticky="ew", padx=2, pady=2)
        
        status_grid = ttk.Frame(status_frame, style="TFrame")
        status_grid.pack(fill=tk.X, padx=5, pady=5)
        
        status_grid.columnconfigure(0, weight=1)
        status_grid.columnconfigure(1, weight=1)
        
        ttk.Label(status_grid, text="State:", style="Status.TLabel").grid(row=0, column=0, sticky="w")
        self.state_label = ttk.Label(status_grid, text="Landing", style="Status.TLabel")
        self.state_label.grid(row=0, column=1, sticky="w")
        
        ttk.Label(status_grid, text="Category:", style="Status.TLabel").grid(row=1, column=0, sticky="w")
        self.category_label = ttk.Label(status_grid, text="None", style="Status.TLabel")
        self.category_label.grid(row=1, column=1, sticky="w")
        
        ttk.Label(status_grid, text="Lights:", style="Status.TLabel").grid(row=2, column=0, sticky="w")
        self.light_status_label = ttk.Label(status_grid, text="Not Connected", style="Status.TLabel")
        self.light_status_label.grid(row=2, column=1, sticky="w")
        
        ttk.Label(status_grid, text="Sequence:", style="Status.TLabel").grid(row=3, column=0, sticky="w")
        self.light_sequence_label = ttk.Label(status_grid, text="Inactive", style="Status.TLabel")
        self.light_sequence_label.grid(row=3, column=1, sticky="w")
        
        ttk.Label(status_grid, text="Answer:", style="Status.TLabel").grid(row=4, column=0, sticky="w")
        self.current_answer_label = ttk.Label(status_grid, text="None", style="Status.TLabel")
        self.current_answer_label.grid(row=4, column=1, sticky="w")
        
        next_btn = ttk.Button(main_frame, text="NEXT (N)", command=self.player.handle_next, style="Primary.TButton")
        next_btn.grid(row=2, column=0, columnspan=2, sticky="ew", padx=2, pady=2, ipady=8)
        
        countdown_btn = ttk.Button(main_frame, text="Skip to Countdown (S)", command=self.player.start_countdown, style="Secondary.TButton")
        countdown_btn.grid(row=3, column=0, sticky="ew", padx=2, pady=2)
        
        connect_btn = ttk.Button(main_frame, text="Connect Lights", command=self.player.connect_to_light_server, style="Connect.TButton")
        connect_btn.grid(row=3, column=1, sticky="ew", padx=2, pady=2)
        
        connection_frame = ttk.Frame(main_frame, style="TileFrame.TFrame")
        connection_frame.grid(row=4, column=0, columnspan=2, sticky="ew", padx=2, pady=2)

        conn_grid = ttk.Frame(connection_frame, style="TFrame")
        conn_grid.pack(fill=tk.X, padx=5, pady=5)

        conn_grid.columnconfigure(0, weight=1)
        conn_grid.columnconfigure(1, weight=3)

        ttk.Label(conn_grid, text="IP Address:", style="Status.TLabel").grid(row=0, column=0, sticky="w")
        self.ip_entry = ttk.Entry(conn_grid, width=15)
        self.ip_entry.grid(row=0, column=1, sticky="ew", padx=5)
        self.ip_entry.insert(0, "127.0.0.1")

        ttk.Label(conn_grid, text="Port:", style="Status.TLabel").grid(row=1, column=0, sticky="w")
        self.port_entry = ttk.Entry(conn_grid, width=6)
        self.port_entry.grid(row=1, column=1, sticky="ew", padx=5)
        self.port_entry.insert(0, "8080")
        
        trigger_btn = ttk.Button(main_frame, text="SEND READY TRIGGER (T)", command=self.player.send_ready_trigger, style="Accent.TButton")
        trigger_btn.grid(row=5, column=0, columnspan=2, sticky="ew", padx=2, pady=2, ipady=8)
        
        volume_frame = ttk.Frame(main_frame, style="TileFrame.TFrame")
        volume_frame.grid(row=6, column=0, columnspan=2, sticky="ew", padx=2, pady=2)
        
        vol_grid = ttk.Frame(volume_frame, style="TFrame")
        vol_grid.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(vol_grid, text="Volume:", style="Status.TLabel").pack(side=tk.LEFT)
        self.volume_value = ttk.Label(vol_grid, text="100%", width=5, style="StatusActive.TLabel")
        self.volume_value.pack(side=tk.RIGHT)
        
        self.volume_scale = ttk.Scale(volume_frame, from_=0, to=100, orient=tk.HORIZONTAL, command=self.on_volume_change, style="TScale")
        self.volume_scale.set(100)
        self.volume_scale.pack(fill=tk.X, padx=5, pady=(0, 5))

    def on_volume_change(self, value):
        volume = int(float(value))
        self.player.set_volume(volume)
        self.volume_value.config(text=f"{volume}%")

    def update_status(self, state, category=None):
        self.state_label.config(text=f"{state.value}", style="StatusActive.TLabel")
        if category:
            self.category_label.config(text=f"{category.value}", style="StatusActive.TLabel")
        else:
            self.category_label.config(text="None", style="Status.TLabel")
            
    def update_light_status(self, connected=False, message=""):
        if connected:
            self.light_status_label.config(text="Connected", style="StatusActive.TLabel")
        else:
            self.light_status_label.config(text="Not Connected", style="Status.TLabel")
            
    def update_light_sequence_status(self, message):
        self.light_sequence_label.config(text=f"{message}", style="StatusActive.TLabel")
        
    def update_current_answer(self, answer):
        self.current_answer_label.config(text=answer, style="StatusActive.TLabel")

class GameshowPlayer:
    def __init__(self):
        self.video_files: Dict[QuestionCategory, List[str]] = {
            QuestionCategory.VRAE: [],
            QuestionCategory.COUNTDOWN: [],
        }
        self.category_cycle = cycle([QuestionCategory.VRAE])
        self.current_category: QuestionCategory = next(self.category_cycle)
        self.category_indices: Dict[QuestionCategory, int] = {
            QuestionCategory.VRAE: 0,
            QuestionCategory.COUNTDOWN: 0,
        }
        
        self.intro_video_path: Optional[str] = None
        self.current_state: GameState = GameState.LANDING
        self.media_player: Optional[vlc.MediaPlayer] = None
        self.media: Optional[vlc.Media] = None
        self.first_pause_occurred: bool = False
        self.second_pause_occurred: bool = False
        self.third_pause_occurred: bool = False
        self.volume: int = 100
        self.countdown_started: bool = False
        
        self.light_socket: Optional[socket.socket] = None
        self.light_connected: bool = False
        
        self.current_video_path: Optional[str] = None
        self.current_answer: Optional[str] = None
        
        self.setup_gui()
        self.setup_vlc()
        self.load_video_files()
        self.show_landing_screen()
        self.setup_global_listener()  # Added to initialize global key listener

    def setup_gui(self) -> None:
        self.root = tk.Tk()
        self.root.attributes('-fullscreen', True)
        self.root.title("Gameshow Video Display")
        self.control_panel = ControlPanel(self.root, self)
        
        self.landing_frame = ttk.Frame(self.root)
        self.landing_label = ttk.Label(self.landing_frame, text=".", font=('Arial', 24), justify=tk.CENTER)
        self.landing_label.pack(expand=True)
        
        self.waiting_frame = ttk.Frame(self.root)
        self.waiting_label = ttk.Label(self.waiting_frame, text=".", font=('Arial', 24), justify=tk.CENTER)
        self.waiting_label.pack(expand=True)
        
        self.video_frame = ttk.Frame(self.root)
        self.video_widget = ttk.Frame(self.video_frame)
        self.video_widget.pack(fill=tk.BOTH, expand=True)
        
        self.root.bind('<Key>', self.handle_key_press)
        self.root.bind('<Escape>', lambda e: self.root.attributes('-fullscreen', False))
        self.root.bind('f', self.toggle_fullscreen)
        self.root.bind('t', self.send_ready_trigger)
        self.root.bind('<Down>', lambda e: self.handle_next())
        self.root.bind('<Up>', lambda e: self.handle_next())
        self.root.bind('<Next>', lambda e: self.handle_next())
        self.root.bind('<Prior>', lambda e: self.handle_next())
        
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def setup_global_listener(self) -> None:
        """Set up a global key listener for the clicker."""
        def on_press(key):
            try:
                # Assuming the clicker sends a PageDown key (modify as needed)
                if key == keyboard.Key.page_down:
                    # Schedule handle_next to run in the Tkinter event loop
                    self.root.after(0, self.handle_next)
            except AttributeError:
                pass

        # Start the listener in a separate thread
        self.listener = keyboard.Listener(on_press=on_press)
        self.listener.start()

    def send_ready_trigger(self, event=None) -> None:
        if not self.light_connected or not self.light_socket:
            messagebox.showinfo("Not Connected", "Please connect to the light server first")
            return
        try:
            command = "DASHBOARD-READY-TRIGGER\r\n"
            self.light_socket.send(command.encode('utf-8'))
            self.control_panel.update_light_sequence_status("Ready Trigger Sent")
            print("Ready trigger sent to dashboard")
            messagebox.showinfo("Ready Trigger", "Ready signal sent to dashboard")
        except Exception as e:
            print(f"Error sending ready trigger: {str(e)}")
            self.light_connected = False
            messagebox.showerror("Connection Error", "Failed to send ready trigger")

    def handle_key_press(self, event: tk.Event) -> None:
        if event.keysym == 'n':
            self.handle_next()
        elif event.keysym == 's':
            if self.current_state == GameState.PLAYING:
                self.start_countdown()
        elif event.keysym == 'g':
            self.set_lights_green()
        elif event.keysym == 'r':
            self.set_lights_red()
        elif event.keysym == 't':
            self.send_ready_trigger()

    def setup_vlc(self) -> None:
        try:
            vlc_args = ['--no-xlib', '--aout=directsound', '--file-caching=1000']
            self.instance = vlc.Instance(vlc_args)
            self.media_player = self.instance.media_player_new()
            self.media_player.audio_set_volume(self.volume)
            self.event_manager = self.media_player.event_manager()
            self.event_manager.event_attach(vlc.EventType.MediaPlayerTimeChanged, self.on_time_changed)
            self.event_manager.event_attach(vlc.EventType.MediaPlayerEndReached, self.on_media_end)
            self.media_player.set_hwnd(self.video_widget.winfo_id())
            self.media_player.set_fullscreen(True)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to initialize VLC: {str(e)}")
            self.root.quit()

    def set_volume(self, volume: int) -> None:
        self.volume = volume
        if self.media_player:
            self.media_player.audio_set_volume(volume)

    def extract_answer_from_filename(self, filename: str) -> str:
        try:
            base_filename = os.path.basename(filename)
            # Look for A, B, C, or D at the start of the filename
            match = re.match(r'([A-Da-d])_', base_filename)
            if match:
                return match.group(1).upper()
            print(f"Warning: Could not extract answer from filename: {base_filename}")
            return "UNKNOWN"
        except Exception as e:
            print(f"Error extracting answer: {str(e)}")
            return "ERROR"

    def play_video(self, video_path: str) -> None:
        if not os.path.exists(video_path):
            messagebox.showerror("Error", f"Video file not found: {video_path}")
            return
        try:
            self.current_video_path = video_path
            if self.current_state == GameState.PLAYING:
                self.current_answer = self.extract_answer_from_filename(video_path)
                print(f"Extracted answer for {os.path.basename(video_path)}: {self.current_answer}")  # Debug line
                self.control_panel.update_current_answer(self.current_answer)
            else:
                self.current_answer = None
                self.control_panel.update_current_answer("None")
            self.media = self.instance.media_new(video_path)
            self.media_player.set_media(self.media)
            self.media_player.play()
            self.first_pause_occurred = False
            self.second_pause_occurred = False
            self.third_pause_occurred = False
        except Exception as e:
            messagebox.showerror("Error", f"Error playing video: {str(e)}")

    def load_video_files(self) -> None:
        base_folder = 'vid'
        if not os.path.exists(base_folder):
            messagebox.showerror("Error", f"Video folder '{base_folder}' not found!")
            self.root.quit()
            return

        visual_folder = os.path.join(base_folder, QuestionCategory.VISUAL.value)
        intro_path = os.path.join(visual_folder, 'intro.mp4')
        if os.path.exists(intro_path):
            self.intro_video_path = intro_path
        else:
            messagebox.showwarning("Warning", "Intro video not found in visual folder!")

        vrae_folder = os.path.join(base_folder, QuestionCategory.VRAE.value)
        if not os.path.exists(vrae_folder):
            messagebox.showwarning("Warning", f"VRAE folder '{vrae_folder}' not found!")
        else:
            vrae_files = [
                os.path.join(vrae_folder, f)
                for f in os.listdir(vrae_folder)
                if f.lower().endswith(('.mp4', '.avi', '.mov'))
            ]
            vrae_files.sort()
            print("Loaded VRAE files in order:", [os.path.basename(f) for f in vrae_files])
            self.video_files[QuestionCategory.VRAE] = vrae_files


    def play_intro_video(self) -> None:
        if not self.intro_video_path:
            self.show_waiting_screen()
            return
        try:
            self.start_dance_lights()
            self.current_category = QuestionCategory.VISUAL
            self.media = self.instance.media_new(self.intro_video_path)
            self.media_player.set_media(self.media)
            self.media_player.play()
            self.current_state = GameState.INTRO
            self.control_panel.update_status(self.current_state, self.current_category)
        except Exception as e:
            messagebox.showerror("Error", f"Error playing intro video: {str(e)}")
            self.show_waiting_screen()

    def start_countdown(self) -> None:
        if self.current_state != GameState.PLAYING:
            return
        self.current_state = GameState.COUNTDOWN
        self.current_category = QuestionCategory.COUNTDOWN
        self.category_indices[QuestionCategory.COUNTDOWN] = 0
        self.countdown_started = True
        self.first_pause_occurred = False
        self.second_pause_occurred = False
        self.third_pause_occurred = False
        self.control_panel.update_status(self.current_state, self.current_category)
        self.play_next_countdown_video()

    def play_next_countdown_video(self) -> None:
        countdown_files = self.video_files[QuestionCategory.COUNTDOWN]
        current_index = self.category_indices[QuestionCategory.COUNTDOWN]
        if current_index < len(countdown_files):
            try:
                self.play_video(countdown_files[current_index])
                self.category_indices[QuestionCategory.COUNTDOWN] += 1
            except Exception as e:
                messagebox.showerror("Error", f"Failed to play countdown video: {str(e)}")
        else:
            messagebox.showinfo("Complete", "Countdown finished!")
            self.root.quit()

    def on_media_end(self, event) -> None:
        current_filename = os.path.basename(self.current_video_path) if self.current_video_path else ""
        parts = current_filename.split('.', 1)
        is_q_video = len(parts) > 1 and parts[1].startswith("Q_")
        
        if self.current_state == GameState.INTRO:
            self.stop_dance_lights()
            self.all_lights_off()
            self.root.after(100, self.show_waiting_screen)
        elif self.current_state == GameState.COUNTDOWN:
            self.root.after(100, self.play_next_countdown_video)
        elif is_q_video:
            print(f"Q_ video ended: {current_filename}")
            if self.light_connected:
                self.all_lights_off()
            self.root.after(100, self.play_next_video)

    def show_waiting_screen(self) -> None:
        self.video_frame.pack_forget()
        self.waiting_frame.pack(fill=tk.BOTH, expand=True)
        self.current_state = GameState.WAITING_TO_START
        self.control_panel.update_status(self.current_state)

    def start_game(self) -> None:
        self.current_state = GameState.PLAYING
        self.waiting_frame.pack_forget()
        self.video_frame.pack(fill=tk.BOTH, expand=True)
        self.control_panel.update_status(self.current_state, self.current_category)
        self.play_next_video()

    def play_next_video(self) -> None:
        current_files = self.video_files[self.current_category]
        current_index = self.category_indices[self.current_category]
        if current_index < len(current_files):
            try:
                self.play_video(current_files[current_index])
                self.category_indices[self.current_category] += 1
                self.current_category = next(self.category_cycle)
                self.control_panel.update_status(self.current_state, self.current_category)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to play video: {str(e)}")
        else:
            if all(self.category_indices[cat] >= len(files) 
                   for cat, files in self.video_files.items() 
                   if cat != QuestionCategory.COUNTDOWN):
                self.start_countdown()
            else:
                self.current_category = next(self.category_cycle)
                self.play_next_video()

    def send_answer_to_server(self) -> None:
        if not self.light_connected or not self.light_socket or not self.current_answer:
            print("Cannot send answer: not connected or no answer available")
            return
        try:
            command = f"awns_{self.current_answer}\r\n"
            self.light_socket.send(command.encode('utf-8'))
            self.control_panel.update_light_sequence_status(f"Answer {self.current_answer} sent")
            print(f"Sent answer command: {command.strip()}")
        except Exception as e:
            print(f"Error sending answer: {str(e)}")
            self.light_connected = False
    def on_time_changed(self, event) -> None:
        if not self.media_player or self.current_state == GameState.INTRO:
            return
        
        current_filename = os.path.basename(self.current_video_path) if self.current_video_path else ""
        is_f_video = current_filename.startswith("F_")
        parts = current_filename.split('.', 1)
        after_dot = parts[1] if len(parts) > 1 else ""
        is_q_video = after_dot.startswith("Q_")
        
        if is_q_video:
            return
            
        current_time = self.media_player.get_time()
        if not self.first_pause_occurred and current_time >= 5000:
            self.media_player.set_pause(1)
            self.first_pause_occurred = True
            if self.light_connected and self.light_socket:
                try:
                    command = "EMS-LEDS-X|10|0|0|\r\n"
                    self.light_socket.send(command.encode('utf-8'))
                    self.control_panel.update_light_sequence_status("RED (First Pause)")
                    print(f"First pause - Sent RED command")
                except Exception as e:
                    print(f"Error sending command: {str(e)}")
        elif current_time >= 10000 and not self.second_pause_occurred and not is_f_video:
            self.second_pause_occurred = True
            self.media_player.set_pause(1)
        elif not self.third_pause_occurred and current_time >= 20000:
            self.media_player.set_pause(1)
            self.third_pause_occurred = True
            if self.current_state == GameState.PLAYING and self.current_answer:
                self.send_answer_to_server()

    def handle_next(self) -> None:
        if self.current_state == GameState.LANDING:
            self.show_video_screen()
            self.play_intro_video()
        elif self.current_state == GameState.WAITING_TO_START:
            self.start_game()
        elif self.current_state in [GameState.PLAYING, GameState.COUNTDOWN]:
            if self.first_pause_occurred and not self.second_pause_occurred:
                if self.light_connected and self.light_socket:
                    try:
                        ready_command = "DASHBOARD-READY-TRIGGER\r\n"
                        self.light_socket.send(ready_command.encode('utf-8'))
                        self.control_panel.update_light_sequence_status("Ready Trigger Sent")
                        print("Ready trigger sent at first pause")
                        red_command = "EMS-LEDS-X|10|0|0|\r\n"
                        self.light_socket.send(red_command.encode('utf-8'))
                        print(f"Next button - Sent RED command")
                    except Exception as e:
                        print(f"Error sending commands: {str(e)}")
            elif self.third_pause_occurred:
                if self.current_state == GameState.PLAYING and self.current_answer:
                    self.send_answer_to_server()
            self.resume_play()

    def show_landing_screen(self) -> None:
        self.video_frame.pack_forget()
        self.waiting_frame.pack_forget()
        self.landing_frame.pack(fill=tk.BOTH, expand=True)
        self.current_state = GameState.LANDING
        self.control_panel.update_status(self.current_state)
        
    def show_video_screen(self) -> None:
        self.landing_frame.pack_forget()
        self.waiting_frame.pack_forget()
        self.video_frame.pack(fill=tk.BOTH, expand=True)

    def resume_play(self) -> None:
        if not self.media_player:
            return
        if self.media_player.get_state() == vlc.State.Ended:
            if self.current_state == GameState.COUNTDOWN:
                self.play_next_countdown_video()
            else:
                self.play_next_video()
        else:
            self.media_player.play()

    def toggle_fullscreen(self, event: Optional[tk.Event] = None) -> None:
        self.root.attributes('-fullscreen', not self.root.attributes('-fullscreen'))
        if self.media_player:
            self.media_player.set_fullscreen(not self.media_player.get_fullscreen())

    def connect_to_light_server(self) -> None:
        if self.light_connected:
            self.disconnect_from_light_server()
        try:
            ip = self.control_panel.ip_entry.get()
            port = int(self.control_panel.port_entry.get())
            self.light_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.light_socket.connect((ip, port))
            self.light_socket.settimeout(2.0)
            response = self.light_socket.recv(1024).decode('utf-8')
            if "Connected" in response:
                self.light_connected = True
                self.control_panel.update_light_status(True, f"{ip}:{port}")
                try:
                    self.light_socket.send("PING\r\n".encode('utf-8'))
                    print("Sent PING to verify connection")
                except Exception as e:
                    print(f"Warning: Could not send PING: {str(e)}")
                self.root.after(5000, self.check_light_connection)
            else:
                messagebox.showerror("Connection Error", "Connected to server but received unexpected response")
                self.disconnect_from_light_server()
        except Exception as e:
            messagebox.showerror("Connection Error", f"Failed to connect to light server: {str(e)}")
            self.disconnect_from_light_server()
    
    def disconnect_from_light_server(self) -> None:
        if self.light_socket:
            try:
                self.light_socket.close()
            except:
                pass
        self.light_socket = None
        self.light_connected = False
        self.control_panel.update_light_status(False, "Disconnected")
    
    def check_light_connection(self) -> None:
        if not self.light_connected or not self.light_socket:
            return
        try:
            self.light_socket.send("PING\r\n".encode('utf-8'))
            self.root.after(5000, self.check_light_connection)
        except Exception as e:
            print(f"Connection check failed: {str(e)}")
            self.disconnect_from_light_server()
    
    def set_lights_green(self) -> None:
        if not self.light_connected or not self.light_socket:
            messagebox.showinfo("Not Connected", "Please connect to the light server first")
            return
        try:
            command = "EMS-LEDS-X|0|10|0|\r\n"
            self.light_socket.send(command.encode('utf-8'))
            self.control_panel.update_light_sequence_status("GREEN (Manual)")
            print("All lights set to GREEN")
        except Exception as e:
            print(f"Error sending green command: {str(e)}")
            self.light_connected = False
            
    def set_lights_red(self) -> None:
        if not self.light_connected or not self.light_socket:
            messagebox.showinfo("Not Connected", "Please connect to the light server first")
            return
        try:
            command = "EMS-LEDS-X|10|0|0|\r\n"
            self.light_socket.send(command.encode('utf-8'))
            self.control_panel.update_light_sequence_status("RED (Manual)")
            print("All lights set to RED")
        except Exception as e:
            print(f"Error sending red command: {str(e)}")
            self.light_connected = False
    
    def start_dance_lights(self) -> None:
        if not self.light_connected:
            return
        try:
            self.light_socket.send("DANCE-LIGHTS-START\r\n".encode('utf-8'))
            self.control_panel.update_light_sequence_status("Dancing")
            print("Dance lights command sent successfully")
        except Exception as e:
            print(f"Error sending dance lights command: {str(e)}")
            self.light_connected = False
    
    def stop_dance_lights(self) -> None:
        if not self.light_connected:
            return
        try:
            self.light_socket.send("DANCE-LIGHTS-STOP\r\n".encode('utf-8'))
            self.control_panel.update_light_sequence_status("Dance stopped")
            print("Stop dance lights command sent successfully")
        except Exception as e:
            print(f"Error stopping dance lights: {str(e)}")
            self.light_connected = False
    
    def all_lights_off(self) -> None:
        if not self.light_connected:
            return
        try:
            self.light_socket.send("EMS-LEDS-X|0|0|0|\r\n".encode('utf-8'))
            self.control_panel.update_light_sequence_status("All OFF")
            print("All lights off command sent successfully")
        except Exception as e:
            print(f"Error turning lights off: {str(e)}")
            self.light_connected = False
            
    def on_closing(self) -> None:
        if self.light_connected:
            self.stop_dance_lights()
            self.all_lights_off()
            self.disconnect_from_light_server()
        if self.media_player:
            self.media_player.stop()
        if hasattr(self, 'listener') and self.listener:
            self.listener.stop()  # Stop the global key listener
        self.root.destroy()
        
    def run(self) -> None:
        self.root.mainloop()

if __name__ == "__main__":
    try:
        player = GameshowPlayer()
        player.run()
    except Exception as e:
        print(f"Fatal error: {str(e)}")
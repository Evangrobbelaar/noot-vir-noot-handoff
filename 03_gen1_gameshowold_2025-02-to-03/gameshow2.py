import vlc
import tkinter as tk
from tkinter import ttk, messagebox
import os
import socket
import re
from typing import List, Optional, Dict
from enum import Enum
from itertools import cycle

class GameState(Enum):
    LANDING = "landing"
    INTRO = "intro"
    WAITING_TO_START = "waiting_to_start"
    PLAYING = "playing"
    COUNTDOWN = "countdown"

class QuestionCategory(Enum):
    GENERAL = "general"
    AUDIO = "audio"
    PHOTO = "photo"
    VISUAL = "visual"
    COUNTDOWN = "countdown"

class ControlPanel(tk.Toplevel):
    def __init__(self, parent, player):
        super().__init__(parent)
        self.player = player
        self.title("Gameshow Control Panel")
        self.geometry("300x300")  # Square layout
        self.configure(bg="#121212")  # Dark background
        self.resizable(True, True)
        self.minsize(250, 250)
        
        # Create custom styles for dark mode
        self.create_styles()
        self.setup_ui()

    def create_styles(self):
        """Create custom styles for dark mode buttons and frames"""
        style = ttk.Style()
        
        # Configure the basic theme for dark mode
        style.configure(".", 
            background="#121212",
            foreground="#ffffff",
            fieldbackground="#1e1e1e",
            troughcolor="#2a2a2a"
        )
        
        # Primary button style (Next button) - neon blue
        style.configure(
            "Primary.TButton",
            background="#121212",
            foreground="#00b2ff",
            bordercolor="#00b2ff",
            font=('Arial', 14, 'bold'),
            padding=8
        )
        
        # Secondary button style - neon green
        style.configure(
            "Secondary.TButton",
            background="#121212",
            foreground="#00ff7f",
            bordercolor="#00ff7f",
            font=('Arial', 11),
            padding=5
        )
        
        # Trigger button style - neon red/pink
        style.configure(
            "Accent.TButton",
            background="#121212",
            foreground="#ff0066",
            bordercolor="#ff0066",
            font=('Arial', 11, 'bold'),
            padding=5
        )
        
        # Connect button style - neon orange/amber
        style.configure(
            "Connect.TButton",
            background="#121212",
            foreground="#ffaa00",
            bordercolor="#ffaa00",
            font=('Arial', 10, 'bold'),
            padding=3
        )
        
        # Frame styles
        style.configure(
            "TFrame",
            background="#121212"
        )
        
        # Status label styles
        style.configure(
            "Status.TLabel",
            background="#121212",
            foreground="#aaaaaa",
            font=('Arial', 9)
        )
        
        style.configure(
            "StatusActive.TLabel",
            background="#121212",
            foreground="#00ff7f",
            font=('Arial', 9, 'bold')
        )
        
        style.configure(
            "TileFrame.TFrame",
            background="#181818",
            relief="raised",
            borderwidth=1
        )
        
        # Header style
        style.configure(
            "Header.TLabel",
            background="#121212",
            foreground="#ffffff",
            font=('Arial', 11, 'bold')
        )
        
        # Scale style for volume
        style.configure(
            "TScale",
            background="#121212",
            troughcolor="#1e1e1e",
            sliderrelief="flat"
        )

    def setup_ui(self):
        # Main grid container
        main_frame = ttk.Frame(self, style="TFrame")
        main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Configure the grid - 2 columns, multiple rows
        main_frame.columnconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        
        # Row 0: Status header
        status_header = ttk.Label(main_frame, text="GAMESHOW CONTROL", style="Header.TLabel")
        status_header.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 5))
        
        # Row 1: Compact status display
        status_frame = ttk.Frame(main_frame, style="TileFrame.TFrame")
        status_frame.grid(row=1, column=0, columnspan=2, sticky="ew", padx=2, pady=2)
        
        # Two-column grid for status indicators
        status_grid = ttk.Frame(status_frame, style="TFrame")
        status_grid.pack(fill=tk.X, padx=5, pady=5)
        
        status_grid.columnconfigure(0, weight=1)
        status_grid.columnconfigure(1, weight=1)
        
        # Row 1: State and Lights
        ttk.Label(status_grid, text="State:", style="Status.TLabel").grid(row=0, column=0, sticky="w")
        self.state_label = ttk.Label(status_grid, text="Landing", style="Status.TLabel")
        self.state_label.grid(row=0, column=1, sticky="w")
        
        # Row 2: Category and Sequence
        ttk.Label(status_grid, text="Category:", style="Status.TLabel").grid(row=1, column=0, sticky="w")
        self.category_label = ttk.Label(status_grid, text="None", style="Status.TLabel")
        self.category_label.grid(row=1, column=1, sticky="w")
        
        ttk.Label(status_grid, text="Lights:", style="Status.TLabel").grid(row=2, column=0, sticky="w")
        self.light_status_label = ttk.Label(status_grid, text="Not Connected", style="Status.TLabel")
        self.light_status_label.grid(row=2, column=1, sticky="w")
        
        ttk.Label(status_grid, text="Sequence:", style="Status.TLabel").grid(row=3, column=0, sticky="w")
        self.light_sequence_label = ttk.Label(status_grid, text="Inactive", style="Status.TLabel")
        self.light_sequence_label.grid(row=3, column=1, sticky="w")
        
        # Add current answer display
        ttk.Label(status_grid, text="Answer:", style="Status.TLabel").grid(row=4, column=0, sticky="w")
        self.current_answer_label = ttk.Label(status_grid, text="None", style="Status.TLabel")
        self.current_answer_label.grid(row=4, column=1, sticky="w")
        
        # Row 2: NEXT button (spans both columns)
        next_btn = ttk.Button(
            main_frame,
            text="NEXT (N)",
            command=self.player.handle_next,
            style="Primary.TButton"
        )
        next_btn.grid(row=2, column=0, columnspan=2, sticky="ew", padx=2, pady=2, ipady=8)
        
        # Row 3: Skip to Countdown & Light Connect (tile buttons)
        countdown_btn = ttk.Button(
            main_frame,
            text="Skip to Countdown (S)",
            command=self.player.start_countdown,
            style="Secondary.TButton"
        )
        countdown_btn.grid(row=3, column=0, sticky="ew", padx=2, pady=2)
        
        connect_btn = ttk.Button(
            main_frame,
            text="Connect Lights",
            command=self.player.connect_to_light_server,
            style="Connect.TButton"
        )
        connect_btn.grid(row=3, column=1, sticky="ew", padx=2, pady=2)
        
        # Row 4: Connection settings (IP and Port)
        connection_frame = ttk.Frame(main_frame, style="TileFrame.TFrame")
        connection_frame.grid(row=4, column=0, columnspan=2, sticky="ew", padx=2, pady=2)

        conn_grid = ttk.Frame(connection_frame, style="TFrame")
        conn_grid.pack(fill=tk.X, padx=5, pady=5)

        # Configure grid columns for the connection settings
        conn_grid.columnconfigure(0, weight=1)  # Label column
        conn_grid.columnconfigure(1, weight=3)  # Entry column

        # IP Address row
        ttk.Label(conn_grid, text="IP Address:", style="Status.TLabel").grid(row=0, column=0, sticky="w")
        self.ip_entry = ttk.Entry(conn_grid, width=15)
        self.ip_entry.grid(row=0, column=1, sticky="ew", padx=5)
        self.ip_entry.insert(0, "127.0.0.1")  # Default to localhost

        # Port row
        ttk.Label(conn_grid, text="Port:", style="Status.TLabel").grid(row=1, column=0, sticky="w")
        self.port_entry = ttk.Entry(conn_grid, width=6)
        self.port_entry.grid(row=1, column=1, sticky="ew", padx=5)
        self.port_entry.insert(0, "8080")  # Default port
        
        # Row 5: Trigger button (spans both columns)
        trigger_btn = ttk.Button(
            main_frame,
            text="SEND READY TRIGGER (T)",
            command=self.player.send_ready_trigger,
            style="Accent.TButton"
        )
        trigger_btn.grid(row=5, column=0, columnspan=2, sticky="ew", padx=2, pady=2, ipady=8)
        
        # Row 6: Volume control
        volume_frame = ttk.Frame(main_frame, style="TileFrame.TFrame")
        volume_frame.grid(row=6, column=0, columnspan=2, sticky="ew", padx=2, pady=2)
        
        vol_grid = ttk.Frame(volume_frame, style="TFrame")
        vol_grid.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(vol_grid, text="Volume:", style="Status.TLabel").pack(side=tk.LEFT)
        self.volume_value = ttk.Label(vol_grid, text="100%", width=5, style="StatusActive.TLabel")
        self.volume_value.pack(side=tk.RIGHT)
        
        self.volume_scale = ttk.Scale(
            volume_frame,
            from_=0,
            to=100,
            orient=tk.HORIZONTAL,
            command=self.on_volume_change,
            style="TScale"
        )
        self.volume_scale.set(100)
        self.volume_scale.pack(fill=tk.X, padx=5, pady=(0, 5))

    def on_volume_change(self, value):
        volume = int(float(value))
        self.player.set_volume(volume)
        # Update volume display label
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
            QuestionCategory.GENERAL: [],
            QuestionCategory.AUDIO: [],
            QuestionCategory.PHOTO: [],
            QuestionCategory.COUNTDOWN: [],
        }
        self.category_cycle = cycle([QuestionCategory.GENERAL, QuestionCategory.AUDIO, QuestionCategory.PHOTO])
        self.current_category: QuestionCategory = next(self.category_cycle)
        self.category_indices: Dict[QuestionCategory, int] = {
            QuestionCategory.GENERAL: 0,
            QuestionCategory.AUDIO: 0,
            QuestionCategory.PHOTO: 0,
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
        
        # Light control variables
        self.light_socket: Optional[socket.socket] = None
        self.light_connected: bool = False
        
        # Current video tracking
        self.current_video_path: Optional[str] = None
        self.current_answer: Optional[str] = None
        
        self.setup_gui()
        self.setup_vlc()
        self.load_video_files()
        self.show_landing_screen()
        
    def setup_gui(self) -> None:
    # Main window for video display
        self.root = tk.Tk()
        self.root.attributes('-fullscreen', True)
        self.root.title("Gameshow Video Display")
        
        # Create separate control panel window
        self.control_panel = ControlPanel(self.root, self)
        
        self.landing_frame = ttk.Frame(self.root)
        self.landing_label = ttk.Label(
            self.landing_frame, 
            text=".",
            font=('Arial', 24),
            justify=tk.CENTER
        )
        self.landing_label.pack(expand=True)
        
        self.waiting_frame = ttk.Frame(self.root)
        self.waiting_label = ttk.Label(
            self.waiting_frame,
            text=".",
            font=('Arial', 24),
            justify=tk.CENTER
        )
        self.waiting_label.pack(expand=True)
        
        self.video_frame = ttk.Frame(self.root)
        self.video_widget = ttk.Frame(self.video_frame)
        self.video_widget.pack(fill=tk.BOTH, expand=True)
        
        # Existing keyboard shortcuts
        self.root.bind('<Key>', self.handle_key_press)
        self.root.bind('<Escape>', lambda e: self.root.attributes('-fullscreen', False))
        self.root.bind('f', self.toggle_fullscreen)
        self.root.bind('t', self.send_ready_trigger)
        
        # Add clicker support - specifically for Up and Down arrows
        # These will act exactly like pressing 'n' on the keyboard
        self.root.bind('<Down>', lambda e: self.handle_next())
        self.root.bind('<Up>', lambda e: self.handle_next())
        
        # Also add Page Up/Down as they're common on clickers
        self.root.bind('<Next>', lambda e: self.handle_next())  # Page Down
        self.root.bind('<Prior>', lambda e: self.handle_next()) # Page Up
        
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def send_ready_trigger(self, event=None) -> None:
        """
        Send a ready trigger to the light server.
        This method prepares the game to be ready and sends a signal to the dashboard.
        
        :param event: Optional tkinter event (for keyboard shortcut compatibility)
        """
        if not self.light_connected or not self.light_socket:
            messagebox.showinfo("Not Connected", "Please connect to the light server first")
            return
            
        try:
            # Send a special trigger command to the light server
            command = "DASHBOARD-READY-TRIGGER\r\n"
            self.light_socket.send(command.encode('utf-8'))
            
            # Optional: Update control panel status
            self.control_panel.update_light_sequence_status("Ready Trigger Sent")
            
            # Optional: Log the trigger for debugging
            print("Ready trigger sent to dashboard")
            
            # Optional: Provide visual feedback
            messagebox.showinfo("Ready Trigger", "Ready signal sent to dashboard")
            
        except Exception as e:
            print(f"Error sending ready trigger: {str(e)}")
            self.light_connected = False
            messagebox.showerror("Connection Error", "Failed to send ready trigger")

    def handle_key_press(self, event: tk.Event) -> None:
        """Handle keyboard shortcuts"""
        if event.keysym == 'n':
            self.handle_next()
        elif event.keysym == 's':
            if self.current_state == GameState.PLAYING:
                self.start_countdown()
        elif event.keysym == 'c':
            self.continue_after_second_pause()
        elif event.keysym == 'g':
            self.set_lights_green()
        elif event.keysym == 'r':
            self.set_lights_red()
        elif event.keysym == 't':
            self.send_ready_trigger()  # Add ready trigger to key press handler

    def setup_vlc(self) -> None:
        try:
            vlc_args = [
                '--no-xlib',
                '--aout=directsound',
                '--file-caching=1000'
            ]
            self.instance = vlc.Instance(vlc_args)
            self.media_player = self.instance.media_player_new()
            
            self.media_player.audio_set_volume(self.volume)
            
            self.event_manager = self.media_player.event_manager()
            self.event_manager.event_attach(
                vlc.EventType.MediaPlayerTimeChanged,
                self.on_time_changed
            )
            self.event_manager.event_attach(
                vlc.EventType.MediaPlayerEndReached,
                self.on_media_end
            )
            
            self.event_manager.event_attach(
                vlc.EventType.MediaPlayerAudioDevice,
                self.on_audio_device_change
            )
            self.event_manager.event_attach(
                vlc.EventType.MediaPlayerAudioVolume,
                self.on_volume_change
            )
            
            self.media_player.set_hwnd(self.video_widget.winfo_id())
            self.media_player.set_fullscreen(True)
            
            self.check_audio_setup()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to initialize VLC: {str(e)}")
            self.root.quit()

    def check_audio_setup(self) -> None:
        if self.media_player:
            try:
                audio_devices = self.media_player.audio_output_device_enum()
                if audio_devices:
                    device = audio_devices
                    while device:
                        device = device.contents
                        print(f"Available audio device: {device.device}")
                        if not device.next:
                            break
                        device = device.next
                
                audio_output = self.media_player.audio_output_device_get()
                print(f"Current audio output: {audio_output}")
                
                volume = self.media_player.audio_get_volume()
                print(f"Current volume: {volume}")
                
            except Exception as e:
                print(f"Audio setup check error: {str(e)}")

    def on_audio_device_change(self, event) -> None:
        if self.media_player:
            device = self.media_player.audio_output_device_get()
            print(f"Audio device changed: {device}")

    def on_volume_change(self, event) -> None:
        if self.media_player:
            volume = self.media_player.audio_get_volume()
            print(f"Volume changed: {volume}")

    def set_volume(self, volume: int) -> None:
        self.volume = volume
        if self.media_player:
            self.media_player.audio_set_volume(volume)

    def check_media_tracks(self) -> None:
        if self.media and self.media_player:
            try:
                audio_tracks = self.media_player.audio_get_track_description()
                print("Available audio tracks:", audio_tracks)
                
                current_track = self.media_player.audio_get_track()
                print("Current audio track:", current_track)
                
            except Exception as e:
                print(f"Media tracks check error: {str(e)}")

    def extract_answer_from_filename(self, filename: str) -> str:
        """
        Extract the answer letter from the filename based on the new naming convention.
        Format: NUMBER*_LETTER.ext (e.g., 1*_A.mp4, 445_C.mp4)
        """
        try:
            # Get just the base filename without directory path
            base_filename = os.path.basename(filename)
            
            # Use regex to extract the answer letter
            match = re.search(r'_([A-Da-d])\.', base_filename)
            if match:
                return match.group(1).upper()  # Return uppercase letter
            
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
            # Store the current video path
            self.current_video_path = video_path
            
            # Extract answer from filename and update control panel
            if self.current_state == GameState.PLAYING:
                self.current_answer = self.extract_answer_from_filename(video_path)
                self.control_panel.update_current_answer(self.current_answer)
                print(f"Current video answer: {self.current_answer}")
            else:
                self.current_answer = None
                self.control_panel.update_current_answer("None")
            
            self.media = self.instance.media_new(video_path)
            self.media_player.set_media(self.media)
            self.media_player.play()
            
            # Reset pause flags when starting a new video
            self.first_pause_occurred = False
            self.second_pause_occurred = False
            self.third_pause_occurred = False
            
            self.root.after(1000, self.check_media_tracks)
            
        except Exception as e:
            messagebox.showerror("Error", f"Error playing video: {str(e)}")

    def load_video_files(self) -> None:
        base_folder = 'vid'
        if not os.path.exists(base_folder):
            messagebox.showerror("Error", f"Video folder '{base_folder}' not found!")
            self.root.quit()
            return

        # Load intro video
        visual_folder = os.path.join(base_folder, QuestionCategory.VISUAL.value)
        intro_path = os.path.join(visual_folder, 'intro.mp4')
        if os.path.exists(intro_path):
            self.intro_video_path = intro_path
        else:
            messagebox.showwarning("Warning", "Intro video not found in visual folder!")

        # Load regular category videos
        for category in [QuestionCategory.GENERAL, QuestionCategory.AUDIO, QuestionCategory.PHOTO]:
            category_folder = os.path.join(base_folder, category.value)
            if not os.path.exists(category_folder):
                messagebox.showwarning("Warning", f"Category folder '{category_folder}' not found!")
                continue

            category_files = [
                os.path.join(category_folder, f)
                for f in os.listdir(category_folder)
                if f.lower().endswith(('.mp4', '.avi', '.mov'))
            ]
            category_files.sort()
            self.video_files[category] = category_files

        # Load countdown videos in reverse numerical order
        countdown_folder = os.path.join(base_folder, QuestionCategory.COUNTDOWN.value)
        if os.path.exists(countdown_folder):
            countdown_files = []
            for i in range(20, 0, -1):  # From 20 down to 1
                file_name = f"{i}.mp4"
                file_path = os.path.join(countdown_folder, file_name)
                if os.path.exists(file_path):
                    countdown_files.append(file_path)
                else:
                    messagebox.showwarning("Warning", f"Countdown video {file_name} not found!")
            self.video_files[QuestionCategory.COUNTDOWN] = countdown_files

    def play_intro_video(self) -> None:
        if not self.intro_video_path:
            self.show_waiting_screen()
            return
            
        try:
            # Start dance lights when intro starts
            self.start_dance_lights()
            
            self.media = self.instance.media_new(self.intro_video_path)
            self.media_player.set_media(self.media)
            self.media_player.play()
            self.current_state = GameState.INTRO
            self.control_panel.update_status(self.current_state)
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
        if self.current_state == GameState.INTRO:
            # Stop dance lights when intro ends
            self.stop_dance_lights()
            self.all_lights_off()
            
            self.root.after(100, self.show_waiting_screen)
        elif self.current_state == GameState.COUNTDOWN:
            self.root.after(100, self.play_next_countdown_video)

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
        """Send the current video's answer to the light server"""
        if not self.light_connected or not self.light_socket or not self.current_answer:
            print("Cannot send answer: not connected or no answer available")
            return

        try:
            # Format the answer command
            command = f"awns_{self.current_answer}\r\n"
            self.light_socket.send(command.encode('utf-8'))
            
            # Update status
            self.control_panel.update_light_sequence_status(f"Answer {self.current_answer} sent")
            print(f"Sent answer command: {command.strip()}")
        except Exception as e:
            print(f"Error sending answer: {str(e)}")
            self.light_connected = False

    def on_time_changed(self, event) -> None:
        """When video time changes, handle pauses and send commands at appropriate times"""
        if not self.media_player or self.current_state == GameState.INTRO:
            return
            
        current_time = self.media_player.get_time()
        
        if not self.first_pause_occurred and current_time >= 5000:
            # First pause at 5 seconds - pause the video
            self.media_player.set_pause(1)
            self.first_pause_occurred = True
            
            # Send light command at first pause (RED)
            if self.light_connected and self.light_socket:
                try:
                    # Use exact command format with CRLF
                    command = "EMS-LEDS-X|10|0|0|\r\n"  # RED command
                    self.light_socket.send(command.encode('utf-8'))
                    self.control_panel.update_light_sequence_status("RED (First Pause)")
                    print(f"First pause - Sent RED command")
                except Exception as e:
                    print(f"Error sending command: {str(e)}")
        
        elif not self.second_pause_occurred and current_time >= 10000:
            self.media_player.set_pause(1)
            self.second_pause_occurred = True
            
        elif not self.third_pause_occurred and current_time >= 20000:
            self.media_player.set_pause(1)
            self.third_pause_occurred = True
            
            # When third pause occurs, send the answer to the server
            if self.current_state == GameState.PLAYING and self.current_answer:
                self.send_answer_to_server()

    def handle_next(self) -> None:
        """Handle Next button press, ensuring light command is sent at first pause"""
        if self.current_state == GameState.LANDING:
            self.show_video_screen()
            self.play_intro_video()
        elif self.current_state == GameState.WAITING_TO_START:
            self.start_game()
        elif self.current_state in [GameState.PLAYING, GameState.COUNTDOWN]:
            # If at first pause, send the READY trigger and RED light command
            if self.first_pause_occurred and not self.second_pause_occurred:
                # First, send the ready trigger
                if self.light_connected and self.light_socket:
                    try:
                        # Send the ready trigger
                        ready_command = "DASHBOARD-READY-TRIGGER\r\n"
                        self.light_socket.send(ready_command.encode('utf-8'))
                        self.control_panel.update_light_sequence_status("Ready Trigger Sent")
                        print("Ready trigger sent at first pause")
                        
                        # Then send the RED command
                        red_command = "EMS-LEDS-X|10|0|0|\r\n"
                        self.light_socket.send(red_command.encode('utf-8'))
                        print(f"Next button - Sent RED command")
                    except Exception as e:
                        print(f"Error sending commands: {str(e)}")
                        
            # If at third pause (end of video), send the answer
            elif self.third_pause_occurred:
                # Send the answer command for the current video
                if self.current_state == GameState.PLAYING and self.current_answer:
                    self.send_answer_to_server()
            
            # Resume play immediately
            self.resume_play()

    def continue_after_second_pause(self) -> None:
        if (self.current_state in [GameState.PLAYING, GameState.COUNTDOWN] and 
            self.second_pause_occurred and not self.third_pause_occurred):
            if self.media_player:
                self.media_player.play()

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

    # Light control methods
    def connect_to_light_server(self) -> None:
        """Connect to the light control server"""
        if self.light_connected:
            # Already connected, disconnect first
            self.disconnect_from_light_server()
            
        try:
            # Get connection details from UI
            ip = self.control_panel.ip_entry.get()
            port = int(self.control_panel.port_entry.get())
            
            # Create socket
            self.light_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.light_socket.connect((ip, port))
            
            # Set timeout for operations
            self.light_socket.settimeout(2.0)
            
            # Wait for server's "Connected" message
            response = self.light_socket.recv(1024).decode('utf-8')
            if "Connected" in response:
                self.light_connected = True
                self.control_panel.update_light_status(True, f"{ip}:{port}")
                
                # Test connection with a ping
                try:
                    self.light_socket.send("PING\r\n".encode('utf-8'))
                    print("Sent PING to verify connection")
                except Exception as e:
                    print(f"Warning: Could not send PING: {str(e)}")
                
                # Add a recurring check to verify the connection is still alive
                self.root.after(5000, self.check_light_connection)
            else:
                messagebox.showerror("Connection Error", 
                                     "Connected to server but received unexpected response")
                self.disconnect_from_light_server()
                
        except Exception as e:
            messagebox.showerror("Connection Error", f"Failed to connect to light server: {str(e)}")
            self.disconnect_from_light_server()
    
    def disconnect_from_light_server(self) -> None:
        """Disconnect from the light control server"""
        if self.light_socket:
            try:
                self.light_socket.close()
            except:
                pass
            
        self.light_socket = None
        self.light_connected = False
        self.control_panel.update_light_status(False, "Disconnected")
    
    def check_light_connection(self) -> None:
        """Periodically check if the light server connection is still alive"""
        if not self.light_connected or not self.light_socket:
            return
            
        try:
            # Try to send a simple command to check connection
            self.light_socket.send("PING\r\n".encode('utf-8'))
            
            # Schedule next check
            self.root.after(5000, self.check_light_connection)
        except Exception as e:
            print(f"Connection check failed: {str(e)}")
            # Connection failed, update status
            self.disconnect_from_light_server()
    
    def send_light_command(self, command: str) -> bool:
        """Simple function to send a command to the light server"""
        if not self.light_connected or not self.light_socket:
            print("Not connected to light server")
            return False
            
        try:
            # Add CRLF line ending if not already present
            if not command.endswith('\r\n'):
                command += '\r\n'
                
            self.light_socket.send(command.encode('utf-8'))
            print(f"Sent light command: {command.strip()}")
            return True
        except Exception as e:
            print(f"Error sending light command: {str(e)}")
            self.light_connected = False
            return False
    
    def set_lights_green(self) -> None:
        """Set all lights to GREEN"""
        if not self.light_connected or not self.light_socket:
            messagebox.showinfo("Not Connected", "Please connect to the light server first")
            return
            
        try:
            command = "EMS-LEDS-X|0|10|0|\r\n"  # Green command
            self.light_socket.send(command.encode('utf-8'))
            self.control_panel.update_light_sequence_status("GREEN (Manual)")
            print("All lights set to GREEN")
        except Exception as e:
            print(f"Error sending green command: {str(e)}")
            self.light_connected = False
            
    def set_lights_red(self) -> None:
        """Set all lights to RED"""
        if not self.light_connected or not self.light_socket:
            messagebox.showinfo("Not Connected", "Please connect to the light server first")
            return
            
        try:
            command = "EMS-LEDS-X|10|0|0|\r\n"  # Red command
            self.light_socket.send(command.encode('utf-8'))
            self.control_panel.update_light_sequence_status("RED (Manual)")
            print("All lights set to RED")
        except Exception as e:
            print(f"Error sending red command: {str(e)}")
            self.light_connected = False
    
    def start_dance_lights(self) -> None:
        """Start the dance lights effect"""
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
        """Stop the dance lights effect"""
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
        """Turn all lights off"""
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
        # Turn off all lights before exiting
        if self.light_connected:
            self.stop_dance_lights()
            self.all_lights_off()
            self.disconnect_from_light_server()
            
        if self.media_player:
            self.media_player.stop()
        self.root.destroy()
        
    def run(self) -> None:
        self.root.mainloop()

if __name__ == "__main__":
    try:
        player = GameshowPlayer()
        player.run()
    except Exception as e:
        print(f"Fatal error: {str(e)}")
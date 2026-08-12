import socket
import threading
import tkinter as tk
from tkinter import scrolledtext, ttk, messagebox
from datetime import datetime
import time
import random
import re
import win32pipe
import win32file
import pywintypes
import json

class LeaderboardConnector:
    """
    Class to enable direct communication with the leaderboard via named pipe.
    """
    def __init__(self):
        self.pipe_name = r'\\.\pipe\gameshow_pipe'
        self.connected = False
    
    def send_to_leaderboard(self, command):
        """Send a command to the leaderboard via named pipe"""
        try:
            pipe = win32file.CreateFile(
                self.pipe_name,
                win32file.GENERIC_WRITE,
                0, None,
                win32file.OPEN_EXISTING,
                0, None
            )
            win32file.WriteFile(pipe, command.encode())
            win32file.CloseHandle(pipe)
            return True
        except Exception as e:
            print(f"Failed to send to leaderboard: {e}")
            return False

class CompactGameServerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("GameServer   0 Connections")
        self.root.geometry("900x600")
        self.root.configure(bg="#121212")
        
        # Variables
        self.server_socket = None
        self.client_connections = []
        self.server_active = False
        self.Str = ""
        self.client_lock = threading.Lock()
        self.color_sequence_active = False
        self.dance_lights_active = False
        self.dance_lights_job = None
        self.correct_answer = None
        
        self.leaderboard_connector = LeaderboardConnector()
        
        self.configure_styles()
        
        # Main container with a 2-column grid layout
        main_container = tk.Frame(root, bg="#121212")
        main_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        main_container.columnconfigure(0, weight=1)  # Left side (LEDs & Log)
        main_container.columnconfigure(1, weight=1)  # Right side (Answer & Points)
        main_container.rowconfigure(0, weight=0)     # Server Controls
        main_container.rowconfigure(1, weight=1)     # Main Content
        main_container.rowconfigure(2, weight=0)     # Bottom Controls
        
        # === TOP ROW: Server controls ===
        top_frame = tk.Frame(main_container, bg="#121212", pady=5)
        top_frame.grid(row=0, column=0, columnspan=2, sticky="ew")
        
        port_frame = tk.Frame(top_frame, bg="#121212")
        port_frame.pack(side=tk.LEFT, fill=tk.Y)
        
        tk.Label(port_frame, text="Port:", bg="#121212", fg="#E0E0E0", 
                font=("Segoe UI", 11, "bold")).pack(side=tk.LEFT, padx=(0, 5))
        
        self.edt_server_port = tk.Entry(port_frame, width=8, font=("Segoe UI", 11),
                                       bg="#2D2D2D", fg="#E0E0E0", insertbackground="#E0E0E0",
                                       relief="flat", bd=0)
        self.edt_server_port.insert(0, "8080")
        self.edt_server_port.pack(side=tk.LEFT, padx=(0, 20), ipady=3)
        self.create_entry_highlight(self.edt_server_port, "#2D2D2D", "#4287f5")
        
        button_frame = tk.Frame(top_frame, bg="#121212")
        button_frame.pack(side=tk.LEFT, fill=tk.Y)
        
        self.bbtn_start_server = self.create_glowing_button(
            button_frame, "Start Server", "#27ae60", "#2ecc71", "#219150",
            self.bbtn_start_server_click)
        self.bbtn_start_server.pack(side=tk.LEFT, padx=(0, 10))
        
        self.server_status_frame = tk.Frame(button_frame, bg="#121212")
        self.server_status_frame.pack(side=tk.LEFT, padx=(0, 10))
        
        self.server_status = tk.Canvas(self.server_status_frame, width=20, height=20, 
                                     bg="#121212", highlightthickness=0)
        self.server_status.pack()
        
        self.server_status.create_oval(2, 2, 18, 18, fill="#e74c3c", outline="#ff6b6b", width=1, tags="status")
        self.server_status_color = "#e74c3c"
        
        self.bbtn_stop_server = self.create_glowing_button(
            button_frame, "Stop Server", "#c0392b", "#e74c3c", "#a93226",
            self.bbtn_stop_server_click)
        self.bbtn_stop_server.pack(side=tk.LEFT)
        
        # === LEFT COLUMN ===
        left_column = tk.Frame(main_container, bg="#121212")
        left_column.grid(row=1, column=0, sticky="nsew", padx=(0, 5), pady=5)
        
        left_column.rowconfigure(0, weight=1)  # LED Controls
        left_column.rowconfigure(1, weight=1)  # Log
        
        led_frame = tk.LabelFrame(left_column, text="LED Controls", 
                               bg="#121212", fg="#E0E0E0", 
                               font=("Segoe UI", 10, "bold"))
        led_frame.grid(row=0, column=0, sticky="nsew", padx=0, pady=(0, 5))
        self.create_led_panel(led_frame)
        
        log_frame = tk.LabelFrame(left_column, text="Server Log", 
                               bg="#121212", fg="#E0E0E0", 
                               font=("Segoe UI", 10, "bold"))
        log_frame.grid(row=1, column=0, sticky="nsew", padx=0, pady=(5, 0))
        
        self.memo1 = scrolledtext.ScrolledText(log_frame, width=35, height=10,
                                           font=("Consolas", 9), 
                                           bg="#1E1E1E", fg="#E0E0E0",
                                           insertbackground="#E0E0E0")
        self.memo1.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        log_buttons_frame = tk.Frame(log_frame, bg="#121212")
        log_buttons_frame.pack(fill=tk.X, padx=5, pady=(0, 5))
        
        self.bit_btn2 = self.create_glowing_button(
            log_buttons_frame, "Clear Log", "#2D2D2D", "#3D3D3D", "#1D1D1D",
            self.bit_btn2_click)
        self.bit_btn2.pack(side=tk.LEFT)
        
        # === RIGHT COLUMN: Answer Controls & Points Side by Side ===
        right_column = tk.Frame(main_container, bg="#121212")
        right_column.grid(row=1, column=1, sticky="nsew", padx=(5, 0), pady=5)
        
        # Configure right_column for two columns side by side
        right_column.columnconfigure(0, weight=1)  # Answer controls
        right_column.columnconfigure(1, weight=1)  # Points controls
        right_column.rowconfigure(0, weight=1)     # Single row for both
        
        # Answer Controls
        answer_frame = tk.LabelFrame(right_column, text="Answer Controls", 
                                 bg="#121212", fg="#E0E0E0", 
                                 font=("Segoe UI", 10, "bold"))
        answer_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 5), pady=5)
        self.create_answer_panel(answer_frame)
        
        # Points Controls
        points_frame = tk.LabelFrame(right_column, text="Leaderboard Points", 
                                  bg="#121212", fg="#E0E0E0", 
                                  font=("Segoe UI", 10, "bold"))
        points_frame.grid(row=0, column=1, sticky="nsew", padx=(5, 0), pady=5)
        self.create_points_panel(points_frame)
        
        # === BOTTOM ROW: Controls ===
        bottom_frame = tk.Frame(main_container, bg="#121212", pady=5)
        bottom_frame.grid(row=2, column=0, columnspan=2, sticky="ew")
        
        custom_frame = bottom_frame  # For compatibility with original code
        
        self.ready_frame = tk.Frame(custom_frame, bg="#121212", bd=2, relief="groove")
        self.ready_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        
        self.ready_label = tk.Label(self.ready_frame, text="READY", fg="#E0E0E0", bg="#121212",
                                 font=("Arial", 14, "bold"))
        self.ready_label.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        self.bbtn_send_to_active = self.create_glowing_button(
            bottom_frame, "Send Ready", "#2980b9", "#3498db", "#1c6ea0",
            self.bbtn_send_to_active_connections_click)
        self.bbtn_send_to_active.pack(side=tk.LEFT, padx=(0, 10))
        
        self.bbtn_dance_lights = self.create_glowing_button(
            bottom_frame, "Dance Lights", "#9b59b6", "#8e44ad", "#7d3c98",
            self.bbtn_dance_lights_click)
        self.bbtn_dance_lights.pack(side=tk.LEFT, padx=(0, 10))

        # New "Award Points" button
        self.bbtn_award_points = self.create_glowing_button(
            bottom_frame, "Award Points", "#27ae60", "#2ecc71", "#219150",
            self.award_points)
        self.bbtn_award_points.pack(side=tk.LEFT, padx=(0, 10))
        
        self.bit_btn1 = self.create_glowing_button(
            bottom_frame, "Close", "#c0392b", "#e74c3c", "#a93226",
            self.bit_btn1_click)
        self.bit_btn1.pack(side=tk.LEFT)
        
        self.animate_status_glow()
        self.timer1_timer()
    
    # All other methods remain unchanged to preserve functionality
    def configure_styles(self):
        self.style = ttk.Style()
        if 'clam' in self.style.theme_names():
            self.style.theme_use("clam")
    
    def create_entry_highlight(self, entry, normal_color, focus_color):
        entry.config(highlightthickness=1, highlightbackground="#333333", highlightcolor=focus_color)
        entry.bind("<FocusIn>", lambda e: entry.config(highlightbackground=focus_color))
        entry.bind("<FocusOut>", lambda e: entry.config(highlightbackground="#333333"))
    
    def create_glowing_button(self, parent, text, color, hover_color, active_color, command):
        button = tk.Button(parent, text=text, font=("Segoe UI", 10, "bold"),
                         bg=color, fg="#FFFFFF", 
                         activebackground=active_color, activeforeground="#FFFFFF",
                         relief="flat", bd=0, padx=10, pady=4,
                         command=command)
        button.bind("<Enter>", lambda e: button.config(bg=hover_color))
        button.bind("<Leave>", lambda e: button.config(bg=color))
        return button
    
    def create_led_button(self, parent, text, color, hover_color, active_color, row, column, command):
        button = tk.Button(parent, text=text, font=("Segoe UI", 10, "bold"),
                         bg=color, fg="#FFFFFF", 
                         activebackground=active_color, activeforeground="#FFFFFF",
                         relief="flat", bd=0, width=5, height=1,
                         command=command)
        button.grid(row=row, column=column, padx=2, pady=2)
        button.bind("<Enter>", lambda e: button.config(bg=hover_color))
        button.bind("<Leave>", lambda e: button.config(bg=color))
        return button
    
    def create_glowing_label(self, parent, text, color, row, column):
        label = tk.Label(parent, text=text, font=("Segoe UI", 10, "bold"),
                       bg="#121212", fg=color)
        label.grid(row=row, column=column, padx=3)
        return label
    
    def create_led_panel(self, parent):
        led_container = tk.Frame(parent, bg="#121212", padx=5, pady=5)
        led_container.pack(fill=tk.BOTH, expand=True)
        grid_frame = tk.Frame(led_container, bg="#121212")
        grid_frame.pack(fill=tk.BOTH, expand=True)
        tk.Label(grid_frame, text="", width=3, bg="#121212").grid(row=0, column=0)
        self.create_glowing_label(grid_frame, "Red", "#c0392b", 0, 1)
        self.create_glowing_label(grid_frame, "Green", "#27ae60", 0, 2)
        self.create_glowing_label(grid_frame, "Blue", "#2980b9", 0, 3)
        labels = ["A", "B", "C", "D", "ALL"]
        for i, label in enumerate(labels):
            tk.Label(grid_frame, text=label, bg="#121212", fg="#E0E0E0",
                   font=("Segoe UI", 10, "bold")).grid(row=i+1, column=0, padx=3, pady=2, sticky="e")
        self.button_red_a = self.create_led_button(grid_frame, "A", "#c0392b", "#e74c3c", "#a93226", 1, 1, lambda: self.button_click("EMS-LEDS-A|10|0|0|"))
        self.button_red_b = self.create_led_button(grid_frame, "B", "#c0392b", "#e74c3c", "#a93226", 2, 1, lambda: self.button_click("EMS-LEDS-B|10|0|0|"))
        self.button_red_c = self.create_led_button(grid_frame, "C", "#c0392b", "#e74c3c", "#a93226", 3, 1, lambda: self.button_click("EMS-LEDS-C|10|0|0|"))
        self.button_red_d = self.create_led_button(grid_frame, "D", "#c0392b", "#e74c3c", "#a93226", 4, 1, lambda: self.button_click("EMS-LEDS-D|10|0|0|"))
        self.button_red_all = self.create_led_button(grid_frame, "ALL", "#c0392b", "#e74c3c", "#a93226", 5, 1, lambda: self.button_click("EMS-LEDS-X|10|0|0|"))
        self.button_green_a = self.create_led_button(grid_frame, "A", "#27ae60", "#2ecc71", "#219150", 1, 2, lambda: self.button_click("EMS-LEDS-A|0|10|0|"))
        self.button_green_b = self.create_led_button(grid_frame, "B", "#27ae60", "#2ecc71", "#219150", 2, 2, lambda: self.button_click("EMS-LEDS-B|0|10|0|"))
        self.button_green_c = self.create_led_button(grid_frame, "C", "#27ae60", "#2ecc71", "#219150", 3, 2, lambda: self.button_click("EMS-LEDS-C|0|10|0|"))
        self.button_green_d = self.create_led_button(grid_frame, "D", "#27ae60", "#2ecc71", "#219150", 4, 2, lambda: self.button_click("EMS-LEDS-D|0|10|0|"))
        self.button_green_all = self.create_led_button(grid_frame, "ALL", "#27ae60", "#2ecc71", "#219150", 5, 2, lambda: self.button_click("EMS-LEDS-X|0|10|0|"))
        self.button_blue_a = self.create_led_button(grid_frame, "A", "#2980b9", "#3498db", "#1c6ea0", 1, 3, lambda: self.button_click("EMS-LEDS-A|0|0|10|"))
        self.button_blue_b = self.create_led_button(grid_frame, "B", "#2980b9", "#3498db", "#1c6ea0", 2, 3, lambda: self.button_click("EMS-LEDS-B|0|0|10|"))
        self.button_blue_c = self.create_led_button(grid_frame, "C", "#2980b9", "#3498db", "#1c6ea0", 3, 3, lambda: self.button_click("EMS-LEDS-C|0|0|10|"))
        self.button_blue_d = self.create_led_button(grid_frame, "D", "#2980b9", "#3498db", "#1c6ea0", 4, 3, lambda: self.button_click("EMS-LEDS-D|0|0|10|"))
        self.button_blue_all = self.create_led_button(grid_frame, "ALL", "#2980b9", "#3498db", "#1c6ea0", 5, 3, lambda: self.button_click("EMS-LEDS-X|0|0|10|"))
        self.button_all_off = self.create_glowing_button(grid_frame, "ALL OFF", "#c0392b", "#e74c3c", "#a93226", lambda: self.button_click("EMS-LEDS-X|0|0|0|"))
        self.button_all_off.grid(row=6, column=1, columnspan=3, padx=2, pady=4, sticky="ew")
    
    def create_answer_panel(self, parent):
        answer_container = tk.Frame(parent, bg="#121212", padx=5, pady=5)
        answer_container.pack(fill=tk.BOTH, expand=True)
        answer_selection_frame = tk.Frame(answer_container, bg="#121212")
        answer_selection_frame.pack(fill=tk.X, pady=5)
        tk.Label(answer_selection_frame, text="Correct Answer:", bg="#121212", fg="#FFFFFF",
               font=("Segoe UI", 11)).pack(side=tk.LEFT, padx=(0, 10))
        answer_options_frame = tk.Frame(answer_selection_frame, bg="#121212")
        answer_options_frame.pack(side=tk.LEFT)
        self.correct_answer_var = tk.StringVar(value="")
        self.answer_buttons = {}
        for option in ["A", "B", "C", "D"]:
            btn = self.create_answer_button(answer_options_frame, option, self.correct_answer_var)
            btn.pack(side=tk.LEFT, padx=5)
            self.answer_buttons[option] = btn
        points_frame = tk.Frame(answer_container, bg="#121212")
        points_frame.pack(fill=tk.X, pady=5)
        tk.Label(points_frame, text="Correct Points:", bg="#121212", fg="#FFFFFF",
               font=("Segoe UI", 10)).grid(row=0, column=0, padx=(0, 5), pady=2, sticky="w")
        self.correct_points_entry = tk.Entry(points_frame, width=5, font=("Segoe UI", 10),
                                         bg="#2D2D2D", fg="#E0E0E0", insertbackground="#E0E0E0")
        self.correct_points_entry.insert(0, "100")
        self.correct_points_entry.grid(row=0, column=1, padx=5, pady=2)
        self.create_entry_highlight(self.correct_points_entry, "#2D2D2D", "#4287f5")
        tk.Label(points_frame, text="Incorrect Points:", bg="#121212", fg="#FFFFFF",
               font=("Segoe UI", 10)).grid(row=1, column=0, padx=(0, 5), pady=2, sticky="w")
        self.incorrect_points_entry = tk.Entry(points_frame, width=5, font=("Segoe UI", 10),
                                           bg="#2D2D2D", fg="#E0E0E0", insertbackground="#E0E0E0")
        self.incorrect_points_entry.insert(0, "-50")
        self.incorrect_points_entry.grid(row=1, column=1, padx=5, pady=2)
        self.create_entry_highlight(self.incorrect_points_entry, "#2D2D2D", "#4287f5")
        action_frame = tk.Frame(answer_container, bg="#121212")
        action_frame.pack(fill=tk.X, pady=10)
        self.generate_commands_btn = self.create_glowing_button(action_frame, "Generate Commands", "#2980b9", "#3498db", "#1c6ea0", self.generate_answer_commands)
        self.generate_commands_btn.pack(side=tk.LEFT, padx=5)
        command_frame = tk.LabelFrame(answer_container, text="Generated Commands", bg="#121212", fg="#E0E0E0", font=("Segoe UI", 10, "bold"))
        command_frame.pack(fill=tk.X, pady=5)
        correct_frame = tk.Frame(command_frame, bg="#121212")
        correct_frame.pack(fill=tk.X, pady=5)
        tk.Label(correct_frame, text="Correct:", bg="#121212", fg="#FFFFFF", font=("Segoe UI", 9)).pack(side=tk.LEFT, padx=5)
        self.correct_command_entry = tk.Entry(correct_frame, font=("Segoe UI", 9), bg="#2D2D2D", fg="#E0E0E0")
        self.correct_command_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        self.create_entry_highlight(self.correct_command_entry, "#2D2D2D", "#4287f5")
        self.send_correct_btn = self.create_glowing_button(correct_frame, "Send", "#27ae60", "#2ecc71", "#219150", self.send_correct_command)
        self.send_correct_btn.pack(side=tk.LEFT, padx=5)
        incorrect_frame = tk.Frame(command_frame, bg="#121212")
        incorrect_frame.pack(fill=tk.X, pady=5)
        tk.Label(incorrect_frame, text="Incorrect:", bg="#121212", fg="#FFFFFF", font=("Segoe UI", 9)).pack(side=tk.LEFT, padx=5)
        self.incorrect_command_entry = tk.Entry(incorrect_frame, font=("Segoe UI", 9), bg="#2D2D2D", fg="#E0E0E0")
        self.incorrect_command_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        self.create_entry_highlight(self.incorrect_command_entry, "#2D2D2D", "#4287f5")
        self.send_incorrect_btn = self.create_glowing_button(incorrect_frame, "Send", "#c0392b", "#e74c3c", "#a93226", self.send_incorrect_command)
        self.send_incorrect_btn.pack(side=tk.LEFT, padx=5)

    def create_answer_button(self, parent, text, variable):
        button_frame = tk.Frame(parent, bg="#121212", bd=2, relief="raised", width=40, height=40)
        button_frame.pack_propagate(False)
        button = tk.Radiobutton(button_frame, text=text, variable=variable, value=text, font=("Segoe UI", 12, "bold"), bg="#1E1E1E", fg="#FFFFFF", selectcolor="#2980b9", activebackground="#2980b9", activeforeground="#FFFFFF", command=lambda v=text: self.on_correct_answer_selected(v))
        button.pack(fill=tk.BOTH, expand=True)
        return button_frame

    def on_correct_answer_selected(self, value):
        self.correct_answer = value
        self.memo1.insert(tk.END, f"Correct answer set to: {value}\n")
        self.memo1.see(tk.END)

    def generate_answer_commands(self):
        """Generate commands based on answers in the log file."""
        answer_counts = {}
        try:
            log_content = self.memo1.get(1.0, tk.END)
            # Updated regex to match @QUESTION:TABLE:ANSWER
            pattern = r'@(\d+):(\d+):([A-D])'
            matches = re.findall(pattern, log_content)
            
            for question, table, answer in matches:
                # Optionally, filter by current question if managed elsewhere
                key = (question, table)  # Group by question and table
                if key not in answer_counts:
                    answer_counts[key] = {'A': 0, 'B': 0, 'C': 0, 'D': 0}
                answer_counts[key][answer] += 1
            
            commands = []
            for (question, table), counts in answer_counts.items():
                most_common_answer = max(counts.items(), key=lambda x: x[1])[0]
                # Example command: "*1*2+D" (assuming table 2, answer D for question 1)
                # Adjust command format as needed based on your requirements
                command = f"*{question}*{table}+{most_common_answer}"
                commands.append(command)
            
            return commands
        except Exception as e:
            self.log_message(f"Error generating answer commands: {str(e)}")
            return []

    def send_correct_command(self):
        command = self.correct_command_entry.get().strip()
        if not command:
            messagebox.showinfo("No Command", "No command to send.")
            return
        result = self.send_points_command(command)
        if result:
            messagebox.showinfo("Success", "Correct points command sent successfully")

    def send_incorrect_command(self):
        command = self.incorrect_command_entry.get().strip()
        if not command:
            messagebox.showinfo("No Command", "No command to send.")
            return
        result = self.send_points_command(command)
        if result:
            messagebox.showinfo("Success", "Incorrect points command sent successfully")
    
    def create_points_panel(self, parent):
        points_container = tk.Frame(parent, bg="#121212")
        points_container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        tables_frame = tk.LabelFrame(points_container, text="Tables", bg="#121212", fg="#E0E0E0", font=("Segoe UI", 10, "bold"))
        tables_frame.pack(fill=tk.X, pady=(0, 5))
        tables_container = tk.Frame(tables_frame, bg="#121212")
        tables_container.pack(fill=tk.X, padx=5, pady=5)
        self.table_vars = {}
        self.table_buttons = {}
        for i in range(1, 16):
            var = tk.BooleanVar()
            self.table_vars[i] = var
            row = (i-1) // 5
            col = (i-1) % 5
            button_frame = tk.Frame(tables_container, bg="#121212", highlightthickness=2, highlightbackground="#333333", width=40, height=30)
            button_frame.grid(row=row, column=col, padx=4, pady=4)
            button_frame.pack_propagate(False)
            number_label = tk.Label(button_frame, text=str(i), bg="#1E1E1E", fg="#E0E0E0", font=("Segoe UI", 11, "bold"), width=3, height=1)
            number_label.pack(fill=tk.BOTH, expand=True)
            self.table_buttons[i] = {'frame': button_frame, 'label': number_label}
            def toggle_handler(event, table_id=i):
                self.toggle_table(table_id)
            number_label.bind("<Button-1>", toggle_handler)
            button_frame.bind("<Button-1>", toggle_handler)
        quick_frame = tk.Frame(tables_frame, bg="#121212")
        quick_frame.pack(fill=tk.X, padx=5, pady=(0, 5))
        select_all_btn = self.create_glowing_button(quick_frame, "Select All", "#2980b9", "#3498db", "#1c6ea0", self.select_all_tables)
        select_all_btn.pack(side=tk.LEFT, padx=2)
        clear_all_btn = self.create_glowing_button(quick_frame, "Clear All", "#2980b9", "#3498db", "#1c6ea0", self.clear_all_tables)
        clear_all_btn.pack(side=tk.LEFT, padx=2)
        points_frame = tk.LabelFrame(points_container, text="Points Adjustment", bg="#121212", fg="#E0E0E0", font=("Segoe UI", 10, "bold"))
        points_frame.pack(fill=tk.X, pady=5)
        points_entry_frame = tk.Frame(points_frame, bg="#121212")
        points_entry_frame.pack(fill=tk.X, padx=5, pady=5)
        tk.Label(points_entry_frame, text="Points:", bg="#121212", fg="#FFFFFF", font=("Segoe UI", 9)).pack(side=tk.LEFT, padx=(0, 5))
        self.points_entry = tk.Entry(points_entry_frame, width=8, font=("Segoe UI", 10), bg="#2D2D2D", fg="#E0E0E0", insertbackground="#E0E0E0")
        self.points_entry.insert(0, "100")
        self.points_entry.pack(side=tk.LEFT, padx=2)
        self.create_entry_highlight(self.points_entry, "#2D2D2D", "#4287f5")
        action_frame = tk.Frame(points_frame, bg="#121212")
        action_frame.pack(fill=tk.X, padx=5, pady=(0, 5))
        add_btn = self.create_glowing_button(action_frame, "+Points", "#27ae60", "#2ecc71", "#219150", self.add_points)
        add_btn.pack(side=tk.LEFT, padx=2)
        subtract_btn = self.create_glowing_button(action_frame, "-Points", "#c0392b", "#e74c3c", "#a93226", self.subtract_points)
        subtract_btn.pack(side=tk.LEFT, padx=2)
        custom_frame = tk.LabelFrame(points_container, text="Custom Command", bg="#121212", fg="#E0E0E0", font=("Segoe UI", 10, "bold"))
        custom_frame.pack(fill=tk.X, pady=(5, 0))
        custom_entry_frame = tk.Frame(custom_frame, bg="#121212")
        custom_entry_frame.pack(fill=tk.X, padx=5, pady=5)
        cmd_label = tk.Label(custom_entry_frame, text="Cmd:", bg="#121212", fg="#FFFFFF", font=("Segoe UI", 9))
        cmd_label.pack(side=tk.LEFT, padx=(0, 5))
        self.custom_entry = tk.Entry(custom_entry_frame, width=15, font=("Segoe UI", 10), bg="#2D2D2D", fg="#E0E0E0", insertbackground="#E0E0E0")
        self.custom_entry.insert(0, "*1*2+100")
        self.custom_entry.pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)
        self.create_entry_highlight(self.custom_entry, "#2D2D2D", "#4287f5")
        send_custom_btn = self.create_glowing_button(custom_entry_frame, "Send", "#2980b9", "#3498db", "#1c6ea0", self.send_custom_command)
        send_custom_btn.pack(side=tk.LEFT, padx=2)
        help_text = "Format: *1*2+100, *3-50, *X+75"
        help_label = tk.Label(custom_frame, text=help_text, justify=tk.LEFT, bg="#121212", fg="#AAAAAA", font=("Segoe UI", 8, "italic"))
        help_label.pack(anchor='w', padx=5, pady=(0, 5))

    def toggle_table(self, table_id):
        current_state = self.table_vars[table_id].get()
        new_state = not current_state
        self.table_vars[table_id].set(new_state)
        button = self.table_buttons[table_id]
        if new_state:
            button['frame'].config(highlightbackground="#4287f5")
            button['label'].config(bg="#2980b9", fg="#FFFFFF")
        else:
            button['frame'].config(highlightbackground="#333333")
            button['label'].config(bg="#1E1E1E", fg="#E0E0E0")

    def select_all_tables(self):
        for table_id in self.table_vars:
            self.table_vars[table_id].set(True)
            button = self.table_buttons[table_id]
            button['frame'].config(highlightbackground="#4287f5")
            button['label'].config(bg="#2980b9", fg="#FFFFFF")

    def clear_all_tables(self):
        for table_id in self.table_vars:
            self.table_vars[table_id].set(False)
            button = self.table_buttons[table_id]
            button['frame'].config(highlightbackground="#333333")
            button['label'].config(bg="#1E1E1E", fg="#E0E0E0")

    def get_selected_tables(self):
        return [str(table) for table, var in self.table_vars.items() if var.get()]
    
    def add_points(self):
        selected_tables = self.get_selected_tables()
        if not selected_tables:
            messagebox.showwarning("No Tables Selected", "Please select at least one table.")
            return
        try:
            points = int(self.points_entry.get())
            if points <= 0:
                messagebox.showwarning("Invalid Points", "Please enter a positive number of points.")
                return
            command = "*" + "*".join(selected_tables) + "+" + str(points)
            result = self.send_points_command(command)
            if result:
                messagebox.showinfo("Success", f"Added {points} points to {len(selected_tables)} tables")
        except ValueError:
            messagebox.showerror("Invalid Points", "Please enter a valid number for points.")
    
    def subtract_points(self):
        selected_tables = self.get_selected_tables()
        if not selected_tables:
            messagebox.showwarning("No Tables Selected", "Please select at least one table.")
            return
        try:
            points = int(self.points_entry.get())
            if points <= 0:
                messagebox.showwarning("Invalid Points", "Please enter a positive number of points.")
                return
            command = "*" + "*".join(selected_tables) + "-" + str(points)
            result = self.send_points_command(command)
            if result:
                messagebox.showinfo("Success", f"Subtracted {points} points from {len(selected_tables)} tables")
        except ValueError:
            messagebox.showerror("Invalid Points", "Please enter a valid number for points.")
    
    def send_custom_command(self):
        command = self.custom_entry.get().strip()
        if not command:
            messagebox.showwarning("Empty Command", "Please enter a command.")
            return
        if not re.match(r'^\*[0-9X*]+([-+]\d+)', command):
            messagebox.showerror("Invalid Command", "Command must be in the format: *tables+points or *tables-points")
            return
        result = self.send_points_command(command)
        if result:
            messagebox.showinfo("Success", f"Command '{command}' sent successfully")
    
    def send_points_command(self, command):
        if not command.endswith('\n'):
            command_with_newline = command + '\n'
        else:
            command_with_newline = command
            command = command.rstrip('\n')
        sign = '+' if '+' in command else '-'
        parts = command.split(sign)
        tables = parts[0].replace('*', ' ').strip()
        points = parts[1].strip()
        action = "Adding" if sign == '+' else "Subtracting"
        log_message = f"{action} {points} points to table(s) {tables}"
        leaderboard_success = self.leaderboard_connector.send_to_leaderboard(command)
        with self.client_lock:
            if not self.client_connections:
                self.memo1.insert(tk.END, "No clients connected to send command to\n")
                if leaderboard_success:
                    self.memo1.insert(tk.END, "Command sent to leaderboard only\n")
                self.memo1.see(tk.END)
                return leaderboard_success
            send_count = 0
            failed_clients = []
            for client in list(self.client_connections):
                try:
                    client.send(command_with_newline.encode('utf-8'))
                    send_count += 1
                except Exception as e:
                    failed_clients.append(client)
            for client in failed_clients:
                if client in self.client_connections:
                    self.client_connections.remove(client)
        self.memo1.insert(tk.END, f"{log_message} (sent to {send_count} connections)")
        if leaderboard_success:
            self.memo1.insert(tk.END, " and leaderboard")
        self.memo1.insert(tk.END, "\n")
        if failed_clients:
            self.memo1.insert(tk.END, f"Failed to send to {len(failed_clients)} connections\n")
        self.memo1.see(tk.END)
        return send_count > 0 or leaderboard_success
    
    def award_points(self):
        """Award points to tables based on their answers and clear the log."""
        if not self.correct_answer:
            messagebox.showwarning("No Correct Answer", "Please set or receive the correct answer first.")
            return
        
        # Read the log to get table answers
        log_content = self.memo1.get(1.0, tk.END)
        # Pattern to match log entries like "@7199:2:B - Answer received from ..."
        # We only care about the table number and answer
        pattern = r'@\d+:(\d+):([A-D])\s*-\s*Answer received from'
        matches = re.findall(pattern, log_content)
        
        if not matches:
            messagebox.showinfo("No Answers", "No valid answers found in the log to award points.")
            return
        
        # Process all answers (log is cleared after each question, so all entries are relevant)
        table_answers = {}
        for table, answer in matches:
            # Store the latest answer for each table (in case of duplicates)
            table_answers[table] = answer
        
        if not table_answers:
            messagebox.showinfo("No Relevant Answers", "No answers found in the log.")
            return
        
        # Award points
        correct_tables = []
        incorrect_tables = []
        
        for table, answer in table_answers.items():
            if answer == self.correct_answer:
                correct_tables.append(table)
            else:
                incorrect_tables.append(table)
        
        # Award +100 points to correct tables
        if correct_tables:
            command = "*" + "*".join(correct_tables) + "+100"
            self.send_points_command(command)
            self.memo1.insert(tk.END, f"Awarded 100 points to tables {', '.join(correct_tables)} (correct answer)\n")
        
        # Deduct 100 points from incorrect tables
        if incorrect_tables:
            command = "*" + "*".join(incorrect_tables) + "-100"
            self.send_points_command(command)
            self.memo1.insert(tk.END, f"Deducted 100 points from tables {', '.join(incorrect_tables)} (incorrect answer)\n")
        
        # Clear the log
        self.memo1.delete(1.0, tk.END)
        self.memo1.insert(tk.END, "Log cleared after awarding points\n")
        self.memo1.see(tk.END)
    
    def animate_status_glow(self):
        self.pulse_glow(self.server_status, self.server_status_color)
        self.root.after(50, self.animate_status_glow)
    
    def pulse_glow(self, canvas, color, min_width=1, max_width=3):
        current_width = canvas.itemcget("status", "width")
        if not current_width:
            current_width = min_width
        else:
            current_width = float(current_width)
        if not hasattr(canvas, 'pulse_direction'):
            canvas.pulse_direction = 1
        new_width = current_width + (0.1 * canvas.pulse_direction)
        if new_width > max_width:
            new_width = max_width
            canvas.pulse_direction = -1
        elif new_width < min_width:
            new_width = min_width
            canvas.pulse_direction = 1
        canvas.itemconfig("status", width=new_width)
    
    def timer1_timer(self):
        with self.client_lock:
            active_connections = len(self.client_connections) if self.server_active else 0
        self.root.title(f"GameServer   {active_connections} Connections")
        self.root.after(1000, self.timer1_timer)
    
    def bbtn_start_server_click(self):
        try:
            port = int(self.edt_server_port.get())
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind(('', port))
            self.server_socket.listen(5)
            self.server_active = True
            self.update_server_status(True)
            threading.Thread(target=self.accept_connections, daemon=True).start()
            self.memo1.insert(tk.END, f"Server started on port {port}\n")
            self.memo1.see(tk.END)
        except Exception as e:
            self.memo1.insert(tk.END, f"Server Error: {str(e)}\n")
            self.memo1.see(tk.END)
    
    def bbtn_stop_server_click(self):
        if self.server_active:
            self.server_active = False
            if self.dance_lights_active:
                self.stop_dance_lights()
            with self.client_lock:
                for client in self.client_connections:
                    try:
                        client.close()
                    except:
                        pass
                self.client_connections = []
            if self.server_socket:
                try:
                    self.server_socket.close()
                except:
                    pass
            self.update_server_status(False)
            self.memo1.insert(tk.END, "Server stopped\n")
            self.memo1.see(tk.END)
    
    def bbtn_send_to_active_connections_click(self):
        if self.server_active:
            with self.client_lock:
                if not self.client_connections:
                    self.memo1.insert(tk.END, "No active connections to send READY to\n")
                    self.memo1.see(tk.END)
                    return
                self.Str = 'READY' + '\r\n'
                success_count = 0
                failed_clients = []
                for client in list(self.client_connections):
                    try:
                        client.send(self.Str.encode('utf-8'))
                        success_count += 1
                    except Exception as e:
                        failed_clients.append(client)
                for client in failed_clients:
                    if client in self.client_connections:
                        self.client_connections.remove(client)
            self.highlight_ready()
            self.memo1.insert(tk.END, f"Sent READY to {success_count} connections\n")
            if failed_clients:
                self.memo1.insert(tk.END, f"Failed to send to {len(failed_clients)} connections\n")
            self.memo1.see(tk.END)
            self.correct_command_entry.delete(0, tk.END)
            self.incorrect_command_entry.delete(0, tk.END)
            if success_count > 0:
                self.start_color_sequence()
    
    def bit_btn1_click(self):
        self.bbtn_stop_server_click()
        self.root.destroy()
    
    def bit_btn2_click(self):
        self.memo1.delete(1.0, tk.END)
    
    def button_click(self, command):
        if self.server_active:
            self.Str = command + '\r\n'
            cmd_parts = command.split('|')
            led_id = cmd_parts[0].split('-')[-1]
            r, g, b = cmd_parts[1], cmd_parts[2], cmd_parts[3]
            color_desc = "RED" if r == "10" else "GREEN" if g == "10" else "BLUE" if b == "10" else "OFF"
            with self.client_lock:
                if not self.client_connections:
                    self.memo1.insert(tk.END, "No clients connected to send command to\n")
                    self.memo1.see(tk.END)
                    return False
                send_count = 0
                failed_clients = []
                for client in list(self.client_connections):
                    try:
                        client.send(self.Str.encode('utf-8'))
                        send_count += 1
                    except Exception as e:
                        failed_clients.append(client)
                for client in failed_clients:
                    if client in self.client_connections:
                        self.client_connections.remove(client)
            self.memo1.insert(tk.END, f"Set LED {led_id} to {color_desc} (sent to {send_count} connections)\n")
            if failed_clients:
                self.memo1.insert(tk.END, f"Failed to send to {len(failed_clients)} connections\n")
            self.memo1.see(tk.END)
            return send_count > 0
        return False
    
    def bbtn_dance_lights_click(self):
        if self.dance_lights_active:
            self.stop_dance_lights()
        else:
            self.start_dance_lights()

    def start_dance_lights(self):
        if not self.server_active or not self.client_connections:
            self.memo1.insert(tk.END, "No clients connected for dance lights\n")
            self.memo1.see(tk.END)
            return
        self.dance_lights_active = True
        self.bbtn_dance_lights.config(text="Stop Dancing")
        self.memo1.insert(tk.END, "Dance lights started at 60 BPM\n")
        self.memo1.see(tk.END)
        self.dance_step()

    def stop_dance_lights(self):
        self.dance_lights_active = False
        self.bbtn_dance_lights.config(text="Dance Lights")
        if self.dance_lights_job is not None:
            self.root.after_cancel(self.dance_lights_job)
            self.dance_lights_job = None
        self.button_click("EMS-LEDS-X|0|0|0|")
        self.memo1.insert(tk.END, "Dance lights stopped\n")
        self.memo1.see(tk.END)

    def dance_step(self):
        if not self.dance_lights_active:
            return
        beat_interval = 1000
        pattern_type = random.randint(1, 5)
        if pattern_type == 1:
            row = random.choice(['A', 'B', 'C', 'D'])
            color = random.choice(['red', 'green', 'blue'])
            r, g, b = (0, 0, 0)
            if color == 'red': r = 10
            elif color == 'green': g = 10
            else: b = 10
            command = f"EMS-LEDS-{row}|{r}|{g}|{b}|"
            self.button_click(command)
        elif pattern_type == 2:
            color = random.choice(['red', 'green', 'blue'])
            r, g, b = (0, 0, 0)
            if color == 'red': r = 10
            elif color == 'green': g = 10
            else: b = 10
            command = f"EMS-LEDS-X|{r}|{g}|{b}|"
            self.button_click(command)
        elif pattern_type == 3:
            color1 = random.choice(['red', 'green', 'blue'])
            r1, g1, b1 = (0, 0, 0)
            if color1 == 'red': r1 = 10
            elif color1 == 'green': g1 = 10
            else: b1 = 10
            for row in ['A', 'C']:
                command = f"EMS-LEDS-{row}|{r1}|{g1}|{b1}|"
                self.button_click(command)
            color2 = random.choice(['red', 'green', 'blue'])
            while color2 == color1:
                color2 = random.choice(['red', 'green', 'blue'])
            r2, g2, b2 = (0, 0, 0)
            if color2 == 'red': r2 = 10
            elif color2 == 'green': g2 = 10
            else: b2 = 10
            for row in ['m2', 'D']:
                command = f"EMS-LEDS-{row}|{r2}|{g2}|{b2}|"
                self.button_click(command)
        elif pattern_type == 4:
            command = "EMS-LEDS-X|0|0|0|"
            self.button_click(command)
        elif pattern_type == 5:
            for row in ['A', 'B', 'C', 'D']:
                color = random.choice(['red', 'green', 'blue', 'off'])
                r, g, b = (0, 0, 0)
                if color == 'red': r = 10
                elif color == 'green': g = 10
                elif color == 'blue': b = 10
                command = f"EMS-LEDS-{row}|{r}|{g}|{b}|"
                self.button_click(command)
        self.dance_lights_job = self.root.after(beat_interval, self.dance_step)
    
    def update_server_status(self, is_active):
        target_color = "#2ecc71" if is_active else "#e74c3c"
        self.animate_color_change(self.server_status, self.server_status_color, target_color)
        self.server_status_color = target_color
    
    def animate_color_change(self, canvas, start_color, end_color, steps=10):
        start_r = int(start_color[1:3], 16)
        start_g = int(start_color[3:5], 16)
        start_b = int(start_color[5:7], 16)
        end_r = int(end_color[1:3], 16)
        end_g = int(end_color[3:5], 16)
        end_b = int(end_color[5:7], 16)
        step_r = (end_r - start_r) / steps
        step_g = (end_g - start_g) / steps
        step_b = (end_b - start_b) / steps
        def animation_step(step):
            if step <= steps:
                r = int(start_r + step_r * step)
                g = int(start_g + step_g * step)
                b = int(start_b + step_b * step)
                color = f"#{r:02x}{g:02x}{b:02x}"
                canvas.itemconfig("status", fill=color)
                outline_color = self.brighten_color(color)
                canvas.itemconfig("status", outline=outline_color)
                canvas.after(20, animation_step, step + 1)
        animation_step(0)
    
    def brighten_color(self, color_hex, factor=1.5):
        r = int(color_hex[1:3], 16)
        g = int(color_hex[3:5], 16)
        b = int(color_hex[5:7], 16)
        r = min(255, int(r * factor))
        g = min(255, int(g * factor))
        b = min(255, int(b * factor))
        return f"#{r:02x}{g:02x}{b:02x}"
    
    def highlight_ready(self):
        orig_bg = self.ready_label.cget("background")
        orig_fg = self.ready_label.cget("foreground")
        orig_font = self.ready_label.cget("font")
        highlight_color = "#3498db"
        glow_color = "#4287f5"
        self.ready_frame.config(bg=glow_color)
        self.ready_label.config(bg=highlight_color, fg="#FFFFFF", font=("Arial", 16, "bold"))
        def step1():
            self.ready_frame.config(bg=highlight_color)
            self.ready_label.config(font=("Arial", 14, "bold"))
            self.root.after(100, step2)
        def step2():
            self.ready_frame.config(bg=orig_bg)
            self.ready_label.config(bg=orig_bg, fg=orig_fg, font=orig_font)
        self.root.after(200, step1)
    
    def accept_connections(self):
        while self.server_active:
            try:
                client, addr = self.server_socket.accept()
                with self.client_lock:
                    self.client_connections.append(client)
                try:
                    client.send("Connected\r\n".encode('utf-8'))
                except Exception as e:
                    self.log_message(f"Error sending connected message: {str(e)}")
                    continue
                self.log_message(f"New connection from {addr[0]}:{addr[1]}")
                threading.Thread(target=self.server_socket1_client_read, args=(client, addr), daemon=True).start()
            except socket.error:
                if self.server_active:
                    self.log_message("Connection accept error")
                break
            except Exception as e:
                if self.server_active:
                    self.log_message(f"Unexpected error in accept_connections: {str(e)}")
                break
    
    def log_message(self, message):
        self.root.after(0, lambda msg=message: self.memo1.insert(tk.END, f"{msg}\n"))
        self.root.after(0, lambda: self.memo1.see(tk.END))
    
    def server_socket1_client_read(self, client, addr):
        buffer = ""
        while self.server_active:
            try:
                data = client.recv(1024)
                if not data:
                    break
                buffer += data.decode('utf-8', errors='replace')
                while '\r\n' in buffer:
                    message, buffer = buffer.split('\r\n', 1)
                    if not message:
                        continue
                    self.process_client_message(client, message, addr)
            except ConnectionError:
                break
            except Exception as e:
                self.log_message(f"Error reading from client {addr[0]}:{addr[1]}: {str(e)}")
                break
        with self.client_lock:
            if client in self.client_connections:
                self.client_connections.remove(client)
        try:
            client.close()
        except:
            pass
        self.log_message(f"Client {addr[0]}:{addr[1]} disconnected")
    
    def process_client_message(self, client, message, addr):
        if len(message) > 5:
            self.log_message(message)
        
        # Check for correct answer message (awns_A, awns_B, etc.)
        if message.startswith('awns_'):
            try:
                answer = message.split('_')[1].strip().upper()
                if answer in ['A', 'B', 'C', 'D']:
                    self.correct_answer = answer
                    self.correct_answer_var.set(answer)
                    self.log_message(f"Correct answer received: {answer}")
                else:
                    self.log_message(f"Invalid correct answer format: {message}")
            except Exception as e:
                self.log_message(f"Error processing correct answer: {str(e)}")
        
        if "READY" in message:
            # [Existing READY logic remains unchanged]
            pass
        elif message.startswith('DASHBOARD-READY-TRIGGER'):
            self.bbtn_send_to_active_connections_click()
        elif message.startswith('*') and ('+' in message or '-' in message):
            # [Existing points logic remains unchanged]
            pass
        elif message.startswith('@') and ':' in message:
            # Handle legacy format @TABLE:ANSWER
            try:
                parts = message.split(':')
                table_part = parts[0][1:]
                answer = parts[1].strip().upper()
                if not table_part.isdigit() or answer not in ['A', 'B', 'C', 'D']:
                    self.log_message(f"Invalid answer format: {message}")
                    return
                client_info = f"{addr[0]}:{addr[1]}"
                # Log without question number for legacy format (assuming current question)
                self.log_message(f"@{table_part}:{answer} - Answer received from {client_info}")
                leaderboard_success = self.leaderboard_connector.send_to_leaderboard(message)
                if leaderboard_success:
                    self.log_message(f"Answer forwarded to leaderboard")
                else:
                    self.log_message(f"Failed to forward answer to leaderboard: {message}")
            except Exception as e:
                self.log_message(f"Error processing answer: {str(e)}")
        elif message.startswith('�|EMS|'):
            # Handle format �|EMS|TABLE|ANSWER|QUESTION|
            try:
                parts = message.split('|')
                if len(parts) >= 5 and parts[1] == 'EMS':
                    table_part = parts[2]  # e.g., "3"
                    answer = parts[3].strip().upper()  # e.g., "D"
                    question_part = parts[4]  # e.g., "1945"
                    if not table_part.isdigit() or answer not in ['A', 'B', 'C', 'D'] or not question_part.isdigit():
                        self.log_message(f"Invalid EMS answer format: {message}")
                        return
                    client_info = f"{addr[0]}:{addr[1]}"
                    # Log with question number included
                    log_entry = f"@{question_part}:{table_part}:{answer} - Answer received from {client_info}"
                    self.log_message(log_entry)
                    # Send standardized format to leaderboard
                    standardized_message = f"@{table_part}:{answer}"
                    leaderboard_success = self.leaderboard_connector.send_to_leaderboard(standardized_message)
                    if leaderboard_success:
                        self.log_message(f"Answer forwarded to leaderboard")
                    else:
                        self.log_message(f"Failed to forward answer to leaderboard: {standardized_message}")
            except Exception as e:
                self.log_message(f"Error processing EMS answer: {str(e)}")
        # [Other existing conditions remain unchanged]

    def start_color_sequence(self):
        if self.color_sequence_active:
            return
        self.color_sequence_active = True
        self.log_message("Starting color sequence: RED")
        self.set_all_leds_color("red")
        self.root.after(5000, self.transition_to_green)
    
    def transition_to_green(self):
        if not self.color_sequence_active:
            return
        # Send READY command before transitioning to green (first pause)
        self.bbtn_send_to_active_connections_click()
        self.log_message("Color sequence: GREEN")
        self.set_all_leds_color("green")
        self.root.after(10000, self.transition_to_blue)
    
    def transition_to_blue(self):
        if not self.color_sequence_active:
            return
        self.log_message("Color sequence: BLUE")
        self.set_all_leds_color("blue")
        self.root.after(5000, self.transition_to_off)
    
    def transition_to_off(self):
        if not self.color_sequence_active:
            return
        self.log_message("Color sequence: OFF (complete)")
        self.set_all_leds_color("off")
        self.color_sequence_active = False
    
    def set_all_leds_color(self, color):
        command = "EMS-LEDS-X|0|10|0|" if color == "green" else "EMS-LEDS-X|10|0|0|" if color == "red" else "EMS-LEDS-X|0|0|10|" if color == "blue" else "EMS-LEDS-X|0|0|0|"
        self.button_click(command)

if __name__ == "__main__":
    root = tk.Tk()
    app = CompactGameServerApp(root)
    root.mainloop()
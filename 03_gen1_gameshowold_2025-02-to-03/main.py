import socket
import threading
import tkinter as tk
from tkinter import scrolledtext, ttk
from datetime import datetime
import time
import random

class DarkGameServerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("GameServer   0 Connections")
        self.root.geometry("850x600")
        self.root.configure(bg="#121212")  # Dark background
        
        # Variables
        self.server_socket = None
        self.client_connections = []
        self.server_active = False
        self.Str = ""
        self.client_lock = threading.Lock()  # Add lock for thread safety
        self.color_sequence_active = False   # Track if color sequence is running
        self.dance_lights_active = False     # Track if dance lights are active
        self.dance_lights_job = None         # To store the scheduled job ID
        
        # Apply dark theme styling
        self.configure_styles()
        
        # Create main container
        main_container = tk.Frame(root, bg="#121212")
        main_container.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)
        
        # Top section - Server controls
        top_frame = tk.Frame(main_container, bg="#121212")
        top_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Port with themed label and entry
        port_frame = tk.Frame(top_frame, bg="#121212")
        port_frame.pack(side=tk.LEFT, fill=tk.Y)
        
        tk.Label(port_frame, text="Port:", bg="#121212", fg="#E0E0E0", 
                font=("Segoe UI", 11, "bold")).pack(side=tk.LEFT, padx=(0, 5))
        
        # Custom styled port entry
        self.edt_server_port = tk.Entry(port_frame, width=8, font=("Segoe UI", 11),
                                       bg="#2D2D2D", fg="#E0E0E0", insertbackground="#E0E0E0",
                                       relief="flat", bd=0)
        self.edt_server_port.insert(0, "8080")
        self.edt_server_port.pack(side=tk.LEFT, padx=(0, 20), ipady=3)
        
        # Create highlighted effect for entry
        self.create_entry_highlight(self.edt_server_port, "#2D2D2D", "#4287f5")
        
        # Server buttons with glowing effect
        button_frame = tk.Frame(top_frame, bg="#121212")
        button_frame.pack(side=tk.LEFT, fill=tk.Y)
        
        # Start Server Button with glow effect
        self.bbtn_start_server = self.create_glowing_button(
            button_frame, "Start Server", "#27ae60", "#2ecc71", "#219150",
            self.bbtn_start_server_click)
        self.bbtn_start_server.pack(side=tk.LEFT, padx=(0, 10))
        
        # Status indicator (glowing orb)
        self.server_status_frame = tk.Frame(button_frame, bg="#121212")
        self.server_status_frame.pack(side=tk.LEFT, padx=(0, 10))
        
        self.server_status = tk.Canvas(self.server_status_frame, width=20, height=20, 
                                     bg="#121212", highlightthickness=0)
        self.server_status.pack()
        
        # Create glowing status indicator
        self.server_status.create_oval(2, 2, 18, 18, fill="#e74c3c", outline="#ff6b6b", width=1, tags="status")
        self.server_status_color = "#e74c3c"  # Initial color (red)
        
        # Stop Server Button with glow effect
        self.bbtn_stop_server = self.create_glowing_button(
            button_frame, "Stop Server", "#c0392b", "#e74c3c", "#a93226",
            self.bbtn_stop_server_click)
        self.bbtn_stop_server.pack(side=tk.LEFT)
        
        # Main content area - split into left and right panels
        content_frame = tk.Frame(main_container, bg="#121212")
        content_frame.pack(fill=tk.BOTH, expand=True)
        
        # Left section - Server log
        left_frame = tk.Frame(content_frame, bg="#121212")
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        
        # Server log with dark styling
        log_frame = tk.LabelFrame(left_frame, text="Server Log", 
                                 bg="#121212", fg="#E0E0E0", 
                                 font=("Segoe UI", 10, "bold"))
        log_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Memo with dark theme
        self.memo1 = scrolledtext.ScrolledText(log_frame, width=35, height=15,
                                              font=("Consolas", 9), 
                                              bg="#1E1E1E", fg="#E0E0E0",
                                              insertbackground="#E0E0E0")
        self.memo1.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Right section with LED grid
        right_frame = tk.Frame(content_frame, bg="#121212")
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        # LED Controls section with exciting styling
        led_frame = tk.LabelFrame(right_frame, text="LED Controls", 
                                 bg="#121212", fg="#E0E0E0", 
                                 font=("Segoe UI", 10, "bold"))
        led_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=(5, 0))
        
        # LED container with dark styling
        led_container = tk.Frame(led_frame, bg="#121212", padx=10, pady=10)
        led_container.pack(fill=tk.BOTH, expand=True)
        
        # LED headers with glowing styling
        header_frame = tk.Frame(led_container, bg="#121212")
        header_frame.pack(fill=tk.X)
        
        # Empty space for alignment
        tk.Label(header_frame, text="", width=5, bg="#121212").grid(row=0, column=0)
        
        # Color headers with glowing effect
        self.create_glowing_label(header_frame, "Red", "#c0392b", 0, 1)
        self.create_glowing_label(header_frame, "Green", "#27ae60", 0, 2)
        self.create_glowing_label(header_frame, "Blue", "#2980b9", 0, 3)
        
        # LED Controls section with simple styling
        led_frame = tk.LabelFrame(right_frame, text="LED Controls", 
                                 bg="#121212", fg="#E0E0E0", 
                                 font=("Segoe UI", 10, "bold"))
        led_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=(5, 0))
        
        # LED container with dark styling
        led_container = tk.Frame(led_frame, bg="#121212", padx=10, pady=10)
        led_container.pack(fill=tk.BOTH, expand=True)
        
        # LED grid with traditional layout
        grid_frame = tk.Frame(led_container, bg="#121212")
        grid_frame.pack(fill=tk.BOTH, expand=True)
        
        # Color headers
        tk.Label(grid_frame, text="", width=5, bg="#121212").grid(row=0, column=0)
        self.create_glowing_label(grid_frame, "Red", "#c0392b", 0, 1)
        self.create_glowing_label(grid_frame, "Green", "#27ae60", 0, 2)
        self.create_glowing_label(grid_frame, "Blue", "#2980b9", 0, 3)
        
        # Row labels A-D with glowing styling
        labels = ["A", "B", "C", "D", "ALL"]
        for i, label in enumerate(labels):
            tk.Label(grid_frame, text=label, bg="#121212", fg="#E0E0E0",
                    font=("Segoe UI", 11, "bold")).grid(
                row=i+1, column=0, padx=5, pady=5, sticky="e")
        
        # Create LED buttons with exact Delphi command behavior
        # Red LED buttons (using exact Delphi commands)
        self.button_red_a = self.create_led_button(
            grid_frame, "A", "#c0392b", "#e74c3c", "#a93226", 1, 1,
            lambda: self.button_click("EMS-LEDS-A|10|0|0|"))
        
        self.button_red_b = self.create_led_button(
            grid_frame, "B", "#c0392b", "#e74c3c", "#a93226", 2, 1,
            lambda: self.button_click("EMS-LEDS-B|10|0|0|"))
        
        self.button_red_c = self.create_led_button(
            grid_frame, "C", "#c0392b", "#e74c3c", "#a93226", 3, 1,
            lambda: self.button_click("EMS-LEDS-C|10|0|0|"))
        
        self.button_red_d = self.create_led_button(
            grid_frame, "D", "#c0392b", "#e74c3c", "#a93226", 4, 1,
            lambda: self.button_click("EMS-LEDS-D|10|0|0|"))
        
        self.button_red_all = self.create_led_button(
            grid_frame, "ALL", "#c0392b", "#e74c3c", "#a93226", 5, 1,
            lambda: self.button_click("EMS-LEDS-X|10|0|0|"))
        
        # Green LED buttons (using exact Delphi commands)
        self.button_green_a = self.create_led_button(
            grid_frame, "A", "#27ae60", "#2ecc71", "#219150", 1, 2,
            lambda: self.button_click("EMS-LEDS-A|0|10|0|"))
        
        self.button_green_b = self.create_led_button(
            grid_frame, "B", "#27ae60", "#2ecc71", "#219150", 2, 2,
            lambda: self.button_click("EMS-LEDS-B|0|10|0|"))
        
        self.button_green_c = self.create_led_button(
            grid_frame, "C", "#27ae60", "#2ecc71", "#219150", 3, 2,
            lambda: self.button_click("EMS-LEDS-C|0|10|0|"))
        
        self.button_green_d = self.create_led_button(
            grid_frame, "D", "#27ae60", "#2ecc71", "#219150", 4, 2,
            lambda: self.button_click("EMS-LEDS-D|0|10|0|"))
        
        self.button_green_all = self.create_led_button(
            grid_frame, "ALL", "#27ae60", "#2ecc71", "#219150", 5, 2,
            lambda: self.button_click("EMS-LEDS-X|0|10|0|"))
        
        # Blue LED buttons (using exact Delphi commands)
        self.button_blue_a = self.create_led_button(
            grid_frame, "A", "#2980b9", "#3498db", "#1c6ea0", 1, 3,
            lambda: self.button_click("EMS-LEDS-A|0|0|10|"))
        
        self.button_blue_b = self.create_led_button(
            grid_frame, "B", "#2980b9", "#3498db", "#1c6ea0", 2, 3,
            lambda: self.button_click("EMS-LEDS-B|0|0|10|"))
        
        self.button_blue_c = self.create_led_button(
            grid_frame, "C", "#2980b9", "#3498db", "#1c6ea0", 3, 3,
            lambda: self.button_click("EMS-LEDS-C|0|0|10|"))
        
        self.button_blue_d = self.create_led_button(
            grid_frame, "D", "#2980b9", "#3498db", "#1c6ea0", 4, 3,
            lambda: self.button_click("EMS-LEDS-D|0|0|10|"))
        
        self.button_blue_all = self.create_led_button(
            grid_frame, "ALL", "#2980b9", "#3498db", "#1c6ea0", 5, 3,
            lambda: self.button_click("EMS-LEDS-X|0|0|10|"))
        
        # All OFF button with distinctive styling - using exact Delphi command
        self.button_all_off = self.create_glowing_button(
            grid_frame, "ALL OFF", "#c0392b", "#e74c3c", "#a93226",
            lambda: self.button_click("EMS-LEDS-X|0|0|0|"))
        self.button_all_off.grid(row=6, column=1, columnspan=3, padx=5, pady=10, sticky="ew")
        
        # Label to explain functionality
        explanation = tk.Label(
            led_container, 
            text="Controls match original Delphi implementation", 
            bg="#121212", fg="#E0E0E0",
            font=("Segoe UI", 9, "italic"))
        explanation.pack(pady=(10, 5))
        
        # Add hover effect to ALL OFF button
        self.button_all_off.bind("<Enter>", lambda e: self.button_all_off.config(bg="#3D3D3D"))
        self.button_all_off.bind("<Leave>", lambda e: self.button_all_off.config(bg="#2D2D2D"))
        
        # Bottom section with modern styling
        bottom_frame = tk.Frame(main_container, bg="#121212")
        bottom_frame.pack(fill=tk.X, pady=(10, 0))
        
        # Clear Memo button with glow effect
        self.bit_btn2 = self.create_glowing_button(
            bottom_frame, "Clear Memo", "#2D2D2D", "#3D3D3D", "#1D1D1D",
            self.bit_btn2_click)
        self.bit_btn2.pack(side=tk.LEFT, padx=(0, 10))
        
        # READY display with glowing effect
        self.ready_frame = tk.Frame(bottom_frame, bg="#121212", bd=2, relief="groove")
        self.ready_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=10)
        
        self.ready_label = tk.Label(self.ready_frame, text="READY", fg="#E0E0E0", bg="#121212",
                                   font=("Arial", 14, "bold"))
        self.ready_label.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Send READY button with glow effect
        self.bbtn_send_to_active = self.create_glowing_button(
            bottom_frame, "Send Ready", "#2980b9", "#3498db", "#1c6ea0",
            self.bbtn_send_to_active_connections_click)
        self.bbtn_send_to_active.pack(side=tk.LEFT, padx=(0, 10))
        
        # Dance Lights button with glow effect
        self.bbtn_dance_lights = self.create_glowing_button(
            bottom_frame, "Dance Lights", "#9b59b6", "#8e44ad", "#7d3c98",
            self.bbtn_dance_lights_click)
        self.bbtn_dance_lights.pack(side=tk.LEFT, padx=(0, 10))
        
        # Close button with glow effect
        self.bit_btn1 = self.create_glowing_button(
            bottom_frame, "Close", "#c0392b", "#e74c3c", "#a93226",
            self.bit_btn1_click)
        self.bit_btn1.pack(side=tk.LEFT)
        
        # Status glow animation
        self.animate_status_glow()
        
        # Initialize timer to update connection count
        self.timer1_timer()
    
    def configure_styles(self):
        """Configure styling for ttk widgets if needed"""
        self.style = ttk.Style()
        if 'clam' in self.style.theme_names():
            self.style.theme_use("clam")
    
    def create_entry_highlight(self, entry, normal_color, focus_color):
        """Create a highlight effect for entry widgets"""
        entry.config(highlightthickness=1, highlightbackground="#333333", highlightcolor=focus_color)
        entry.bind("<FocusIn>", lambda e: entry.config(highlightbackground=focus_color))
        entry.bind("<FocusOut>", lambda e: entry.config(highlightbackground="#333333"))
    
    def create_glowing_button(self, parent, text, color, hover_color, active_color, command):
        """Create a button with glowing effect"""
        button = tk.Button(parent, text=text, font=("Segoe UI", 10, "bold"),
                          bg=color, fg="#FFFFFF", 
                          activebackground=active_color, activeforeground="#FFFFFF",
                          relief="flat", bd=0, padx=10, pady=4,
                          command=command)
        
        # Add hover effect
        button.bind("<Enter>", lambda e: button.config(bg=hover_color))
        button.bind("<Leave>", lambda e: button.config(bg=color))
        
        return button
    
    def create_led_button(self, parent, text, color, hover_color, active_color, row, column, command):
        """Create a styled LED button"""
        button = tk.Button(parent, text=text, font=("Segoe UI", 10, "bold"),
                          bg=color, fg="#FFFFFF", 
                          activebackground=active_color, activeforeground="#FFFFFF",
                          relief="flat", bd=0, width=8, height=1,
                          command=command)
        
        button.grid(row=row, column=column, padx=5, pady=5)
        
        # Add hover effect
        button.bind("<Enter>", lambda e: button.config(bg=hover_color))
        button.bind("<Leave>", lambda e: button.config(bg=color))
        
        return button
    
    def create_glowing_label(self, parent, text, color, row, column):
        """Create a label with glowing effect using grid layout"""
        label = tk.Label(parent, text=text, font=("Segoe UI", 11, "bold"),
                        bg="#121212", fg=color)
        label.grid(row=row, column=column, padx=10)
        
        return label
    
    def create_glowing_label_pack(self, parent, text, color):
        """Create a label with glowing effect using pack layout"""
        label = tk.Label(parent, text=text, font=("Segoe UI", 9, "bold"),
                        bg="#121212", fg=color, width=6)
        label.pack(side=tk.LEFT, padx=5)
        
        return label
    
    def animate_status_glow(self):
        """Create a subtle pulsing glow effect for status indicators"""
        # Server status glow
        self.pulse_glow(self.server_status, self.server_status_color)
        
        # Schedule next animation
        self.root.after(50, self.animate_status_glow)
    
    def pulse_glow(self, canvas, color, min_width=1, max_width=3):
        """Create a pulsing glow effect for status indicators"""
        # Get current outline width
        current_width = canvas.itemcget("status", "width")
        if not current_width:
            current_width = min_width
        else:
            current_width = float(current_width)
        
        # Determine direction
        if not hasattr(canvas, 'pulse_direction'):
            canvas.pulse_direction = 1
        
        # Update width
        new_width = current_width + (0.1 * canvas.pulse_direction)
        if new_width > max_width:
            new_width = max_width
            canvas.pulse_direction = -1
        elif new_width < min_width:
            new_width = min_width
            canvas.pulse_direction = 1
        
        # Set new width
        canvas.itemconfig("status", width=new_width)
    
    # Timer function to update connection count - exact match to Delphi
    def timer1_timer(self):
        with self.client_lock:  # Add lock for thread safety
            active_connections = len(self.client_connections) if self.server_active else 0
        self.root.title(f"GameServer   {active_connections} Connections")
        self.root.after(1000, self.timer1_timer)  # Run every 1000ms
    
    # Button click handlers with status updates - matched to Delphi behavior
    def bbtn_start_server_click(self):
        try:
            port = int(self.edt_server_port.get())
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind(('', port))
            self.server_socket.listen(5)
            self.server_active = True
            
            # Update UI with smooth color transition
            self.update_server_status(True)
            
            # Start a thread to accept connections
            threading.Thread(target=self.accept_connections, daemon=True).start()
            
            # Log message
            self.memo1.insert(tk.END, f"Server started on port {port}\n")
            self.memo1.see(tk.END)
        except Exception as e:
            self.memo1.insert(tk.END, f"Server Error: {str(e)}\n")
            self.memo1.see(tk.END)
    
    def bbtn_stop_server_click(self):
        if self.server_active:
            self.server_active = False
            
            # Stop dance lights if active
            if self.dance_lights_active:
                self.stop_dance_lights()
            
            # Close all client connections
            with self.client_lock:  # Add lock for thread safety
                for client in self.client_connections:
                    try:
                        client.close()
                    except:
                        pass
                self.client_connections = []
            
            # Close server socket
            if self.server_socket:
                try:
                    self.server_socket.close()
                except:
                    pass
            
            # Update UI with smooth color transition
            self.update_server_status(False)
            
            # Log message
            self.memo1.insert(tk.END, "Server stopped\n")
            self.memo1.see(tk.END)
    
    # Match Delphi READY command exactly including CRLF
    def bbtn_send_to_active_connections_click(self):
        if self.server_active:
            with self.client_lock:  # Add lock for thread safety
                if not self.client_connections:
                    # No clients to send to
                    self.memo1.insert(tk.END, "No active connections to send READY to\n")
                    self.memo1.see(tk.END)
                    return
                
                # Exactly match Delphi formatting - CRLF as in Delphi: #13 #10
                self.Str = 'READY' + '\r\n'
                success_count = 0
                failed_clients = []
                
                for client in list(self.client_connections):  # Make a copy of the list
                    try:
                        client.send(self.Str.encode('utf-8'))
                        success_count += 1
                    except Exception as e:
                        # Mark this client for removal
                        failed_clients.append(client)
                        
                # Remove failed clients
                for client in failed_clients:
                    if client in self.client_connections:
                        self.client_connections.remove(client)
                        
            # Highlight the READY display momentarily
            self.highlight_ready()
            
            # Log message
            self.memo1.insert(tk.END, f"Sent READY to {success_count} connections\n")
            if failed_clients:
                self.memo1.insert(tk.END, f"Failed to send to {len(failed_clients)} connections\n")
            self.memo1.see(tk.END)
            
            # Start the color sequence if there are active connections
            if success_count > 0:
                self.start_color_sequence()
    
    def bit_btn1_click(self):
        self.bbtn_stop_server_click()  # Stop server
        self.root.destroy()  # Exit application
    
    def bit_btn2_click(self):
        self.memo1.delete(1.0, tk.END)  # Clear memo1
    
    def button_click(self, command):
        if self.server_active:
            # Match Delphi formatting exactly for CRLF
            self.Str = command + '\r\n'
            
            # Parse command to log meaningful message
            cmd_parts = command.split('|')
            led_id = cmd_parts[0].split('-')[-1]
            r, g, b = cmd_parts[1], cmd_parts[2], cmd_parts[3]
            
            color_desc = ""
            if r == "10": color_desc = "RED"
            elif g == "10": color_desc = "GREEN"
            elif b == "10": color_desc = "BLUE"
            else: color_desc = "OFF"
            
            with self.client_lock:  # Add lock for thread safety
                if not self.client_connections:
                    self.memo1.insert(tk.END, "No clients connected to send command to\n")
                    self.memo1.see(tk.END)
                    return
                
                # Send to ALL connected clients
                send_count = 0
                failed_clients = []
                
                for client in list(self.client_connections):  # Make a copy of the list
                    try:
                        client.send(self.Str.encode('utf-8'))
                        send_count += 1
                    except Exception as e:
                        failed_clients.append(client)
                
                # Remove failed clients
                for client in failed_clients:
                    if client in self.client_connections:
                        self.client_connections.remove(client)
            
            # Log successful sends
            self.memo1.insert(tk.END, f"Set LED {led_id} to {color_desc} (sent to {send_count} connections)\n")
            if failed_clients:
                self.memo1.insert(tk.END, f"Failed to send to {len(failed_clients)} connections\n")
            self.memo1.see(tk.END)
    
    # Dance Lights methods
    def bbtn_dance_lights_click(self):
        """Toggle dance lights on/off"""
        if self.dance_lights_active:
            # Turn off dance lights
            self.stop_dance_lights()
        else:
            # Turn on dance lights
            self.start_dance_lights()

    def start_dance_lights(self):
        """Start the dance lights sequence at 60 BPM"""
        if not self.server_active or not self.client_connections:
            self.memo1.insert(tk.END, "No clients connected for dance lights\n")
            self.memo1.see(tk.END)
            return
            
        self.dance_lights_active = True
        self.bbtn_dance_lights.config(text="Stop Dancing")
        self.memo1.insert(tk.END, "Dance lights started at 60 BPM\n")
        self.memo1.see(tk.END)
        
        # Start the dance sequence
        self.dance_step()

    def stop_dance_lights(self):
        """Stop the dance lights sequence"""
        self.dance_lights_active = False
        self.bbtn_dance_lights.config(text="Dance Lights")
        
        # Cancel the scheduled job if it exists
        if self.dance_lights_job is not None:
            self.root.after_cancel(self.dance_lights_job)
            self.dance_lights_job = None
            
        # Turn all lights off
        self.button_click("EMS-LEDS-X|0|0|0|")
        
        self.memo1.insert(tk.END, "Dance lights stopped\n")
        self.memo1.see(tk.END)

    def dance_step(self):
        """Perform one step in the dance lights sequence"""
        if not self.dance_lights_active:
            return
            
        # 60 BPM = 1 beat per second = 1000 ms
        beat_interval = 1000
        
        # Choose a random light pattern
        pattern_type = random.randint(1, 5)
        
        if pattern_type == 1:
            # Single row, random color
            row = random.choice(['A', 'B', 'C', 'D'])
            color = random.choice(['red', 'green', 'blue'])
            r, g, b = (0, 0, 0)
            
            if color == 'red':
                r = 10
            elif color == 'green':
                g = 10
            else:
                b = 10
                
            command = f"EMS-LEDS-{row}|{r}|{g}|{b}|"
            self.button_click(command)
            
        elif pattern_type == 2:
            # All rows, same color
            color = random.choice(['red', 'green', 'blue'])
            r, g, b = (0, 0, 0)
            
            if color == 'red':
                r = 10
            elif color == 'green':
                g = 10
            else:
                b = 10
                
            command = f"EMS-LEDS-X|{r}|{g}|{b}|"
            self.button_click(command)
            
        elif pattern_type == 3:
            # Alternating rows
            color1 = random.choice(['red', 'green', 'blue'])
            r1, g1, b1 = (0, 0, 0)
            
            if color1 == 'red':
                r1 = 10
            elif color1 == 'green':
                g1 = 10
            else:
                b1 = 10
            
            # Send to alternating rows
            for row in ['A', 'C']:
                command = f"EMS-LEDS-{row}|{r1}|{g1}|{b1}|"
                self.button_click(command)
                
            # Different color for other rows
            color2 = random.choice(['red', 'green', 'blue'])
            while color2 == color1:  # Ensure different color
                color2 = random.choice(['red', 'green', 'blue'])
                
            r2, g2, b2 = (0, 0, 0)
            if color2 == 'red':
                r2 = 10
            elif color2 == 'green':
                g2 = 10
            else:
                b2 = 10
                
            for row in ['B', 'D']:
                command = f"EMS-LEDS-{row}|{r2}|{g2}|{b2}|"
                self.button_click(command)
                
        elif pattern_type == 4:
            # Blackout (all off) for a beat
            command = "EMS-LEDS-X|0|0|0|"
            self.button_click(command)
            
        elif pattern_type == 5:
            # Random colors for each row
            for row in ['A', 'B', 'C', 'D']:
                color = random.choice(['red', 'green', 'blue', 'off'])
                r, g, b = (0, 0, 0)
                
                if color == 'red':
                    r = 10
                elif color == 'green':
                    g = 10
                elif color == 'blue':
                    b = 10
                    
                command = f"EMS-LEDS-{row}|{r}|{g}|{b}|"
                self.button_click(command)
        
        # Schedule the next beat
        self.dance_lights_job = self.root.after(beat_interval, self.dance_step)
    
    # UI update methods with animations
    def update_server_status(self, is_active):
        """Update server status indicator with smooth transition"""
        target_color = "#2ecc71" if is_active else "#e74c3c"  # Green or Red
        self.animate_color_change(self.server_status, self.server_status_color, target_color)
        self.server_status_color = target_color
    
    def animate_color_change(self, canvas, start_color, end_color, steps=10):
        """Animate color change from start to end color"""
        # Convert hex to RGB
        start_r = int(start_color[1:3], 16)
        start_g = int(start_color[3:5], 16)
        start_b = int(start_color[5:7], 16)
        
        end_r = int(end_color[1:3], 16)
        end_g = int(end_color[3:5], 16)
        end_b = int(end_color[5:7], 16)
        
        # Calculate step size for each color channel
        step_r = (end_r - start_r) / steps
        step_g = (end_g - start_g) / steps
        step_b = (end_b - start_b) / steps
        
        # Function to perform animation step
        def animation_step(step):
            if step <= steps:
                # Calculate current color
                r = int(start_r + step_r * step)
                g = int(start_g + step_g * step)
                b = int(start_b + step_b * step)
                
                # Convert back to hex
                color = f"#{r:02x}{g:02x}{b:02x}"
                
                # Update canvas - both the fill and outline for a glowing effect
                canvas.itemconfig("status", fill=color)
                # Brighten the outline color for glow effect
                outline_color = self.brighten_color(color)
                canvas.itemconfig("status", outline=outline_color)
                
                # Schedule next step
                canvas.after(20, animation_step, step + 1)
        
        # Start animation
        animation_step(0)
    
    def brighten_color(self, color_hex, factor=1.5):
        """Brighten a color by a factor for glow effect"""
        # Convert hex to RGB
        r = int(color_hex[1:3], 16)
        g = int(color_hex[3:5], 16)
        b = int(color_hex[5:7], 16)
        
        # Brighten
        r = min(255, int(r * factor))
        g = min(255, int(g * factor))
        b = min(255, int(b * factor))
        
        # Convert back to hex
        return f"#{r:02x}{g:02x}{b:02x}"
    
    def highlight_ready(self):
        """Highlight the READY indicator momentarily with glowing effect"""
        # Save original styling
        orig_bg = self.ready_label.cget("background")
        orig_fg = self.ready_label.cget("foreground")
        orig_font = self.ready_label.cget("font")
        
        # Apply highlight with glow effect
        highlight_color = "#3498db"  # Bright blue
        glow_color = "#4287f5"       # Brighter blue for glow
        
        # Create glow animation for READY text
        self.ready_frame.config(bg=glow_color)
        self.ready_label.config(bg=highlight_color, fg="#FFFFFF", font=("Arial", 16, "bold"))
        
        # Schedule multi-step return to normal
        def step1():
            self.ready_frame.config(bg=highlight_color)
            self.ready_label.config(font=("Arial", 14, "bold"))
            self.root.after(100, step2)
        
        def step2():
            self.ready_frame.config(bg=orig_bg)
            self.ready_label.config(bg=orig_bg, fg=orig_fg, font=orig_font)
        
        # Start the animation sequence
        self.root.after(200, step1)
    
    # Socket handling methods - fixed to match Delphi behavior
    def accept_connections(self):
        while self.server_active:
            try:
                client, addr = self.server_socket.accept()
                
                # Add thread safety for client connections
                with self.client_lock:
                    self.client_connections.append(client)
                
                # Send "Connected" message exactly as in Delphi
                try:
                    client.send("Connected\r\n".encode('utf-8'))  # Add proper line ending
                except Exception as e:
                    self.log_message(f"Error sending connected message: {str(e)}")
                    continue
                
                # Log the connection with address info
                self.log_message(f"New connection from {addr[0]}:{addr[1]}")
                
                # Start a thread to receive messages from this client
                threading.Thread(target=self.server_socket1_client_read, 
                                args=(client, addr), daemon=True).start()
            except socket.error:
                if self.server_active:  # Only log if not intentionally closed
                    self.log_message("Connection accept error")
                break
            except Exception as e:
                if self.server_active:
                    self.log_message(f"Unexpected error in accept_connections: {str(e)}")
                break
    
    def log_message(self, message):
        """Thread-safe logging to UI"""
        self.root.after(0, lambda msg=message: self.memo1.insert(tk.END, f"{msg}\n"))
        self.root.after(0, lambda: self.memo1.see(tk.END))
    
    # Fixed to properly handle message processing
    def server_socket1_client_read(self, client, addr):
        buffer = ""
        
        while self.server_active:
            try:
                data = client.recv(1024)
                if not data:
                    # Client disconnected
                    break
                
                # Accumulate and process data
                buffer += data.decode('utf-8', errors='replace')
                
                # Process any complete messages in the buffer
                while '\r\n' in buffer:
                    # Extract one complete message
                    message, buffer = buffer.split('\r\n', 1)
                    
                    # Skip empty messages
                    if not message:
                        continue
                    
                    # Process the message
                    self.process_client_message(client, message)
            except ConnectionError:
                # Connection was closed
                break
            except Exception as e:
                self.log_message(f"Error reading from client {addr[0]}:{addr[1]}: {str(e)}")
                break
        
        # Client disconnected - clean up
        with self.client_lock:
            if client in self.client_connections:
                self.client_connections.remove(client)
        
        try:
            client.close()
        except:
            pass
        
        # Log the disconnection
        self.log_message(f"Client {addr[0]}:{addr[1]} disconnected")
    
# In the DarkGameServerApp class, find the process_client_message method and modify it:

    def process_client_message(self, client, message):
        """Process received client message"""
        # Log the message if length is greater than 5 (exactly as in Delphi)
        if len(message) > 5:
            self.log_message(message)
        
        # Special handling for READY messages
        if "READY" in message:
            # Create a properly formatted READY message with CRLF
            ready_message = "READY\r\n"
            
            # Forward to all connected clients
            with self.client_lock:
                for conn in list(self.client_connections):
                    if conn != client:  # Don't send back to originator
                        try:
                            conn.send(ready_message.encode('utf-8'))
                        except:
                            pass
            
            # Highlight the READY display
            self.root.after(0, self.highlight_ready)
            
            # Start the color sequence
            self.root.after(0, self.start_color_sequence)
        
        # New commands for integration with GameshowPlayer
        elif "DANCE-LIGHTS-START" in message:
            # Start the dance lights
            self.root.after(0, self.start_dance_lights)
            self.log_message("Received command to start dance lights")
            
        elif "DANCE-LIGHTS-STOP" in message:
            # Stop the dance lights
            self.root.after(0, self.stop_dance_lights)
            self.log_message("Received command to stop dance lights")
        
        elif "PING" in message:
            # Simple ping to check if connection is alive
            # No need to do anything here, connection is verified by successful receipt
            pass

    # Add color sequence methods
    def start_color_sequence(self):
        """Start the LED color sequence (green 10s → red 5s → blue 5s → off)"""
        # Cancel any existing sequence
        if self.color_sequence_active:
            return
            
        self.color_sequence_active = True
        self.log_message("Starting color sequence: GREEN")
        
        # Start with green for 10 seconds
        self.set_all_leds_color("green")
        
        # Schedule the color transitions
        self.root.after(10000, self.transition_to_red)
    
    def transition_to_red(self):
        """Transition to red color for 5 seconds"""
        if not self.color_sequence_active:
            return
            
        self.log_message("Color sequence: RED")
        self.set_all_leds_color("red")
        self.root.after(5000, self.transition_to_blue)
    
    def transition_to_blue(self):
        """Transition to blue color for 5 seconds"""
        if not self.color_sequence_active:
            return
            
        self.log_message("Color sequence: BLUE")
        self.set_all_leds_color("blue")
        self.root.after(5000, self.transition_to_off)
    
    def transition_to_off(self):
        """End the sequence by turning all LEDs off"""
        if not self.color_sequence_active:
            return
            
        self.log_message("Color sequence: OFF (complete)")
        self.set_all_leds_color("off")
        self.color_sequence_active = False
    
    def set_all_leds_color(self, color):
        """Set all LEDs to the specified color"""
        command = ""
        
        if color == "green":
            command = "EMS-LEDS-X|0|10|0|"
        elif color == "red":
            command = "EMS-LEDS-X|10|0|0|"
        elif color == "blue":
            command = "EMS-LEDS-X|0|0|10|"
        else:  # off
            command = "EMS-LEDS-X|0|0|0|"
        
        # Send command to all connected clients
        self.button_click(command)

# Main entrypoint
if __name__ == "__main__":
    root = tk.Tk()
    app = DarkGameServerApp(root)
    root.mainloop()
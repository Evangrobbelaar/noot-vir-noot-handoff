import os
import sys
import subprocess
import tkinter as tk
from tkinter import messagebox
import hashlib
import time

# List of valid password hashes
VALID_HASHES = [
    "fd7a8df840be1d7f57c7ce3b30f74cc2b9f35b7b63a7e47d257d9a4a8c387c75",  # Regular password: "gameshow123"
    "a2e458b4c9e7e4e8c6c2e5b6f5e9d8b2e4f6c8a7b5d9e2f4c6a8b7d9e2f4c6a8"   # Master password: "admin_master_pass"
]

class PasswordWindow:
    def __init__(self, root):
        self.root = root
        self.root.title("Gameshow Login")
        self.root.geometry("320x200")
        self.root.resizable(False, False)
        
        # Configure appearance
        self.root.configure(bg="#222222")
        
        # Center on screen
        self.center_window()
        
        # Create widgets
        self.create_widgets()
        
        # Set focus to password entry
        self.password_entry.focus_set()
        
        # Bind Enter key to login
        self.root.bind("<Return>", lambda event: self.verify_password())
        
    def center_window(self):
        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        x = (screen_width - width) // 2
        y = (screen_height - height) // 2
        self.root.geometry(f"+{x}+{y}")
    
    def create_widgets(self):
        # Header
        header_frame = tk.Frame(self.root, bg="#222222", pady=10)
        header_frame.pack(fill=tk.X)
        
        header_label = tk.Label(
            header_frame, 
            text="GAMESHOW LOGIN", 
            font=("Arial", 16, "bold"),
            fg="#FFFFFF",
            bg="#222222"
        )
        header_label.pack()
        
        # Main content
        content_frame = tk.Frame(self.root, bg="#222222", padx=30, pady=10)
        content_frame.pack(fill=tk.BOTH, expand=True)
        
        # Password label
        password_label = tk.Label(
            content_frame,
            text="Password:",
            font=("Arial", 12),
            fg="#FFFFFF",
            bg="#222222",
            anchor="w"
        )
        password_label.pack(fill=tk.X, pady=(0, 5))
        
        # Password entry
        self.password_var = tk.StringVar()
        self.password_entry = tk.Entry(
            content_frame,
            textvariable=self.password_var,
            show="•",
            font=("Arial", 12),
            bd=0,
            highlightthickness=1,
            highlightbackground="#555555",
            highlightcolor="#3498db",
            bg="#333333",
            fg="#FFFFFF",
            insertbackground="#FFFFFF"
        )
        self.password_entry.pack(fill=tk.X, pady=(0, 15))
        
        # Button frame
        button_frame = tk.Frame(content_frame, bg="#222222")
        button_frame.pack(fill=tk.X)
        
        # Login button
        login_button = tk.Button(
            button_frame,
            text="Login",
            command=self.verify_password,
            bg="#3498db",
            fg="#FFFFFF",
            font=("Arial", 11, "bold"),
            activebackground="#2980b9",
            activeforeground="#FFFFFF",
            bd=0,
            padx=15,
            pady=5,
            cursor="hand2"
        )
        login_button.pack(side=tk.LEFT, padx=(0, 10))
        
        # Cancel button
        cancel_button = tk.Button(
            button_frame,
            text="Cancel",
            command=self.root.destroy,
            bg="#e74c3c",
            fg="#FFFFFF",
            font=("Arial", 11),
            activebackground="#c0392b",
            activeforeground="#FFFFFF",
            bd=0,
            padx=10,
            pady=5,
            cursor="hand2"
        )
        cancel_button.pack(side=tk.LEFT)
    
    def verify_password(self):
        password = self.password_var.get()
        
        # Check if password is empty
        if not password:
            messagebox.showerror("Error", "Please enter a password", parent=self.root)
            return
        
        # Hash the entered password
        hashed = hashlib.sha256(password.encode()).hexdigest()
        
        # Check if hashed password matches any valid hash
        if hashed in VALID_HASHES:
            self.root.destroy()
            # Launch the applications
            self.launch_applications()
        else:
            messagebox.showerror("Access Denied", "Incorrect password", parent=self.root)
            self.password_entry.select_range(0, tk.END)
            self.password_entry.focus_set()
    
    def launch_applications(self):
        try:
            # Get the directory where this script is located
            script_dir = os.path.dirname(os.path.abspath(__file__))
            
            # Define paths to applications
            toggler_path = os.path.join(script_dir, "toggler.py")
            gameshow_path = os.path.join(script_dir, "gameshow2.py")
            leaderboard_path = os.path.join(script_dir, "leaderboard.py")
            bsd_path = os.path.join(script_dir, "bsd.py")
            
            # Check if files exist
            missing_files = []
            if not os.path.exists(toggler_path):
                missing_files.append(f"Toggler script at {toggler_path}")
            if not os.path.exists(gameshow_path):
                missing_files.append(f"Gameshow script at {gameshow_path}")
            if not os.path.exists(leaderboard_path):
                missing_files.append(f"Leaderboard script at {leaderboard_path}")
            if not os.path.exists(bsd_path):
                missing_files.append(f"BSD script at {bsd_path}")
            
            if missing_files:
                error_msg = "Some required files are missing:\n" + \
                           "\n".join(f" - {file}" for file in missing_files)
                messagebox.showerror("Error", error_msg)
                return
            
            # Create a status window
            status_root = tk.Tk()
            status_root.title("Launching Applications")
            status_root.geometry("400x250")
            status_root.configure(bg="#222222")
            
            # Center status window
            screen_width = status_root.winfo_screenwidth()
            screen_height = status_root.winfo_screenheight()
            x = (screen_width - 400) // 2
            y = (screen_height - 250) // 2
            status_root.geometry(f"+{x}+{y}")
            
            # Status header
            header_label = tk.Label(
                status_root, 
                text="LAUNCHING APPLICATIONS", 
                font=("Arial", 16, "bold"),
                fg="#FFFFFF",
                bg="#222222",
                pady=10
            )
            header_label.pack()
            
            # Status text box
            status_text = tk.Text(
                status_root,
                height=10,
                width=45,
                font=("Consolas", 10),
                bg="#333333",
                fg="#FFFFFF",
                padx=10,
                pady=10
            )
            status_text.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
            
            # Close button
            close_button = tk.Button(
                status_root,
                text="Close",
                command=status_root.destroy,
                bg="#3498db",
                fg="#FFFFFF",
                font=("Arial", 11, "bold"),
                bd=0,
                padx=20,
                pady=5
            )
            close_button.pack(pady=10)
            
            # Function to update status
            def update_status(message):
                status_text.insert(tk.END, message + "\n")
                status_text.see(tk.END)
                status_root.update()
            
            # Start applications
            update_status("Password authentication successful!")
            
            # Start BSD console first
            update_status("Starting BSD console...")
            bsd_process = subprocess.Popen(
                [sys.executable, bsd_path], 
                creationflags=subprocess.CREATE_NEW_CONSOLE
            )
            time.sleep(2)
            update_status("BSD console started successfully")
            
            # Then start toggler which will handle the other apps
            update_status("Starting toggler...")
            update_status("(The toggler will start the gameshow and leaderboard)")
            toggler_process = subprocess.Popen(
                [sys.executable, toggler_path, gameshow_path, leaderboard_path], 
                creationflags=subprocess.CREATE_NEW_CONSOLE
            )
            time.sleep(1)
            update_status("Toggler started successfully")
            
            # Final messages
            update_status("\nAll applications started successfully!")
            update_status("Press 'L' to toggle between gameshow and leaderboard")
            update_status("Press 'Q' to quit all applications")
            
            # This will keep the status window open until user closes it
            status_root.mainloop()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to start applications: {str(e)}")

def main():
    # Create main window
    root = tk.Tk()
    app = PasswordWindow(root)
    
    # Run the application
    root.mainloop()

if __name__ == "__main__":
    main()
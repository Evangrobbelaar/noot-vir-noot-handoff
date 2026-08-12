import subprocess
import time
import keyboard
import sys
import os
import win32gui
import win32con
import win32api
import ctypes
from threading import Thread

class SimpleToggler:
    def __init__(self):
        self.gameshow_process = None
        self.leaderboard_process = None
        self.gameshow_visible = True  # Start with gameshow visible
        
        # Window handles
        self.gameshow_hwnd = None
        self.leaderboard_hwnd = None
        
        # Remember leaderboard position and state
        self.leaderboard_position = None  # Will store (left, top, right, bottom)
        self.leaderboard_placement = None  # Will store window placement state
        
        # File paths
        self.gameshow_path = "gameshow2.py"
        self.leaderboard_path = "leaderboard.py"
        
        # Keyboard shortcuts
        self.toggle_key = 'l'  # Press 'l' to toggle between apps
        self.exit_key = 'q'    # Press 'q' to quit both apps
        
        # Additional clicker support - map 'b' to also toggle
        self.clicker_toggle_key = 'b'  # Press 'b' on clicker to toggle
        
        # Window titles to find
        self.gameshow_title = "Gameshow Video Display"
        self.leaderboard_title = "Dynamic Leaderboard"
        
        print("Simple App Toggler initialized")
        print(f"Press '{self.toggle_key}' or '{self.clicker_toggle_key}' to toggle between Gameshow and Leaderboard")
        print(f"Press '{self.exit_key}' to quit all applications")

    def start_apps(self):
        """Start both applications initially"""
        print("Starting Gameshow...")
        try:
            # Start Gameshow
            self.gameshow_process = subprocess.Popen([sys.executable, self.gameshow_path],
                                      creationflags=subprocess.CREATE_NEW_CONSOLE)
        except Exception as e:
            print(f"Error starting Gameshow: {e}")
            return False
            
        print("Starting Leaderboard...")
        try:
            # Start Leaderboard
            self.leaderboard_process = subprocess.Popen([sys.executable, self.leaderboard_path],
                                        creationflags=subprocess.CREATE_NEW_CONSOLE)
        except Exception as e:
            print(f"Error starting Leaderboard: {e}")
            if self.gameshow_process:
                self.gameshow_process.terminate()
            return False
            
        # Give time for windows to initialize
        print("Waiting for applications to start...")
        time.sleep(3)
        
        # Find window handles
        self.find_windows()
        
        # Initial setup: Show Gameshow, hide Leaderboard
        self.show_gameshow()
        return True

    def find_windows(self):
        """Find window handles for both applications"""
        print("Finding application windows...")
        
        # Reset handles
        self.gameshow_hwnd = None
        self.leaderboard_hwnd = None
        
        # Find all windows and look for our applications
        windows = []
        
        def enum_windows_callback(hwnd, results):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                if title:
                    results.append((hwnd, title))
            return True
        
        win32gui.EnumWindows(enum_windows_callback, windows)
        
        # Find our applications by title
        for hwnd, title in windows:
            if self.gameshow_title in title:
                self.gameshow_hwnd = hwnd
                print(f"Found Gameshow window: '{title}'")
            elif self.leaderboard_title in title:
                self.leaderboard_hwnd = hwnd
                print(f"Found Leaderboard window: '{title}'")
                
                # Save leaderboard position and state when we find it
                if not self.leaderboard_position:
                    self.save_leaderboard_state()
                
        if not self.gameshow_hwnd:
            print("Could not find Gameshow window!")
            
        if not self.leaderboard_hwnd:
            print("Could not find Leaderboard window!")

    def save_leaderboard_state(self):
        """Save the current position and placement of the leaderboard window"""
        if not self.leaderboard_hwnd or not win32gui.IsWindow(self.leaderboard_hwnd):
            print("Cannot save leaderboard state - invalid handle")
            return False
            
        try:
            # Get window placement (includes restore, minimize and maximize states)
            placement = win32gui.GetWindowPlacement(self.leaderboard_hwnd)
            self.leaderboard_placement = placement
            
            # Get window rect
            rect = win32gui.GetWindowRect(self.leaderboard_hwnd)
            self.leaderboard_position = rect
            
            print(f"Saved leaderboard state: position={rect}, showCmd={placement[1]}")
            return True
        except Exception as e:
            print(f"Error saving leaderboard state: {e}")
            return False
            
    def restore_leaderboard_state(self):
        """Restore the saved position and state of the leaderboard window"""
        if not self.leaderboard_hwnd or not win32gui.IsWindow(self.leaderboard_hwnd):
            print("Cannot restore leaderboard state - invalid handle")
            return False
            
        try:
            if self.leaderboard_placement:
                win32gui.SetWindowPlacement(self.leaderboard_hwnd, self.leaderboard_placement)
                print(f"Restored leaderboard to saved placement, showCmd={self.leaderboard_placement[1]}")
                return True
            elif self.leaderboard_position:
                # Fallback to just setting position if no placement saved
                left, top, right, bottom = self.leaderboard_position
                width = right - left
                height = bottom - top
                win32gui.MoveWindow(self.leaderboard_hwnd, left, top, width, height, True)
                print(f"Restored leaderboard to saved position: {self.leaderboard_position}")
                return True
            else:
                print("No saved leaderboard state to restore")
                return False
        except Exception as e:
            print(f"Error restoring leaderboard state: {e}")
            return False

    def get_window_monitor(self, hwnd):
        """Get the monitor that a window is on"""
        try:
            monitor = win32api.MonitorFromWindow(hwnd, win32con.MONITOR_DEFAULTTONEAREST)
            monitor_info = win32api.GetMonitorInfo(monitor)
            return monitor_info
        except Exception as e:
            print(f"Error getting window monitor: {e}")
            return None

    def bring_to_foreground(self, hwnd):
        """Try multiple methods to bring a window to the foreground"""
        if not hwnd or not win32gui.IsWindow(hwnd):
            return False
            
        try:
            # First method: SetForegroundWindow
            win32gui.SetForegroundWindow(hwnd)
            return True
        except Exception:
            try:
                # Second method: BringWindowToTop + SetActiveWindow
                win32gui.BringWindowToTop(hwnd)
                win32gui.SetActiveWindow(hwnd)
                return True
            except Exception as e:
                print(f"Error bringing window to foreground: {e}")
                return False

    def show_gameshow(self):
        """Show Gameshow window and hide Leaderboard"""
        if not self.gameshow_hwnd or not win32gui.IsWindow(self.gameshow_hwnd):
            print("Gameshow window not found or invalid, refreshing windows...")
            self.find_windows()
            
        if self.gameshow_hwnd and win32gui.IsWindow(self.gameshow_hwnd):
            # Show gameshow
            print("Showing gameshow window")
            win32gui.ShowWindow(self.gameshow_hwnd, win32con.SW_SHOW)
            self.bring_to_foreground(self.gameshow_hwnd)
            
            # Hide leaderboard by sending command
            if self.leaderboard_hwnd and win32gui.IsWindow(self.leaderboard_hwnd):
                print("Hiding leaderboard window")
                self.send_command_to_leaderboard("HIDE")
                
            self.gameshow_visible = True
            print("Gameshow window is now visible")
            return True
        else:
            print("Could not find valid Gameshow window to show")
            return False

    def show_leaderboard(self):
        """Show Leaderboard window and hide Gameshow"""
        if not self.leaderboard_hwnd or not win32gui.IsWindow(self.leaderboard_hwnd):
            print("Leaderboard window not found or invalid, refreshing windows...")
            self.find_windows()
            
        if self.leaderboard_hwnd and win32gui.IsWindow(self.leaderboard_hwnd):
            # If both windows are available, check that they're on same monitor
            if self.gameshow_hwnd and win32gui.IsWindow(self.gameshow_hwnd):
                game_monitor = self.get_window_monitor(self.gameshow_hwnd)
                lead_monitor = self.get_window_monitor(self.leaderboard_hwnd)
                
                # If the leaderboard isn't on the same monitor as the gameshow,
                # get the position of the gameshow monitor
                if game_monitor and lead_monitor and game_monitor['Monitor'] != lead_monitor['Monitor']:
                    print("Warning: Leaderboard and Gameshow are on different monitors.")
                    print("Make sure to drag the leaderboard to the same screen as the gameshow.")
            
            # Save current leaderboard state if not already saved
            if not self.leaderboard_position:
                self.save_leaderboard_state()
                
            # Show leaderboard
            print("Showing leaderboard window")
            self.send_command_to_leaderboard("SHOW")
            
            # Restore the leaderboard to its saved state
            self.restore_leaderboard_state()
            
            # Make sure it's in the foreground
            self.bring_to_foreground(self.leaderboard_hwnd)
            
            # Hide gameshow
            if self.gameshow_hwnd and win32gui.IsWindow(self.gameshow_hwnd):
                print("Hiding gameshow window")
                win32gui.ShowWindow(self.gameshow_hwnd, win32con.SW_HIDE)
                
            self.gameshow_visible = False
            print("Leaderboard window is now visible")
            return True
        else:
            print("Could not find valid Leaderboard window to show")
            return False

    def send_command_to_leaderboard(self, command):
        """Send a command to the leaderboard application via named pipe"""
        try:
            # Connect to the named pipe
            import win32file
            pipe_name = r'\\.\pipe\gameshow_pipe'
            pipe = win32file.CreateFile(
                pipe_name,
                win32file.GENERIC_READ | win32file.GENERIC_WRITE,
                0, None,
                win32file.OPEN_EXISTING,
                0, None
            )
            
            # Send the command
            win32file.WriteFile(pipe, command.encode('utf-8'))
            win32file.CloseHandle(pipe)
            print(f"Sent command to leaderboard: {command}")
            return True
        except Exception as e:
            print(f"Error sending command to leaderboard: {e}")
            return False

    def toggle_visibility(self):
        """Toggle which application is visible"""
        print("\n--- Toggling visibility ---")
        
        # If switching from gameshow to leaderboard, save the leaderboard state
        if self.gameshow_visible and self.leaderboard_hwnd and win32gui.IsWindow(self.leaderboard_hwnd):
            # Save leaderboard state before hiding it
            self.save_leaderboard_state()
        
        if self.gameshow_visible:
            self.show_leaderboard()
        else:
            self.show_gameshow()
            
        # Add a slight delay to make sure the toggling has finished
        time.sleep(0.2)

    def manual_window_selection(self):
        """Allow manual window selection"""
        print("\nManual window selection mode:")
        print("Navigate to the desired window, then:")
        print("Press 1 to select the current window as the Gameshow window")
        print("Press 2 to select the current window as the Leaderboard window")
        print("Press ESC to cancel")
        
        # Use a one-time keyboard hook for selection
        selection_complete = [False]  # Use a list for mutable closure variable
        
        def on_press(key):
            if selection_complete[0]:
                return False
                
            if not hasattr(key, 'name'):
                return True
                
            if key.name == '1':
                # Get the foreground window
                hwnd = win32gui.GetForegroundWindow()
                if hwnd:
                    title = win32gui.GetWindowText(hwnd)
                    self.gameshow_hwnd = hwnd
                    print(f"Selected '{title}' as the Gameshow window")
                    selection_complete[0] = True
                    return False
            elif key.name == '2':
                # Get the foreground window
                hwnd = win32gui.GetForegroundWindow()
                if hwnd:
                    title = win32gui.GetWindowText(hwnd)
                    self.leaderboard_hwnd = hwnd
                    # Save position immediately
                    self.save_leaderboard_state()
                    print(f"Selected '{title}' as the Leaderboard window")
                    selection_complete[0] = True
                    return False
            elif key.name == 'esc':
                print("Manual selection canceled")
                selection_complete[0] = True
                return False
            return True
        
        # Create a temporary hook
        temp_hook = keyboard.hook(on_press)
        
        # Wait for selection to complete
        while not selection_complete[0]:
            time.sleep(0.1)
        
        # Remove the hook
        keyboard.unhook(temp_hook)

    def close_apps(self):
        """Terminate both applications"""
        print("Closing all applications...")
        try:
            if self.gameshow_process:
                self.gameshow_process.terminate()
            if self.leaderboard_process:
                self.leaderboard_process.terminate()
        except Exception as e:
            print(f"Error closing applications: {e}")
        
        print("Applications closed. Exiting.")
        os._exit(0)  # Force exit to avoid threading issues

    def run(self):
        """Run the toggler and listen for keyboard shortcuts"""
        if not self.start_apps():
            print("Failed to start applications.")
            return
        
        # Set up exception handling to improve stability
        def toggle_with_error_handling():
            try:
                self.toggle_visibility()
            except Exception as e:
                print(f"Error in toggle handler: {e}")
                # Try to find windows again in case of error
                self.find_windows()
                
        def manual_with_error_handling():
            try:
                self.manual_window_selection()
            except Exception as e:
                print(f"Error in manual selection: {e}")
                
        def refresh_windows_with_error_handling():
            try:
                self.find_windows()
                print("Window detection refreshed")
            except Exception as e:
                print(f"Error refreshing windows: {e}")
        
        # Set up keyboard hotkeys with error handling
        keyboard.add_hotkey(self.toggle_key, toggle_with_error_handling, suppress=True)
        
        # Add the clicker toggle key (b) with the same function as the regular toggle key (l)
        keyboard.add_hotkey(self.clicker_toggle_key, toggle_with_error_handling, suppress=True)
        
        keyboard.add_hotkey('m', manual_with_error_handling, suppress=True)
        keyboard.add_hotkey('r', refresh_windows_with_error_handling, suppress=True)
        keyboard.add_hotkey(self.exit_key, self.close_apps, suppress=True)
        
        print("Toggler is running.")
        print(f"Press '{self.toggle_key}' or '{self.clicker_toggle_key}' to toggle visibility")
        print("Press 'm' for manual window selection")
        print("Press 'r' to refresh window detection")
        print(f"Press '{self.exit_key}' to quit.")
        print("\nPresentation clicker support: The 'B' button on your clicker will toggle the leaderboard")
        
        # Main loop to keep the program running
        try:
            while True:
                time.sleep(0.1)  # Avoid high CPU usage
        except KeyboardInterrupt:
            self.close_apps()

if __name__ == "__main__":
    toggler = SimpleToggler()
    
    # Get correct file paths if provided by command line
    if len(sys.argv) > 1:
        toggler.gameshow_path = sys.argv[1]
    if len(sys.argv) > 2:
        toggler.leaderboard_path = sys.argv[2]
        
    toggler.run()
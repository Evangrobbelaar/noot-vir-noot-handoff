import subprocess
import time
import keyboard
import sys
import os
import win32gui
import win32con
import ctypes
import psutil

class SimpleToggler:
    def __init__(self):
        self.gameshow_process = None
        self.leaderboard_process = None
        self.gameshow_visible = True
        self.gameshow_hwnd = None
        self.leaderboard_hwnd = None
        self.leaderboard_placement = None
        self.gameshow_placement = None
        self.gameshow_path = "gameshow2.py"
        self.leaderboard_path = "leaderboard.py"
        self.toggle_key = 'l'
        self.exit_key = 'q'
        self.clicker_toggle_key = 'b'
        self.gameshow_title = "Gameshow Video Display"
        self.leaderboard_title = "Dynamic Leaderboard"
        self.is_running = False
        
        print("Simple App Toggler initialized")
        print(f"Press '{self.toggle_key}' or '{self.clicker_toggle_key}' to toggle between Gameshow and Leaderboard")
        print(f"Press '{self.exit_key}' to quit all applications")

    def validate_process(self, process):
        """Validate if a process is still running"""
        try:
            return process is not None and psutil.pid_exists(process.pid) and psutil.Process(process.pid).is_running()
        except psutil.NoSuchProcess:
            return False

    def start_apps(self):
        """Start both applications with retry logic"""
        print("Starting Gameshow...")
        for _ in range(3):
            try:
                self.gameshow_process = subprocess.Popen(
                    [sys.executable, self.gameshow_path],
                    creationflags=subprocess.CREATE_NEW_CONSOLE
                )
                time.sleep(1)
                if self.validate_process(self.gameshow_process):
                    break
            except Exception as e:
                print(f"Error starting Gameshow: {e}")
                time.sleep(1)
        else:
            print("Failed to start Gameshow after retries")
            return False
            
        print("Starting Leaderboard...")
        for _ in range(3):
            try:
                self.leaderboard_process = subprocess.Popen(
                    [sys.executable, self.leaderboard_path],
                    creationflags=subprocess.CREATE_NEW_CONSOLE
                )
                time.sleep(1)
                if self.validate_process(self.leaderboard_process):
                    break
            except Exception as e:
                print(f"Error starting Leaderboard: {e}")
                if self.gameshow_process:
                    self.gameshow_process.terminate()
                time.sleep(1)
        else:
            print("Failed to start Leaderboard after retries")
            return False
            
        print("Waiting for applications to start...")
        time.sleep(3)
        
        self.find_windows()
        
        if self.gameshow_hwnd and self.leaderboard_hwnd:
            self.save_gameshow_state()
            self.save_leaderboard_state()
            self.lock_leaderboard_window()  # New: Lock leaderboard window
            self.show_gameshow()
            return True
        else:
            print("Failed to find both windows")
            return False

    def find_windows(self):
        """Find window handles with retry logic"""
        for _ in range(3):
            self.gameshow_hwnd = None
            self.leaderboard_hwnd = None
            
            def enum_windows_callback(hwnd, results):
                if win32gui.IsWindowVisible(hwnd) and win32gui.IsWindow(hwnd):
                    title = win32gui.GetWindowText(hwnd)
                    if title:
                        results.append((hwnd, title))
                return True
            
            windows = []
            win32gui.EnumWindows(enum_windows_callback, windows)
            
            for hwnd, title in windows:
                if self.gameshow_title in title and not self.gameshow_hwnd:
                    self.gameshow_hwnd = hwnd
                    print(f"Found Gameshow window: '{title}'")
                elif self.leaderboard_title in title and not self.leaderboard_hwnd:
                    self.leaderboard_hwnd = hwnd
                    print(f"Found Leaderboard window: '{title}'")
            
            if self.gameshow_hwnd and self.leaderboard_hwnd:
                break
            time.sleep(1)
        
        if not self.gameshow_hwnd:
            print("Could not find Gameshow window!")
        if not self.leaderboard_hwnd:
            print("Could not find Leaderboard window!")

    def lock_leaderboard_window(self):
        """Prevent leaderboard window from being closed by intercepting WM_CLOSE"""
        if self.leaderboard_hwnd and win32gui.IsWindow(self.leaderboard_hwnd):
            try:
                # Subclass the window to handle WM_CLOSE
                self.original_wndproc = win32gui.GetWindowLong(self.leaderboard_hwnd, win32con.GWL_WNDPROC)
                def new_wndproc(hwnd, msg, wparam, lparam):
                    if msg == win32con.WM_CLOSE:
                        print("Leaderboard close attempt blocked")
                        return 0  # Ignore close event
                    return win32gui.CallWindowProc(self.original_wndproc, hwnd, msg, wparam, lparam)
                self.new_wndproc = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_int, ctypes.c_uint, ctypes.c_wparam, ctypes.c_lparam)(new_wndproc)
                win32gui.SetWindowLong(self.leaderboard_hwnd, win32con.GWL_WNDPROC, ctypes.cast(self.new_wndproc, ctypes.c_void_p).value)
                print("Leaderboard window locked against closure")
            except Exception as e:
                print(f"Error locking leaderboard window: {e}")

    def save_gameshow_state(self):
        """Save the current placement of the gameshow window"""
        if self.gameshow_hwnd and win32gui.IsWindow(self.gameshow_hwnd):
            try:
                self.gameshow_placement = win32gui.GetWindowPlacement(self.gameshow_hwnd)
                print(f"Saved gameshow state: position={self.gameshow_placement[4]}")
                return True
            except Exception as e:
                print(f"Error saving gameshow state: {e}")
        return False

    def save_leaderboard_state(self):
        """Save the current placement of the leaderboard window"""
        if self.leaderboard_hwnd and win32gui.IsWindow(self.leaderboard_hwnd):
            try:
                self.leaderboard_placement = win32gui.GetWindowPlacement(self.leaderboard_hwnd)
                print(f"Saved leaderboard state: position={self.leaderboard_placement[4]}")
                return True
            except Exception as e:
                print(f"Error saving leaderboard state: {e}")
        return False

    def bring_to_foreground(self, hwnd):
        """Bring a window to the foreground without changing position"""
        if not hwnd or not win32gui.IsWindow(hwnd):
            return False
        for _ in range(3):
            try:
                win32gui.BringWindowToTop(hwnd)
                return True
            except Exception as e:
                print(f"Error bringing window to foreground: {e}")
                time.sleep(0.1)
        return False

    def show_gameshow(self):
        """Show Gameshow window and hide Leaderboard, preserving positions"""
        if not self.gameshow_hwnd or not win32gui.IsWindow(self.gameshow_hwnd):
            print("Gameshow window not found, refreshing...")
            self.find_windows()
            
        if self.gameshow_hwnd and win32gui.IsWindow(self.gameshow_hwnd):
            if self.gameshow_placement:
                win32gui.SetWindowPlacement(self.gameshow_hwnd, self.gameshow_placement)
            else:
                win32gui.ShowWindow(self.gameshow_hwnd, win32con.SW_SHOWNOACTIVATE)
                
            self.bring_to_foreground(self.gameshow_hwnd)
            
            if self.leaderboard_hwnd and win32gui.IsWindow(self.leaderboard_hwnd):
                win32gui.SetWindowPos(
                    self.leaderboard_hwnd, 
                    win32con.HWND_NOTOPMOST, 
                    0, 0, 0, 0, 
                    win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_NOACTIVATE
                )
                win32gui.ShowWindow(self.leaderboard_hwnd, win32con.SW_HIDE)
            
            self.gameshow_visible = True
            print("Gameshow window is now visible at saved position")
            return True
        return False

    def show_leaderboard(self):
        """Show Leaderboard window and hide Gameshow, preserving positions"""
        if not self.leaderboard_hwnd or not win32gui.IsWindow(self.leaderboard_hwnd):
            print("Leaderboard window not found, refreshing...")
            self.find_windows()
            
        if self.leaderboard_hwnd and win32gui.IsWindow(self.leaderboard_hwnd):
            if self.leaderboard_placement:
                win32gui.SetWindowPlacement(self.leaderboard_hwnd, self.leaderboard_placement)
            else:
                win32gui.ShowWindow(self.leaderboard_hwnd, win32con.SW_SHOWNOACTIVATE)
                
            win32gui.SetWindowPos(
                self.leaderboard_hwnd, 
                win32con.HWND_TOPMOST,
                0, 0, 0, 0,
                win32con.SWP_NOMOVE | win32con.SWP_NOSIZE
            )
            
            self.bring_to_foreground(self.leaderboard_hwnd)
            
            if self.gameshow_hwnd and win32gui.IsWindow(self.gameshow_hwnd):
                win32gui.ShowWindow(self.gameshow_hwnd, win32con.SW_HIDE)
            
            self.gameshow_visible = False
            print("Leaderboard window is now visible at saved position")
            return True
        return False

    def check_and_restart_leaderboard(self):
        """Check if leaderboard process is running and restart if necessary"""
        if not self.validate_process(self.leaderboard_process):
            print("Leaderboard process stopped, attempting to restart...")
            for _ in range(3):
                try:
                    self.leaderboard_process = subprocess.Popen(
                        [sys.executable, self.leaderboard_path],
                        creationflags=subprocess.CREATE_NEW_CONSOLE
                    )
                    time.sleep(1)
                    if self.validate_process(self.leaderboard_process):
                        print("Leaderboard restarted successfully")
                        self.find_windows()
                        self.lock_leaderboard_window()  # Re-lock the new window
                        self.save_leaderboard_state()
                        if not self.gameshow_visible:
                            self.show_leaderboard()
                        return True
                except Exception as e:
                    print(f"Error restarting Leaderboard: {e}")
                    time.sleep(1)
            print("Failed to restart Leaderboard after retries")
            return False
        return True

    def toggle_visibility(self):
        """Toggle which application is visible with position preservation"""
        if not self.validate_process(self.gameshow_process):
            print("Gameshow process has stopped, attempting restart...")
            self.close_apps()
            self.start_apps()
            return
            
        # Check and restart leaderboard if necessary
        self.check_and_restart_leaderboard()
            
        # Save positions before toggling
        if not self.gameshow_visible:
            self.save_leaderboard_state()
        else:
            self.save_gameshow_state()
            
        if self.gameshow_visible:
            self.show_leaderboard()
        else:
            self.show_gameshow()
        
        time.sleep(0.2)

    def close_apps(self):
        """Terminate both applications"""
        self.is_running = False
        print("Closing all applications...")
        try:
            if self.gameshow_process and self.validate_process(self.gameshow_process):
                self.gameshow_process.terminate()
            if self.leaderboard_process and self.validate_process(self.leaderboard_process):
                self.leaderboard_process.terminate()
        except Exception as e:
            print(f"Error closing applications: {e}")
        print("Applications closed. Exiting.")
        os._exit(0)

    def handle_key_event(self, event):
        """Handle global keyboard events"""
        if event.event_type == keyboard.KEY_DOWN:
            try:
                if event.name == self.toggle_key or event.name == self.clicker_toggle_key:
                    self.toggle_visibility()
                elif event.name == self.exit_key:
                    self.close_apps()
            except Exception as e:
                print(f"Error in key handler: {e}")
                self.find_windows()

    def run(self):
        """Run the toggler with global key listening"""
        if not self.start_apps():
            print("Failed to start applications.")
            return
            
        self.is_running = True
        keyboard.hook(self.handle_key_event)
        
        print("Toggler is running with global key listening.")
        print(f"Press '{self.toggle_key}' or '{self.clicker_toggle_key}' to toggle visibility")
        print(f"Press '{self.exit_key}' to quit.")
        
        try:
            while self.is_running:
                self.check_and_restart_leaderboard()  # Periodically check leaderboard
                time.sleep(0.5)  # Increased interval to reduce CPU usage
        except KeyboardInterrupt:
            self.close_apps()

if __name__ == "__main__":
    try:
        import psutil
    except ImportError:
        print("psutil module is required. Please install it using: pip install psutil")
        sys.exit(1)
        
    toggler = SimpleToggler()
    if len(sys.argv) > 1:
        toggler.gameshow_path = sys.argv[1]
    if len(sys.argv) > 2:
        toggler.leaderboard_path = sys.argv[2]
    toggler.run()
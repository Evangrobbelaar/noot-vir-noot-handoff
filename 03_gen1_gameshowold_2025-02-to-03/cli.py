#!/usr/bin/env python3
"""
Windows Presentation Clicker Input Reader

This program detects and reads input from a presentation clicker connected via USB,
printing all events to the terminal. It uses the pynput library which works on Windows.

Requirements:
- Python 3.x
- pynput library (install with: pip install pynput)
"""

from pynput import keyboard
import time
import sys
import threading

# Flag to control when to stop listening
running = True

def on_press(key):
    """Callback function when a key is pressed"""
    try:
        # For regular keys
        timestamp = time.strftime("%H:%M:%S", time.localtime())
        print(f"[{timestamp}] KEY PRESSED: {key.char}")
    except AttributeError:
        # For special keys
        timestamp = time.strftime("%H:%M:%S", time.localtime())
        # Map some common presentation clicker buttons to their likely function
        key_name = str(key)
        if key == keyboard.Key.left:
            key_name = "LEFT/PREVIOUS SLIDE"
        elif key == keyboard.Key.right:
            key_name = "RIGHT/NEXT SLIDE"
        elif key == keyboard.Key.up:
            key_name = "UP"
        elif key == keyboard.Key.down:
            key_name = "DOWN"
        elif key == keyboard.Key.page_up:
            key_name = "PAGE UP"
        elif key == keyboard.Key.page_down:
            key_name = "PAGE DOWN"
        elif key == keyboard.Key.f5:
            key_name = "START PRESENTATION (F5)"
        elif key == keyboard.Key.esc:
            key_name = "EXIT PRESENTATION (ESC)"
        
        print(f"[{timestamp}] KEY PRESSED: {key_name}")

def on_release(key):
    """Callback function when a key is released"""
    timestamp = time.strftime("%H:%M:%S", time.localtime())
    
    # Map keys to friendly names like in the press function
    key_name = str(key)
    if key == keyboard.Key.left:
        key_name = "LEFT/PREVIOUS SLIDE"
    elif key == keyboard.Key.right:
        key_name = "RIGHT/NEXT SLIDE"
    elif key == keyboard.Key.up:
        key_name = "UP"
    elif key == keyboard.Key.down:
        key_name = "DOWN"
    elif key == keyboard.Key.page_up:
        key_name = "PAGE UP"
    elif key == keyboard.Key.page_down:
        key_name = "PAGE DOWN"
    elif key == keyboard.Key.f5:
        key_name = "START PRESENTATION (F5)"
    elif key == keyboard.Key.esc:
        key_name = "EXIT PRESENTATION (ESC)"
        
    print(f"[{timestamp}] KEY RELEASED: {key_name}")
    
    # Stop listener if ESC is pressed while holding CTRL
    if key == keyboard.Key.esc and keyboard.Controller().pressed(keyboard.Key.ctrl):
        global running
        running = False
        return False  # Stop listener

def monitor_keyboard():
    """Start monitoring keyboard inputs"""
    print("Presentation Clicker Input Reader for Windows")
    print("============================================")
    print("Press Ctrl+ESC to exit")
    
    # Start listening for keyboard events
    with keyboard.Listener(
            on_press=on_press,
            on_release=on_release) as listener:
        listener.join()

def check_exit():
    """Thread to check for exit command from console"""
    global running
    while running:
        user_input = input("")
        if user_input.lower() == "exit":
            running = False
            print("\nExiting program...")
            break
    
    # Force exit if the listener doesn't stop
    sys.exit(0)

def main():
    """Main function to run the program"""
    try:
        # Start a thread to check for console exit command
        exit_thread = threading.Thread(target=check_exit)
        exit_thread.daemon = True
        exit_thread.start()
        
        # Start keyboard monitoring
        monitor_keyboard()
        
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
    
    print("Program ended")
    
if __name__ == "__main__":
    main()
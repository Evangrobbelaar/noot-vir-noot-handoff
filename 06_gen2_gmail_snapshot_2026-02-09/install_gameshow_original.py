import os
import sys
import shutil
import subprocess
import time
import sqlite3
import tkinter as tk
from tkinter import messagebox

# Configuration
APP_NAME = "Gameshow"
REQUIRED_FILES = ["toggler.py", "gameshow2.py", "leaderboard.py", "bsd.py"]
REQUIRED_DIRS = ["vid"]
ICON_FILENAME = "gameshow_icon.png"  # Look for this file in the current directory
DB_FILE = "access_codes.db"  # Database file for access codes

def create_icon_from_png(png_path):
    """Convert a PNG file to an ICO file using PIL if available"""
    try:
        from PIL import Image
        import tempfile
        
        ico_path = os.path.join(tempfile.gettempdir(), 'gameshow_icon.ico')
        img = Image.open(png_path)
        img.save(ico_path, format='ICO')
        return ico_path
    except ImportError:
        print("PIL/Pillow not found. Using default icon.")
        return None
    except Exception as e:
        print(f"Error creating icon from PNG: {e}")
        return None

def initialize_database(db_path):
    """Initialize the database and create the access_codes table if it doesn't exist."""
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS access_codes
                 (code TEXT PRIMARY KEY)''')
    conn.commit()
    conn.close()

def add_initial_codes(db_path, codes):
    """Add initial access codes to the database."""
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    for code in codes:
        try:
            c.execute("INSERT INTO access_codes (code) VALUES (?)", (code,))
            conn.commit()
            print(f"Added initial access code: {code}")
        except sqlite3.IntegrityError:
            print(f"Access code '{code}' already exists.")
    conn.close()

def main():
    print(f"\n{'-'*60}")
    print(f"{APP_NAME} App Installer (With PNG Icon and Access Codes)".center(60))
    print(f"{'-'*60}\n")
    
    # 1. Check environment
    print("Checking environment...")
    current_dir = os.getcwd()
    print(f"Current directory: {current_dir}")
    
    # Check for icon file
    icon_path = os.path.join(current_dir, ICON_FILENAME)
    has_custom_icon = os.path.exists(icon_path)
    if has_custom_icon:
        print(f"✓ Found custom icon: {ICON_FILENAME}")
    else:
        print(f"! Custom icon '{ICON_FILENAME}' not found, will use default icon")
    
    # 2. Verify required files exist
    print("\nVerifying files...")
    missing_files = []
    for filename in REQUIRED_FILES:
        file_path = os.path.join(current_dir, filename)
        if not os.path.isfile(file_path):
            missing_files.append(filename)
        else:
            print(f"✓ Found {filename}")
    
    missing_dirs = []
    for dirname in REQUIRED_DIRS:
        dir_path = os.path.join(current_dir, dirname)
        if not os.path.isdir(dir_path):
            missing_dirs.append(dirname)
        else:
            print(f"✓ Found {dirname}/ directory")
    
    if missing_files or missing_dirs:
        print("\nERROR: Some required files or directories are missing:")
        for file in missing_files:
            print(f"  - {file}")
        for dir in missing_dirs:
            print(f"  - {dir}/ directory")
        print("\nPlease make sure all required files are in the current directory.")
        input("\nPress Enter to exit...")
        return
    
    # 3. Create app directory on desktop
    desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
    app_dir = os.path.join(desktop_path, f"{APP_NAME}App")
    
    print(f"\nCreating app directory: {app_dir}")
    if os.path.exists(app_dir):
        choice = input(f"The directory {app_dir} already exists. Overwrite? (y/n): ")
        if choice.lower() != 'y':
            print("Installation cancelled.")
            return
        
        print("Removing existing directory...")
        try:
            shutil.rmtree(app_dir)
        except Exception as e:
            print(f"Error removing directory: {e}")
            print("Please close any applications that might be using files in this directory.")
            input("\nPress Enter to exit...")
            return
    
    # Create the directory
    try:
        os.makedirs(app_dir)
        print(f"Created directory: {app_dir}")
    except Exception as e:
        print(f"Error creating directory: {e}")
        input("\nPress Enter to exit...")
        return
    
    # 4. Copy files
    print("\nCopying files...")
    
    # Copy Python files
    for filename in REQUIRED_FILES:
        src_path = os.path.join(current_dir, filename)
        dst_path = os.path.join(app_dir, filename)
        
        try:
            shutil.copy2(src_path, dst_path)
            print(f"✓ Copied {filename}")
        except Exception as e:
            print(f"Error copying {filename}: {e}")
    
    # Copy icon file if it exists
    if has_custom_icon:
        try:
            icon_dest = os.path.join(app_dir, ICON_FILENAME)
            shutil.copy2(icon_path, icon_dest)
            print(f"✓ Copied {ICON_FILENAME}")
        except Exception as e:
            print(f"Error copying icon file: {e}")
            has_custom_icon = False
    
    # Copy vid directory with all its contents
    for dirname in REQUIRED_DIRS:
        src_dir = os.path.join(current_dir, dirname)
        dst_dir = os.path.join(app_dir, dirname)
        
        try:
            shutil.copytree(src_dir, dst_dir)
            print(f"✓ Copied {dirname}/ directory with all contents")
        except Exception as e:
            print(f"Error copying {dirname}/ directory: {e}")
    
    # 5. Create or copy the access code database
    db_source = os.path.join(current_dir, DB_FILE)
    db_dest = os.path.join(app_dir, DB_FILE)
    
    if os.path.exists(db_source):
        shutil.copy2(db_source, db_dest)
        print(f"✓ Copied existing {DB_FILE}")
    else:
        initialize_database(db_dest)
        # Add initial access codes (customize as needed)
        initial_codes = ["code1", "code2", "code3"]
        add_initial_codes(db_dest, initial_codes)
        print(f"✓ Created and populated {DB_FILE} with initial access codes")
    
    # 6. Create launcher script with access code authentication and landing screen
    launcher_content = f"""\"\"\"
Gameshow Launcher with Access Code Authentication and Landing Screen
\"\"\"
import os
import sys
import subprocess
import time
import sqlite3
import tkinter as tk
from tkinter import messagebox

# Database file path
DB_FILE = '{DB_FILE}'

def use_access_code(code):
    \"\"\"Validate an access code: check if it exists, remove it if it does, and return True/False.\"\"\"
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT code FROM access_codes WHERE code = ?", (code,))
    result = c.fetchone()
    if result:
        c.execute("DELETE FROM access_codes WHERE code = ?", (code,))
        conn.commit()
        conn.close()
        return True
    else:
        conn.close()
        return False

def check_access_code():
    def verify():
        entered_code = entry.get()
        if use_access_code(entered_code):
            root.destroy()
            show_landing_screen()
        else:
            messagebox.showerror("Error", "Invalid or used access code!")
            entry.delete(0, tk.END)

    root = tk.Tk()
    root.title("Gameshow Launcher")
    root.geometry("300x150")
    
    tk.Label(root, text="Enter your access code to launch Gameshow:").pack(pady=10)
    entry = tk.Entry(root, show="*")
    entry.pack(pady=10)
    
    tk.Button(root, text="Login", command=verify).pack(pady=10)
    
    root.mainloop()

def show_landing_screen():
    def launch_apps():
        root.destroy()
        start_applications()

    root = tk.Tk()
    root.title("Gameshow - Getting Started")
    root.geometry("500x400")
    
    tk.Label(root, text="Welcome to Gameshow!", font=("Arial", 16, "bold")).pack(pady=10)
    
    instructions = (
        "To use the Gameshow application:\\n\\n"
        "1. Switch on the clicker device\\n"
        "2. Insert the USB dongle into your device\\n"
        "3. Drag the Leaderboard window to its display screen\\n"
        "4. Drag the Gameshow window to its display screen\\n"
        "5. Press the clicker to start the game\\n"
        "6. Assign points using the BSD dashboard\\n\\n"
        "Additional controls:\\n"
        "- Press 'L' to toggle between Gameshow and Leaderboard\\n"
        "- Press 'Q' to quit all applications"
    )
    
    tk.Label(root, text=instructions, justify="left", wraplength=450).pack(pady=10)
    
    tk.Button(root, text="Launch Gameshow", command=launch_apps, 
             font=("Arial", 12), bg="green", fg="white").pack(pady=20)
    
    root.mainloop()

def start_applications():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    
    toggler_path = os.path.join(script_dir, "toggler.py")
    gameshow_path = os.path.join(script_dir, "gameshow2.py")
    leaderboard_path = os.path.join(script_dir, "leaderboard.py")
    bsd_path = os.path.join(script_dir, "bsd.py")
    
    missing_files = []
    if not os.path.exists(toggler_path):
        missing_files.append(f"Toggler script at {{toggler_path}}")
    if not os.path.exists(gameshow_path):
        missing_files.append(f"Gameshow script at {{gameshow_path}}")
    if not os.path.exists(leaderboard_path):
        missing_files.append(f"Leaderboard script at {{leaderboard_path}}")
    if not os.path.exists(bsd_path):
        missing_files.append(f"BSD script at {{bsd_path}}")
    
    if missing_files:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("Error", "Missing files:\\n" + "\\n".join(missing_files))
        root.destroy()
        return
    
    try:
        # Start BSD console
        bsd_process = subprocess.Popen([sys.executable, bsd_path], 
                                     creationflags=subprocess.CREATE_NEW_CONSOLE)
        time.sleep(2)
        
        # Start toggler
        toggler_process = subprocess.Popen(
            [sys.executable, toggler_path, gameshow_path, leaderboard_path], 
            creationflags=subprocess.CREATE_NEW_CONSOLE
        )
        
    except Exception as e:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("Error", f"Failed to start applications: {{e}}")
        root.destroy()

if __name__ == "__main__":
    check_access_code()
"""
    
    # Create launcher script
    print("\nCreating launcher script...")
    launcher_path = os.path.join(app_dir, f"{APP_NAME}_launcher.py")
    
    try:
        with open(launcher_path, 'w') as f:
            f.write(launcher_content)
        print(f"✓ Created {os.path.basename(launcher_path)}")
    except Exception as e:
        print(f"Error creating launcher script: {e}")
    
    # 7. Create batch file for easy launching
    batch_path = os.path.join(app_dir, f"{APP_NAME}.bat")
    
    try:
        with open(batch_path, 'w') as f:
            f.write(f'@echo off\ncd /d "{app_dir}"\n"{sys.executable}" "{launcher_path}"\n')
        print(f"✓ Created {os.path.basename(batch_path)}")
    except Exception as e:
        print(f"Error creating batch file: {e}")
    
    # 8. Create desktop shortcut
    shortcut_path = os.path.join(desktop_path, f"{APP_NAME}.bat")
    
    try:
        with open(shortcut_path, 'w') as f:
            f.write(f'@echo off\ncd /d "{app_dir}"\n"{sys.executable}" "{launcher_path}"\n')
        print(f"✓ Created desktop shortcut: {os.path.basename(shortcut_path)}")
    except Exception as e:
        print(f"Error creating desktop shortcut: {e}")
    
    # 9. Try to create a Windows .lnk shortcut with custom icon
    try:
        import winshell
        from win32com.client import Dispatch
        
        print("\nCreating Windows shortcut...")
        
        shell = Dispatch('WScript.Shell')
        link_path = os.path.join(desktop_path, f"{APP_NAME}.lnk")
        
        shortcut = shell.CreateShortCut(link_path)
        shortcut.Targetpath = sys.executable
        shortcut.Arguments = f'"{launcher_path}"'
        shortcut.WorkingDirectory = app_dir
        
        if has_custom_icon:
            icon_dest = os.path.join(app_dir, ICON_FILENAME)
            icon_ico = create_icon_from_png(icon_dest)
            
            if icon_ico:
                shortcut.IconLocation = icon_ico
                print("✓ Using custom icon from PNG file")
            else:
                print("! Could not convert PNG to icon, using default Python icon")
                shortcut.IconLocation = f"{sys.executable},0"
        else:
            shortcut.IconLocation = f"{sys.executable},0"
            
        shortcut.save()
        
        print(f"✓ Created Windows shortcut: {os.path.basename(link_path)}")
        
        if os.path.exists(shortcut_path):
            os.remove(shortcut_path)
            print(f"✓ Removed temporary .bat shortcut")
        
    except ImportError:
        print("\nNote: For a better desktop shortcut with custom icon, install:")
        print("      pip install pywin32")
        print("      pip install pillow")
    except Exception as e:
        print(f"\nNote: Could not create Windows shortcut with custom icon: {e}")
        print("      Using the .bat shortcut instead.")
    
    # 10. Done!
    print(f"\n{'-'*60}")
    print(f"Installation Complete!".center(60))
    print(f"{'-'*60}")
    print(f"\nThe {APP_NAME} App has been installed to:")
    print(f"  {app_dir}")
    print("\nYou can run the application by:")
    print(f"  1. Double-clicking the '{APP_NAME}' icon on your desktop")
    print(f"  2. Double-clicking '{APP_NAME}.bat' in the app directory")
    
    print("\nThe following files were created:")
    print(f"  - toggler.py")
    print(f"  - gameshow2.py")
    print(f"  - leaderboard.py")
    print(f"  - bsd.py")
    print(f"  - {APP_NAME}_launcher.py")
    print(f"  - {APP_NAME}.bat")
    print(f"  - vid/ (directory with all contents)")
    print(f"  - {DB_FILE} (access code database)")
    
    if has_custom_icon:
        print(f"  - {ICON_FILENAME} (custom icon)")
    
    print(f"\nAccess codes have been added to {DB_FILE} for one-time use.")
    
    input("\nPress Enter to exit...")

if __name__ == "__main__":
    main()
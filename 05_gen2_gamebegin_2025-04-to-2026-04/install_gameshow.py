"""
install_gameshow.py — one-shot installer

Creates a self-contained copy of the Gameshow app in ~/Desktop/GameshowApp
and places a proper Windows .lnk shortcut on the desktop.

After installation:
  - Double-click the Gameshow icon on your desktop to launch.
  - At the access-code prompt enter  00000  (master code, always works)
    or any valid one-time code from the database.
"""

import os
import sys
import stat
import shutil
import sqlite3

# ── Configuration ─────────────────────────────────────────────────────────────
APP_NAME       = "Gameshow"
REQUIRED_FILES = ["toggler.py", "gameshow2.py", "leaderboard.py", "bsd.py"]
REQUIRED_DIRS  = ["vid"]
DB_FILE        = "access_codes.db"
MASTER_CODE    = "00000"   # never consumed from the database


# ── Helpers ───────────────────────────────────────────────────────────────────

def _find_pythonw() -> str:
    """Return path to pythonw.exe (no console window), fall back to python.exe."""
    pythonw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    return pythonw if os.path.exists(pythonw) else sys.executable


def _find_icon(search_dirs: list) -> str | None:
    """
    Look for an icon to use for the shortcut.
    Preference: gameshow_icon.ico → gameshow_icon.png (converted) → None.
    """
    for d in search_dirs:
        ico = os.path.join(d, "gameshow_icon.ico")
        if os.path.exists(ico):
            return ico

    for d in search_dirs:
        png = os.path.join(d, "gameshow_icon.png")
        if os.path.exists(png):
            try:
                from PIL import Image
                import tempfile
                ico_path = os.path.join(tempfile.gettempdir(), "gameshow_icon.ico")
                Image.open(png).save(ico_path, format="ICO")
                print("✓ Converted PNG icon to ICO")
                return ico_path
            except ImportError:
                pass   # PIL not available
            except Exception as e:
                print(f"! Could not convert PNG icon: {e}")

    return None


def _create_lnk(lnk_path: str, target: str, args: str,
                work_dir: str, icon: str | None):
    """Create a Windows .lnk shortcut using win32com.client (part of pywin32)."""
    from win32com.client import Dispatch
    shell     = Dispatch("WScript.Shell")
    shortcut  = shell.CreateShortCut(lnk_path)
    shortcut.Targetpath      = target
    shortcut.Arguments       = args
    shortcut.WorkingDirectory = work_dir
    shortcut.IconLocation    = f"{icon},0" if icon else f"{target},0"
    shortcut.save()


def initialize_database(db_path):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS access_codes (code TEXT PRIMARY KEY)")
    conn.commit()
    conn.close()


def add_initial_codes(db_path, codes):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    for code in codes:
        try:
            c.execute("INSERT INTO access_codes (code) VALUES (?)", (code,))
            conn.commit()
            print(f"  Added access code: {code}")
        except sqlite3.IntegrityError:
            print(f"  Code '{code}' already in database.")
    conn.close()


# ── Generated launcher content ────────────────────────────────────────────────
# (Written to Gameshow_launcher.py inside the installed app directory.)

LAUNCHER_CONTENT = '''\
"""
Gameshow Launcher — access-code authentication + landing screen.
Master code 00000 always works without consuming a database entry.
"""
import os, sys, subprocess, time, sqlite3
import tkinter as tk
from tkinter import messagebox

SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
DB_FILE     = os.path.join(SCRIPT_DIR, "access_codes.db")
MASTER_CODE = "00000"   # never consumed from DB


def use_access_code(code: str) -> bool:
    """Check code in DB; if found, delete it (one-time use) and return True."""
    try:
        conn = sqlite3.connect(DB_FILE)
        c    = conn.cursor()
        c.execute("SELECT code FROM access_codes WHERE code = ?", (code,))
        if c.fetchone():
            c.execute("DELETE FROM access_codes WHERE code = ?", (code,))
            conn.commit()
            conn.close()
            return True
        conn.close()
    except Exception as e:
        print(f"DB error: {e}")
    return False


def check_access_code():
    def verify():
        code = entry.get().strip()
        if code == MASTER_CODE or use_access_code(code):
            root.destroy()
            show_landing_screen()
        else:
            messagebox.showerror("Access Denied",
                                 "Invalid or already-used access code.",
                                 parent=root)
            entry.delete(0, tk.END)
            entry.focus_set()

    root = tk.Tk()
    root.title("Gameshow Login")
    root.geometry("340x160")
    root.configure(bg="#222222")
    root.resizable(False, False)

    # centre on screen
    root.update_idletasks()
    sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
    root.geometry(f"+{(sw - 340) // 2}+{(sh - 160) // 2}")

    tk.Label(root, text="GAMESHOW LOGIN",
             font=("Arial", 15, "bold"), fg="#ffffff",
             bg="#222222").pack(pady=(16, 4))
    tk.Label(root,
             text="Enter access code  (master: 00000)",
             font=("Arial", 9), fg="#888888",
             bg="#222222").pack(pady=(0, 8))

    frame = tk.Frame(root, bg="#222222", padx=30)
    frame.pack(fill=tk.X)
    entry = tk.Entry(frame, show="•", font=("Arial", 13), bd=0,
                     highlightthickness=1, highlightbackground="#555555",
                     highlightcolor="#3498db",
                     bg="#333333", fg="#ffffff", insertbackground="#ffffff")
    entry.pack(fill=tk.X, ipady=4, pady=(0, 10))
    entry.focus_set()
    root.bind("<Return>", lambda _: verify())

    tk.Button(frame, text="Login", command=verify,
              bg="#3498db", fg="#ffffff", font=("Arial", 11, "bold"),
              activebackground="#2980b9", bd=0,
              padx=16, pady=5).pack(side=tk.LEFT, padx=(0, 10))
    tk.Button(frame, text="Cancel", command=root.destroy,
              bg="#e74c3c", fg="#ffffff", font=("Arial", 11),
              activebackground="#c0392b", bd=0,
              padx=10, pady=5).pack(side=tk.LEFT)

    root.mainloop()


def show_landing_screen():
    def launch_apps():
        root.destroy()
        start_applications()

    root = tk.Tk()
    root.title("Gameshow — Getting Started")
    root.geometry("520x410")
    root.configure(bg="#1a1a2e")
    root.resizable(False, False)

    root.update_idletasks()
    sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
    root.geometry(f"+{(sw - 520) // 2}+{(sh - 410) // 2}")

    tk.Label(root, text="Welcome to Gameshow!",
             font=("Arial", 17, "bold"),
             fg="#e94560", bg="#1a1a2e").pack(pady=(20, 6))

    instructions = (
        "Before launching, make sure:\\n\\n"
        "  1. Switch on the clicker device\\n"
        "  2. Insert the USB dongle into your computer\\n"
        "  3. The leaderboard screen is connected\\n\\n"
        "After launch:\\n\\n"
        "  • Press  L  or  B  to toggle Gameshow ↔ Leaderboard\\n"
        "  • Press  Q  to quit all applications\\n"
        "  • Press  T  to send the READY trigger to buzzers"
    )

    tk.Label(root, text=instructions,
             font=("Segoe UI", 10), fg="#cccccc",
             bg="#1a1a2e", justify="left").pack(padx=30, pady=6, anchor="w")

    tk.Button(root, text="  Launch Gameshow  ",
              command=launch_apps,
              font=("Arial", 13, "bold"),
              bg="#27ae60", fg="#ffffff",
              activebackground="#2ecc71", activeforeground="#ffffff",
              bd=0, padx=20, pady=8).pack(pady=20)

    root.mainloop()


def start_applications():
    os.chdir(SCRIPT_DIR)

    toggler_path     = os.path.join(SCRIPT_DIR, "toggler.py")
    gameshow_path    = os.path.join(SCRIPT_DIR, "gameshow2.py")
    leaderboard_path = os.path.join(SCRIPT_DIR, "leaderboard.py")
    bsd_path         = os.path.join(SCRIPT_DIR, "bsd.py")

    missing = [p for p in (toggler_path, gameshow_path,
                            leaderboard_path, bsd_path)
               if not os.path.exists(p)]
    if missing:
        r = tk.Tk(); r.withdraw()
        messagebox.showerror("Missing Files",
                             "Required files not found:\\n" +
                             "\\n".join(f"  {os.path.basename(p)}"
                                        for p in missing))
        r.destroy()
        return

    try:
        subprocess.Popen([sys.executable, bsd_path],
                         creationflags=subprocess.CREATE_NEW_CONSOLE)
        time.sleep(2)
        subprocess.Popen(
            [sys.executable, toggler_path, gameshow_path, leaderboard_path],
            creationflags=subprocess.CREATE_NEW_CONSOLE,
        )
    except Exception as e:
        r = tk.Tk(); r.withdraw()
        messagebox.showerror("Launch Error",
                             f"Failed to start applications:\\n{e}")
        r.destroy()


if __name__ == "__main__":
    check_access_code()
'''


# ── Main installer ─────────────────────────────────────────────────────────────

def main():
    sys.stdout.reconfigure(encoding="utf-8")
    sep = "-" * 60
    print(f"\n{sep}")
    print(f"  {APP_NAME} Installer".center(60))
    print(f"{sep}\n")

    current_dir  = os.path.dirname(os.path.abspath(__file__))
    desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
    app_dir      = os.path.join(desktop_path, f"{APP_NAME}App")
    pythonw_exe  = _find_pythonw()

    print(f"Source : {current_dir}")
    print(f"Install: {app_dir}")
    print(f"Python : {pythonw_exe}\n")

    # 1. Verify required files ─────────────────────────────────────────────────
    print("Checking source files...")
    missing_files = [f for f in REQUIRED_FILES
                     if not os.path.isfile(os.path.join(current_dir, f))]
    missing_dirs  = [d for d in REQUIRED_DIRS
                     if not os.path.isdir(os.path.join(current_dir, d))]

    for f in REQUIRED_FILES:
        mark = "✓" if f not in missing_files else "✗"
        print(f"  {mark} {f}")
    for d in REQUIRED_DIRS:
        mark = "✓" if d not in missing_dirs else "✗"
        print(f"  {mark} {d}/")

    if missing_files or missing_dirs:
        print("\nERROR: required files are missing — aborting.")
        input("Press Enter to exit...")
        return

    # 2. Create / overwrite install directory ─────────────────────────────────
    if os.path.exists(app_dir):
        answer = input(f"\n{APP_NAME}App already exists. Overwrite? (y/n): ")
        if answer.lower() != "y":
            print("Installation cancelled.")
            return
        def _force_remove(func, path, _):
            """onerror handler: strip read-only flag then retry."""
            os.chmod(path, stat.S_IWRITE)
            func(path)
        try:
            shutil.rmtree(app_dir, onerror=_force_remove)
        except Exception as e:
            print(f"ERROR removing existing directory: {e}")
            print("Close any apps that may be using files there, then try again.")
            input("Press Enter to exit...")
            return

    os.makedirs(app_dir)
    print(f"\n✓ Created {app_dir}")

    # 3. Copy game files ───────────────────────────────────────────────────────
    print("\nCopying files...")
    for filename in REQUIRED_FILES:
        try:
            shutil.copy2(os.path.join(current_dir, filename),
                         os.path.join(app_dir, filename))
            print(f"  ✓ {filename}")
        except Exception as e:
            print(f"  ✗ {filename}: {e}")

    for dirname in REQUIRED_DIRS:
        try:
            shutil.copytree(os.path.join(current_dir, dirname),
                            os.path.join(app_dir, dirname))
            print(f"  ✓ {dirname}/")
        except Exception as e:
            print(f"  ✗ {dirname}/: {e}")

    # Copy any icon files found next to the installer
    for icon_name in ("gameshow_icon.ico", "gameshow_icon.png"):
        src = os.path.join(current_dir, icon_name)
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(app_dir, icon_name))
            print(f"  ✓ {icon_name}")

    # 4. Access-code database ──────────────────────────────────────────────────
    db_source = os.path.join(current_dir, DB_FILE)
    db_dest   = os.path.join(app_dir, DB_FILE)
    if os.path.exists(db_source):
        shutil.copy2(db_source, db_dest)
        print(f"\n✓ Copied existing {DB_FILE}")
    else:
        initialize_database(db_dest)
        add_initial_codes(db_dest, ["code1", "code2", "code3"])
        print(f"\n✓ Created {DB_FILE} with starter codes")

    print(f"  (Master code '{MASTER_CODE}' always works — no DB entry needed)")

    # 5. Write the launcher script ─────────────────────────────────────────────
    launcher_path = os.path.join(app_dir, f"{APP_NAME}_launcher.py")
    with open(launcher_path, "w", encoding="utf-8") as f:
        f.write(LAUNCHER_CONTENT)
    print(f"\n✓ Created {os.path.basename(launcher_path)}")

    # 6. Desktop shortcut (.lnk) ───────────────────────────────────────────────
    print("\nCreating desktop shortcut...")
    icon_path = _find_icon([app_dir, current_dir])
    lnk_path  = os.path.join(desktop_path, f"{APP_NAME}.lnk")

    try:
        _create_lnk(
            lnk_path  = lnk_path,
            target    = pythonw_exe,            # no console window on click
            args      = f'"{launcher_path}"',
            work_dir  = app_dir,
            icon      = icon_path,
        )
        print(f"  ✓ Desktop shortcut created: {APP_NAME}.lnk")
        if icon_path:
            print(f"  ✓ Icon: {os.path.basename(icon_path)}")
        else:
            print(f"  ℹ No custom icon found — using Python default")
            print(f"    (place gameshow_icon.ico next to this script and re-run)")
    except ImportError:
        # pywin32 not installed — fall back to a .bat on the desktop
        bat_path = os.path.join(desktop_path, f"{APP_NAME}.bat")
        with open(bat_path, "w") as f:
            f.write(f'@echo off\ncd /d "{app_dir}"\n'
                    f'"{sys.executable}" "{launcher_path}"\n')
        print(f"  ✓ Fallback .bat shortcut created on desktop")
        print(f"  ! Install pywin32 for a proper .lnk icon:  pip install pywin32")
    except Exception as e:
        print(f"  ✗ Shortcut error: {e}")

    # 7. Done ──────────────────────────────────────────────────────────────────
    print(f"\n{sep}")
    print(f"  Installation complete!".center(60))
    print(f"{sep}")
    print(f"\nApp folder : {app_dir}")
    print(f"Desktop    : {APP_NAME}.lnk  (double-click to launch)")
    print(f"\nAt the login prompt:")
    print(f"  • Master code  :  {MASTER_CODE}  (always works)")
    print(f"  • One-time code:  any code from {DB_FILE}")
    input("\nPress Enter to exit...")


if __name__ == "__main__":
    main()

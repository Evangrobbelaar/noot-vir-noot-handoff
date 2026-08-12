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
        "Before launching, make sure:\n\n"
        "  1. Switch on the clicker device\n"
        "  2. Insert the USB dongle into your computer\n"
        "  3. The leaderboard screen is connected\n\n"
        "After launch:\n\n"
        "  • Press  L  or  B  to toggle Gameshow ↔ Leaderboard\n"
        "  • Press  Q  to quit all applications\n"
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
                             "Required files not found:\n" +
                             "\n".join(f"  {os.path.basename(p)}"
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
                             f"Failed to start applications:\n{e}")
        r.destroy()


if __name__ == "__main__":
    check_access_code()

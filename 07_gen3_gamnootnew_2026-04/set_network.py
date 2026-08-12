"""
Network Setup Utility — sets or resets the IPv4 configuration for the
gameshow router connection (192.168.8.x network).

Run as Administrator for the changes to take effect.

Static settings (from the router):
  IP      : 192.168.8.160
  Mask    : 255.255.255.0
  Gateway : 192.168.8.1
"""
import subprocess
import sys
import ctypes
import tkinter as tk
from tkinter import messagebox

STATIC_IP      = "192.168.8.160"
STATIC_MASK    = "255.255.255.0"
STATIC_GATEWAY = "192.168.8.1"


def is_admin() -> bool:
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        return False


def run_as_admin():
    """Re-launch this script with admin rights."""
    ctypes.windll.shell32.ShellExecuteW(
        None, "runas", sys.executable, " ".join(f'"{a}"' for a in sys.argv), None, 1
    )
    sys.exit()


def get_adapters() -> list[str]:
    """Return a list of network adapter names that are currently enabled."""
    result = subprocess.run(
        ["netsh", "interface", "show", "interface"],
        capture_output=True, text=True
    )
    adapters = []
    for line in result.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 4 and parts[1] == "Connected":
            name = " ".join(parts[3:])
            adapters.append(name)
    return adapters or ["Ethernet"]


def set_static(adapter: str) -> tuple[bool, str]:
    """Apply static IP settings to the named adapter."""
    cmd_ip = [
        "netsh", "interface", "ip", "set", "address",
        f"name={adapter}", "source=static",
        f"addr={STATIC_IP}", f"mask={STATIC_MASK}",
        f"gateway={STATIC_GATEWAY}", "gwmetric=1"
    ]
    cmd_dns = [
        "netsh", "interface", "ip", "set", "dns",
        f"name={adapter}", "source=static", "addr=8.8.8.8"
    ]
    for cmd in (cmd_ip, cmd_dns):
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            return False, r.stderr.strip() or r.stdout.strip()
    return True, f"Static IP {STATIC_IP} applied to '{adapter}'"


def set_dhcp(adapter: str) -> tuple[bool, str]:
    """Reset adapter to DHCP."""
    cmd_ip  = ["netsh", "interface", "ip", "set", "address",
               f"name={adapter}", "source=dhcp"]
    cmd_dns = ["netsh", "interface", "ip", "set", "dns",
               f"name={adapter}", "source=dhcp"]
    for cmd in (cmd_ip, cmd_dns):
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            return False, r.stderr.strip() or r.stdout.strip()
    return True, f"'{adapter}' reset to DHCP"


class NetworkSetupApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Gameshow Network Setup")
        self.root.configure(bg="#1a1a2e")
        self.root.resizable(False, False)
        self._build_ui()

    def _build_ui(self):
        tk.Label(self.root, text="Gameshow Network Setup",
                 font=("Arial", 14, "bold"),
                 fg="#e94560", bg="#1a1a2e").pack(pady=(16, 4))

        # Info box
        info = (
            f"Static settings for gameshow router:\n\n"
            f"  IP Address : {STATIC_IP}\n"
            f"  Subnet     : {STATIC_MASK}\n"
            f"  Gateway    : {STATIC_GATEWAY}\n"
        )
        tk.Label(self.root, text=info, font=("Consolas", 10),
                 fg="#cccccc", bg="#1a1a2e", justify="left",
                 relief="groove", bd=1).pack(padx=20, pady=8, fill=tk.X)

        # Adapter selection
        adapter_frame = tk.Frame(self.root, bg="#1a1a2e")
        adapter_frame.pack(padx=20, pady=4, fill=tk.X)

        tk.Label(adapter_frame, text="Network adapter:",
                 font=("Segoe UI", 10), fg="#cccccc",
                 bg="#1a1a2e").pack(side=tk.LEFT)

        self.adapter_var = tk.StringVar()
        adapters = get_adapters()
        self.adapter_var.set(adapters[0] if adapters else "Ethernet")

        option = tk.OptionMenu(adapter_frame, self.adapter_var, *adapters)
        option.config(bg="#2d2d2d", fg="#e0e0e0",
                      activebackground="#3d3d3d", font=("Segoe UI", 10),
                      highlightthickness=0, relief="flat")
        option["menu"].config(bg="#2d2d2d", fg="#e0e0e0")
        option.pack(side=tk.LEFT, padx=8)

        refresh_btn = tk.Button(adapter_frame, text="↻",
                                bg="#2d2d2d", fg="#e0e0e0",
                                font=("Arial", 12), relief="flat",
                                command=self._refresh_adapters)
        refresh_btn.pack(side=tk.LEFT)

        # Buttons
        btn_frame = tk.Frame(self.root, bg="#1a1a2e")
        btn_frame.pack(pady=12)

        self._btn(btn_frame, "Set Static IP\n(Connect to Router)",
                  "#27ae60", "#2ecc71", self._apply_static).pack(
                      side=tk.LEFT, padx=8)
        self._btn(btn_frame, "Reset to DHCP\n(Normal Network)",
                  "#2980b9", "#3498db", self._apply_dhcp).pack(
                      side=tk.LEFT, padx=8)

        # Status
        self.status_lbl = tk.Label(
            self.root, text="", font=("Segoe UI", 10),
            fg="#aaaaaa", bg="#1a1a2e", wraplength=380,
        )
        self.status_lbl.pack(padx=20, pady=(0, 16))

        if not is_admin():
            self.status_lbl.config(
                text="⚠  Not running as Administrator — changes will fail.\n"
                     "Close and re-run as Administrator.",
                fg="#f39c12",
            )

    def _refresh_adapters(self):
        adapters = get_adapters()
        menu = self.root.nametowidget(
            str(self.root.children.get("!optionmenu", ""))
        )
        # Rebuild via fresh widget (simpler than manipulating OptionMenu internals)
        self._build_ui()

    def _apply_static(self):
        adapter = self.adapter_var.get().strip()
        ok, msg = set_static(adapter)
        color = "#2ecc71" if ok else "#e74c3c"
        self.status_lbl.config(text=("✓ " if ok else "✗ ") + msg, fg=color)
        if not ok:
            messagebox.showerror("Error", msg, parent=self.root)

    def _apply_dhcp(self):
        adapter = self.adapter_var.get().strip()
        ok, msg = set_dhcp(adapter)
        color = "#2ecc71" if ok else "#e74c3c"
        self.status_lbl.config(text=("✓ " if ok else "✗ ") + msg, fg=color)
        if not ok:
            messagebox.showerror("Error", msg, parent=self.root)

    @staticmethod
    def _btn(parent, text, color, hover, cmd):
        b = tk.Button(parent, text=text, bg=color, fg="#ffffff",
                      font=("Segoe UI", 10, "bold"),
                      activebackground=hover, relief="flat", bd=0,
                      padx=14, pady=8, command=cmd)
        b.bind("<Enter>", lambda _: b.config(bg=hover))
        b.bind("<Leave>", lambda _: b.config(bg=color))
        return b


if __name__ == "__main__":
    if not is_admin():
        answer = input(
            "This script needs Administrator rights to change network settings.\n"
            "Re-launch as Administrator? [Y/n]: "
        ).strip().lower()
        if answer != "n":
            run_as_admin()
        # If they said no, still show the GUI (it will show a warning)

    root = tk.Tk()
    root.geometry("420x340")
    app = NetworkSetupApp(root)
    root.mainloop()

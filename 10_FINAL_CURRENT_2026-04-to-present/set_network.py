"""
Gameshow Network Switcher
=========================
Switches a named WiFi/Ethernet adapter between your normal DHCP setting
and the static-IP configuration needed to reach the gameshow router.

What the manual steps look like in Windows:
  Network & Sharing Centre → Change adapter settings →
  Right-click adapter → Properties → IPv4 Properties →
  "Use the following IP address" → fill in IP / Subnet / Gateway

This program does exactly that via netsh, with one click.

Run as Administrator (or it will re-launch itself elevated automatically).
"""

import os
import sys
import json
import ctypes
import subprocess
import threading
import tkinter as tk
from tkinter import messagebox, ttk
import logging

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [NET] %(levelname)s %(message)s"
)
log = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROFILE_PATH = os.path.join(BASE_DIR, "network_profile.json")

# ---------------------------------------------------------------------------
# Elevation helper
# ---------------------------------------------------------------------------


def _is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def _relaunch_as_admin():
    """Re-launch this script with UAC elevation."""
    params = " ".join(f'"{a}"' for a in sys.argv)
    ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, params, None, 1)
    sys.exit(0)


# ---------------------------------------------------------------------------
# netsh helpers
# ---------------------------------------------------------------------------


def _run(cmd: list[str]) -> tuple[int, str, str]:
    """Run a command, return (returncode, stdout, stderr)."""
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
    return result.returncode, result.stdout.strip(), result.stderr.strip()


def get_adapters() -> list[str]:
    """Return list of adapter names visible to netsh."""
    rc, out, _ = _run(["netsh", "interface", "show", "interface"])
    names = []
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 4 and parts[0] in ("Enabled", "Disabled"):
            # last token(s) form the adapter name
            name = " ".join(parts[3:])
            names.append(name)
    return names


def get_current_config(adapter: str) -> dict:
    """Read current IPv4 config for adapter via netsh."""
    rc, out, _ = _run(["netsh", "interface", "ip", "show", "config", f"name={adapter}"])
    cfg = {
        "adapter": adapter,
        "dhcp": True,
        "ip": "",
        "subnet": "",
        "gateway": "",
        "dns": "",
    }
    for line in out.splitlines():
        line = line.strip()
        if "DHCP enabled" in line:
            cfg["dhcp"] = "Yes" in line
        elif "IP Address" in line and ":" in line:
            cfg["ip"] = line.split(":", 1)[1].strip().split()[0]
        elif "Subnet Prefix" in line and "mask" in line.lower():
            # e.g. "Subnet Prefix:         192.168.1.0/24 (mask 255.255.255.0)"
            try:
                mask_part = line.split("mask")[-1].strip().rstrip(")")
                cfg["subnet"] = mask_part
            except Exception:
                pass
        elif "Default Gateway" in line and ":" in line:
            cfg["gateway"] = line.split(":", 1)[1].strip()
        elif "DNS Servers" in line and ":" in line:
            cfg["dns"] = line.split(":", 1)[1].strip()
    return cfg


def apply_static(
    adapter: str, ip: str, subnet: str, gateway: str, dns: str
) -> tuple[bool, str]:
    """Set adapter to static IP. Returns (success, message)."""
    rc, out, err = _run(
        [
            "netsh",
            "interface",
            "ip",
            "set",
            "address",
            f"name={adapter}",
            "static",
            ip,
            subnet,
            gateway,
        ]
    )
    if rc != 0:
        return False, f"Failed to set IP: {err or out}"

    if dns:
        _run(
            [
                "netsh",
                "interface",
                "ip",
                "set",
                "dns",
                f"name={adapter}",
                "static",
                dns,
            ]
        )

    return True, f"Static IP {ip} applied to {adapter}"


def apply_dhcp(adapter: str) -> tuple[bool, str]:
    """Set adapter back to DHCP."""
    rc, out, err = _run(
        [
            "netsh",
            "interface",
            "ip",
            "set",
            "address",
            f"name={adapter}",
            "dhcp",
        ]
    )
    if rc != 0:
        return False, f"Failed to set DHCP: {err or out}"
    _run(["netsh", "interface", "ip", "set", "dns", f"name={adapter}", "dhcp"])
    return True, f"DHCP restored on {adapter}"


# ---------------------------------------------------------------------------
# Profile persistence
# ---------------------------------------------------------------------------


def load_profile() -> dict:
    if os.path.isfile(PROFILE_PATH):
        try:
            with open(PROFILE_PATH) as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "adapter": "",
        "gameshow_ip": "192.168.4.100",
        "gameshow_subnet": "255.255.255.0",
        "gameshow_gateway": "192.168.4.1",
        "gameshow_dns": "8.8.8.8",
    }


def save_profile(data: dict):
    with open(PROFILE_PATH, "w") as f:
        json.dump(data, f, indent=2)


# ---------------------------------------------------------------------------
# GUI
# ---------------------------------------------------------------------------

DARK_BG = "#0D1117"
PANEL_BG = "#161B22"
FG = "#E6EDF3"
DIM_FG = "#8B949E"
GREEN_BG = "#238636"
BLUE_BG = "#1F6FEB"
RED_BG = "#B91C1C"


def _lbl(parent, text, fg=None, font=None, **kw):
    return tk.Label(
        parent, text=text, bg=PANEL_BG, fg=fg or FG, font=font or ("Segoe UI", 9), **kw
    )


def _ent(parent, textvariable, width=20, **kw):
    return tk.Entry(
        parent,
        textvariable=textvariable,
        width=width,
        bg="#21262D",
        fg=FG,
        insertbackground=FG,
        relief=tk.FLAT,
        font=("Segoe UI", 9),
        **kw,
    )


def _btn(parent, text, cmd, bg=GREEN_BG, **kw):
    return tk.Button(
        parent,
        text=text,
        command=cmd,
        bg=bg,
        fg="white",
        activebackground=bg,
        relief=tk.FLAT,
        bd=0,
        padx=10,
        pady=6,
        font=("Segoe UI", 9, "bold"),
        cursor="hand2",
        **kw,
    )


class NetworkSwitcher(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Gameshow Network Switcher")
        self.configure(bg=DARK_BG)
        self.resizable(False, False)
        self.geometry("520x560+200+100")

        self._profile = load_profile()
        self._adapters: list[str] = []

        self._adapter_var = tk.StringVar(value=self._profile.get("adapter", ""))
        self._gs_ip_var = tk.StringVar(
            value=self._profile.get("gameshow_ip", "192.168.4.100")
        )
        self._gs_sub_var = tk.StringVar(
            value=self._profile.get("gameshow_subnet", "255.255.255.0")
        )
        self._gs_gw_var = tk.StringVar(
            value=self._profile.get("gameshow_gateway", "192.168.4.1")
        )
        self._gs_dns_var = tk.StringVar(
            value=self._profile.get("gameshow_dns", "8.8.8.8")
        )

        self._build_ui()
        self.after(100, self._refresh_adapters)

    # ------------------------------------------------------------------
    def _build_ui(self):
        # ── Title ──
        tk.Label(
            self,
            text="Gameshow Network Switcher",
            bg=DARK_BG,
            fg=FG,
            font=("Segoe UI", 14, "bold"),
        ).pack(pady=(16, 4))
        tk.Label(
            self,
            text="One click to switch between your home/office network and the gameshow router.",
            bg=DARK_BG,
            fg=DIM_FG,
            font=("Segoe UI", 9),
            wraplength=480,
        ).pack(pady=(0, 12))

        # ── Adapter selection ──
        sec1 = tk.LabelFrame(
            self,
            text="Network Adapter",
            bg=PANEL_BG,
            fg=DIM_FG,
            font=("Segoe UI", 9, "bold"),
            relief=tk.FLAT,
            bd=1,
        )
        sec1.pack(fill=tk.X, padx=16, pady=4)

        row = tk.Frame(sec1, bg=PANEL_BG)
        row.pack(fill=tk.X, padx=6, pady=6)
        _lbl(row, "Adapter:").pack(side=tk.LEFT)
        self._adapter_combo = ttk.Combobox(
            row,
            textvariable=self._adapter_var,
            width=28,
            state="readonly",
            font=("Segoe UI", 9),
        )
        self._adapter_combo.pack(side=tk.LEFT, padx=6)
        _btn(row, "↺ Refresh", self._refresh_adapters, bg="#21262D").pack(
            side=tk.LEFT, padx=4
        )

        # ── Gameshow static settings ──
        sec2 = tk.LabelFrame(
            self,
            text="Gameshow Router Settings  (static IP to apply)",
            bg=PANEL_BG,
            fg=DIM_FG,
            font=("Segoe UI", 9, "bold"),
            relief=tk.FLAT,
            bd=1,
        )
        sec2.pack(fill=tk.X, padx=16, pady=4)

        fields = [
            ("PC IP address:", self._gs_ip_var, "e.g. 192.168.4.100"),
            ("Subnet mask:", self._gs_sub_var, "e.g. 255.255.255.0"),
            ("Default gateway:", self._gs_gw_var, "Router IP, e.g. 192.168.4.1"),
            ("DNS server:", self._gs_dns_var, "e.g. 8.8.8.8"),
        ]
        for label, var, hint in fields:
            r = tk.Frame(sec2, bg=PANEL_BG)
            r.pack(fill=tk.X, padx=6, pady=3)
            _lbl(r, label, width=18, anchor="w").pack(side=tk.LEFT)
            _ent(r, var, width=18).pack(side=tk.LEFT, padx=4)
            _lbl(r, hint, fg=DIM_FG, font=("Segoe UI", 8)).pack(side=tk.LEFT)

        _btn(sec2, "💾  Save Settings", self._save_settings, bg="#21262D").pack(
            anchor="e", padx=6, pady=(2, 6)
        )

        # ── Current config display ──
        sec3 = tk.LabelFrame(
            self,
            text="Current Adapter Config",
            bg=PANEL_BG,
            fg=DIM_FG,
            font=("Segoe UI", 9, "bold"),
            relief=tk.FLAT,
            bd=1,
        )
        sec3.pack(fill=tk.X, padx=16, pady=4)
        self._current_info = tk.Label(
            sec3,
            text="Select an adapter and click Refresh",
            bg=PANEL_BG,
            fg=DIM_FG,
            font=("Consolas", 9),
            justify="left",
            anchor="w",
        )
        self._current_info.pack(fill=tk.X, padx=8, pady=6)

        # ── Action buttons ──
        abtn = tk.Frame(self, bg=DARK_BG)
        abtn.pack(fill=tk.X, padx=16, pady=12)
        abtn.columnconfigure(0, weight=1)
        abtn.columnconfigure(1, weight=1)

        _btn(
            abtn, "🎮  Switch to GAMESHOW", self._switch_to_gameshow, bg="#1F6FEB"
        ).grid(row=0, column=0, padx=(0, 4), sticky="ew", ipady=4)
        _btn(
            abtn, "🏠  Restore NORMAL (DHCP)", self._switch_to_normal, bg="#374151"
        ).grid(row=0, column=1, padx=(4, 0), sticky="ew", ipady=4)

        # ── Status bar ──
        self._status_var = tk.StringVar(value="Ready")
        tk.Label(
            self,
            textvariable=self._status_var,
            bg=DARK_BG,
            fg="#3FB950",
            font=("Segoe UI", 9, "italic"),
        ).pack(pady=(0, 10))

    # ------------------------------------------------------------------
    def _refresh_adapters(self):
        self._status("Scanning adapters…")

        def work():
            adapters = get_adapters()
            self.after(0, lambda: self._on_adapters(adapters))

        threading.Thread(target=work, daemon=True).start()

    def _on_adapters(self, adapters: list[str]):
        self._adapters = adapters
        self._adapter_combo["values"] = adapters
        # Auto-select saved adapter if it still exists
        saved = self._profile.get("adapter", "")
        if saved in adapters:
            self._adapter_var.set(saved)
        elif adapters:
            self._adapter_var.set(adapters[0])
        self._refresh_current_config()

    def _refresh_current_config(self):
        adapter = self._adapter_var.get()
        if not adapter:
            return

        def work():
            cfg = get_current_config(adapter)
            self.after(0, lambda: self._show_config(cfg))

        threading.Thread(target=work, daemon=True).start()

    def _show_config(self, cfg: dict):
        mode = "DHCP (automatic)" if cfg["dhcp"] else "Static IP"
        text = (
            f"  Mode:    {mode}\n"
            f"  IP:      {cfg['ip'] or '—'}\n"
            f"  Subnet:  {cfg['subnet'] or '—'}\n"
            f"  Gateway: {cfg['gateway'] or '—'}\n"
            f"  DNS:     {cfg['dns'] or '—'}"
        )
        self._current_info.config(text=text)
        self._status("Ready")

    def _save_settings(self):
        adapter = self._adapter_var.get()
        if not adapter:
            messagebox.showwarning("No adapter", "Select an adapter first")
            return
        self._profile.update(
            {
                "adapter": adapter,
                "gameshow_ip": self._gs_ip_var.get(),
                "gameshow_subnet": self._gs_sub_var.get(),
                "gameshow_gateway": self._gs_gw_var.get(),
                "gameshow_dns": self._gs_dns_var.get(),
            }
        )
        save_profile(self._profile)
        self._status("Settings saved.")

    def _switch_to_gameshow(self):
        adapter = self._adapter_var.get()
        if not adapter:
            messagebox.showwarning("No adapter", "Select a network adapter first")
            return
        ip = self._gs_ip_var.get().strip()
        sub = self._gs_sub_var.get().strip()
        gw = self._gs_gw_var.get().strip()
        dns = self._gs_dns_var.get().strip()

        if not all([ip, sub, gw]):
            messagebox.showwarning(
                "Missing fields", "Fill in IP, Subnet, and Gateway first"
            )
            return

        # Save current config as backup so we can restore it
        self._status("Reading current config…")

        def work():
            backup = get_current_config(adapter)
            # Only overwrite backup if currently DHCP (don't clobber a previously saved backup)
            if backup["dhcp"]:
                self._profile["backup"] = backup
                save_profile(self._profile)
            ok, msg = apply_static(adapter, ip, sub, gw, dns)
            self.after(0, lambda: self._on_switch_done(ok, msg))

        threading.Thread(target=work, daemon=True).start()

    def _switch_to_normal(self):
        adapter = self._adapter_var.get()
        if not adapter:
            messagebox.showwarning("No adapter", "Select a network adapter first")
            return
        self._status("Restoring DHCP…")

        def work():
            ok, msg = apply_dhcp(adapter)
            self.after(0, lambda: self._on_switch_done(ok, msg))

        threading.Thread(target=work, daemon=True).start()

    def _on_switch_done(self, ok: bool, msg: str):
        if ok:
            self._status(f"✔  {msg}")
            messagebox.showinfo("Done", msg)
        else:
            self._status(f"✘  {msg}")
            messagebox.showerror(
                "Failed", msg + "\n\nMake sure you are running as Administrator."
            )
        self._refresh_current_config()

    def _status(self, msg: str):
        self._status_var.set(msg)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if sys.platform != "win32":
        print("This tool is Windows-only (uses netsh).")
        sys.exit(1)

    if not _is_admin():
        root = tk.Tk()
        root.withdraw()
        if messagebox.askokcancel(
            "Admin required",
            "Changing network settings requires Administrator privileges.\n"
            "Click OK to re-launch elevated.",
        ):
            root.destroy()
            _relaunch_as_admin()
        else:
            root.destroy()
            sys.exit(0)
    else:
        app = NetworkSwitcher()
        app.mainloop()

"""
Gameshow Question Video Generator
----------------------------------
Edit questions in the left panel, preview live in the center,
click Generate to produce styled 5-scene MP4 videos straight into vid/vrae/.

Scenes per question:
  1. Category card  (5 s)
  2. Question       (5 s)
  3. Options+Timer  (15 s, fully animated countdown ring)
  4. Time's Up      (3 s)
  5. Answer reveal  (5 s)
"""

import json
import math
import random
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QColor, QFont, QImage, QPixmap
from PyQt5.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

# ─────────────────────────── paths / constants ────────────────────────────────

BASE_DIR = Path(__file__).parent
VID_VRAE = BASE_DIR / "vid" / "vrae"
Q_PATH = BASE_DIR / "questions.json"
SFX_PATH = BASE_DIR / "sfx_config.json"

W, H = 1920, 1080
FPS = 30
SCENE_DUR = {"category": 5, "question": 5, "options": 15, "timeout": 3, "answer": 5}

ANSWER_COLORS = {
    "A": (46, 204, 113),
    "B": (52, 152, 219),
    "C": (155, 89, 182),
    "D": (230, 126, 34),
}

# ─────────────────────────── fonts ────────────────────────────────────────────

_FONT_DIR = Path("C:/Windows/Fonts")


def _ttf(names, size):
    for n in names:
        p = _FONT_DIR / n
        if p.exists():
            try:
                return ImageFont.truetype(str(p), size)
            except Exception:
                pass
    return ImageFont.load_default()


def FD(sz):
    return _ttf(["impact.ttf", "arialbd.ttf"], sz)  # Display


def FB(sz):
    return _ttf(["seguibl.ttf", "arialbd.ttf", "impact.ttf"], sz)  # Bold


def FR(sz):
    return _ttf(["arialbd.ttf", "arial.ttf"], sz)  # Regular


# ─────────────────────────── themes ───────────────────────────────────────────

THEMES = [
    {
        "name": "Cosmic",
        "bg_center": (12, 4, 45),
        "bg_edge": (3, 0, 80),
        "accent": (0, 220, 255),
        "accent2": (200, 0, 255),
        "text": (220, 240, 255),
        "card_bg": (8, 10, 55),
        "card_a": 140,  # card bg alpha 0-255
        "border": (0, 180, 255),
        "hdr_bg": (5, 2, 35),
        "hdr_a": 210,
        "pattern": "stars",
    },
    {
        "name": "Volcanic",
        "bg_center": (28, 6, 0),
        "bg_edge": (70, 15, 0),
        "accent": (255, 150, 0),
        "accent2": (255, 60, 0),
        "text": (255, 245, 210),
        "card_bg": (45, 10, 0),
        "card_a": 150,
        "border": (255, 120, 0),
        "hdr_bg": (22, 4, 0),
        "hdr_a": 220,
        "pattern": "embers",
    },
    {
        "name": "Electric",
        "bg_center": (0, 5, 18),
        "bg_edge": (0, 0, 6),
        "accent": (0, 255, 255),
        "accent2": (255, 255, 0),
        "text": (200, 255, 255),
        "card_bg": (0, 12, 28),
        "card_a": 160,
        "border": (0, 200, 255),
        "hdr_bg": (0, 6, 20),
        "hdr_a": 220,
        "pattern": "grid",
    },
    {
        "name": "Royale",
        "bg_center": (8, 4, 38),
        "bg_edge": (22, 0, 70),
        "accent": (210, 172, 48),
        "accent2": (255, 215, 100),
        "text": (255, 248, 215),
        "card_bg": (12, 4, 42),
        "card_a": 150,
        "border": (195, 158, 40),
        "hdr_bg": (6, 2, 32),
        "hdr_a": 220,
        "pattern": "diamonds",
    },
    {
        "name": "Emerald",
        "bg_center": (0, 28, 18),
        "bg_edge": (0, 55, 32),
        "accent": (0, 255, 155),
        "accent2": (80, 255, 200),
        "text": (200, 255, 230),
        "card_bg": (0, 18, 12),
        "card_a": 155,
        "border": (0, 195, 125),
        "hdr_bg": (0, 12, 8),
        "hdr_a": 220,
        "pattern": "hexagons",
    },
]

# ─────────────────────────── background ───────────────────────────────────────


def _make_bg(theme: dict, rng: random.Random) -> Image.Image:
    """Radial-gradient background + per-theme pattern + vignette."""
    cx, cy = W / 2, H / 2
    xs = np.linspace(0, W, W, dtype=np.float32)
    ys = np.linspace(0, H, H, dtype=np.float32)
    xx, yy = np.meshgrid(xs, ys)
    dist = np.sqrt(((xx - cx) / W) ** 2 + ((yy - cy) / H) ** 2)
    dist = np.clip(dist / 0.72, 0.0, 1.0)

    c0 = np.array(theme["bg_center"], dtype=np.float32)
    c1 = np.array(theme["bg_edge"], dtype=np.float32)

    arr = np.empty((H, W, 3), dtype=np.float32)
    for ch in range(3):
        arr[:, :, ch] = c0[ch] * (1 - dist) + c1[ch] * dist

    # Vignette — darken edges
    vig = 1.0 - np.clip(dist * 1.6 - 0.25, 0.0, 0.65)
    arr *= vig[:, :, np.newaxis]

    arr = np.clip(arr, 0, 255).astype(np.uint8)
    img = Image.fromarray(arr, "RGB")

    pat = theme["pattern"]
    d = ImageDraw.Draw(img)

    if pat == "stars":
        for _ in range(90):
            x, y = rng.randint(0, W - 1), rng.randint(0, H - 1)
            r = rng.randint(1, 3)
            br = rng.randint(140, 255)
            d.ellipse((x - r, y - r, x + r, y + r), fill=(br, br, br))
        for _ in range(220):
            x, y = rng.randint(0, W - 1), rng.randint(0, H - 1)
            br = rng.randint(50, 110)
            d.point((x, y), fill=(br, br, br))
        acc = theme["accent"]
        for _ in range(20):
            x, y = rng.randint(0, W - 1), rng.randint(0, H - 1)
            r = rng.randint(1, 2)
            bri = rng.uniform(0.4, 0.9)
            d.ellipse(
                (x - r, y - r, x + r, y + r), fill=tuple(int(c * bri) for c in acc)
            )

    elif pat == "embers":
        acc = theme["accent"]
        for _ in range(150):
            x, y = rng.randint(0, W - 1), rng.randint(0, H - 1)
            r = rng.randint(1, 3)
            bri = rng.uniform(0.3, 1.0)
            d.ellipse(
                (x - r, y - r, x + r, y + r), fill=tuple(int(c * bri) for c in acc)
            )
        for _ in range(80):
            x, y = rng.randint(0, W - 1), rng.randint(0, H - 1)
            br = rng.randint(40, 100)
            d.point((x, y), fill=(br, br // 3, 0))

    elif pat == "grid":
        ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        od = ImageDraw.Draw(ov)
        ar, ag, ab = theme["accent"]
        sp = 80
        for x in range(0, W, sp):
            od.line([(x, 0), (x, H)], fill=(ar, ag, ab, 22), width=1)
        for y in range(0, H, sp):
            od.line([(0, y), (W, y)], fill=(ar, ag, ab, 22), width=1)
        for x in range(0, W, sp * 4):
            od.line([(x, 0), (x, H)], fill=(ar, ag, ab, 50), width=2)
        for y in range(0, H, sp * 4):
            od.line([(0, y), (W, y)], fill=(ar, ag, ab, 50), width=2)
        img = Image.alpha_composite(img.convert("RGBA"), ov).convert("RGB")

    elif pat == "diamonds":
        ar, ag, ab = theme["accent"]
        size = 110
        for row in range(-1, H // size + 2):
            for col in range(-1, W // size + 2):
                cx2 = col * size + (row % 2) * size // 2
                cy2 = row * size
                half = size // 3
                pts = [
                    (cx2, cy2 - half),
                    (cx2 + half, cy2),
                    (cx2, cy2 + half),
                    (cx2 - half, cy2),
                ]
                d.line(pts + [pts[0]], fill=(ar // 4, ag // 4, ab // 4), width=1)

    elif pat == "hexagons":
        ar, ag, ab = theme["accent"]
        sz = 72
        hh = sz * math.sqrt(3) / 2
        for row in range(-1, int(H / hh) + 2):
            for col in range(-1, int(W / (sz * 1.5)) + 2):
                cx2 = col * sz * 1.5
                cy2 = row * hh * 2 + (col % 2) * hh
                pts = []
                for i in range(6):
                    ang = math.radians(60 * i - 30)
                    pts.append((cx2 + sz * math.cos(ang), cy2 + sz * math.sin(ang)))
                d.polygon(pts, outline=(ar // 5, ag // 5, ab // 5))

    return img


# ─────────────────────────── drawing helpers ──────────────────────────────────


def _wrap(text: str, font: ImageFont.FreeTypeFont, max_w: int) -> list[str]:
    dummy = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    words = text.split()
    lines, cur = [], ""
    for w in words:
        test = (cur + " " + w).strip()
        if dummy.textlength(test, font=font) <= max_w:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines or [""]


def _glow_text(
    img: Image.Image,
    text: str,
    xy,
    font,
    color,
    glow_col,
    radius: int = 20,
    anchor: str = "mm",
):
    """Draw text with a soft glow halo."""
    gl = Image.new("RGBA", img.size, (0, 0, 0, 0))
    gd = ImageDraw.Draw(gl)
    r, g, b = glow_col[:3]
    for dx in range(-3, 4):
        for dy in range(-3, 4):
            gd.text(
                (xy[0] + dx, xy[1] + dy),
                text,
                font=font,
                fill=(r, g, b, 55),
                anchor=anchor,
            )
    gl = gl.filter(ImageFilter.GaussianBlur(radius))
    img.paste(Image.alpha_composite(img.convert("RGBA"), gl).convert("RGB"))
    d = ImageDraw.Draw(img)
    for dx, dy in [
        (-2, 0),
        (2, 0),
        (0, -2),
        (0, 2),
        (-2, -2),
        (2, -2),
        (-2, 2),
        (2, 2),
    ]:
        d.text((xy[0] + dx, xy[1] + dy), text, font=font, fill=(0, 0, 0), anchor=anchor)
    d.text(xy, text, font=font, fill=color, anchor=anchor)


def _shadow_rect(img: Image.Image, rect, radius, fill, border, bw=4):
    """Rounded rect with drop shadow."""
    x1, y1, x2, y2 = rect
    sh = Image.new("RGBA", img.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(sh)
    sd.rounded_rectangle(
        (x1 + 8, y1 + 8, x2 + 8, y2 + 8), radius=radius, fill=(0, 0, 0, 110)
    )
    sh = sh.filter(ImageFilter.GaussianBlur(14))
    img.paste(Image.alpha_composite(img.convert("RGBA"), sh).convert("RGB"))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((x1, y1, x2, y2), radius=radius, fill=fill)
    if border:
        d.rounded_rectangle((x1, y1, x2, y2), radius=radius, outline=border, width=bw)


def _timer_ring(img: Image.Image, cx, cy, ro, ri, progress, acc, warn):
    """Animated countdown ring. progress 1.0→0.0."""
    ov = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    d.ellipse((cx - ro, cy - ro, cx + ro, cy + ro), fill=(0, 0, 0, 100))
    d.ellipse((cx - ri, cy - ri, cx + ri, cy + ri), fill=(0, 0, 0, 0))
    if progress > 0.001:
        col = acc if progress > 0.3 else warn
        end = -90 + 360 * progress
        d.arc(
            (cx - ro, cy - ro, cx + ro, cy + ro),
            start=-90,
            end=end,
            fill=(*col, 255),
            width=ro - ri,
        )
    img.paste(Image.alpha_composite(img.convert("RGBA"), ov).convert("RGB"))


# ─────────────────────────── card layout ──────────────────────────────────────

CARD_W = 910
CARD_H = 440
CARD_R = 26
_PAD = 45
_CARD_GAP = 10
_CARD_Y = 136

CARD_POS = {
    "A": (_PAD, _CARD_Y),
    "B": (_PAD + CARD_W + _CARD_GAP, _CARD_Y),
    "C": (_PAD, _CARD_Y + CARD_H + 16),
    "D": (_PAD + CARD_W + _CARD_GAP, _CARD_Y + CARD_H + 16),
}

_TIMER_CX = W - 72
_TIMER_CY = 62
_TIMER_RO = 58
_TIMER_RI = 40

# ─────────────────────────── scene renderers ──────────────────────────────────


def _hdr_overlay(img: Image.Image, theme: dict, h_px=122):
    """Semi-transparent header band."""
    ov = Image.new("RGBA", img.size, (0, 0, 0, 0))
    r, g, b = theme["hdr_bg"]
    a = theme["hdr_a"]
    ImageDraw.Draw(ov).rectangle((0, 0, W, h_px), fill=(r, g, b, a))
    return Image.alpha_composite(img.convert("RGBA"), ov).convert("RGB")


def scene_category(q: dict, bg: Image.Image, theme: dict) -> Image.Image:
    img = bg.copy()
    acc = theme["accent"]
    acc2 = theme["accent2"][:3]
    txt = theme["text"]

    # Central glassy panel
    pm = 180
    ov = Image.new("RGBA", img.size, (0, 0, 0, 0))
    r, g, b = theme["card_bg"]
    a = 205
    ImageDraw.Draw(ov).rounded_rectangle(
        (pm, 160, W - pm, H - 160), radius=40, fill=(r, g, b, a)
    )
    img = Image.alpha_composite(img.convert("RGBA"), ov).convert("RGB")

    d = ImageDraw.Draw(img)
    # Accent bar — top of panel
    d.line([(pm + 50, 205), (W - pm - 50, 205)], fill=(*acc, 200), width=3)
    # Accent bar — bottom of panel
    d.line([(pm + 50, H - 205), (W - pm - 50, H - 205)], fill=(*acc, 200), width=3)

    # Q-number chip (top-right)
    qn = f"Q{int(q.get('number', 1)):02d}"
    d.rounded_rectangle(
        (W - pm - 10 - 120, 168, W - pm - 10, 200), radius=10, fill=(*acc, 60)
    )
    d.text((W - pm - 65, 184), qn, font=FR(26), fill=acc, anchor="mm")

    # "CATEGORY" sub-label
    d.text((W // 2, 305), "CATEGORY", font=FB(34), fill=(*acc2, 180), anchor="mm")

    # Thin separator
    d.line([(pm + 120, 345), (W - pm - 120, 345)], fill=(*acc, 70), width=2)

    # Big category text
    cat = q.get("category", "GENERAL").upper()
    f_cat = FD(min(140, max(60, 1400 // max(len(cat), 1))))
    _glow_text(img, cat, (W // 2, H // 2 + 30), f_cat, txt, acc, radius=35)

    d = ImageDraw.Draw(img)
    d.text((W // 2, H - 245), "GET READY!", font=FB(32), fill=(*acc2, 150), anchor="mm")

    return img


def scene_question(q: dict, bg: Image.Image, theme: dict) -> Image.Image:
    img = _hdr_overlay(bg.copy(), theme)
    acc = theme["accent"]
    acc2 = theme["accent2"][:3]
    txt = theme["text"]

    d = ImageDraw.Draw(img)
    d.line([(0, 122), (W, 122)], fill=acc, width=3)
    d.text(
        (55, 61), f"Q{int(q.get('number', 1)):02d}", font=FB(46), fill=acc, anchor="lm"
    )
    d.text(
        (W // 2, 61),
        q.get("category", "").upper(),
        font=FR(34),
        fill=(*acc2, 190),
        anchor="mm",
    )

    media = q.get("media_type", "text").lower()
    q_img_path = q.get("question_image", "") if media == "photo" else ""
    has_img = bool(q_img_path) and Path(q_img_path).exists()

    PY1, PY2 = 142, H - 40  # panel vertical range

    if has_img:
        q_img = Image.open(q_img_path).convert("RGB")
        img_max_w = int(W * 0.46)
        img_max_h = PY2 - PY1 - 60
        q_img.thumbnail((img_max_w, img_max_h), Image.LANCZOS)
        ix, iy = 55, PY1 + (PY2 - PY1 - q_img.height) // 2
        # Card behind image
        _shadow_rect(
            img,
            (ix - 10, iy - 10, ix + q_img.width + 10, iy + q_img.height + 10),
            16,
            (5, 5, 5),
            acc,
            bw=3,
        )
        img.paste(q_img, (ix, iy))
        # Text card on right
        tx1 = ix + q_img.width + 36
        ov = Image.new("RGBA", img.size, (0, 0, 0, 0))
        r, g, b = theme["card_bg"]
        ImageDraw.Draw(ov).rounded_rectangle(
            (tx1 - 10, PY1, W - 40, PY2), radius=24, fill=(r, g, b, theme["card_a"])
        )
        img = Image.alpha_composite(img.convert("RGBA"), ov).convert("RGB")
        text_cx = (tx1 + W - 40) // 2
        text_max_w = W - 80 - tx1
        max_lines = 4
        start_f_sz = 52
    else:
        ov = Image.new("RGBA", img.size, (0, 0, 0, 0))
        r, g, b = theme["card_bg"]
        ImageDraw.Draw(ov).rounded_rectangle(
            (70, 155, W - 70, H - 80), radius=28, fill=(r, g, b, theme["card_a"])
        )
        img = Image.alpha_composite(img.convert("RGBA"), ov).convert("RGB")
        text_cx = W // 2
        text_max_w = W - 220
        PY1, PY2 = 155, H - 80
        max_lines = 5
        start_f_sz = 68

    # Audio indicator badge
    if media == "audio":
        d2 = ImageDraw.Draw(img)
        badge = "  AUDIO QUESTION"
        bw = (
            int(ImageDraw.Draw(Image.new("RGB", (1, 1))).textlength(badge, font=FR(28)))
            + 40
        )
        bx = W // 2 - bw // 2
        by = PY1 + 18
        d2.rounded_rectangle((bx, by, bx + bw, by + 42), radius=10, fill=(*acc, 60))
        d2.text((W // 2, by + 21), badge, font=FR(28), fill=acc, anchor="mm")

    # Question text — auto-shrink
    q_text = q.get("question", "")
    f_sz = start_f_sz
    while f_sz >= 28:
        fnt = FB(f_sz)
        lines = _wrap(q_text, fnt, text_max_w)
        if len(lines) <= max_lines:
            break
        f_sz -= 6

    fnt = FB(f_sz)
    lines = _wrap(q_text, fnt, text_max_w)
    line_h = f_sz + 18
    cy = (PY1 + PY2) // 2
    start_y = cy - (len(lines) * line_h) // 2

    for i, line in enumerate(lines):
        _glow_text(
            img,
            line,
            (text_cx, start_y + i * line_h),
            fnt,
            txt,
            acc,
            radius=14,
            anchor="mt",
        )

    return img


def scene_options_base(q: dict, bg: Image.Image, theme: dict) -> Image.Image:
    """Render cards + header but NO timer (timer is composited per-frame)."""
    img = _hdr_overlay(bg.copy(), theme)
    acc = theme["accent"]
    acc2 = theme["accent2"][:3]

    d = ImageDraw.Draw(img)
    d.line([(0, 122), (W, 122)], fill=acc, width=3)
    d.text(
        (55, 61), f"Q{int(q.get('number', 1)):02d}", font=FB(44), fill=acc, anchor="lm"
    )

    # Question text (truncated, top bar)
    q_text = q.get("question", "")
    f_qtop = FR(30)
    lines = _wrap(q_text, f_qtop, W - 380)[:2]
    for i, ln in enumerate(lines):
        d.text((W // 2, 44 + i * 34), ln, font=f_qtop, fill=theme["text"], anchor="mm")

    # Answer cards
    for letter in "ABCD":
        x1, y1 = CARD_POS[letter]
        x2, y2 = x1 + CARD_W, y1 + CARD_H
        lc = ANSWER_COLORS[letter]
        fill = (lc[0] // 6, lc[1] // 6, lc[2] // 6)
        _shadow_rect(img, (x1, y1, x2, y2), CARD_R, fill, lc, bw=4)

        # Letter badge — bigger for larger cards
        br = 70
        bcx = x1 + 95
        bcy = (y1 + y2) // 2
        d = ImageDraw.Draw(img)
        d.ellipse((bcx - br, bcy - br, bcx + br, bcy + br), fill=lc)
        d.text((bcx, bcy), letter, font=FD(76), fill=(10, 10, 10), anchor="mm")

        # Answer text — more room with taller cards
        ans = q.get(f"option_{letter.lower()}", "")
        f_sz = 52
        while f_sz >= 26:
            fa = FB(f_sz)
            alns = _wrap(ans, fa, CARD_W - 210)
            if len(alns) <= 3:
                break
            f_sz -= 6
        fa = FB(f_sz)
        alns = _wrap(ans, fa, CARD_W - 210)
        ty = bcy - (len(alns) - 1) * (f_sz + 10) // 2
        for i, al in enumerate(alns):
            d.text(
                (x1 + 185, ty + i * (f_sz + 10)),
                al,
                font=fa,
                fill=(235, 235, 235),
                anchor="lm",
            )

    return img


def scene_ff_base(q: dict, bg: Image.Image, theme: dict) -> Image.Image:
    """Fastest-finger countdown screen — large centered ring, no A/B/C/D cards."""
    img = _hdr_overlay(bg.copy(), theme)
    acc = theme["accent"]
    txt = theme["text"]
    d = ImageDraw.Draw(img)
    d.line([(0, 122), (W, 122)], fill=acc, width=3)
    _glow_text(
        img,
        "FASTEST FINGER!",
        (W // 2, H // 2 - 110),
        FD(118),
        txt,
        acc,
        radius=32,
        anchor="mm",
    )
    _glow_text(
        img,
        "First to press any button gets to answer",
        (W // 2, H // 2 + 30),
        FR(44),
        txt,
        acc,
        radius=12,
        anchor="mm",
    )
    return img


def scene_timeout(q: dict, bg: Image.Image, theme: dict) -> Image.Image:
    img = bg.copy()
    # Red tint
    ov = Image.new("RGBA", img.size, (160, 0, 0, 55))
    img = Image.alpha_composite(img.convert("RGBA"), ov).convert("RGB")
    d = ImageDraw.Draw(img)
    d.rectangle((0, 0, W, H), outline=(200, 0, 0), width=22)
    _glow_text(
        img,
        "TIME'S UP!",
        (W // 2, H // 2),
        FD(185),
        (255, 60, 60),
        (180, 0, 0),
        radius=45,
    )
    return img


def scene_answer(q: dict, bg: Image.Image, theme: dict) -> Image.Image:
    """Single large centered answer card — only the correct answer is shown."""
    img = _hdr_overlay(bg.copy(), theme)
    acc = theme["accent"]
    acc2 = theme["accent2"][:3]
    correct = q.get("correct_answer", "A").upper()
    lc = ANSWER_COLORS[correct]

    d = ImageDraw.Draw(img)
    d.line([(0, 122), (W, 122)], fill=acc, width=3)
    _glow_text(
        img, "CORRECT ANSWER", (W // 2, 61), FB(52), acc2, acc, radius=14, anchor="mm"
    )

    # ── Starburst rays behind the card ───────────────────────────────────────
    area_cy = (H + 122) // 2
    rays = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    rd = ImageDraw.Draw(rays)
    for i in range(24):
        a1 = math.radians(i * 15)
        a2 = math.radians(i * 15 + 7)
        r_len = max(W, H) * 0.85
        pts = [
            (W // 2, area_cy),
            (W // 2 + math.cos(a1) * r_len, area_cy + math.sin(a1) * r_len),
            (W // 2 + math.cos(a2) * r_len, area_cy + math.sin(a2) * r_len),
        ]
        rd.polygon(pts, fill=(*lc, 18))
    rays = rays.filter(ImageFilter.GaussianBlur(6))
    img = Image.alpha_composite(img.convert("RGBA"), rays).convert("RGB")

    # ── Large outer glow ─────────────────────────────────────────────────────
    CW, CH = 1480, 380
    cx1 = (W - CW) // 2
    cy1 = area_cy - CH // 2
    cx2, cy2 = cx1 + CW, cy1 + CH

    gv = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(gv)
    gd.rounded_rectangle(
        (cx1 - 35, cy1 - 35, cx2 + 35, cy2 + 35), radius=CARD_R + 24, fill=(*lc, 20)
    )
    gd.rounded_rectangle(
        (cx1 - 18, cy1 - 18, cx2 + 18, cy2 + 18), radius=CARD_R + 14, fill=(*lc, 36)
    )
    gv = gv.filter(ImageFilter.GaussianBlur(18))
    img = Image.alpha_composite(img.convert("RGBA"), gv).convert("RGB")

    # ── The card ─────────────────────────────────────────────────────────────
    fill = (lc[0] // 4, lc[1] // 4, lc[2] // 4)
    _shadow_rect(img, (cx1, cy1, cx2, cy2), CARD_R + 4, fill, (0, 255, 110), bw=6)

    # Letter badge
    bcy = (cy1 + cy2) // 2
    br = 88
    bcx = cx1 + 112
    d = ImageDraw.Draw(img)
    d.ellipse((bcx - br, bcy - br, bcx + br, bcy + br), fill=lc)
    d.text((bcx, bcy), correct, font=FD(108), fill=(10, 10, 10), anchor="mm")

    # Answer text
    ans = q.get(f"option_{correct.lower()}", "")
    media = q.get("media_type", "text").lower()
    a_img_path = q.get("answer_image", "") if media == "photo" else ""
    has_a_img = bool(a_img_path) and Path(a_img_path).exists()

    text_x = cx1 + 220
    check_margin = 120
    text_max_w = cx2 - text_x - check_margin

    if has_a_img:
        # Image on the right, text shrinks to left portion
        a_img_pil = Image.open(a_img_path).convert("RGB")
        img_max_w = int((cx2 - text_x) * 0.45)
        img_max_h = CH - 30
        a_img_pil.thumbnail((img_max_w, img_max_h), Image.LANCZOS)
        img_x = cx2 - a_img_pil.width - 20
        img_y = bcy - a_img_pil.height // 2
        img.paste(a_img_pil, (img_x, img_y))
        text_max_w = img_x - text_x - 30
        check_margin = 0  # no separate checkmark space; it goes above image

    f_sz = 80
    while f_sz >= 36:
        fnt = FB(f_sz)
        lines = _wrap(ans, fnt, text_max_w)
        if len(lines) <= 3:
            break
        f_sz -= 8
    fnt = FB(f_sz)
    lines = _wrap(ans, fnt, text_max_w)
    lh = f_sz + 14
    ty = bcy - (len(lines) * lh) // 2
    for i, ln in enumerate(lines):
        _glow_text(
            img,
            ln,
            (text_x, ty + i * lh),
            fnt,
            (255, 255, 255),
            lc,
            radius=10,
            anchor="lm",
        )

    # Checkmark
    if not has_a_img:
        d = ImageDraw.Draw(img)
        d.text((cx2 - 60, bcy), "✓", font=FB(130), fill=(0, 255, 110), anchor="rm")

    return img


# ─────────────────────────── animation helpers ────────────────────────────────

DISSOLVE_N = 12  # cross-dissolve frames between scenes


def _init_bg_particles(theme: dict, rng: random.Random) -> list:
    pat = theme["pattern"]
    acc = theme["accent"]
    p = []
    if pat == "stars":
        for _ in range(28):
            p.append(
                {
                    "x": rng.uniform(0, W),
                    "y": rng.uniform(0, H),
                    "vx": rng.uniform(-0.25, 0.25),
                    "vy": rng.uniform(-0.25, 0.25),
                    "r": rng.randint(1, 3),
                    "type": "star",
                    "bright": rng.randint(140, 255),
                    "ph": rng.uniform(0, 6.28),
                }
            )
    elif pat == "embers":
        for _ in range(38):
            p.append(
                {
                    "x": rng.uniform(0, W),
                    "y": rng.uniform(0, H),
                    "vx": rng.uniform(-0.5, 0.5),
                    "vy": rng.uniform(-1.3, -0.4),
                    "r": rng.randint(1, 4),
                    "type": "ember",
                    "color": acc,
                    "ph": rng.uniform(0, 6.28),
                }
            )
    else:
        for _ in range(22):
            p.append(
                {
                    "x": rng.uniform(0, W),
                    "y": rng.uniform(0, H),
                    "vx": rng.uniform(-0.4, 0.4),
                    "vy": rng.uniform(-0.4, 0.4),
                    "r": rng.randint(1, 3),
                    "type": "dot",
                    "color": acc,
                    "ph": rng.uniform(0, 6.28),
                }
            )
    return p


def _draw_bg_particles(d: ImageDraw.ImageDraw, particles: list, f: int):
    for p in particles:
        p["x"] = (p["x"] + p["vx"]) % W
        p["y"] = (p["y"] + p["vy"]) % H
        x, y, r = int(p["x"]), int(p["y"]), p["r"]
        pt = p["type"]
        if pt == "star":
            bright = int(p["bright"] * (0.55 + 0.45 * math.sin(f * 0.07 + p["ph"])))
            d.ellipse((x - r, y - r, x + r, y + r), fill=(bright, bright, bright))
        elif pt == "ember":
            bright = 0.35 + 0.65 * math.sin(f * 0.11 + p["ph"]) ** 2
            c = p["color"]
            col = tuple(int(v * bright) for v in c)
            d.ellipse((x - r, y - r, x + r, y + r), fill=col)
        else:
            bright = 0.15 + 0.45 * abs(math.sin(f * 0.09 + p["ph"]))
            c = p["color"]
            col = tuple(int(v * bright) for v in c)
            d.ellipse((x - r, y - r, x + r, y + r), fill=col)


def _init_confetti(rng: random.Random, n: int = 70) -> list:
    cx, cy = W // 2, int(H * 0.42)
    COLS = [
        (255, 215, 0),
        (255, 80, 80),
        (0, 255, 140),
        (80, 160, 255),
        (255, 180, 30),
        (220, 0, 255),
        (0, 220, 255),
        (255, 140, 200),
    ]
    pieces = []
    for _ in range(n):
        ang = rng.uniform(0, 2 * math.pi)
        spd = rng.uniform(420, 950)
        pieces.append(
            {
                "x": cx + rng.uniform(-140, 140),
                "y": cy + rng.uniform(-75, 75),
                "vx": math.cos(ang) * spd,
                "vy": math.sin(ang) * spd - 390,
                "color": rng.choice(COLS),
                "w": rng.randint(7, 21),
                "h": rng.randint(4, 12),
                "life": rng.uniform(0.9, 2.4),
                "shape": rng.choice(["rect", "rect", "rect", "circ"]),
            }
        )
    return pieces


def _draw_confetti(d: ImageDraw.ImageDraw, pieces: list, t_s: float):
    G = 530.0
    for p in pieces:
        if t_s > p["life"]:
            continue
        alpha = max(0.0, 1.0 - t_s / p["life"])
        x = p["x"] + p["vx"] * t_s
        y = p["y"] + p["vy"] * t_s + 0.5 * G * t_s * t_s
        if y > H + 70 or x < -70 or x > W + 70:
            continue
        c = tuple(int(v * alpha) for v in p["color"])
        if not any(c):
            continue
        w, h = p["w"], p["h"]
        if p["shape"] == "circ":
            d.ellipse((x - w, y - w, x + w, y + w), fill=c)
        else:
            d.rectangle((x - w, y - h, x + w, y + h), fill=c)


# ─────────────────────────── video encoder ────────────────────────────────────


class RenderWorker(QThread):
    progress = pyqtSignal(int, int)  # (done, total)
    log_msg = pyqtSignal(str)
    finished = pyqtSignal(bool, str)  # (all_ok, summary)

    def __init__(
        self,
        questions: list[dict],
        bgm_path: str = "",
        sfx: dict | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self.questions = questions
        self.bgm_path = bgm_path
        self.sfx = sfx or {}

    def run(self):
        VID_VRAE.mkdir(parents=True, exist_ok=True)
        total = len(self.questions)
        errors = []

        for idx, q in enumerate(self.questions):
            self.progress.emit(idx, total)
            qnum = int(q.get("number", idx + 1))
            correct = q.get("correct_answer", "A").upper()
            slug = q.get("question", "q")[:30].lower()
            slug = "".join(c if c.isalnum() else "-" for c in slug).strip("-")
            q_type = q.get("type", "MC").upper()

            if q_type == "FF":
                prefix = "F_"
            elif correct in ANSWER_COLORS:
                prefix = correct + "_"
            else:
                prefix = ""

            fname = f"{prefix}q{qnum:02d}_{slug}.mp4"
            out = VID_VRAE / fname

            self.log_msg.emit(f"Rendering {fname}…")
            ok, info = _encode_question(q, self.bgm_path, self.sfx)
            if ok:
                # Write from pipe output already in out
                # info is path to temp file; rename it
                import shutil

                shutil.move(str(info), str(out))
                # Write per-video sidecar so the player knows exact pause timestamps
                dis = DISSOLVE_N / FPS
                opts = int(q.get("options_duration", SCENE_DUR["options"]))
                pause1_ms = int(SCENE_DUR["category"] * 1000)
                pause2_ms = int(
                    (SCENE_DUR["category"] + dis + SCENE_DUR["question"] + dis + opts)
                    * 1000
                )
                meta = {
                    "mode": q.get("type", "MC").upper(),
                    "pause_ms": [pause1_ms, pause2_ms],
                }
                out.with_suffix(".meta.json").write_text(
                    json.dumps(meta, indent=2), encoding="utf-8"
                )
                self.log_msg.emit(f"  ✔ {fname}")
            else:
                errors.append(f"{fname}: {info}")
                self.log_msg.emit(f"  ✘ {fname}: {info}")

        self.progress.emit(total, total)
        if errors:
            self.finished.emit(False, "\n".join(errors))
        else:
            self.finished.emit(True, f"Generated {total} video(s) → vid/vrae/")


def _apply_audio_overlays(
    video_path: str,
    q: dict,
    opts_dur: int,
    bgm_path: str = "",
    sfx: dict | None = None,
) -> str:
    """Mix BGM, SFX, question_audio, and/or answer_audio into the video at correct offsets.
    sfx keys: intro, countdown_tick, timeout
    Returns the path to the final video (may be a new temp file).
    """
    if sfx is None:
        sfx = {}
    dis = DISSOLVE_N / FPS

    # Exact millisecond offsets for each audio cue
    intro_delay_ms = 0
    q_audio_delay_ms = int((SCENE_DUR["category"] + dis) * 1000)
    countdown_delay_ms = int(
        (SCENE_DUR["category"] + dis + SCENE_DUR["question"] + dis) * 1000
    )
    timeout_delay_ms = int(
        (SCENE_DUR["category"] + dis + SCENE_DUR["question"] + dis + opts_dur + dis)
        * 1000
    )
    a_audio_delay_ms = int(
        (
            SCENE_DUR["category"]
            + dis
            + SCENE_DUR["question"]
            + dis
            + opts_dur
            + dis
            + SCENE_DUR["timeout"]
            + dis
        )
        * 1000
    )

    q_audio = q.get("question_audio", "")
    a_audio = q.get("answer_audio", "")
    has_q = bool(q_audio) and Path(q_audio).exists()
    has_a = bool(a_audio) and Path(a_audio).exists()
    has_bgm = bool(bgm_path) and Path(bgm_path).exists()

    intro_sfx = sfx.get("intro", "")
    tick_sfx = sfx.get("countdown_tick", "")
    timeout_sfx = sfx.get("timeout", "")
    has_intro = bool(intro_sfx) and Path(intro_sfx).exists()
    has_timeout = bool(timeout_sfx) and Path(timeout_sfx).exists()

    # Build looped countdown track (one tick per second) into a temp file
    countdown_tmp = ""
    if tick_sfx and Path(tick_sfx).exists():
        countdown_tmp = _build_countdown_audio(tick_sfx, opts_dur)
    has_countdown = bool(countdown_tmp)

    if not any([has_q, has_a, has_bgm, has_intro, has_countdown, has_timeout]):
        return video_path

    import os
    import tempfile

    out_tmp = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
    out_tmp.close()

    # [0] = video (silent anullsrc track), then optional tracks in order
    inputs = ["-i", video_path]
    filter_parts: list[str] = []
    mix_labels = ["[0:a]"]

    idx = 1
    if has_bgm:
        inputs += ["-stream_loop", "-1", "-i", bgm_path]
        filter_parts.append(f"[{idx}:a]volume=0.25[bgmv]")
        mix_labels.append("[bgmv]")
        idx += 1
    if has_intro:
        d = intro_delay_ms
        inputs += ["-i", intro_sfx]
        filter_parts.append(f"[{idx}:a]adelay={d}|{d}[introsfx]")
        mix_labels.append("[introsfx]")
        idx += 1
    if has_countdown:
        d = countdown_delay_ms
        inputs += ["-i", countdown_tmp]
        filter_parts.append(f"[{idx}:a]adelay={d}|{d}[cntdown]")
        mix_labels.append("[cntdown]")
        idx += 1
    if has_timeout:
        d = timeout_delay_ms
        inputs += ["-i", timeout_sfx]
        filter_parts.append(f"[{idx}:a]adelay={d}|{d}[tosfx]")
        mix_labels.append("[tosfx]")
        idx += 1
    if has_q:
        inputs += ["-i", q_audio]
        d = q_audio_delay_ms
        filter_parts.append(f"[{idx}:a]adelay={d}|{d}[qa]")
        mix_labels.append("[qa]")
        idx += 1
    if has_a:
        inputs += ["-i", a_audio]
        d = a_audio_delay_ms
        filter_parts.append(f"[{idx}:a]adelay={d}|{d}[aa]")
        mix_labels.append("[aa]")

    n = len(mix_labels)
    mix_in = "".join(mix_labels)
    filter_parts.append(f"{mix_in}amix=inputs={n}:duration=first[aout]")

    cmd = (
        ["ffmpeg", "-y"]
        + inputs
        + [
            "-filter_complex",
            ";".join(filter_parts),
            "-map",
            "0:v",
            "-map",
            "[aout]",
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            out_tmp.name,
        ]
    )
    result = subprocess.run(cmd, capture_output=True)
    # Clean up temporary countdown track regardless of outcome
    if countdown_tmp:
        try:
            os.unlink(countdown_tmp)
        except Exception:
            pass
    if result.returncode == 0:
        try:
            os.unlink(video_path)
        except Exception:
            pass
        return out_tmp.name
    # If mixing fails keep the original silent video
    try:
        os.unlink(out_tmp.name)
    except Exception:
        pass
    return video_path


def _encode_question(
    q: dict, bgm_path: str = "", sfx: dict | None = None
) -> tuple[bool, str]:
    """Encode one question into a temp file with animated backgrounds,
    cross-dissolve transitions, and a confetti celebration on the answer scene.
    Returns (True, tmp_path) or (False, error_string).
    """
    import tempfile

    tmp = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
    tmp.close()
    out_path = tmp.name

    qnum = int(q.get("number", 1))
    theme_idx = (qnum - 1) % len(THEMES)
    theme = THEMES[theme_idx]
    rng = random.Random(qnum * 17 + 3)
    opts_dur = int(q.get("options_duration", SCENE_DUR["options"]))
    q_type = q.get("type", "MC").upper()

    try:
        bg = _make_bg(theme, rng)
    except Exception as e:
        return False, f"bg render error: {e}"

    bg_f32 = np.array(bg, dtype=np.float32)
    bg_particles = _init_bg_particles(theme, rng)
    confetti = _init_confetti(rng)

    try:
        s1 = np.array(scene_category(q, bg, theme), dtype=np.float32)
        s2 = np.array(scene_question(q, bg, theme), dtype=np.float32)
        s3 = np.array(
            scene_ff_base(q, bg, theme)
            if q_type == "FF"
            else scene_options_base(q, bg, theme),
            dtype=np.float32,
        )
        s4 = np.array(scene_timeout(q, bg, theme), dtype=np.float32)
        s5 = np.array(scene_answer(q, bg, theme), dtype=np.float32)
    except Exception as e:
        return False, f"scene render error: {e}"

    acc = theme["accent"]
    warn = (255, 80, 80)

    # Pre-compute edge-only red vignette for low-timer tension effect
    _tv_xs = np.linspace(0, W, W, dtype=np.float32)
    _tv_ys = np.linspace(0, H, H, dtype=np.float32)
    _tv_xx, _tv_yy = np.meshgrid(_tv_xs, _tv_ys)
    _tv_d = np.clip(
        np.sqrt(
            ((_tv_xx - W / 2) / (W * 0.4)) ** 2 + ((_tv_yy - H / 2) / (H * 0.4)) ** 2
        )
        - 0.55,
        0,
        1,
    )
    tension_vign = np.zeros((H, W, 3), dtype=np.float32)
    tension_vign[:, :, 0] = _tv_d * 255  # red channel only

    cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "rawvideo",
        "-vcodec",
        "rawvideo",
        "-s",
        f"{W}x{H}",
        "-pix_fmt",
        "rgb24",
        "-r",
        str(FPS),
        "-i",
        "-",
        "-f",
        "lavfi",
        "-i",
        "anullsrc=channel_layout=stereo:sample_rate=44100",
        "-vcodec",
        "libx264",
        "-preset",
        "fast",
        "-crf",
        "18",
        "-pix_fmt",
        "yuv420p",
        "-acodec",
        "aac",
        "-b:a",
        "64k",
        "-shortest",
        out_path,
    ]
    try:
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception as e:
        return False, str(e)

    last_u8 = [None]  # holds last written frame as uint8 ndarray for dissolves

    def _write(img: Image.Image):
        arr = np.array(img)
        proc.stdin.write(arr.tobytes())
        last_u8[0] = arr

    def _dissolve(target_f32: np.ndarray, n: int = DISSOLVE_N):
        if last_u8[0] is None:
            return
        a = last_u8[0].astype(np.float32)
        for i in range(n):
            t = np.float32((i + 1) / (n + 1))
            frame = np.clip(a * (1 - t) + target_f32 * t, 0, 255).astype(np.uint8)
            proc.stdin.write(frame.tobytes())

    def _pulse(f: int, total: int, amp: float = 0.05, freq: float = 1.5) -> np.float32:
        return np.float32(1.0 + amp * math.sin(f / max(total, 1) * 2 * math.pi * freq))

    try:
        # ── Scene 1: Category (fade-in from bg) ───────────────────────────────
        n1 = SCENE_DUR["category"] * FPS
        FADE = 20
        for f in range(n1):
            pv = _pulse(f, n1)
            if f < FADE:
                a = np.float32(f / FADE)
                arr = np.clip(bg_f32 * (1 - a) + s1 * a * pv, 0, 255).astype(np.uint8)
            else:
                arr = np.clip(s1 * pv, 0, 255).astype(np.uint8)
            img = Image.fromarray(arr)
            _draw_bg_particles(ImageDraw.Draw(img), bg_particles, f)
            _write(img)

        # ── Dissolve 1 → 2 ───────────────────────────────────────────────────
        _dissolve(s2)

        # ── Scene 2: Question ────────────────────────────────────────────────
        n2 = SCENE_DUR["question"] * FPS
        for f in range(n2):
            pv = _pulse(f, n2)
            arr = np.clip(s2 * pv, 0, 255).astype(np.uint8)
            img = Image.fromarray(arr)
            _draw_bg_particles(ImageDraw.Draw(img), bg_particles, n1 + f)
            _write(img)

        # ── Dissolve 2 → 3 ───────────────────────────────────────────────────
        _dissolve(s3)

        # ── Scene 3: Countdown (MC = options + corner timer; FF = big centred ring) ──
        n3 = opts_dur * FPS
        f_off3 = n1 + n2
        # FF uses a large centred timer so contestants can see the countdown clearly
        ff_cx, ff_cy, ff_ro, ff_ri = W // 2, H // 2 + 100, 200, 140
        for f in range(n3):
            progress = 1.0 - f / n3
            pv = _pulse(f, n3)
            arr = np.clip(s3 * pv, 0, 255).astype(np.uint8)
            img = Image.fromarray(arr)
            d = ImageDraw.Draw(img)
            _draw_bg_particles(d, bg_particles, f_off3 + f)
            secs_left = math.ceil(progress * opts_dur)
            col = acc if progress > 0.3 else warn
            if q_type == "FF":
                _timer_ring(img, ff_cx, ff_cy, ff_ro, ff_ri, progress, acc, warn)
                ImageDraw.Draw(img).text(
                    (ff_cx, ff_cy), str(secs_left), font=FD(110), fill=col, anchor="mm"
                )
            else:
                _timer_ring(
                    img, _TIMER_CX, _TIMER_CY, _TIMER_RO, _TIMER_RI, progress, acc, warn
                )
                ImageDraw.Draw(img).text(
                    (_TIMER_CX, _TIMER_CY),
                    str(secs_left),
                    font=FD(46),
                    fill=col,
                    anchor="mm",
                )
            # ── Tension vignette: red edges pulse when < 30% time left ────────
            if progress < 0.3:
                urgency = np.float32(1.0 - progress / 0.3)
                phase = np.float32(abs(math.sin(f * 0.22 * (1.0 + urgency * 1.5))))
                tv_a = phase * urgency * np.float32(0.48)
                img_arr = np.array(img).astype(np.float32)
                img = Image.fromarray(
                    np.clip(img_arr + tension_vign * tv_a, 0, 255).astype(np.uint8)
                )
            _write(img)

        # ── Dissolve 3 → 4 ───────────────────────────────────────────────────
        _dissolve(s4)

        # ── Scene 4: Timeout (red flash + shake) ─────────────────────────────
        n4 = SCENE_DUR["timeout"] * FPS
        f_off4 = n1 + n2 + n3
        for f in range(n4):
            pv = _pulse(f, n4, amp=0.08, freq=2.5)
            arr = s4 * pv
            if f < 10:
                flash = np.float32((10 - f) / 10 * 0.45)
                red = np.zeros_like(arr)
                red[:, :, 0] = 220
                arr = arr * (1 - flash) + red * flash
            arr = np.clip(arr, 0, 255).astype(np.uint8)
            if f < 22:
                shake = int(7 * math.sin(f * 2.0) * max(0.0, 1 - f / 22))
                if shake:
                    arr = np.roll(arr, shake, axis=1)
            img = Image.fromarray(arr)
            _draw_bg_particles(ImageDraw.Draw(img), bg_particles, f_off4 + f)
            _write(img)

        # ── Dissolve 4 → 5 ───────────────────────────────────────────────────
        _dissolve(s5)

        # ── Scene 5: Answer + zoom punch-in + white flash + confetti ────────
        n5 = SCENE_DUR["answer"] * FPS
        f_off5 = n1 + n2 + n3 + n4
        ZOOM_FRAMES = 28
        for f in range(n5):
            t_s = f / FPS
            pv = _pulse(f, n5, amp=0.08, freq=1.2)
            arr = s5 * pv
            if f < 9:
                flash = np.float32((9 - f) / 9 * 0.78)
                arr = arr + 255 * flash
            arr = np.clip(arr, 0, 255).astype(np.uint8)
            img = Image.fromarray(arr)
            d = ImageDraw.Draw(img)
            _draw_bg_particles(d, bg_particles, f_off5 + f)
            _draw_confetti(d, confetti, t_s)
            # Zoom punch-in: card slams into view from large scale → 100%
            if f < ZOOM_FRAMES:
                zoom = np.float32(1.18 - 0.18 * (f / ZOOM_FRAMES))
                nw, nh = int(W / zoom), int(H / zoom)
                lft, top = (W - nw) // 2, (H - nh) // 2
                img = img.crop((lft, top, lft + nw, top + nh)).resize(
                    (W, H), Image.BILINEAR
                )
            _write(img)

        proc.stdin.close()
        proc.wait(timeout=300)
    except Exception as e:
        try:
            proc.kill()
        except Exception:
            pass
        return False, str(e)

    if proc.returncode != 0:
        return False, f"ffmpeg exited {proc.returncode}"

    # Mix in BGM, SFX, question/answer audio if provided
    out_path = _apply_audio_overlays(out_path, q, opts_dur, bgm_path, sfx or {})

    return True, out_path


# ─────────────────────────── question store ───────────────────────────────────


def _load_questions() -> list[dict]:
    if Q_PATH.exists():
        try:
            return json.loads(Q_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return []


def _save_questions(qs: list[dict]):
    Q_PATH.write_text(json.dumps(qs, indent=2, ensure_ascii=False), encoding="utf-8")


def _load_sfx() -> dict:
    if SFX_PATH.exists():
        try:
            return json.loads(SFX_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"intro": "", "countdown_tick": "", "timeout": ""}


def _save_sfx(cfg: dict):
    SFX_PATH.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")


def _build_countdown_audio(tick_path: str, duration_secs: int) -> str:
    """Create a looped tick track: one tick per second for duration_secs seconds.
    Returns path to a temp WAV, or empty string on failure.
    """
    import tempfile

    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp.close()
    n = max(1, duration_secs)
    cmd = ["ffmpeg", "-y"]
    for _ in range(n):
        cmd += ["-i", tick_path]
    filter_parts = [f"[{i}:a]apad=whole_dur=1[s{i}]" for i in range(n)]
    concat_in = "".join(f"[s{i}]" for i in range(n))
    filter_parts.append(f"{concat_in}concat=n={n}:v=0:a=1[out]")
    cmd += ["-filter_complex", ";".join(filter_parts), "-map", "[out]", tmp.name]
    result = subprocess.run(cmd, capture_output=True)
    if result.returncode == 0:
        return tmp.name
    try:
        import os

        os.unlink(tmp.name)
    except Exception:
        pass
    return ""


def _blank_question(number: int) -> dict:
    return {
        "number": number,
        "category": "GENERAL",
        "question": "",
        "option_a": "",
        "option_b": "",
        "option_c": "",
        "option_d": "",
        "correct_answer": "A",
        "type": "MC",
        "media_type": "text",
        "question_image": "",
        "answer_image": "",
        "question_audio": "",
        "answer_audio": "",
        "options_duration": 5,
    }


# ─────────────────────────── question edit dialog ─────────────────────────────


class QuestionDialog(QDialog):
    DARK = """
        QDialog { background:#0D1117; color:#E6EDF3; }
        QLabel  { color:#8B949E; }
        QLineEdit, QTextEdit, QComboBox {
            background:#161B22; color:#E6EDF3; border:1px solid #30363D;
            border-radius:4px; padding:4px; font-size:13px;
        }
        QDialogButtonBox QPushButton {
            background:#21262D; color:#E6EDF3; border:1px solid #30363D;
            border-radius:4px; padding:6px 14px;
        }
        QDialogButtonBox QPushButton:hover { background:#30363D; }
    """

    def __init__(self, q: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Question")
        self.setMinimumWidth(620)
        self.setStyleSheet(self.DARK)
        self._q = dict(q)
        self._build()

    def _build(self):
        lay = QFormLayout(self)
        lay.setSpacing(8)
        lay.setContentsMargins(16, 16, 16, 8)

        def _le(key, placeholder=""):
            w = QLineEdit(str(self._q.get(key, "")))
            w.setPlaceholderText(placeholder)
            w.textChanged.connect(lambda v, k=key: self._q.update({k: v}))
            return w

        lay.addRow("Number:", _le("number"))
        lay.addRow("Category:", _le("category", "e.g. GEOGRAPHY"))

        # Question type: MC / FF
        self._type_cb = QComboBox()
        self._type_cb.addItems(["MC", "FF"])
        self._type_cb.setCurrentText(self._q.get("type", "MC"))
        self._type_cb.currentTextChanged.connect(lambda v: self._q.update({"type": v}))
        lay.addRow("Type:", self._type_cb)

        # Media type: Text / Photo / Audio
        self._media_cb = QComboBox()
        self._media_cb.addItems(["Text", "Photo", "Audio"])
        self._media_cb.setCurrentText(self._q.get("media_type", "text").capitalize())
        self._media_cb.currentTextChanged.connect(self._on_media_change)
        lay.addRow("Media:", self._media_cb)

        # Question text
        self._q_edit = QTextEdit()
        self._q_edit.setPlainText(self._q.get("question", ""))
        self._q_edit.setFixedHeight(80)
        self._q_edit.textChanged.connect(
            lambda: self._q.update({"question": self._q_edit.toPlainText()})
        )
        lay.addRow("Question:", self._q_edit)

        # ── Photo fields (shown only when Media = Photo) ───────────────────────
        self._photo_box = QWidget()
        pb = QFormLayout(self._photo_box)
        pb.setContentsMargins(0, 0, 0, 0)
        pb.setSpacing(5)
        self._q_img_le = QLineEdit(str(self._q.get("question_image", "")))
        self._q_img_le.textChanged.connect(
            lambda v: self._q.update({"question_image": v})
        )
        pb.addRow(
            "Q. Image:",
            self._make_browse_row(
                self._q_img_le, "Images (*.jpg *.jpeg *.png *.bmp *.webp *.gif)"
            ),
        )
        self._a_img_le = QLineEdit(str(self._q.get("answer_image", "")))
        self._a_img_le.textChanged.connect(
            lambda v: self._q.update({"answer_image": v})
        )
        pb.addRow(
            "Ans. Image:",
            self._make_browse_row(
                self._a_img_le, "Images (*.jpg *.jpeg *.png *.bmp *.webp *.gif)"
            ),
        )
        lay.addRow(self._photo_box)

        # ── Audio fields (shown only when Media = Audio) ───────────────────────
        self._audio_box = QWidget()
        ab = QFormLayout(self._audio_box)
        ab.setContentsMargins(0, 0, 0, 0)
        ab.setSpacing(5)
        self._q_aud_le = QLineEdit(str(self._q.get("question_audio", "")))
        self._q_aud_le.textChanged.connect(
            lambda v: self._q.update({"question_audio": v})
        )
        ab.addRow(
            "Q. Audio:",
            self._make_browse_row(
                self._q_aud_le, "Audio (*.mp3 *.wav *.ogg *.aac *.m4a *.flac)"
            ),
        )
        self._a_aud_le = QLineEdit(str(self._q.get("answer_audio", "")))
        self._a_aud_le.textChanged.connect(
            lambda v: self._q.update({"answer_audio": v})
        )
        ab.addRow(
            "Ans. Audio:",
            self._make_browse_row(
                self._a_aud_le, "Audio (*.mp3 *.wav *.ogg *.aac *.m4a *.flac)"
            ),
        )
        lay.addRow(self._audio_box)

        # Correct answer
        self._ans_cb = QComboBox()
        self._ans_cb.addItems(["A", "B", "C", "D"])
        self._ans_cb.setCurrentText(self._q.get("correct_answer", "A"))
        self._ans_cb.currentTextChanged.connect(
            lambda v: self._q.update({"correct_answer": v})
        )
        lay.addRow("Correct:", self._ans_cb)

        # Options
        for letter in "ABCD":
            lay.addRow(
                f"Option {letter}:", _le(f"option_{letter.lower()}", f"Answer {letter}")
            )

        lay.addRow("Timer (s):", _le("options_duration", "5"))

        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addRow(bb)

        # Set initial visibility based on current media type
        self._photo_box.setVisible(False)
        self._audio_box.setVisible(False)
        self._on_media_change(self._media_cb.currentText())

    def _make_browse_row(self, le: QLineEdit, file_filter: str) -> QWidget:
        w = QWidget()
        hl = QHBoxLayout(w)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.addWidget(le)
        btn = QPushButton("Browse…")
        btn.setMaximumWidth(82)
        btn.clicked.connect(lambda _, l=le, f=file_filter: self._browse(l, f))
        hl.addWidget(btn)
        return w

    def _browse_bgm(self, le: QLineEdit):
        from PyQt5.QtWidgets import QFileDialog

        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Background Music",
            "",
            "Audio Files (*.mp3 *.wav *.ogg *.aac *.flac)",
        )
        if path:
            le.setText(path)

    def _browse(self, le: QLineEdit, file_filter: str):
        from PyQt5.QtWidgets import QFileDialog

        start = ""
        if le.text():
            p = Path(le.text()).parent
            if p.exists():
                start = str(p)
        path, _ = QFileDialog.getOpenFileName(self, "Select File", start, file_filter)
        if path:
            le.setText(path)

    def _on_media_change(self, val: str):
        self._q["media_type"] = val.lower()
        self._photo_box.setVisible(val == "Photo")
        self._audio_box.setVisible(val == "Audio")
        self.adjustSize()

    def result_q(self) -> dict:
        try:
            self._q["number"] = int(self._q["number"])
        except (ValueError, KeyError, TypeError):
            self._q["number"] = 1
        try:
            self._q["options_duration"] = int(self._q.get("options_duration", 5))
        except (ValueError, TypeError):
            self._q["options_duration"] = 5
        return self._q


# ─────────────────────────── preview widget ───────────────────────────────────


class PreviewWidget(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumSize(640, 360)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setStyleSheet("background:#000; border:1px solid #30363D;")
        self._pil = None

    def set_image(self, pil_img: Image.Image):
        self._pil = pil_img
        self._repaint()

    def resizeEvent(self, _e):
        self._repaint()

    def _repaint(self):
        if self._pil is None:
            return
        w, h = self.width(), self.height()
        scaled = self._pil.copy()
        scaled.thumbnail((w, h), Image.LANCZOS)
        data = scaled.tobytes("raw", "RGB")
        qimg = QImage(data, scaled.width, scaled.height, QImage.Format_RGB888)
        self.setPixmap(QPixmap.fromImage(qimg))


# ─────────────────────────── main window ──────────────────────────────────────

DARK_STYLE = """
QMainWindow, QWidget { background:#0D1117; color:#E6EDF3; }
QGroupBox {
    border:1px solid #30363D; border-radius:4px; margin-top:8px;
    font-weight:bold; color:#8B949E; padding:4px;
}
QGroupBox::title { subcontrol-origin:margin; left:8px; padding:0 4px; }
QListWidget {
    background:#161B22; border:1px solid #30363D; border-radius:4px;
    color:#E6EDF3; font-size:12px; selection-background-color:#1F6FEB;
}
QListWidget::item { padding:5px 8px; border-bottom:1px solid #21262D; }
QListWidget::item:selected { background:#1F6FEB; color:#fff; }
QPushButton {
    background:#21262D; color:#E6EDF3; border:1px solid #30363D;
    border-radius:4px; padding:6px 14px; font-size:12px;
}
QPushButton:hover { background:#30363D; }
QPushButton:disabled { color:#484F58; background:#161B22; }
QComboBox {
    background:#21262D; color:#E6EDF3; border:1px solid #30363D;
    border-radius:4px; padding:4px 8px;
}
QComboBox QAbstractItemView { background:#1C2128; color:#E6EDF3;
    selection-background-color:#1F6FEB; }
QProgressBar {
    background:#21262D; border:1px solid #30363D; border-radius:4px;
    text-align:center; color:#fff;
}
QProgressBar::chunk { background:#238636; border-radius:3px; }
QTextEdit, QLineEdit {
    background:#161B22; color:#E6EDF3; border:1px solid #30363D;
    border-radius:4px; padding:4px;
}
QScrollBar:vertical { background:#0D1117; width:8px; }
QScrollBar::handle:vertical { background:#30363D; border-radius:4px; }
"""


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Question Video Generator")
        self.setMinimumSize(1200, 700)
        self.resize(1400, 800)
        self._questions: list[dict] = _load_questions()
        self._sfx_cfg: dict = _load_sfx()
        self._worker: RenderWorker | None = None
        self._build_ui()
        self._refresh_list()

    # ── build ──────────────────────────────────────────────────────────────────

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        # Title
        title = QLabel("Question Video Generator")
        title.setFont(QFont("Segoe UI", 14, QFont.Bold))
        title.setStyleSheet("color:#58A6FF;")
        root.addWidget(title)

        hint = QLabel(
            "Each question generates a 5-scene MP4 video (Category → Question → Options+Timer → "
            "Time's Up → Answer).  Videos land in vid/vrae/ with correct A_/B_/C_/D_/F_ prefixes."
        )
        hint.setStyleSheet("color:#8B949E; font-size:11px;")
        hint.setWordWrap(True)
        root.addWidget(hint)

        splitter = QSplitter(Qt.Horizontal)
        root.addWidget(splitter, 1)

        # ── LEFT: question list ────────────────────────────────────────────────
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        ll.setSpacing(4)

        lbl = QLabel("Questions")
        lbl.setStyleSheet("color:#8B949E; font-size:11px;")
        ll.addWidget(lbl)

        self._list = QListWidget()
        self._list.currentRowChanged.connect(self._on_select)
        ll.addWidget(self._list, 1)

        btns = QHBoxLayout()
        b_add = QPushButton("➕ Add")
        b_edit = QPushButton("✏ Edit")
        b_dup = QPushButton("⧉ Dup")
        b_del = QPushButton("✖ Del")
        for b in (b_add, b_edit, b_dup, b_del):
            btns.addWidget(b)
        ll.addLayout(btns)

        b_add.clicked.connect(self._add_question)
        b_edit.clicked.connect(self._edit_question)
        b_dup.clicked.connect(self._dup_question)
        b_del.clicked.connect(self._del_question)

        splitter.addWidget(left)

        # ── CENTER: preview ────────────────────────────────────────────────────
        center = QWidget()
        cl = QVBoxLayout(center)
        cl.setContentsMargins(6, 0, 6, 0)
        cl.setSpacing(4)

        pv_lbl = QLabel("Preview")
        pv_lbl.setStyleSheet("color:#8B949E; font-size:11px;")
        cl.addWidget(pv_lbl)

        self._preview = PreviewWidget()
        cl.addWidget(self._preview, 1)

        # Scene selector
        sc_row = QHBoxLayout()
        sc_row.addWidget(QLabel("Scene:"))
        self._scene_cb = QComboBox()
        self._scene_cb.addItems(
            ["Category", "Question", "Options (start)", "Time's Up", "Answer"]
        )
        self._scene_cb.currentIndexChanged.connect(self._refresh_preview)
        sc_row.addWidget(self._scene_cb)
        sc_row.addStretch()

        b_prev = QPushButton("⟳ Refresh Preview")
        b_prev.clicked.connect(self._refresh_preview)
        sc_row.addWidget(b_prev)
        cl.addLayout(sc_row)

        splitter.addWidget(center)

        # ── RIGHT: generation ──────────────────────────────────────────────────
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(6)

        gen_grp = QGroupBox("Generate Videos")
        gl = QVBoxLayout(gen_grp)

        # Theme legend
        leg = QLabel()
        leg.setWordWrap(True)
        _THEME_COLS = ("cyan", "orange", "yellow", "gold", "lime")
        theme_parts = []
        for i, t in enumerate(THEMES):
            col = _THEME_COLS[i]
            name = t["name"]
            theme_parts.append(
                f'<span style="color:{col}">Q{i + 1},{i + 6},… {name}</span>'
            )
        theme_html = "  ".join(theme_parts)
        leg.setText(f"<small>{theme_html}</small>")
        leg.setTextFormat(Qt.RichText)
        gl.addWidget(leg)

        # BGM picker
        bgm_row = QHBoxLayout()
        bgm_lbl = QLabel("Background Music:")
        bgm_lbl.setStyleSheet("font-weight:bold;")
        bgm_row.addWidget(bgm_lbl)
        self._bgm_le = QLineEdit()
        self._bgm_le.setPlaceholderText("optional — MP3/WAV looped at 25% volume")
        bgm_row.addWidget(self._bgm_le, 1)
        bgm_browse = QPushButton("Browse")
        bgm_browse.setFixedWidth(70)
        bgm_browse.clicked.connect(lambda: self._browse_bgm(self._bgm_le))
        bgm_row.addWidget(bgm_browse)
        gl.addLayout(bgm_row)

        # SFX pickers
        sfx_grp = QGroupBox("Sound Effects  (auto-synced)")
        sfx_gl = QVBoxLayout(sfx_grp)
        sfx_gl.setSpacing(4)

        def _sfx_row(label: str, placeholder: str, attr: str, sfx_key: str):
            row = QHBoxLayout()
            lbl = QLabel(label)
            lbl.setFixedWidth(115)
            row.addWidget(lbl)
            le = QLineEdit()
            le.setPlaceholderText(placeholder)
            le.setText(self._sfx_cfg.get(sfx_key, ""))
            le.textChanged.connect(lambda t, k=sfx_key: self._sfx_cfg.update({k: t}))
            setattr(self, attr, le)
            row.addWidget(le, 1)
            btn = QPushButton("Browse")
            btn.setFixedWidth(65)
            btn.clicked.connect(lambda _, l=le: self._browse_bgm(l))
            row.addWidget(btn)
            sfx_gl.addLayout(row)

        _sfx_row("Intro Jingle:", "plays at question start", "_sfx_intro_le", "intro")
        _sfx_row(
            "Countdown Tick:", "repeats every second", "_sfx_tick_le", "countdown_tick"
        )
        _sfx_row(
            "Timeout Sound:", "plays when time runs out", "_sfx_timeout_le", "timeout"
        )
        gl.addWidget(sfx_grp)

        self._btn_gen_one = QPushButton("🎬  Generate Selected")
        self._btn_gen_one.setStyleSheet(
            "background:#1F6FEB; color:white; font-weight:bold; padding:8px;"
        )
        self._btn_gen_one.clicked.connect(self._gen_selected)
        gl.addWidget(self._btn_gen_one)

        self._btn_gen_all = QPushButton("🎬  Generate ALL Questions")
        self._btn_gen_all.setStyleSheet(
            "background:#238636; color:white; font-weight:bold; padding:8px;"
        )
        self._btn_gen_all.clicked.connect(self._gen_all)
        gl.addWidget(self._btn_gen_all)

        self._progress = QProgressBar()
        self._progress.setVisible(False)
        gl.addWidget(self._progress)

        rl.addWidget(gen_grp)

        # Log
        log_grp = QGroupBox("Log")
        log_l = QVBoxLayout(log_grp)
        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setFont(QFont("Consolas", 8))
        self._log.setFixedHeight(220)
        log_l.addWidget(self._log)
        b_clr = QPushButton("Clear")
        b_clr.clicked.connect(self._log.clear)
        log_l.addWidget(b_clr)
        rl.addWidget(log_grp)

        rl.addStretch()

        splitter.addWidget(right)
        splitter.setSizes([280, 700, 320])

    # ── list management ────────────────────────────────────────────────────────

    def _refresh_list(self):
        self._list.clear()
        for q in self._questions:
            cor = q.get("correct_answer", "?")
            cat = q.get("category", "")[:16]
            txt = q.get("question", "")[:45]
            try:
                qn = int(q.get("number", 0))
            except (ValueError, TypeError):
                qn = 0
            lbl = f"Q{qn:02d}  [{cor}]  {cat} — {txt}"
            item = QListWidgetItem(lbl)
            # Colour by correct answer
            col_map = {"A": "#2ECC71", "B": "#3498DB", "C": "#9B59B6", "D": "#E67E22"}
            item.setForeground(QColor(col_map.get(cor, "#E6EDF3")))
            self._list.addItem(item)

    def _current_q(self) -> dict | None:
        row = self._list.currentRow()
        if 0 <= row < len(self._questions):
            return self._questions[row]
        return None

    def _add_question(self):
        n = max((q.get("number", 0) for q in self._questions), default=0) + 1
        dlg = QuestionDialog(_blank_question(n), self)
        if dlg.exec_() == QDialog.Accepted:
            self._questions.append(dlg.result_q())
            _save_questions(self._questions)
            self._refresh_list()
            self._list.setCurrentRow(len(self._questions) - 1)

    def _edit_question(self):
        q = self._current_q()
        if not q:
            return
        row = self._list.currentRow()
        dlg = QuestionDialog(q, self)
        if dlg.exec_() == QDialog.Accepted:
            self._questions[row] = dlg.result_q()
            _save_questions(self._questions)
            self._refresh_list()
            self._list.setCurrentRow(row)

    def _dup_question(self):
        q = self._current_q()
        if not q:
            return
        import copy

        nq = copy.deepcopy(q)
        nq["number"] = max((x.get("number", 0) for x in self._questions), default=0) + 1
        self._questions.append(nq)
        _save_questions(self._questions)
        self._refresh_list()
        self._list.setCurrentRow(len(self._questions) - 1)

    def _del_question(self):
        row = self._list.currentRow()
        if row < 0:
            return
        if (
            QMessageBox.question(
                self,
                "Delete",
                "Delete this question?",
                QMessageBox.Yes | QMessageBox.No,
            )
            == QMessageBox.Yes
        ):
            self._questions.pop(row)
            _save_questions(self._questions)
            self._refresh_list()

    # ── preview ────────────────────────────────────────────────────────────────

    def _on_select(self, _row):
        self._refresh_preview()

    def _refresh_preview(self):
        q = self._current_q()
        if not q:
            return
        qnum = int(q.get("number", 1))
        idx = (qnum - 1) % len(THEMES)
        theme = THEMES[idx]
        rng = random.Random(qnum * 17 + 3)
        try:
            bg = _make_bg(theme, rng)
            sc = self._scene_cb.currentIndex()
            if sc == 0:
                img = scene_category(q, bg, theme)
            elif sc == 1:
                img = scene_question(q, bg, theme)
            elif sc == 2:
                base = scene_options_base(q, bg, theme)
                _timer_ring(
                    base,
                    _TIMER_CX,
                    _TIMER_CY,
                    _TIMER_RO,
                    _TIMER_RI,
                    1.0,
                    theme["accent"],
                    (255, 80, 80),
                )
                ImageDraw.Draw(base).text(
                    (_TIMER_CX, _TIMER_CY),
                    str(q.get("options_duration", 15)),
                    font=FD(38),
                    fill=theme["accent"],
                    anchor="mm",
                )
                img = base
            elif sc == 3:
                img = scene_timeout(q, bg, theme)
            else:
                img = scene_answer(q, bg, theme)
            self._preview.set_image(img)
        except Exception as exc:
            self._log.append(f"[PREVIEW ERROR] {exc}")

    # ── generation ─────────────────────────────────────────────────────────────

    def _gen_selected(self):
        q = self._current_q()
        if not q:
            QMessageBox.warning(self, "None selected", "Select a question first.")
            return
        self._start_render([q])

    def _gen_all(self):
        if not self._questions:
            QMessageBox.warning(self, "Empty", "No questions to generate.")
            return
        self._start_render(self._questions)

    def _start_render(self, qs: list[dict]):
        if self._worker and self._worker.isRunning():
            return
        self._btn_gen_one.setEnabled(False)
        self._btn_gen_all.setEnabled(False)
        self._progress.setVisible(True)
        self._progress.setMaximum(len(qs))
        self._progress.setValue(0)

        bgm = self._bgm_le.text().strip()
        _save_sfx(self._sfx_cfg)
        self._worker = RenderWorker(qs, bgm, self._sfx_cfg, self)
        self._worker.progress.connect(self._on_progress)
        self._worker.log_msg.connect(self._log.append)
        self._worker.finished.connect(self._on_done)
        self._worker.start()

    def _on_progress(self, done, total):
        self._progress.setValue(done)

    def _on_done(self, ok, msg):
        self._progress.setVisible(False)
        self._btn_gen_one.setEnabled(True)
        self._btn_gen_all.setEnabled(True)
        if ok:
            QMessageBox.information(self, "Done", msg)
        else:
            QMessageBox.warning(self, "Errors", msg)

    def _browse_bgm(self, le: "QLineEdit"):
        from PyQt5.QtWidgets import QFileDialog

        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Audio File",
            "",
            "Audio Files (*.mp3 *.wav *.ogg *.aac *.flac)",
        )
        if path:
            le.setText(path)


# ─────────────────────────── entry point ──────────────────────────────────────


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(DARK_STYLE)
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()

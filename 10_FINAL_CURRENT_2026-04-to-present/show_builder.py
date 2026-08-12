"""
Gameshow Show Builder
=====================
Drag-and-drop video ordering tool. Output goes directly to the gameshow
vid/ folder with timestamps stamped to enforce play order in VS Code /
Windows Explorer (same technique as sort22.py).

How to use:
  1. Drop videos from anywhere onto the left panel (or click Add Files).
  2. Use Up/Down arrows or drag rows to set the exact play order.
  3. Assign a gameshow prefix per video (A_, B_, C_, D_, F_, Q_, none).
  4. Click "Build Show" to copy+stamp files into vid/vrae/ (or countdown/).
"""

import os
import sys
import shutil
import json
from datetime import datetime, timedelta

from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QLabel,
    QPushButton,
    QListWidget,
    QListWidgetItem,
    QFileDialog,
    QMessageBox,
    QProgressBar,
    QComboBox,
    QAbstractItemView,
    QSplitter,
    QGroupBox,
    QRadioButton,
    QButtonGroup,
    QDialog,
    QDialogButtonBox,
    QCheckBox,
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QDragEnterEvent, QDropEvent, QFont, QColor

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
try:
    with open(CONFIG_PATH) as f:
        CONFIG = json.load(f)
except Exception:
    CONFIG = {"gameshow": {"video_folder": "vid"}}

VID_DIR = os.path.join(BASE_DIR, CONFIG["gameshow"]["video_folder"])
VRAE_DIR = os.path.join(VID_DIR, "vrae")
COUNTDOWN_DIR = os.path.join(VID_DIR, "countdown")
VISUAL_DIR = os.path.join(VID_DIR, "visual")

VIDEO_EXTS = {
    ".mp4",
    ".mov",
    ".avi",
    ".mkv",
    ".webm",
    ".flv",
    ".wmv",
    ".m4v",
    ".mpg",
    ".mpeg",
    ".m2ts",
}

# Prefix definitions: (display_label, file_prefix, colour_hex, description)
PREFIXES = [
    ("A_", "A_", "#2ECC71", "Answer A"),
    ("B_", "B_", "#3498DB", "Answer B"),
    ("C_", "C_", "#9B59B6", "Answer C"),
    ("D_", "D_", "#E67E22", "Answer D"),
    ("F_", "F_", "#F0883E", "Skip 2nd pause"),
    (".Q_", ".Q_", "#58A6FF", "No pauses (bridge)"),
    ("(none)", "", "#8B949E", "No prefix"),
]

# ---------------------------------------------------------------------------
# Dark theme helper
# ---------------------------------------------------------------------------

DARK_STYLE = """
QMainWindow, QWidget, QDialog {
    background-color: #0D1117;
    color: #E6EDF3;
}
QGroupBox {
    border: 1px solid #30363D;
    border-radius: 4px;
    margin-top: 8px;
    font-weight: bold;
    color: #8B949E;
    padding: 6px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 8px;
    padding: 0 4px;
}
QListWidget {
    background-color: #161B22;
    border: 1px solid #30363D;
    border-radius: 4px;
    color: #E6EDF3;
    font-size: 13px;
    selection-background-color: #1F6FEB;
}
QListWidget::item {
    padding: 6px 8px;
    border-bottom: 1px solid #21262D;
}
QListWidget::item:selected {
    background-color: #1F6FEB;
    color: white;
}
QPushButton {
    background-color: #21262D;
    color: #E6EDF3;
    border: 1px solid #30363D;
    border-radius: 4px;
    padding: 6px 14px;
    font-size: 12px;
}
QPushButton:hover {
    background-color: #30363D;
}
QPushButton:pressed {
    background-color: #1F6FEB;
}
QPushButton:disabled {
    color: #484F58;
    background-color: #161B22;
}
QComboBox {
    background-color: #21262D;
    color: #E6EDF3;
    border: 1px solid #30363D;
    border-radius: 4px;
    padding: 4px 8px;
    min-width: 120px;
}
QComboBox QAbstractItemView {
    background-color: #1C2128;
    color: #E6EDF3;
    selection-background-color: #1F6FEB;
}
QProgressBar {
    background-color: #21262D;
    border: 1px solid #30363D;
    border-radius: 4px;
    text-align: center;
    color: white;
}
QProgressBar::chunk {
    background-color: #238636;
    border-radius: 3px;
}
QLabel {
    color: #E6EDF3;
}
QRadioButton {
    color: #E6EDF3;
    spacing: 6px;
}
QCheckBox {
    color: #E6EDF3;
}
QScrollArea {
    border: none;
}
"""

# ---------------------------------------------------------------------------
# Video entry (one row in the list)
# ---------------------------------------------------------------------------


class VideoItem:
    """Represents one video file with its assigned prefix."""

    def __init__(self, path: str):
        self.path = path
        self.original_name = os.path.basename(path)
        self._detect_prefix()

    def _detect_prefix(self):
        """Try to detect an existing gameshow prefix from the filename."""
        stem = self.original_name
        for _, pfx, _, _ in PREFIXES:
            if pfx and stem.startswith(pfx):
                self.prefix = pfx
                return
        # .Q_ can appear anywhere
        if ".Q_" in stem:
            self.prefix = ".Q_"
            return
        self.prefix = ""

    @property
    def output_name(self) -> str:
        """Filename with prefix applied, stripping any existing gameshow prefix."""
        stem = self.original_name
        # Strip existing prefix
        for _, pfx, _, _ in PREFIXES:
            if pfx and stem.startswith(pfx):
                stem = stem[len(pfx) :]
                break
        # .Q_ is inserted before the extension
        if self.prefix == ".Q_":
            name, ext = os.path.splitext(stem)
            return f"{name}.Q_{ext}"
        elif self.prefix:
            return self.prefix + stem
        return stem

    @property
    def display_text(self) -> str:
        pfx_label = self.prefix if self.prefix else "(no prefix)"
        return f"[{pfx_label:<6}]  {self.output_name}"

    @property
    def prefix_colour(self) -> str:
        for _, pfx, colour, _ in PREFIXES:
            if pfx == self.prefix:
                return colour
        return "#8B949E"


# ---------------------------------------------------------------------------
# Draggable list widget
# ---------------------------------------------------------------------------


class DraggableList(QListWidget):
    """QListWidget with internal drag-to-reorder enabled."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragDropMode(QAbstractItemView.InternalMove)
        self.setDefaultDropAction(Qt.MoveAction)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setAcceptDrops(True)
        self.setDragEnabled(True)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.source() is self:
            super().dragEnterEvent(event)
        elif event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent):
        if event.source() is self:
            super().dropEvent(event)
            # After internal reorder, notify parent window
            main = self.window()
            if hasattr(main, "_sync_items_after_drag"):
                main._sync_items_after_drag()
        elif event.mimeData().hasUrls():
            # Forward external file drops to the main window
            main = self.window()
            if hasattr(main, "dropEvent"):
                main.dropEvent(event)
        else:
            event.ignore()


# ---------------------------------------------------------------------------
# Prefix chooser dialog
# ---------------------------------------------------------------------------


class PrefixDialog(QDialog):
    def __init__(self, current_prefix: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Set Prefix")
        self.setMinimumWidth(300)
        self.chosen = current_prefix

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Choose a gameshow prefix for this video:"))

        self._group = QButtonGroup(self)
        for label, pfx, colour, desc in PREFIXES:
            rb = QRadioButton(f"{label:<8}  —  {desc}")
            rb.setStyleSheet(
                f"color: {colour}; font-family: Consolas; font-size: 12px;"
            )
            rb.setProperty("pfx", pfx)
            if pfx == current_prefix:
                rb.setChecked(True)
            self._group.addButton(rb)
            layout.addWidget(rb)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_ok)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_ok(self):
        btn = self._group.checkedButton()
        if btn:
            self.chosen = btn.property("pfx")
        self.accept()


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------


class ShowBuilder(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Gameshow Show Builder")
        self.setMinimumSize(960, 640)
        self.resize(1100, 700)

        self._items: list[VideoItem] = []  # parallel to list widget rows
        self._build_ui()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(10, 8, 10, 8)
        root.setSpacing(6)

        # ── Title ──
        title = QLabel("Gameshow Show Builder")
        title.setFont(QFont("Segoe UI", 15, QFont.Bold))
        title.setStyleSheet("color: #58A6FF;")
        root.addWidget(title)

        hint = QLabel(
            "Drag videos from Explorer onto the list, reorder by dragging rows or ↑↓ buttons, "
            "assign a prefix per video, then click Build Show."
        )
        hint.setStyleSheet("color: #8B949E; font-size: 11px;")
        hint.setWordWrap(True)
        root.addWidget(hint)

        # ── Main splitter ──
        splitter = QSplitter(Qt.Horizontal)
        root.addWidget(splitter, 1)

        # Left: video list
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        ll.setSpacing(4)

        list_label = QLabel("Show Order  (drag to reorder)")
        list_label.setStyleSheet("color: #8B949E; font-size: 11px;")
        ll.addWidget(list_label)

        self._list = DraggableList()
        self._list.itemDoubleClicked.connect(self._edit_prefix)
        ll.addWidget(self._list, 1)

        # List buttons row
        list_btns = QHBoxLayout()
        self._btn_add = QPushButton("➕ Add Files")
        self._btn_remove = QPushButton("✖ Remove")
        self._btn_clear = QPushButton("🗑 Clear All")
        self._btn_up = QPushButton("↑ Up")
        self._btn_down = QPushButton("↓ Down")
        for b in (
            self._btn_add,
            self._btn_remove,
            self._btn_clear,
            self._btn_up,
            self._btn_down,
        ):
            list_btns.addWidget(b)
        ll.addLayout(list_btns)

        # Drop hint overlay label (shown when list is empty)
        self._drop_hint = QLabel(
            "⬇  Drag & Drop video files here\n(or click Add Files)",
            alignment=Qt.AlignCenter,
        )
        self._drop_hint.setStyleSheet(
            "color: #484F58; font-size: 14px; border: 2px dashed #30363D;"
            "border-radius: 8px; padding: 30px;"
        )
        ll.addWidget(self._drop_hint)
        self._list.setAcceptDrops(True)
        self._list.installEventFilter(self)

        splitter.addWidget(left)

        # Right: settings + preview
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(6, 0, 0, 0)
        rl.setSpacing(8)

        # Prefix assignment group
        pfx_group = QGroupBox("Quick Prefix Assignment")
        pg = QVBoxLayout(pfx_group)
        pg.setSpacing(4)

        pfx_hint = QLabel("Select video(s) in the list, then click a prefix button:")
        pfx_hint.setStyleSheet("color: #8B949E; font-size: 10px;")
        pg.addWidget(pfx_hint)

        pfx_grid = QHBoxLayout()
        for label, pfx, colour, desc in PREFIXES:
            btn = QPushButton(label)
            btn.setToolTip(desc)
            btn.setStyleSheet(
                f"background-color: {colour}22; color: {colour}; "
                f"border: 1px solid {colour}; font-weight: bold; "
                f"padding: 5px 8px; min-width: 50px;"
            )
            btn.clicked.connect(lambda checked, p=pfx: self._assign_prefix(p))
            pfx_grid.addWidget(btn)
        pg.addLayout(pfx_grid)
        rl.addWidget(pfx_group)

        # Output destination group
        out_group = QGroupBox("Output Destination")
        og = QVBoxLayout(out_group)

        dest_row = QHBoxLayout()
        dest_row.addWidget(QLabel("Destination:"))
        self._dest_combo = QComboBox()
        self._dest_combo.addItem("vid/vrae/   (question videos)", VRAE_DIR)
        self._dest_combo.addItem("vid/countdown/   (countdown videos)", COUNTDOWN_DIR)
        self._dest_combo.addItem("vid/visual/   (intro / visual)", VISUAL_DIR)
        dest_row.addWidget(self._dest_combo, 1)
        og.addLayout(dest_row)

        ts_row = QHBoxLayout()
        self._overwrite_check = QCheckBox("Overwrite existing files in destination")
        self._overwrite_check.setChecked(True)
        ts_row.addWidget(self._overwrite_check)
        og.addLayout(ts_row)

        rl.addWidget(out_group)

        # Show preview
        prev_group = QGroupBox("Show Preview")
        prev_layout = QVBoxLayout(prev_group)
        self._preview = QListWidget()
        self._preview.setSelectionMode(QAbstractItemView.NoSelection)
        self._preview.setFocusPolicy(Qt.NoFocus)
        prev_layout.addWidget(self._preview)
        rl.addWidget(prev_group, 1)

        # Build button + progress
        self._progress = QProgressBar()
        self._progress.setVisible(False)
        rl.addWidget(self._progress)

        self._btn_build = QPushButton("🎬  Build Show  →  Copy & Stamp Files")
        self._btn_build.setStyleSheet(
            "background-color: #238636; color: white; font-weight: bold; "
            "font-size: 13px; padding: 10px;"
        )
        rl.addWidget(self._btn_build)

        splitter.addWidget(right)
        splitter.setSizes([550, 430])

        # Connections
        self._btn_add.clicked.connect(self._add_files)
        self._btn_remove.clicked.connect(self._remove_selected)
        self._btn_clear.clicked.connect(self._clear_all)
        self._btn_up.clicked.connect(self._move_up)
        self._btn_down.clicked.connect(self._move_down)
        self._btn_build.clicked.connect(self._build_show)
        self._list.currentRowChanged.connect(self._refresh_preview)
        self._dest_combo.currentIndexChanged.connect(self._refresh_preview)

        self._refresh_ui()

    # ------------------------------------------------------------------
    # Drag-drop into the window
    # ------------------------------------------------------------------

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        urls = event.mimeData().urls()
        added = []
        for url in urls:
            path = url.toLocalFile()
            if os.path.isfile(path) and _is_video(path):
                if path not in [i.path for i in self._items]:
                    self._add_item(VideoItem(path))
                    added.append(path)
            elif os.path.isdir(path):
                for fname in sorted(os.listdir(path)):
                    fpath = os.path.join(path, fname)
                    if _is_video(fpath) and fpath not in [i.path for i in self._items]:
                        self._add_item(VideoItem(fpath))
                        added.append(fpath)
        self._refresh_ui()

    # ------------------------------------------------------------------
    # List management
    # ------------------------------------------------------------------

    def _add_item(self, item: VideoItem):
        self._items.append(item)
        lw_item = QListWidgetItem(item.display_text)
        lw_item.setForeground(QColor(item.prefix_colour))
        lw_item.setFont(QFont("Consolas", 10))
        self._list.addItem(lw_item)

    def _sync_items_after_drag(self):
        """After internal drag-reorder, re-sync self._items to match list widget order."""
        if self._list.count() != len(self._items):
            return
        # The list widget rows have moved — rebuild _items in new order
        # We key by display_text since items are unique
        text_to_item = {it.display_text: it for it in self._items}
        new_order = []
        for i in range(self._list.count()):
            text = self._list.item(i).text()
            if text in text_to_item:
                new_order.append(text_to_item[text])
        if len(new_order) == len(self._items):
            self._items = new_order
        self._refresh_preview()

    def _add_files(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Select Video Files",
            "",
            "Video Files (*.mp4 *.mov *.avi *.mkv *.webm *.wmv *.m4v *.mpg);;All Files (*)",
        )
        existing = {it.path for it in self._items}
        for p in paths:
            if p not in existing:
                self._add_item(VideoItem(p))
        self._refresh_ui()

    def _remove_selected(self):
        row = self._list.currentRow()
        if 0 <= row < len(self._items):
            self._items.pop(row)
            self._list.takeItem(row)
            self._refresh_ui()

    def _clear_all(self):
        if not self._items:
            return
        if (
            QMessageBox.question(
                self,
                "Clear",
                "Remove all videos from the list?",
                QMessageBox.Yes | QMessageBox.No,
            )
            == QMessageBox.Yes
        ):
            self._items.clear()
            self._list.clear()
            self._refresh_ui()

    def _move_up(self):
        row = self._list.currentRow()
        if row > 0:
            self._items[row], self._items[row - 1] = (
                self._items[row - 1],
                self._items[row],
            )
            self._rebuild_list_widget(select=row - 1)

    def _move_down(self):
        row = self._list.currentRow()
        if 0 <= row < len(self._items) - 1:
            self._items[row], self._items[row + 1] = (
                self._items[row + 1],
                self._items[row],
            )
            self._rebuild_list_widget(select=row + 1)

    def _rebuild_list_widget(self, select: int = -1):
        self._list.blockSignals(True)
        self._list.clear()
        for item in self._items:
            lw = QListWidgetItem(item.display_text)
            lw.setForeground(QColor(item.prefix_colour))
            lw.setFont(QFont("Consolas", 10))
            self._list.addItem(lw)
        if 0 <= select < self._list.count():
            self._list.setCurrentRow(select)
        self._list.blockSignals(False)
        self._refresh_preview()

    # ------------------------------------------------------------------
    # Prefix assignment
    # ------------------------------------------------------------------

    def _assign_prefix(self, pfx: str):
        rows = [i for i in range(self._list.count()) if self._list.item(i).isSelected()]
        if not rows:
            row = self._list.currentRow()
            if row >= 0:
                rows = [row]
        if not rows:
            QMessageBox.information(self, "No selection", "Select a video first.")
            return
        for r in rows:
            if 0 <= r < len(self._items):
                self._items[r].prefix = pfx
        self._rebuild_list_widget(select=rows[-1])

    def _edit_prefix(self, lw_item: QListWidgetItem):
        row = self._list.row(lw_item)
        if 0 <= row < len(self._items):
            dlg = PrefixDialog(self._items[row].prefix, self)
            if dlg.exec_() == QDialog.Accepted:
                self._items[row].prefix = dlg.chosen
                self._rebuild_list_widget(select=row)

    # ------------------------------------------------------------------
    # Preview
    # ------------------------------------------------------------------

    def _refresh_preview(self):
        self._preview.clear()
        dest_dir = self._dest_combo.currentData()
        dest_name = os.path.basename(dest_dir)
        self._preview.addItem(QListWidgetItem(f"📁  Output → {dest_name}/"))
        self._preview.addItem(QListWidgetItem(""))

        for i, item in enumerate(self._items, 1):
            lw = QListWidgetItem(f"  {i:02d}.  {item.output_name}")
            lw.setForeground(QColor(item.prefix_colour))
            lw.setFont(QFont("Consolas", 10))

            # Annotate what will happen at runtime
            notes = []
            if item.prefix in ("A_", "B_", "C_", "D_"):
                notes.append(f"answer={item.prefix[0]}, pauses @ 5s/10s/20s")
            elif item.prefix == "F_":
                notes.append("pauses @ 5s and 20s only")
            elif item.prefix == ".Q_":
                notes.append("no pauses — plays straight through")
            else:
                notes.append("pauses @ 5s/10s/20s  (no correct answer)")
            if notes:
                note_item = QListWidgetItem(f"         ↳ {notes[0]}")
                note_item.setForeground(QColor("#484F58"))
                note_item.setFont(QFont("Segoe UI", 8))
                self._preview.addItem(lw)
                self._preview.addItem(note_item)
            else:
                self._preview.addItem(lw)

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def _build_show(self):
        if not self._items:
            QMessageBox.warning(self, "Empty", "Add videos to the list first.")
            return

        dest_dir = self._dest_combo.currentData()
        os.makedirs(dest_dir, exist_ok=True)

        overwrite = self._overwrite_check.isChecked()
        total = len(self._items)
        conflicts = []
        for item in self._items:
            dest_path = os.path.join(dest_dir, item.output_name)
            if os.path.exists(dest_path) and not overwrite:
                conflicts.append(item.output_name)

        if conflicts:
            msg = (
                f"{len(conflicts)} file(s) already exist:\n"
                + "\n".join(conflicts[:8])
                + (f"\n…and {len(conflicts) - 8} more" if len(conflicts) > 8 else "")
            )
            reply = QMessageBox.question(
                self,
                "Files exist",
                msg + "\n\nOverwrite all?",
                QMessageBox.Yes | QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                return

        self._progress.setVisible(True)
        self._progress.setMaximum(total)
        self._progress.setValue(0)
        self._btn_build.setEnabled(False)

        # Timestamps: first item = oldest (bottom in VS Code "newest first" sort)
        # This is the same "reverse mode" logic as sort22.py
        base_time = datetime.now()
        success, errors = 0, []

        for i, item in enumerate(self._items):
            dest_path = os.path.join(dest_dir, item.output_name)
            try:
                shutil.copy2(item.path, dest_path)
                # Oldest timestamp = first in list (VS Code reverse-sort friendly)
                # i=0 → oldest, i=N-1 → newest
                offset = total - 1 - i  # first item gets lowest index = oldest
                ts = (base_time + timedelta(seconds=offset * 2)).timestamp()
                os.utime(dest_path, (ts, ts))
                success += 1
            except Exception as exc:
                errors.append(f"{item.output_name}: {exc}")
            finally:
                self._progress.setValue(i + 1)
                QApplication.processEvents()

        self._progress.setVisible(False)
        self._btn_build.setEnabled(True)

        # Summary
        dest_name = os.path.basename(dest_dir)
        msg = f"✔  {success}/{total} files copied to {dest_name}/\n\n"
        msg += "Play order (top of VS Code file list = plays FIRST).\n"
        if errors:
            msg += f"\n⚠  {len(errors)} error(s):\n" + "\n".join(errors[:5])
        QMessageBox.information(self, "Build Complete", msg)

    # ------------------------------------------------------------------
    # Housekeeping
    # ------------------------------------------------------------------

    def _refresh_ui(self):
        has = len(self._items) > 0
        self._drop_hint.setVisible(not has)
        self._list.setVisible(has)
        self._btn_remove.setEnabled(has)
        self._btn_clear.setEnabled(has)
        self._btn_build.setEnabled(has)
        self._refresh_preview()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _is_video(path: str) -> bool:
    return os.path.splitext(path)[1].lower() in VIDEO_EXTS


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(DARK_STYLE)
    window = ShowBuilder()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()

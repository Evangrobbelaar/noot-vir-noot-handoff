import sys
import os
import shutil
from datetime import datetime, timedelta
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QFileDialog, QDateTimeEdit, QSpinBox, QGroupBox,
    QMessageBox, QProgressBar, QCheckBox
)
from PyQt5.QtCore import Qt, QDateTime
from PyQt5.QtGui import QDragEnterEvent, QDropEvent


class VideoMetadataSorter(QWidget):
    def __init__(self):
        super().__init__()
        self.video_files = []
        self.dest_folder = None
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("Video Playlist Metadata Sorter (VS Code Friendly)")
        self.setGeometry(300, 100, 720, 650)

        layout = QVBoxLayout()

        # === Drag & Drop Area (Banner) ===
        self.drop_area = QLabel("Drag & Drop Video Files Here\n(or click 'Add Files')")
        self.drop_area.setAlignment(Qt.AlignCenter)
        self.drop_area.setMinimumHeight(120)
        self.drop_area.setAcceptDrops(True)
        self.drop_area.setStyleSheet(self.get_default_style())
        self.drop_area.dragEnterEvent = self.label_drag_enter
        self.drop_area.dropEvent = self.label_drop

        # === File List ===
        self.file_list = QListWidget()
        self.file_list.setSelectionMode(QListWidget.MultiSelection)

        # === Buttons ===
        btn_layout = QHBoxLayout()
        self.add_btn = QPushButton("Add Files")
        self.remove_btn = QPushButton("Remove Selected")
        self.clear_btn = QPushButton("Clear All")
        btn_layout.addWidget(self.add_btn)
        btn_layout.addWidget(self.remove_btn)
        btn_layout.addWidget(self.clear_btn)

        # === Settings Group ===
        settings_group = QGroupBox("Timestamp Settings")
        settings_layout = QVBoxLayout()

        # Base Time
        time_layout = QHBoxLayout()
        time_layout.addWidget(QLabel("Start Date/Time:"))
        self.datetime_edit = QDateTimeEdit()
        self.datetime_edit.setCalendarPopup(True)
        self.datetime_edit.setDateTime(QDateTime.currentDateTime())
        time_layout.addWidget(self.datetime_edit)
        settings_layout.addLayout(time_layout)

        # Interval
        interval_layout = QHBoxLayout()
        interval_layout.addWidget(QLabel("Interval (seconds):"))
        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(1, 3600)
        self.interval_spin.setValue(2)
        interval_layout.addWidget(self.interval_spin)
        settings_layout.addLayout(interval_layout)

        # Reverse Order Toggle
        self.reverse_check = QCheckBox("Reverse order (first = oldest, last = newest)")
        self.reverse_check.setToolTip(
            "Enable for VS Code, Windows Explorer, etc.\n"
            "that sort 'Newest First' by default."
        )
        self.reverse_check.setChecked(True)  # Default: VS Code friendly
        settings_layout.addWidget(self.reverse_check)

        settings_group.setLayout(settings_layout)

        # === Destination Folder ===
        dest_layout = QHBoxLayout()
        dest_layout.addWidget(QLabel("Destination Folder:"))
        self.dest_label = QLabel("Not selected")
        self.dest_label.setStyleSheet("color: gray;")
        self.dest_btn = QPushButton("Choose Folder")
        dest_layout.addWidget(self.dest_label)
        dest_layout.addWidget(self.dest_btn)

        # === Progress Bar ===
        self.progress = QProgressBar()
        self.progress.setVisible(False)

        # === Apply Button ===
        self.apply_btn = QPushButton("Apply Metadata & Copy")
        self.apply_btn.setStyleSheet("font-weight: bold; padding: 10px; background-color: #4CAF50; color: white;")

        # === Connect Signals ===
        self.add_btn.clicked.connect(self.add_files)
        self.remove_btn.clicked.connect(self.remove_selected)
        self.clear_btn.clicked.connect(self.clear_list)
        self.dest_btn.clicked.connect(self.choose_destination)
        self.apply_btn.clicked.connect(self.apply_metadata)

        # === Assemble Layout ===
        layout.addWidget(self.drop_area)
        layout.addWidget(self.file_list)
        layout.addLayout(btn_layout)
        layout.addWidget(settings_group)
        layout.addLayout(dest_layout)
        layout.addWidget(self.progress)
        layout.addWidget(self.apply_btn)

        self.setLayout(layout)

    # === Styling ===
    def get_default_style(self):
        return """
            QLabel {
                border: 3px dashed #aaa;
                border-radius: 10px;
                padding: 20px;
                font-size: 16px;
                color: #555;
                background-color: #f9f9f9;
            }
        """

    def get_hover_style(self):
        return """
            QLabel {
                border: 3px dashed #4a90e2;
                border-radius: 10px;
                padding: 20px;
                font-size: 16px;
                color: #0056b3;
                background-color: #e8f4ff;
            }
        """

    # === Drag & Drop ===
    def label_drag_enter(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            correct_files = any(self.is_video_file(u.toLocalFile()) for u in event.mimeData().urls())
            if correct_files:
                self.drop_area.setStyleSheet(self.get_hover_style())
                event.acceptProposedAction()
            else:
                event.ignore()
        else:
            event.ignore()

    def label_drop(self, event: QDropEvent):
        self.drop_area.setStyleSheet(self.get_default_style())
        urls = event.mimeData().urls()
        valid_files = []
        invalid_files = []

        for url in urls:
            path = url.toLocalFile()
            if os.path.isfile(path):
                if self.is_video_file(path):
                    valid_files.append(path)
                else:
                    invalid_files.append(os.path.basename(path))
            else:
                invalid_files.append(os.path.basename(path))

        added = 0
        for file in valid_files:
            if file not in self.video_files:
                self.video_files.append(file)
                self.file_list.addItem(os.path.basename(file))
                added += 1

        if invalid_files:
            QMessageBox.warning(
                self, "Skipped Files",
                f"{len(invalid_files)} file(s) skipped (not video):\n" +
                "\n".join(invalid_files[:8]) +
                (f"\n... and {len(invalid_files)-8} more" if len(invalid_files) > 8 else "")
            )

        if added:
            QMessageBox.information(self, "Added", f"Added {added} video(s) to list.")

        event.acceptProposedAction()

    # === File Check ===
    def is_video_file(self, path):
        exts = {'.mp4', '.mov', '.avi', '.mkv', '.webm', '.flv', '.wmv', '.m4v', '.mpg', '.mpeg', '.3gp', '.m2ts'}
        return os.path.splitext(path)[1].lower() in exts

    # === File Management ===
    def add_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "Select Video Files",
            "", "Video Files (*.mp4 *.mov *.avi *.mkv *.webm *.flv *.wmv *.m4v *.mpg *.mpeg *.3gp *.m2ts);;All Files (*)"
        )
        if files:
            added = 0
            for file in files:
                if file not in self.video_files:
                    self.video_files.append(file)
                    self.file_list.addItem(os.path.basename(file))
                    added += 1
            if added:
                QMessageBox.information(self, "Added", f"Added {added} file(s).")

    def remove_selected(self):
        selected = self.file_list.selectedItems()
        if not selected:
            QMessageBox.warning(self, "No Selection", "Select files to remove.")
            return
        for item in selected:
            idx = self.file_list.row(item)
            self.video_files.pop(idx)
            self.file_list.takeItem(idx)

    def clear_list(self):
        if self.video_files:
            reply = QMessageBox.question(self, "Clear All", "Remove all files?",
                                         QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.Yes:
                self.video_files.clear()
                self.file_list.clear()

    def choose_destination(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Destination Folder")
        if folder:
            self.dest_folder = folder
            short_name = folder.split("/")[-1] if "/" in folder else folder.split("\\")[-1]
            self.dest_label.setText(short_name)
            self.dest_label.setToolTip(folder)
            self.dest_label.setStyleSheet("color: black;")

    # === MAIN: Apply Metadata (REVERSED by default) ===
    def apply_metadata(self):
        if not self.video_files:
            QMessageBox.warning(self, "No Files", "Add video files first.")
            return
        if not self.dest_folder:
            QMessageBox.warning(self, "No Folder", "Select destination folder.")
            return

        base_time = self.datetime_edit.dateTime().toPyDateTime()
        interval = self.interval_spin.value()
        total = len(self.video_files)
        reverse_mode = self.reverse_check.isChecked()

        self.progress.setVisible(True)
        self.progress.setMaximum(total)
        self.progress.setValue(0)

        success = 0
        for i, src_path in enumerate(self.video_files):
            try:
                filename = os.path.basename(src_path)
                dest_path = os.path.join(self.dest_folder, filename)
                shutil.copy2(src_path, dest_path)

                # Choose index: normal or reversed
                if reverse_mode:
                    # First in list = oldest
                    idx = total - 1 - i
                else:
                    # First in list = newest
                    idx = i

                new_time = base_time + timedelta(seconds=idx * interval)
                ts = new_time.timestamp()
                os.utime(dest_path, (ts, ts))
                success += 1
            except Exception as e:
                print(f"Error: {src_path} → {e}")
            finally:
                self.progress.setValue(i + 1)
                QApplication.processEvents()

        self.progress.setVisible(False)

        mode = "REVERSE (VS Code: Newest First)" if reverse_mode else "NORMAL (Oldest First)"
        QMessageBox.information(
            self, "Success!",
            f"Processed {success}/{total} files.\n\n"
            f"Mode: <b>{mode}</b>\n"
            f"• First in list → {'oldest (bottom)' if reverse_mode else 'newest (top)'}\n"
            f"• Last in list → {'newest (top)' if reverse_mode else 'oldest (bottom)'}\n\n"
            f"Files ready in:\n<b>{self.dest_folder}</b>"
        )


# === Run App ===
if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = VideoMetadataSorter()
    window.show()
    sys.exit(app.exec_())
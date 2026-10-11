"""PySide6 desktop interface."""
import logging
import os
import threading
from pathlib import Path
from PySide6.QtCore import QSettings, QThread, Signal, QTimer, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QApplication, QComboBox, QFileDialog, QFrame, QGridLayout, QHBoxLayout, QLabel,
    QLineEdit, QMainWindow, QPushButton, QSpinBox,
    QStackedWidget, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
    QHeaderView, QAbstractItemView,
)
from .database import Database
from .engine import Scanner
from .monitor import Monitor
from .reporting import export_scan
from .translations import TEXT, tr

LOG = logging.getLogger(__name__)

STYLE = """
* { font-family: 'DejaVu Sans', 'Segoe UI', sans-serif; }
QMainWindow, QWidget { background: #0A0E14; color: #E8EEF7; }
QLabel { background: transparent; }
QLabel#muted { color: #8190A5; }
QLabel#eyebrow { color: #00E5A0; font-size: 11px; font-weight: 700; letter-spacing: 2px; }
QLabel#hero { font-size: 26px; font-weight: 800; }
QFrame#sidebar { background: #101720; border-right: 1px solid #253140; }
QFrame#card, QFrame#panel { background: #121821; border: 1px solid #263342; border-radius: 14px; }
QPushButton { background: #1B2633; color: #E8EEF7; border: 1px solid #314253; border-radius: 8px; padding: 10px 15px; font-weight: 600; }
QPushButton:hover { background: #253649; border-color: #4D7CFE; }
QPushButton:disabled { color: #647182; background: #141C26; }
QPushButton#primary { background: #00E5A0; color: #06130F; border: none; }
QPushButton#primary:hover { background: #51F1BC; }
QPushButton#nav { text-align: left; border: none; background: transparent; padding: 12px 12px; font-size: 15px; }
QPushButton#nav:checked { background: #1C2F3B; color: #00E5A0; }
QLineEdit, QComboBox, QSpinBox { background: #0C121A; border: 1px solid #354352; border-radius: 8px; padding: 9px; color: #E8EEF7; }
QTableWidget { background: #121821; alternate-background-color: #15202B; border: none; gridline-color: #273544; selection-background-color: #274A58; }
QHeaderView::section { background: #17212C; color: #9BACBE; padding: 10px; border: none; font-weight: 700; }
QScrollBar:vertical { background: #121821; width: 10px; }
QScrollBar::handle:vertical { background: #354352; border-radius: 4px; }
"""


class ScanWorker(QThread):
    completed = Signal(object)
    failed = Signal(str)

    def __init__(self, scanner, directory):
        super().__init__()
        self.scanner = scanner
        self.directory = directory
        self.cancelled = threading.Event()

    def run(self):
        try:
            self.completed.emit(self.scanner.scan(self.directory, self.cancelled))
        except Exception as error:
            LOG.exception("Scan failed")
            self.failed.emit(str(error))


class Window(QMainWindow):
    scan_requested = Signal()

    def __init__(self, db_path, demo_directory=None, language=None):
        super().__init__()
        self.settings = QSettings("FileIntegrityMonitor", "FIM")
        self.language = language or self.settings.value("language", "en")
        if self.language not in TEXT:
            self.language = "en"
        self.db = Database(db_path)
        self.scanner = Scanner(self.db)
        self.monitor = None
        self.worker = None
        self.last_result = None
        self._status_key = "ready"
        self._note_key = "choose"
        self._note_kwargs = {}
        self.directory = str(Path(demo_directory).expanduser().resolve()) if demo_directory else self.settings.value("directory", "")
        self.display_directory = str(demo_directory) if demo_directory else self.directory
        latest = self.db.latest_scan(self.directory) if self.directory else None
        self._status_key = latest["status"] if latest else "ready"
        self._note_key = "live_note" if self.directory and self.db.history(self.directory) else "no_events" if self.directory else "choose"
        self.setMinimumSize(920, 650)
        self.resize(1250, 790)
        self.setWindowTitle("FIM Guard")
        self.setStyleSheet(STYLE)
        self.scan_requested.connect(self.scan)
        self._build()
        self.retranslate()
        self.refresh_events()
        self.load_latest_counts()

    def t(self, key, **kwargs):
        return tr(self.language, key, **kwargs)

    def _render_status(self):
        color, background = {
            "ready": ("#9BACBE", "#1B2633"),
            "scanning": ("#4D7CFE", "#18233B"),
            "paused": ("#FFB020", "#332514"),
            "partial": ("#FFB020", "#332514"),
            "interrupted": ("#FFB020", "#332514"),
        }.get(self._status_key, ("#00E5A0", "#132920"))
        self.status_label.setStyleSheet(
            f"color:{color};font-weight:700;padding:8px 15px;background:{background};border-radius:8px"
        )
        self.status_label.setText("●  " + self.t(self._status_key))

    def set_status(self, key):
        self._status_key = key
        self._render_status()
        self.statusBar().showMessage(self.t(key))

    def set_note(self, key, **kwargs):
        self._note_key = key
        self._note_kwargs = kwargs
        self.note.setText(self.t(key, **kwargs))
        self._update_note_visibility()

    def _label(self, name=None, text=""):
        label = QLabel(text)
        if name:
            label.setObjectName(name)
        return label

    def _update_note_visibility(self):
        self.note.setVisible(self._wide_controls is not False or self._note_key == "scan_errors")

    def _panel(self):
        frame = QFrame()
        frame.setObjectName("panel")
        return frame

    def _build(self):
        base = QWidget()
        outer = QHBoxLayout(base)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self.setCentralWidget(base)

        sidebar = QFrame()
        self.sidebar = sidebar
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(220)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(18, 30, 18, 24)
        logo = self._label("eyebrow", "◆  FIM / 01")
        side.addWidget(logo)
        side.addSpacing(38)
        self.nav = []
        for index in range(3):
            button = QPushButton()
            button.setObjectName("nav")
            button.setCheckable(True)
            button.clicked.connect(lambda checked=False, i=index: self.set_page(i))
            side.addWidget(button)
            self.nav.append(button)
        side.addStretch()
        side.addWidget(self._label("muted", "SHA-256  •  SQLITE"))
        outer.addWidget(sidebar)

        content = QWidget()
        main = QVBoxLayout(content)
        self.content_layout = main
        main.setContentsMargins(30, 26, 30, 24)
        main.setSpacing(18)
        header = QGridLayout()
        self.header = header
        title_widget = QWidget()
        self.title_widget = title_widget
        titles = QVBoxLayout(title_widget)
        titles.setContentsMargins(0, 0, 0, 0)
        self.tagline = self._label("eyebrow")
        self.title = self._label("hero")
        titles.addWidget(self.tagline)
        titles.addWidget(self.title)
        actions_widget = QWidget()
        self.actions_widget = actions_widget
        actions = QHBoxLayout(actions_widget)
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setSpacing(16)
        self.status_label = QLabel()
        actions.addWidget(self.status_label)
        self.language_combo = QComboBox()
        self.language_combo.addItem("English", "en")
        self.language_combo.addItem("O‘zbekcha", "uz")
        self.language_combo.addItem("Русский", "ru")
        self.language_combo.currentIndexChanged.connect(self.change_language)
        actions.addWidget(self.language_combo)
        self._wide_header = None
        self.arrange_header(True)
        main.addLayout(header)
        self.pages = QStackedWidget()
        main.addWidget(self.pages, 1)
        outer.addWidget(content, 1)
        self._dashboard()
        self._history()
        self._settings()
        self.statusBar().setStyleSheet("color:#9BACBE;background:#101720;padding:6px")
        self.set_page(0)

    def _dashboard(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(17)
        self.dashboard_layout = layout
        directory_panel = self._panel()
        p = QVBoxLayout(directory_panel)
        p.setContentsMargins(20, 17, 20, 18)
        self.dir_label = self._label("eyebrow")
        p.addWidget(self.dir_label)
        row = QHBoxLayout()
        self.path_input = QLineEdit(self.display_directory)
        self.path_input.setToolTip(self.directory)
        self.path_input.setReadOnly(True)
        row.addWidget(self.path_input, 1)
        self.browse_button = QPushButton()
        self.browse_button.clicked.connect(self.choose_directory)
        row.addWidget(self.browse_button)
        p.addLayout(row)
        layout.addWidget(directory_panel)

        controls = QGridLayout()
        controls.setHorizontalSpacing(12)
        controls.setVerticalSpacing(10)
        self.controls = controls
        self.baseline_button = QPushButton()
        self.baseline_button.clicked.connect(self.scan)
        self.scan_button = QPushButton()
        self.scan_button.setObjectName("primary")
        self.scan_button.clicked.connect(self.scan)
        self.start_button = QPushButton()
        self.start_button.clicked.connect(self.start_monitor)
        self.pause_button = QPushButton()
        self.pause_button.clicked.connect(self.toggle_pause)
        self.stop_button = QPushButton()
        self.stop_button.clicked.connect(self.stop_monitor)
        self.control_buttons = (self.baseline_button, self.scan_button, self.start_button, self.pause_button, self.stop_button)
        self._wide_controls = None
        self.arrange_controls(self.width() >= 1130)
        layout.addLayout(controls)

        cards = QHBoxLayout()
        self.card_values = {}
        self.card_titles = {}
        for key, color in (("added", "#00E5A0"), ("modified", "#FFB020"), ("deleted", "#FF4D6A"), ("errors", "#4D7CFE")):
            frame = QFrame()
            frame.setObjectName("card")
            box = QVBoxLayout(frame)
            box.setContentsMargins(20, 16, 20, 17)
            label = self._label("muted")
            value = QLabel("0")
            value.setStyleSheet(f"font-size:30px;font-weight:800;color:{color};")
            box.addWidget(label)
            box.addWidget(value)
            self.card_titles[key] = label
            self.card_values[key] = value
            cards.addWidget(frame)
        layout.addLayout(cards)

        event_panel = self._panel()
        ev = QVBoxLayout(event_panel)
        ev.setContentsMargins(18, 16, 18, 16)
        heading = QHBoxLayout()
        self.events_title = self._label("hero")
        self.events_title.setStyleSheet("font-size:19px;font-weight:700")
        heading.addWidget(self.events_title)
        heading.addStretch()
        self.export_button = QPushButton()
        self.export_button.clicked.connect(self.export)
        heading.addWidget(self.export_button)
        ev.addLayout(heading)
        self.event_table = self._table(3)
        ev.addWidget(self.event_table)
        layout.addWidget(event_panel, 1)
        self.note = self._label("muted")
        self.note.setWordWrap(True)
        layout.addWidget(self.note)
        self.pages.addWidget(page)

    def arrange_header(self, wide):
        if self._wide_header == wide:
            return
        self._wide_header = wide
        self.header.removeWidget(self.title_widget)
        self.header.removeWidget(self.actions_widget)
        self.header.addWidget(self.title_widget, 0, 0)
        if wide:
            self.header.addWidget(self.actions_widget, 0, 1)
        else:
            self.header.addWidget(self.actions_widget, 1, 0, alignment=Qt.AlignRight)
        self.header.setColumnStretch(0, 1)

    def arrange_controls(self, wide):
        if self._wide_controls == wide:
            return
        self._wide_controls = wide
        while self.controls.count():
            self.controls.takeAt(0)
        for index, button in enumerate(self.control_buttons):
            row, column = (0, index) if wide else divmod(index, 3)
            self.controls.addWidget(button, row, column)
        for column in range(5):
            self.controls.setColumnStretch(column, 1 if column < (5 if wide else 3) else 0)

    def resizeEvent(self, event):
        if hasattr(self, "controls"):
            wide = event.size().width() >= 1130
            self.arrange_controls(wide)
            self.arrange_header(wide)
            margins = (30, 26, 30, 24) if wide else (20, 16, 20, 14)
            self.content_layout.setContentsMargins(*margins)
            self.content_layout.setSpacing(18 if wide else 12)
            self.dashboard_layout.setSpacing(17 if wide else 10)
            self._update_note_visibility()
            self.sidebar.setFixedWidth(220 if wide else 200)
            self.title.setStyleSheet("font-size:26px;font-weight:800" if wide else "font-size:19px;font-weight:800")
            for button in self.nav:
                button.setStyleSheet("font-size:15px" if wide else "font-size:13px")
        super().resizeEvent(event)

    def _table(self, columns):
        table = QTableWidget(0, columns)
        table.setAlternatingRowColors(True)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.verticalHeader().hide()
        table.horizontalHeader().setSectionResizeMode(columns - 1, QHeaderView.Stretch)
        table.setColumnWidth(0, 245)
        table.setColumnWidth(1, 128)
        if columns == 4:
            table.setColumnWidth(2, 165)
        return table

    def _history(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        top = QHBoxLayout()
        self.history_title = self._label("hero")
        top.addWidget(self.history_title)
        top.addStretch()
        self.refresh_button = QPushButton()
        self.refresh_button.clicked.connect(self.refresh_events)
        top.addWidget(self.refresh_button)
        layout.addLayout(top)
        self.history_table = self._table(4)
        layout.addWidget(self.history_table)
        self.pages.addWidget(page)

    def _settings(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(15)
        self.settings_title = self._label("hero")
        self.settings_hint = self._label("muted")
        layout.addWidget(self.settings_title)
        layout.addWidget(self.settings_hint)
        panel = self._panel()
        box = QVBoxLayout(panel)
        box.setContentsMargins(22, 22, 22, 22)
        self.interval_label = self._label("eyebrow")
        box.addWidget(self.interval_label)
        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(5, 3600)
        self.interval_spin.setValue(int(self.settings.value("interval", 60)))
        self.interval_spin.valueChanged.connect(lambda value: self.settings.setValue("interval", value))
        box.addWidget(self.interval_spin)
        box.addSpacing(20)
        self.privacy_title = self._label("eyebrow")
        self.privacy_text = self._label("muted")
        self.privacy_text.setWordWrap(True)
        box.addWidget(self.privacy_title)
        box.addWidget(self.privacy_text)
        box.addSpacing(20)
        self.about_title = self._label("eyebrow")
        self.about_text = self._label("muted")
        box.addWidget(self.about_title)
        box.addWidget(self.about_text)
        layout.addWidget(panel)
        layout.addStretch()
        self.pages.addWidget(page)

    def set_page(self, index):
        self.pages.setCurrentIndex(index)
        for i, button in enumerate(self.nav):
            button.setChecked(i == index)
        if index == 1:
            self.refresh_events()

    def retranslate(self):
        self.tagline.setText(self.t("tagline"))
        self.title.setText(self.t("title"))
        self.setWindowTitle(self.t("title"))
        self._render_status()
        self.statusBar().showMessage(self.t(self._status_key))
        self.note.setText(self.t(self._note_key, **self._note_kwargs))
        self._update_note_visibility()
        for button, key in zip(self.nav, ("dashboard", "history", "settings")):
            button.setText(self.t(key))
        for widget, key in ((self.dir_label, "directory"), (self.browse_button, "browse"),
                            (self.baseline_button, "baseline"), (self.scan_button, "scan"),
                            (self.start_button, "start"), (self.stop_button, "stop"),
                            (self.events_title, "events"), (self.export_button, "export"),
                            (self.history_title, "all_events"), (self.refresh_button, "refresh"),
                            (self.settings_title, "settings_title"), (self.settings_hint, "settings_hint"),
                            (self.interval_label, "interval"), (self.privacy_title, "privacy"),
                            (self.privacy_text, "privacy_text"), (self.about_title, "about"),
                            (self.about_text, "about_text")):
            widget.setText(self.t(key))
        self.pause_button.setText(self.t("resume" if self.monitor and self.monitor.paused.is_set() else "pause"))
        for key, widget in self.card_titles.items():
            widget.setText(self.t(key).upper())
        self.event_table.setHorizontalHeaderLabels([self.t("time"), self.t("type"), self.t("path")])
        self.history_table.setHorizontalHeaderLabels([self.t("time"), self.t("type"), self.t("root"), self.t("path")])
        self.language_combo.blockSignals(True)
        self.language_combo.setCurrentIndex(self.language_combo.findData(self.language))
        self.language_combo.blockSignals(False)
        self.update_controls()
        self.refresh_events()

    def change_language(self):
        language = self.language_combo.currentData()
        if language and language != self.language:
            self.language = language
            self.settings.setValue("language", language)
            self.retranslate()

    def choose_directory(self):
        path = QFileDialog.getExistingDirectory(self, self.t("folder_title"), self.directory or str(Path.home()))
        if path:
            self.select_directory(path)

    def select_directory(self, path):
        if Path(path).expanduser().is_symlink():
            self.statusBar().showMessage(self.t("invalid"))
            return
        try:
            path = str(Path(path).expanduser().resolve(strict=True))
        except (OSError, RuntimeError):
            self.statusBar().showMessage(self.t("invalid"))
            return
        if not Path(path).is_dir() or not os.access(path, os.R_OK | os.X_OK):
            self.set_status("ready")
            self.statusBar().showMessage(self.t("invalid"))
            return
        self.stop_monitor()
        self.directory = path
        self.display_directory = path
        self.path_input.setText(path)
        self.path_input.setToolTip(path)
        self.settings.setValue("directory", path)
        self.last_result = None
        for value in self.card_values.values():
            value.setText("0")
        self.load_latest_counts()
        latest = self.db.latest_scan(path)
        self.set_status(latest["status"] if latest else "ready")
        self.set_note("live_note" if self.db.history(path) else "no_events")
        self.refresh_events()
        self.update_controls()

    def update_controls(self):
        available = bool(self.directory)
        busy = self.worker is not None and self.worker.isRunning()
        self.browse_button.setEnabled(not busy)
        self.scan_button.setEnabled(available and not busy)
        self.baseline_button.setEnabled(available and not busy and not self.db.has_root(self.directory))
        self.start_button.setEnabled(available and self.monitor is None)
        self.pause_button.setEnabled(self.monitor is not None)
        self.stop_button.setEnabled(self.monitor is not None)
        if self.monitor:
            self.pause_button.setText(self.t("resume" if self.monitor.paused.is_set() else "pause"))
        self.export_button.setEnabled(bool(self.db.latest_scan(self.directory) if available else None))

    def scan(self):
        if not self.directory:
            self.statusBar().showMessage(self.t("select_first"))
            return
        if self.worker and self.worker.isRunning():
            return
        self.set_status("scanning")
        self.worker = ScanWorker(self.scanner, self.directory)
        self.worker.completed.connect(self.scan_finished)
        self.worker.failed.connect(self.scan_failed)
        self.worker.finished.connect(self.update_controls)
        self.worker.start()
        self.update_controls()

    def scan_finished(self, result):
        self.last_result = result
        counts = result.counts()
        for key in ("added", "modified", "deleted"):
            self.card_values[key].setText(str(counts[key]))
        self.card_values["errors"].setText(str(len(result.errors)))
        status = "baseline_done" if result.initial and result.status == "complete" else result.status
        self.set_status(status if result.status != "complete" else "paused" if self.monitor and self.monitor.paused.is_set() else "watching" if self.monitor else status)
        self.statusBar().showMessage(self.t(status))
        if result.errors:
            self.set_note("scan_errors", count=len(result.errors))
        elif result.initial:
            self.set_note("initial_note")
        else:
            self.set_note("live_note")
        self.refresh_events()
        self.update_controls()

    def scan_failed(self, detail):
        self.set_status("partial")
        self.statusBar().showMessage(self.t("scan_failed", detail=detail))
        self.update_controls()

    def start_monitor(self):
        if not self.directory:
            self.statusBar().showMessage(self.t("select_first"))
            return
        try:
            if not self.db.has_root(self.directory):
                self.scan()
            self.monitor = Monitor(self.directory, self.scan_requested.emit, self.interval_spin.value())
            self.monitor.start()
            self.set_status("watching")
            self.set_note("live_note")
        except Exception as error:
            if self.monitor:
                self.monitor.stop()
            self.monitor = None
            self.set_status("ready")
            self.statusBar().showMessage(self.t("monitor_failed", detail=str(error)))
        self.update_controls()

    def toggle_pause(self):
        if not self.monitor:
            return
        if self.monitor.paused.is_set():
            self.monitor.resume()
            self.set_status("watching")
        else:
            self.monitor.pause()
            self.set_status("paused")
        self.update_controls()

    def stop_monitor(self):
        if self.monitor:
            self.monitor.stop()
            self.monitor = None
            latest = self.db.latest_scan(self.directory) if self.directory else None
            self.set_status(latest["status"] if latest else "ready")
        self.update_controls()

    def load_latest_counts(self):
        if not self.directory:
            return
        with self.db.connect() as connection:
            row = connection.execute(
                "SELECT added,modified,deleted,errors FROM scans WHERE root=? ORDER BY id DESC LIMIT 1",
                (self.directory,),
            ).fetchone()
        if row:
            for key in ("added", "modified", "deleted", "errors"):
                self.card_values[key].setText(str(row[key]))

    def refresh_events(self):
        if not hasattr(self, "event_table"):
            return
        rows = self.db.history(self.directory) if self.directory else []
        all_rows = self.db.history()
        for table, subset in ((self.event_table, rows[:100]), (self.history_table, all_rows)):
            table.setRowCount(len(subset))
            for index, row in enumerate(subset):
                fields = ([row["timestamp"], self.t(row["kind"]), row["path"]]
                          if table is self.event_table else
                          [row["timestamp"], self.t(row["kind"]), Path(row["root"]).name, row["path"]])
                for column, value in enumerate(fields):
                    item = QTableWidgetItem(value)
                    if table is self.history_table and column == 2:
                        item.setToolTip(row["root"])
                    if column == 1:
                        item.setForeground(QColor({"added": "#00E5A0", "modified": "#FFB020", "deleted": "#FF4D6A"}[row["kind"]]))
                    table.setItem(index, column, item)
        if not rows and not self.last_result and self._note_key in ("choose", "no_events"):
            self.set_note("choose" if not self.directory else "no_events")
        self.update_controls()

    def export(self):
        scan = self.db.latest_scan(self.directory) if self.directory else None
        filename, _ = QFileDialog.getSaveFileName(self, self.t("report_title"), "fim-report.json", self.t("report_filter"))
        if filename:
            try:
                path = export_scan(scan, self.db.scan_events(scan["id"]), filename)
                self.statusBar().showMessage(self.t("exported", path=str(path)))
            except Exception as error:
                self.statusBar().showMessage(self.t("export_failed", detail=str(error)))

    def closeEvent(self, event):
        self.stop_monitor()
        if self.worker and self.worker.isRunning():
            self.worker.cancelled.set()
            if not self.worker.wait(5000):
                event.ignore()
                return
        super().closeEvent(event)


def run(db_path, demo_directory=None, language=None, page=0, screenshot=None):
    app = QApplication.instance() or QApplication([])
    app.setStyle("Fusion")
    window = Window(db_path, demo_directory, language)
    window.set_page(page)
    window.show()
    if screenshot:
        def capture():
            window.grab().save(str(screenshot))
            app.quit()
        QTimer.singleShot(900, capture)
    return app.exec()

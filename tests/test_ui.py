import json
import os
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication
from fim.ui import Window


def test_language_persists(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    QSettings.setDefaultFormat(QSettings.IniFormat)
    QSettings.setPath(QSettings.IniFormat, QSettings.UserScope, str(tmp_path / "config"))
    app = QApplication.instance() or QApplication([])
    window = Window(tmp_path / "db.sqlite", language="en")
    window.language_combo.setCurrentIndex(window.language_combo.findData("uz"))
    assert window.title.text() == "FAYL YAXLITLIGI MONITORI"
    assert window.settings.value("language") == "uz"
    window.set_status("watching")
    window.set_note("live_note")
    window.language_combo.setCurrentIndex(window.language_combo.findData("ru"))
    assert window.status_label.text().endswith("Мониторинг включён")
    assert window.note.text().startswith("Изменения проверяются")
    window.language_combo.setCurrentIndex(window.language_combo.findData("uz"))
    window.close()
    reopened = Window(tmp_path / "db.sqlite")
    assert reopened.language == "uz"
    reopened.close()
    assert app is not None


def test_live_monitor_updates_real_window(tmp_path, monkeypatch):
    import time

    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    QSettings.setDefaultFormat(QSettings.IniFormat)
    QSettings.setPath(QSettings.IniFormat, QSettings.UserScope, str(tmp_path / "config"))
    app = QApplication.instance() or QApplication([])
    root = tmp_path / "monitored"
    root.mkdir()
    (root / "record.txt").write_text("initial")
    window = Window(tmp_path / "db.sqlite", root, "en")
    window.show()

    def until(predicate, seconds=10):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            app.processEvents()
            if predicate():
                return True
            time.sleep(0.02)
        return False

    window.baseline_button.click()
    assert until(lambda: window.db.has_root(str(root)) and not window.worker.isRunning())
    window.start_button.click()
    assert window.monitor is not None
    (root / "record.txt").write_text("changed")
    assert until(lambda: window.event_table.rowCount() == 1)
    assert window.event_table.item(0, 1).text() == "Modified"
    window.pause_button.click()
    assert window.monitor.paused.is_set()
    window.language_combo.setCurrentIndex(window.language_combo.findData("uz"))
    assert window.status_label.text().endswith("Kuzatuv to‘xtatildi")
    (root / "second.txt").write_text("added while paused")
    time.sleep(0.8)
    app.processEvents()
    assert window.event_table.rowCount() == 1
    window.pause_button.click()
    assert until(lambda: window.event_table.rowCount() == 2)
    assert window.card_values["added"].text() == "1"
    window.close()
    assert app is not None


def test_switch_directory_resets_counts_and_rejects_missing(tmp_path, monkeypatch):
    from fim.database import Database
    from fim.engine import Scanner

    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    QSettings.setDefaultFormat(QSettings.IniFormat)
    QSettings.setPath(QSettings.IniFormat, QSettings.UserScope, str(tmp_path / "config"))
    app = QApplication.instance() or QApplication([])
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    db_path = tmp_path / "db.sqlite"
    scanner = Scanner(Database(db_path))
    scanner.scan(first)
    (first / "new.txt").write_text("new")
    scanner.scan(first)
    scanner.scan(second)
    window = Window(db_path, first, "en")
    assert window.card_values["added"].text() == "1"
    assert window.note.text() == window.t("live_note")
    report = tmp_path / "gui-export.json"
    with patch("fim.ui.QFileDialog.getSaveFileName", return_value=(str(report), "")):
        window.export_button.click()
    assert json.loads(report.read_text(encoding="utf-8"))["scan"]["added"] == 1
    window.select_directory(second)
    assert window.card_values["added"].text() == "0"
    assert window.event_table.rowCount() == 0
    assert window.history_table.rowCount() == 1
    assert window.note.text() == window.t("no_events")
    window.select_directory(tmp_path / "missing")
    assert window.directory == str(second)
    assert window.statusBar().currentMessage() == window.t("invalid")
    window.close()
    assert app is not None


def test_narrow_layout_preserves_status_and_errors(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    QSettings.setDefaultFormat(QSettings.IniFormat)
    QSettings.setPath(QSettings.IniFormat, QSettings.UserScope, str(tmp_path / "config"))
    app = QApplication.instance() or QApplication([])
    window = Window(tmp_path / "db.sqlite", language="ru")
    window.show()
    window.resize(920, 650)
    app.processEvents()
    assert window._wide_header is False
    assert window.header.itemAtPosition(1, 0).widget() is window.actions_widget
    assert not window.note.isVisible()
    window.set_note("scan_errors", count=1)
    window.set_status("partial")
    assert "#FFB020" in window.status_label.styleSheet()
    assert window.note.isVisible()
    window.resize(1250, 790)
    app.processEvents()
    assert window._wide_header is True
    assert window.header.itemAtPosition(0, 1).widget() is window.actions_widget
    window.close()

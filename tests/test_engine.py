import hashlib
import json
import os
import threading
import time
from string import Formatter
from unittest.mock import patch

import pytest

from fim.database import Database
from fim.engine import Scanner, sha256_file
from fim.monitor import Monitor
from fim.reporting import export_events
from fim.translations import TEXT, tr


@pytest.fixture
def setup(tmp_path):
    root = tmp_path / "watched"
    root.mkdir()
    db = Database(tmp_path / "state.sqlite")
    return root, db, Scanner(db)


def test_sha256(tmp_path):
    file = tmp_path / "hello.txt"
    file.write_bytes(b"hello")
    assert sha256_file(file) == hashlib.sha256(b"hello").hexdigest()


def test_baseline_and_changes(setup):
    root, db, scanner = setup
    (root / "alpha.txt").write_text("one")
    first = scanner.scan(root)
    assert first.initial and first.status == "complete" and not first.events
    assert db.baseline(str(root.resolve()))["alpha.txt"][0] == sha256_file(root / "alpha.txt")
    (root / "alpha.txt").write_text("two")
    (root / "βeta.txt").write_text("unicode")
    second = scanner.scan(root)
    assert {(e.path, e.kind) for e in second.events} == {
        ("alpha.txt", "modified"), ("βeta.txt", "added")
    }
    (root / "alpha.txt").unlink()
    third = scanner.scan(root)
    assert [(e.path, e.kind) for e in third.events] == [("alpha.txt", "deleted")]
    assert not scanner.scan(root).events  # No duplicate alert after advancing baseline.
    assert len(db.history(str(root.resolve()))) == 3
    assert len(Database(db.path).history(str(root.resolve()))) == 3


def test_symlinks_are_skipped(setup, tmp_path):
    root, db, scanner = setup
    outside = tmp_path / "private.txt"
    outside.write_text("outside")
    try:
        (root / "alias.txt").symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip("Symlink creation is unavailable on this runner")
    other = tmp_path / "other"
    other.mkdir()
    (other / "secret.txt").write_text("secret")
    try:
        (root / "linked-folder").symlink_to(other, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("Directory symlink creation is unavailable on this runner")
    assert scanner.scan(root).status == "complete"
    assert db.baseline(str(root.resolve())) == {}


def test_permission_error_preserves_baseline(setup):
    root, db, scanner = setup
    file = root / "important.txt"
    file.write_text("original")
    scanner.scan(root)
    original = sha256_file(file)

    def denied(path, cancelled=None):
        raise PermissionError("denied")

    with patch("fim.engine.sha256_file", side_effect=denied):
        result = scanner.scan(root)
    assert result.status == "partial" and result.errors and not result.events
    assert db.baseline(str(root.resolve()))["important.txt"][0] == original


def test_interruption_does_not_advance_baseline(setup):
    root, db, scanner = setup
    (root / "one.txt").write_text("one")
    scanner.scan(root)
    (root / "two.txt").write_text("two")
    cancelled = threading.Event()
    cancelled.set()
    result = scanner.scan(root, cancelled)
    assert result.status == "interrupted" and not result.events
    assert "two.txt" not in db.baseline(str(root.resolve()))
    assert scanner.scan(root).events[0].kind == "added"


def test_invalid_directory(setup, tmp_path):
    _, _, scanner = setup
    with pytest.raises((ValueError, FileNotFoundError)):
        scanner.scan(tmp_path / "missing")
    file = tmp_path / "file"
    file.write_text("x")
    with pytest.raises(ValueError):
        scanner.scan(file)


def test_exports(setup, tmp_path):
    root, db, scanner = setup
    scanner.scan(root)
    (root / "файл.txt").write_text("data")
    scanner.scan(root)
    rows = db.history(str(root.resolve()))
    json_path = export_events(rows, tmp_path / "report.json")
    csv_path = export_events(rows, tmp_path / "report.csv")
    assert json.loads(json_path.read_text(encoding="utf-8"))[0]["path"] == "файл.txt"
    assert "файл.txt" in csv_path.read_text(encoding="utf-8-sig")
    assert "data" not in json_path.read_text(encoding="utf-8")
    with pytest.raises(ValueError):
        export_events(rows, tmp_path / "report.txt")


def test_translation_completeness():
    keys = set(TEXT["en"])
    assert all(set(TEXT[language]) == keys for language in ("uz", "ru"))
    assert all(all(value.strip() for value in TEXT[language].values()) for language in TEXT)
    assert tr("uz", "added") == "Qo‘shilgan"
    def placeholders(value):
        return {field for _, field, _, _ in Formatter().parse(value) if field}

    for key in keys:
        assert placeholders(TEXT["en"][key]) == placeholders(TEXT["uz"][key]) == placeholders(TEXT["ru"][key])


def test_monitor_restart_and_pause(setup):
    root, _, scanner = setup
    scanner.scan(root)
    hits = []
    monitor = Monitor(str(root), lambda: hits.append(time.monotonic()), interval=5)
    monitor.start()
    monitor.pause()
    monitor.resume()
    (root / "new.txt").write_text("new")
    deadline = time.monotonic() + 10
    while not hits and time.monotonic() < deadline:
        time.sleep(0.05)
    monitor.stop()
    assert hits
    monitor.start()
    monitor.resume()
    deadline = time.monotonic() + 10
    while len(hits) < 2 and time.monotonic() < deadline:
        time.sleep(0.05)
    monitor.stop()
    assert len(hits) >= 2


def test_special_file_is_skipped(setup):
    if not hasattr(os, "mkfifo"):
        pytest.skip("FIFO unavailable on this platform")
    root, db, scanner = setup
    os.mkfifo(root / "pipe")
    assert scanner.scan(root).status == "complete"
    assert db.baseline(str(root.resolve())) == {}


def test_scan_report_contains_summary(setup, tmp_path):
    from fim.reporting import export_scan

    root, db, scanner = setup
    scanner.scan(root)
    (root / "added.txt").write_text("contents")
    result = scanner.scan(root)
    scan = db.latest_scan(str(root.resolve()))
    events = db.scan_events(result.scan_id)
    json_path = export_scan(scan, events, tmp_path / "scan.json")
    csv_path = export_scan(scan, events, tmp_path / "scan.csv")
    data = json.loads(json_path.read_text(encoding="utf-8"))
    assert data["scan"]["added"] == 1
    assert data["events"][0]["path"] == "added.txt"
    assert "added_count" in csv_path.read_text(encoding="utf-8-sig")
    assert "contents" not in json_path.read_text(encoding="utf-8")
    assert "contents" not in csv_path.read_text(encoding="utf-8-sig")


def test_partial_scan_emits_no_alert_then_recovers(setup):
    root, db, scanner = setup
    original = root / "one.txt"
    original.write_text("one")
    scanner.scan(root)
    (root / "two.txt").write_text("two")
    with patch("fim.engine.sha256_file", side_effect=PermissionError("denied")):
        partial = scanner.scan(root)
    assert partial.status == "partial" and not partial.events
    assert "two.txt" not in db.baseline(str(root.resolve()))
    recovered = scanner.scan(root)
    assert [(event.path, event.kind) for event in recovered.events] == [("two.txt", "added")]


def test_csv_formula_escape_and_empty_summary(setup, tmp_path):
    import csv
    from fim.reporting import export_scan

    root, db, scanner = setup
    initial = scanner.scan(root)
    empty = export_scan(db.latest_scan(str(root.resolve())), db.scan_events(initial.scan_id), tmp_path / "empty.csv")
    with empty.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 1 and rows[0]["status"] == "complete" and rows[0]["path"] == ""
    (root / "=2+2.txt").write_text("synthetic")
    result = scanner.scan(root)
    report = export_scan(db.latest_scan(str(root.resolve())), db.scan_events(result.scan_id), tmp_path / "safe.csv")
    with report.open(encoding="utf-8-sig", newline="") as stream:
        path = next(csv.DictReader(stream))["path"]
    assert path.startswith("'=2+2.txt")


def test_database_files_inside_selected_root_are_excluded(tmp_path):
    root = tmp_path / "selected"
    root.mkdir()
    db = Database(root / "fim.sqlite")
    scanner = Scanner(db)
    (root / "user.txt").write_text("user content")
    assert scanner.scan(root).status == "complete"
    assert list(db.baseline(str(root.resolve()))) == ["user.txt"]
    assert scanner.scan(root).events == []


def test_selected_symlink_root_is_rejected(tmp_path):
    actual = tmp_path / "actual"
    actual.mkdir()
    alias = tmp_path / "alias"
    try:
        alias.symlink_to(actual, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("Symlink creation is unavailable on this runner")
    scanner = Scanner(Database(tmp_path / "db.sqlite"))
    with pytest.raises(ValueError):
        scanner.scan(alias)


def test_inaccessible_subtree_does_not_create_false_deletions(setup):
    root, db, scanner = setup
    child = root / "restricted"
    child.mkdir()
    (child / "kept.txt").write_text("original")
    scanner.scan(root)

    def failed_walk(path, followlinks, onerror):
        onerror(PermissionError(13, "Permission denied", str(child)))
        yield str(root), [], []

    with patch("fim.engine.os.walk", side_effect=failed_walk):
        result = scanner.scan(root)
    assert result.status == "partial" and not result.events
    assert "restricted/kept.txt" in db.baseline(str(root.resolve()))
    assert not scanner.scan(root).events


def test_scan_does_not_change_source_file(setup):
    root, _, scanner = setup
    file = root / "read-only-data.txt"
    file.write_bytes(b"never changed by the scanner")
    before = (file.read_bytes(), file.stat().st_mtime_ns)
    scanner.scan(root)
    scanner.scan(root)
    assert (file.read_bytes(), file.stat().st_mtime_ns) == before


def test_file_changed_during_hash_keeps_previous_baseline(setup):
    root, db, scanner = setup
    file = root / "active.txt"
    file.write_text("original")
    scanner.scan(root)
    original_digest = db.baseline(str(root.resolve()))["active.txt"][0]
    real_hash = sha256_file

    def mutate_after_hash(path, cancelled=None):
        digest = real_hash(path, cancelled)
        file.write_text("a different length")
        return digest

    with patch("fim.engine.sha256_file", side_effect=mutate_after_hash):
        result = scanner.scan(root)
    assert result.status == "partial" and not result.events
    assert db.baseline(str(root.resolve()))["active.txt"][0] == original_digest
    assert scanner.scan(root).events[0].kind == "modified"


def test_overlapping_scans_are_rejected(setup):
    root, db, scanner = setup
    file = root / "record.txt"
    file.write_text("old")
    scanner.scan(root)
    file.write_text("new")
    entered = threading.Event()
    release = threading.Event()
    real_hash = sha256_file
    results = []

    def slow_hash(path, cancelled=None):
        entered.set()
        assert release.wait(timeout=5)
        return real_hash(path, cancelled)

    def first_scan():
        results.append(scanner.scan(root))

    with patch("fim.engine.sha256_file", side_effect=slow_hash):
        worker = threading.Thread(target=first_scan)
        worker.start()
        assert entered.wait(timeout=5)
        with pytest.raises(RuntimeError, match="already running"):
            scanner.scan(root)
        release.set()
        worker.join(timeout=5)
    assert not worker.is_alive()
    assert len(results) == 1 and results[0].events[0].kind == "modified"
    assert len(db.history(str(root.resolve()))) == 1

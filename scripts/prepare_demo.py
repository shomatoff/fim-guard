"""Create disposable synthetic files and genuine watchdog events for screenshots."""
import threading
import time
from pathlib import Path
from fim.database import Database
from fim.engine import Scanner
from fim.monitor import Monitor


def main():
    base = Path("demo-data").resolve()
    root = base / "monitored"
    (root / "config").mkdir(parents=True, exist_ok=True)
    (root / "logs").mkdir(exist_ok=True)
    (root / "reports").mkdir(exist_ok=True)
    (root / "config" / "policy.yaml").write_text("version: 1\nmode: enforce\n")
    (root / "logs" / "audit.log").write_text("Synthetic audit record\n")
    (root / "identity.txt").write_text("Synthetic demo identity\n")
    old_report = root / "reports" / "summary.txt"
    if old_report.exists():
        old_report.unlink()
    db_path = base / "demo.sqlite"
    if db_path.exists():
        db_path.unlink()
    db = Database(db_path)
    scanner = Scanner(db)
    scanner.scan(root)
    done = threading.Event()

    def scan():
        result = scanner.scan(root)
        if result.events:
            done.set()

    monitor = Monitor(str(root), scan, interval=5)
    monitor.start()
    time.sleep(0.2)
    (root / "config" / "policy.yaml").write_text("version: 2\nmode: enforce\n")
    (root / "logs" / "audit.log").unlink()
    old_report.write_text("Synthetic demonstration data only.\n")
    if not done.wait(timeout=8):
        monitor.stop()
        raise RuntimeError("watchdog did not report the synthetic changes")
    monitor.stop()
    print(f"Genuine watchdog scan recorded {len(db.history(str(root)))} events")


if __name__ == "__main__":
    main()

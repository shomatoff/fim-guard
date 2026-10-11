"""Read-only integrity scanner. Baseline advances only after complete scans."""

import hashlib
import os
import stat
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256_file(path, cancelled=None):
    digest = hashlib.sha256()
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0)
    fd = os.open(path, flags)
    with os.fdopen(fd, "rb") as source:
        while chunk := source.read(1024 * 1024):
            if cancelled is not None and cancelled.is_set():
                raise InterruptedError("scan cancelled")
            digest.update(chunk)
    return digest.hexdigest()


@dataclass(frozen=True)
class Event:
    path: str
    kind: str
    timestamp: str
    old_hash: str | None = None
    new_hash: str | None = None


@dataclass
class Result:
    root: str
    status: str
    events: list[Event]
    errors: list[str]
    scan_id: int
    initial: bool

    def counts(self):
        return {kind: sum(e.kind == kind for e in self.events) for kind in ("added", "modified", "deleted")}


class Scanner:
    def __init__(self, database):
        self.database = database
        self._lock = threading.Lock()

    def scan(self, directory, cancelled=None):
        selected = Path(directory).expanduser()
        if selected.is_symlink():
            raise ValueError(f"Symlink directory is not monitored: {directory}")
        root_path = selected.resolve(strict=True)
        if not root_path.is_dir() or not os.access(root_path, os.R_OK | os.X_OK):
            raise ValueError(f"Invalid or inaccessible directory: {directory}")
        root = str(root_path)
        if not self._lock.acquire(blocking=False):
            raise RuntimeError("A scan is already running")
        try:
            return self._scan(root_path, root, cancelled)
        finally:
            self._lock.release()

    def _scan(self, root_path, root, cancelled):
        started = now()
        database_path = self.database.path.resolve()
        internal_files = {os.path.normcase(str(database_path) + suffix) for suffix in ("", "-wal", "-shm", "-journal")}
        initial = not self.database.has_root(root)
        previous = self.database.baseline(root)
        current = {}
        errors = []
        protected = set()
        interrupted = False

        def walk_error(error):
            errors.append(f"{error.filename}: {error.strerror}")
            protected.add(str(error.filename))

        try:
            for folder, dirs, files in os.walk(root_path, followlinks=False, onerror=walk_error):
                if cancelled is not None and cancelled.is_set():
                    raise InterruptedError
                dirs[:] = [d for d in dirs if not (Path(folder) / d).is_symlink()]
                for name in files:
                    path = Path(folder) / name
                    if path.is_symlink() or os.path.normcase(str(path)) in internal_files:
                        continue
                    relative = path.relative_to(root_path).as_posix()
                    try:
                        before = path.lstat()
                        if not stat.S_ISREG(before.st_mode):
                            continue
                        digest = sha256_file(path, cancelled)
                        after = path.lstat()
                        if not stat.S_ISREG(after.st_mode) or (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns):
                            raise OSError("File changed during hashing")
                        current[relative] = (digest, after.st_size)
                    except InterruptedError:
                        raise
                    except OSError as error:
                        errors.append(f"{path}: {error}")
                        protected.add(str(path))
        except InterruptedError:
            interrupted = True
        events = []
        if not initial and not interrupted:
            timestamp = now()
            for path, (digest, _) in current.items():
                old = previous.get(path)
                if old is None:
                    events.append(Event(path, "added", timestamp, new_hash=digest))
                elif old[0] != digest:
                    events.append(Event(path, "modified", timestamp, old[0], digest))
            for path, (digest, _) in previous.items():
                if path not in current and not any(
                    str(root_path / path) == p or str(root_path / path).startswith(p + os.sep)
                    for p in protected
                ):
                    events.append(Event(path, "deleted", timestamp, old_hash=digest))
        status = "interrupted" if interrupted else "partial" if errors else "complete"
        if status != "complete":
            events = []  # An incomplete snapshot cannot support reliable alerts.
        scan_id = self.database.save_scan(root, started, now(), status, current, events, errors, initial and status == "complete")
        return Result(root, status, sorted(events, key=lambda e: (e.path, e.kind)), errors, scan_id, initial)

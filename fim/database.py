"""SQLite persistence for baselines, scans and events."""

import sqlite3
from contextlib import contextmanager
from pathlib import Path


class Database:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS roots (
                    path TEXT PRIMARY KEY, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS files (
                    root TEXT NOT NULL, path TEXT NOT NULL, sha256 TEXT NOT NULL,
                    size INTEGER NOT NULL, PRIMARY KEY(root, path),
                    FOREIGN KEY(root) REFERENCES roots(path) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS scans (
                    id INTEGER PRIMARY KEY, root TEXT NOT NULL, started_at TEXT NOT NULL,
                    finished_at TEXT NOT NULL, status TEXT NOT NULL,
                    added INTEGER NOT NULL, modified INTEGER NOT NULL,
                    deleted INTEGER NOT NULL, errors INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY, scan_id INTEGER NOT NULL,
                    root TEXT NOT NULL, path TEXT NOT NULL, kind TEXT NOT NULL,
                    timestamp TEXT NOT NULL, old_hash TEXT, new_hash TEXT,
                    FOREIGN KEY(scan_id) REFERENCES scans(id)
                );
                CREATE INDEX IF NOT EXISTS idx_events_root ON events(root, id DESC);
            """)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=30)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def has_root(self, root):
        with self.connect() as db:
            return db.execute("SELECT 1 FROM roots WHERE path=?", (root,)).fetchone() is not None

    def baseline(self, root):
        with self.connect() as db:
            rows = db.execute("SELECT path,sha256,size FROM files WHERE root=?", (root,))
            return {row["path"]: (row["sha256"], row["size"]) for row in rows}

    def save_scan(self, root, started, finished, status, current, events, errors, initial):
        counts = {kind: sum(e.kind == kind for e in events) for kind in ("added", "modified", "deleted")}
        with self.connect() as db:
            if initial:
                db.execute("INSERT INTO roots(path,created_at) VALUES(?,?)", (root, finished))
            cur = db.execute(
                "INSERT INTO scans(root,started_at,finished_at,status,added,modified,deleted,errors) "
                "VALUES(?,?,?,?,?,?,?,?)",
                (root, started, finished, status, counts["added"], counts["modified"], counts["deleted"], len(errors)),
            )
            scan_id = cur.lastrowid
            db.executemany(
                "INSERT INTO events(scan_id,root,path,kind,timestamp,old_hash,new_hash) VALUES(?,?,?,?,?,?,?)",
                [(scan_id, root, e.path, e.kind, e.timestamp, e.old_hash, e.new_hash) for e in events],
            )
            if status == "complete":
                db.execute("DELETE FROM files WHERE root=?", (root,))
                db.executemany(
                    "INSERT INTO files(root,path,sha256,size) VALUES(?,?,?,?)",
                    [(root, path, digest, size) for path, (digest, size) in current.items()],
                )
        return scan_id

    def latest_scan(self, root):
        with self.connect() as db:
            row = db.execute("SELECT * FROM scans WHERE root=? ORDER BY id DESC LIMIT 1", (root,)).fetchone()
            return dict(row) if row else None

    def scan_events(self, scan_id):
        with self.connect() as db:
            rows = db.execute("SELECT * FROM events WHERE scan_id=? ORDER BY id", (scan_id,))
            return [dict(row) for row in rows]

    def history(self, root=None, limit=1000):
        with self.connect() as db:
            if root:
                rows = db.execute("SELECT * FROM events WHERE root=? ORDER BY id DESC LIMIT ?", (root, limit))
            else:
                rows = db.execute("SELECT * FROM events ORDER BY id DESC LIMIT ?", (limit,))
            return [dict(row) for row in rows]

    def roots(self):
        with self.connect() as db:
            return [row[0] for row in db.execute("SELECT path FROM roots ORDER BY path")]

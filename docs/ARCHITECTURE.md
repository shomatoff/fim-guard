# Architecture

```text
Explicitly selected folder
        │
        ├── manual scan ────────┐
        └── watchdog + timer ───┤
                                ▼
                            Scanner ─── SHA-256 reads
                                │
                                ▼
                      SQLite transaction
                         │          │
                  baseline/events   scan summary
                         └────┬─────┘
                              ▼
                         PySide6 UI ─── JSON / CSV export
```

`fim/engine.py` walks a selected root without following symlinks and hashes regular files in chunks. The engine compares each complete snapshot with the last baseline. It checks file identity, size and modification time before and after hashing to avoid recording a file that changed during the read. An incomplete or interrupted scan is recorded but does not advance the baseline or emit events.

`fim/database.py` owns the SQLite schema and transactions. The `(root, path)` key keeps baselines separate for each selected folder. A successful scan saves events and replaces that root's baseline atomically. SQLite and journal files are excluded from scans when stored inside a selected root.

`fim/monitor.py` debounces watchdog events and performs periodic reconciliation because filesystem notifications can be missed. `fim/ui.py` runs scans in a `QThread`, receives watchdog requests through Qt signals, and renders dashboard, history and settings pages. `fim/translations.py` supplies Uzbek, Russian and English interface text. `fim/reporting.py` exports the latest scan summary and events without file contents; CSV formula text is escaped.

The default database and warning log are stored in the operating system application data directory. Packaging is handled by `scripts/build.py`; `.github/workflows/ci.yml` runs checks and builds platform archives.

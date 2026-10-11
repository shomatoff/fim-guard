# Testing and verification

## Automated checks

From the project root, use Python 3.12 and install `requirements.txt` in a virtual environment. Run:

```sh
python -m pytest -q
python -m ruff check .
python scripts/build.py
```

Tests use temporary directories and SQLite databases. They cover:

| Area | Verified behavior |
| --- | --- |
| Hashing | SHA-256 matches `hashlib`; scanning does not change source bytes or modification times. |
| Baselines | First scan creates a baseline; complete scans advance it; restart preserves it. |
| Changes | Added, modified and deleted files produce one event each; repeated scans do not duplicate alerts. |
| Failure handling | Inaccessible files and subtrees, interrupted scans and invalid paths do not create false deletion alerts or advance the baseline. |
| Filesystem safety | Symlink targets, symlinked root folders and special files are skipped or rejected; internal SQLite files are excluded. |
| Monitoring | watchdog starts, stops and restarts; pause suppresses automatic scans; resume reconciles changes. |
| UI | Real PySide6 window receives watchdog events, updates the table and cards, switches languages, changes folders and exports the latest scan. |
| Reports and text | JSON/CSV contain scan summaries and event metadata, no file contents; CSV formula text is escaped; translation keys and placeholders match. |

`actionlint .github/workflows/ci.yml` validates the GitHub Actions workflow. Markdown links and all five PNG screenshot files are checked before publication. `git diff --check` catches whitespace errors.

## Desktop and screenshot check

Run `python main.py` to inspect the dashboard, event history, settings, language switcher and export dialog. On Linux, `python -m scripts.prepare_demo` creates disposable synthetic files, creates a baseline, starts watchdog and waits for a real event scan. The demo database and files are ignored by Git.

Screenshots under `docs/screenshots/` are captured from the actual running PySide6 window under Xvfb. For example:

```sh
xvfb-run -a python main.py --db demo-data/demo.sqlite --directory demo-data/monitored --lang en --screenshot docs/screenshots/dashboard-en.png
```

The Linux PyInstaller archive is built locally and the bundled executable is launched under Xvfb as a smoke test. Windows is built by GitHub Actions on `windows-latest` after publication; a physical Windows display and filesystem notification test remains outstanding. Qt is also inspected locally at 920×650 with 125% and 150% scaling; the narrow layout keeps the full title visible and event rows scrollable.

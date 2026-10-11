# FIM Guard — English guide

FIM checks the contents of files in folders you explicitly select. It creates a SHA-256 baseline and records added, modified and deleted paths in SQLite. The desktop interface supports manual checks, live watchdog notifications, pause/resume, history and JSON/CSV reports.

## Install

Use Python 3.12. Create a virtual environment, activate it, run `python -m pip install -r requirements.txt`, then `python main.py`. On Ubuntu, missing Qt XCB libraries can be installed with `sudo apt install libgl1 libegl1 libx11-xcb1 libxcb-cursor0 libxkbcommon-x11-0 libdbus-1-3` if needed. Windows uses the same Python commands in PowerShell, with `.venv\Scripts\Activate.ps1` for activation.

## Use

Choose a folder, create the baseline, then scan manually or start monitoring. Events show UTC times and relative paths. Pause stops automatic reconciliation; resume triggers a fresh check. Export the latest scan summary and events from the dashboard to JSON or CSV. The language selector is at the top right and persists locally.

The application stores its SQLite database and warning log in the operating system's application data directory. It never stores file contents. Reports can contain sensitive paths and hashes; review them before sharing.

## Verify

Run `python -m pytest -q`, `python -m ruff check .`, and `python scripts/build.py`. Linux packaging is verified locally; Windows is built by CI and requires real hardware testing for display scaling and filesystem notifications. See [architecture](ARCHITECTURE.md), [testing](TESTING.md), and [security](SECURITY.md).

"""Desktop entry point."""
import argparse
import logging
import sys
from pathlib import Path
from PySide6.QtCore import QStandardPaths
from fim.ui import run


def main():
    parser = argparse.ArgumentParser(description="FIM Guard desktop application")
    parser.add_argument("--db", type=Path, help="SQLite database path")
    parser.add_argument("--directory", type=Path, help="Preselect a directory")
    parser.add_argument("--lang", choices=("en", "uz", "ru"))
    parser.add_argument("--page", type=int, choices=(0, 1, 2), default=0)
    parser.add_argument("--screenshot", type=Path, help="Capture the running window")
    args = parser.parse_args()
    data_dir = Path(QStandardPaths.writableLocation(QStandardPaths.AppDataLocation))
    data_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(filename=data_dir / "fim.log", level=logging.WARNING,
                        format="%(asctime)s %(levelname)s %(name)s %(message)s")
    db = args.db or data_dir / "fim.sqlite"
    return run(db, args.directory, args.lang, args.page, args.screenshot)


if __name__ == "__main__":
    sys.exit(main())

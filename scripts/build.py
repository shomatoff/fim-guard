"""Build a target-platform archive with PyInstaller."""
import platform
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
NAME = "File-Integrity-Monitor"


def main():
    subprocess.run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
                    "--windowed", "--onedir", "--name", NAME,
                    str(ROOT / "main.py")], cwd=ROOT, check=True)
    target = DIST / NAME
    if not target.exists():
        raise RuntimeError("PyInstaller output missing")
    if platform.system() == "Windows":
        shutil.make_archive(str(DIST / f"{NAME}-Windows-x64"), "zip", DIST, NAME)
    elif platform.system() == "Linux":
        shutil.make_archive(str(DIST / f"{NAME}-Linux-x64"), "gztar", DIST, NAME)
    else:
        raise RuntimeError("Only Windows and Linux packages are configured")


if __name__ == "__main__":
    main()

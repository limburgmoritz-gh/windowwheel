"""Automatischer Start beim Anmelden über einen LaunchAgent (nur bei Start aus dem Quellcode).

Bei einer Homebrew-Installation übernimmt das `brew services start windowwheel`.
"""

import fcntl
import logging
import os
import plistlib
from pathlib import Path

log = logging.getLogger(__name__)

from .config import DATA_DIR

LABEL = "local.windowwheel"
PROJECT_DIR = Path(__file__).resolve().parent.parent
PYTHON = PROJECT_DIR / ".venv" / "bin" / "python"
PLIST = Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"
LOG_FILE = Path.home() / "Library" / "Logs" / "WindowWheel.log"
LOCK_FILE = DATA_DIR / "windowwheel.lock"


def installed_with_homebrew():
    parts = Path(__file__).resolve().parts
    return "Cellar" in parts and "windowwheel" in parts

_lock = None


def is_enabled():
    return PLIST.exists()


def enable():
    PLIST.parent.mkdir(parents=True, exist_ok=True)
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    plist = {
        "Label": LABEL,
        "ProgramArguments": [str(PYTHON), "-m", "windowwheel"],
        "WorkingDirectory": str(PROJECT_DIR),
        "EnvironmentVariables": {"PYTHONUNBUFFERED": "1"},
        "RunAtLoad": True,
        # Nach einem Absturz neu starten, aber nicht nach "Beenden" im Menü.
        "KeepAlive": {"SuccessfulExit": False},
        "ProcessType": "Interactive",
        "LimitLoadToSessionType": "Aqua",
        "StandardOutPath": str(LOG_FILE),
        "StandardErrorPath": str(LOG_FILE),
    }
    with open(PLIST, "wb") as fh:
        plistlib.dump(plist, fh)
    log.info("Launch at login enabled: %s", PLIST)


def disable():
    # Eine gerade laufende Instanz bleibt bis zum Beenden aktiv.
    if PLIST.exists():
        PLIST.unlink()
    log.info("Launch at login disabled")


def acquire_single_instance():
    """False, wenn WindowWheel schon läuft (z.B. per Autostart und zusätzlich per ./run.sh)."""
    global _lock
    LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    _lock = open(LOCK_FILE, "w")
    try:
        fcntl.flock(_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return False
    _lock.write(str(os.getpid()))
    _lock.flush()
    return True

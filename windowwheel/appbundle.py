"""Legt ~/Applications/WindowWheel.app an – damit Spotlight, Launchpad und der Finder das
Programm finden und man es per Doppelklick bzw. ⌘ Leertaste starten kann.

Die App ist nur ein Starter: Läuft WindowWheel als Homebrew-Dienst, wird dieser gestartet,
sonst das Programm direkt. Läuft es schon, passiert nichts (es gibt immer nur eine Instanz).
"""

import logging
import os
import plistlib
import shutil
import subprocess
from pathlib import Path

from . import __version__
from .autostart import PROJECT_DIR, installed_with_homebrew

log = logging.getLogger(__name__)

APP = Path.home() / "Applications" / "WindowWheel.app"
BUNDLE_ID = "io.github.limburgmoritz-gh.windowwheel"
ICON = Path(__file__).resolve().parent / "resources" / "AppIcon.icns"
BREW_SERVICE = "sh.brew.windowwheel"
LSREGISTER = ("/System/Library/Frameworks/CoreServices.framework/Frameworks/"
              "LaunchServices.framework/Support/lsregister")


def _command():
    """Stabiler Pfad zum Programm (übersteht Homebrew-Updates)."""
    if installed_with_homebrew():
        parts = Path(__file__).resolve().parts
        prefix = Path(*parts[:parts.index("Cellar")])
        return prefix / "opt" / "windowwheel" / "bin" / "windowwheel"
    return PROJECT_DIR / "run.sh"


def _script():
    return f"""#!/bin/zsh
# Startet WindowWheel. Läuft es schon, passiert nichts – es gibt immer nur eine Instanz.
if [ -f "$HOME/Library/LaunchAgents/{BREW_SERVICE}.plist" ]; then
  launchctl kickstart "gui/$(id -u)/{BREW_SERVICE}" 2>/dev/null && exit 0
fi
exec "{_command()}"
"""


def _info_plist():
    return {
        "CFBundleName": "WindowWheel",
        "CFBundleDisplayName": "WindowWheel",
        "CFBundleIdentifier": BUNDLE_ID,
        "CFBundleVersion": __version__,
        "CFBundleShortVersionString": __version__,
        "CFBundleExecutable": "WindowWheel",
        "CFBundleIconFile": "AppIcon",
        "CFBundlePackageType": "APPL",
        "LSUIElement": True,  # kein Dock-Symbol – WindowWheel lebt in der Menüleiste
        "LSMinimumSystemVersion": "14.0",
        "NSHumanReadableCopyright": "MIT License",
    }


def ensure_installed():
    """App-Bundle anlegen bzw. aktualisieren (Version, Pfad oder Icon geändert)."""
    contents = APP / "Contents"
    executable = contents / "MacOS" / "WindowWheel"
    plist_path = contents / "Info.plist"
    try:
        current = plistlib.loads(plist_path.read_bytes()) if plist_path.exists() else None
        if current == _info_plist() and executable.exists() and executable.read_text() == _script():
            return
        (contents / "MacOS").mkdir(parents=True, exist_ok=True)
        (contents / "Resources").mkdir(parents=True, exist_ok=True)
        executable.write_text(_script())
        executable.chmod(0o755)
        plist_path.write_bytes(plistlib.dumps(_info_plist()))
        if ICON.exists():
            shutil.copy(ICON, contents / "Resources" / "AppIcon.icns")
        os.utime(APP)  # Finder/Spotlight sollen das neue Icon übernehmen
        subprocess.run([LSREGISTER, "-f", str(APP)], capture_output=True)
        log.info("Installed app: %s (available in Spotlight)", APP)
    except OSError as exc:
        log.warning("Could not create WindowWheel.app: %s", exc)

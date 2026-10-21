"""Laden/Speichern der Konfiguration (Hotkey, Abstand, Layouts)."""

import json
import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger(__name__)

# Benutzerdaten liegen außerhalb des Programmordners, damit Updates (z.B. per
# Homebrew) die eigenen Layouts nicht überschreiben.
DATA_DIR = Path(os.environ.get("WINDOWWHEEL_HOME", Path.home() / "Library" / "Application Support" / "WindowWheel"))
CONFIG_PATH = Path(os.environ.get("WINDOWWHEEL_CONFIG", DATA_DIR / "config.json"))
STATE_PATH = DATA_DIR / "state.json"

# Slots: [x, y, breite, höhe] als Anteil (0..1) der nutzbaren Bildschirmfläche,
# y zählt von oben. Die Reihenfolge der Slots ist die Reihenfolge beim Zuweisen.
DEFAULT_CONFIG = {
    "hotkey": "alt+tab",
    "gap": 12,
    "center_cursor": True,
    "hide_others": True,
    "layouts": [
        {"name": "Halves", "slots": [[0, 0, 0.5, 1], [0.5, 0, 0.5, 1]]},
        {"name": "Thirds", "slots": [[0, 0, 0.3333, 1], [0.3333, 0, 0.3334, 1], [0.6667, 0, 0.3333, 1]]},
        {"name": "Center Focus", "slots": [[0.25, 0, 0.5, 1], [0, 0, 0.25, 1], [0.75, 0, 0.25, 1]]},
        {"name": "Main + 2", "slots": [[0, 0, 0.6, 1], [0.6, 0, 0.4, 0.5], [0.6, 0.5, 0.4, 0.5]]},
        {"name": "Quarters", "slots": [[0, 0, 0.25, 1], [0.25, 0, 0.25, 1], [0.5, 0, 0.25, 1], [0.75, 0, 0.25, 1]]},
        {"name": "Grid 2×2", "slots": [[0, 0, 0.5, 0.5], [0.5, 0, 0.5, 0.5], [0, 0.5, 0.5, 0.5], [0.5, 0.5, 0.5, 0.5]]},
        {"name": "Center + 4", "slots": [[0.25, 0, 0.5, 1], [0, 0, 0.25, 0.5], [0, 0.5, 0.25, 0.5], [0.75, 0, 0.25, 0.5], [0.75, 0.5, 0.25, 0.5]]},
        {"name": "Two Thirds", "slots": [[0, 0, 0.6667, 1], [0.6667, 0, 0.3333, 1]]},
    ],
}


@dataclass
class Layout:
    name: str
    slots: list  # Liste von (x, y, w, h) als Anteile
    gap: tuple = None  # eigener Abstand als Anteil (Breite, Höhe) der Bildschirmfläche, sonst der globale
    index: int = -1  # Position in config.json, zum Zurückschreiben des Abstands


@dataclass
class Config:
    hotkey: str
    gap: float
    center_cursor: bool
    hide_others: bool
    layouts: list
    raw: dict
    mtime: float


def _parse_gap(value):
    if isinstance(value, list) and len(value) == 2 and all(isinstance(v, (int, float)) and 0 <= v < 0.5 for v in value):
        return (float(value[0]), float(value[1]))
    return None


def _parse_layouts(raw_layouts):
    layouts = []
    for index, entry in enumerate(raw_layouts):
        name = str(entry.get("name", "Layout"))
        slots = []
        for slot in entry.get("slots", []):
            if len(slot) != 4 or not all(isinstance(v, (int, float)) for v in slot):
                log.warning("Layout %r: ignoring invalid slot %r", name, slot)
                continue
            x, y, w, h = (float(v) for v in slot)
            if w <= 0 or h <= 0 or x < 0 or y < 0 or x + w > 1.001 or y + h > 1.001:
                log.warning("Layout %r: slot %r is outside 0..1", name, slot)
                continue
            slots.append((x, y, w, h))
        if slots:
            layouts.append(Layout(name, slots, _parse_gap(entry.get("gap_rel")), index))
    return layouts


def load_config():
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not CONFIG_PATH.exists():
        save_raw(DEFAULT_CONFIG)
        log.info("Created default configuration: %s", CONFIG_PATH)
    try:
        raw = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        log.error("config.json is unreadable (%s) – using defaults", exc)
        raw = DEFAULT_CONFIG
    layouts = _parse_layouts(raw.get("layouts", [])) if raw is not DEFAULT_CONFIG else []
    if not layouts:  # Standard-Layouts ohne Index: werden nie in eine kaputte Datei geschrieben
        layouts = [Layout(l.name, l.slots, l.gap) for l in _parse_layouts(DEFAULT_CONFIG["layouts"])]
    return Config(
        hotkey=str(raw.get("hotkey", DEFAULT_CONFIG["hotkey"])),
        gap=float(raw.get("gap", DEFAULT_CONFIG["gap"])),
        center_cursor=bool(raw.get("center_cursor", True)),
        hide_others=bool(raw.get("hide_others", True)),
        layouts=layouts,
        raw=raw,
        mtime=config_mtime(),
    )


def config_mtime():
    try:
        return CONFIG_PATH.stat().st_mtime
    except OSError:
        return 0.0


def save_raw(raw):
    text = json.dumps(raw, indent=2, ensure_ascii=False)
    # Zahlenlisten (Slots) einzeilig schreiben, damit die Datei gut editierbar bleibt.
    text = re.sub(
        r"\[\s*([-\d.eE]+(?:\s*,\s*[-\d.eE]+)*)\s*\]",
        lambda m: "[" + ", ".join(p.strip() for p in m.group(1).split(",")) + "]",
        text,
    )
    CONFIG_PATH.write_text(text + "\n", encoding="utf-8")


def load_state():
    """Laufzeit-Zustand (z.B. zuletzt gewähltes Layout je Bildschirm)."""
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def save_state(state):
    try:
        STATE_PATH.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    except OSError as exc:
        log.warning("Could not save state: %s", exc)


def save_layout_gap(raw, layout, rel_gap):
    """Abstand eines Layouts (Anteil von Breite/Höhe) in config.json merken."""
    entries = raw.get("layouts", [])
    if not 0 <= layout.index < len(entries):
        return False
    entries[layout.index].pop("gap", None)
    entries[layout.index]["gap_rel"] = list(rel_gap)
    save_raw(raw)
    return True

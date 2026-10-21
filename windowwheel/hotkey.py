"""Globaler Hotkey über einen CGEventTap.

Der Tap kann Tastendrücke verschlucken (der Hotkey landet nicht in der
aktiven App) und bemerkt das Loslassen der Modifier – das braucht das
"gedrückt halten, zielen, loslassen"-Verhalten des Rads.
"""

import logging

import Quartz as Q

log = logging.getLogger(__name__)

# Virtuelle Keycodes (physische Tastenposition, ANSI-Belegung).
KEYCODES = {
    "a": 0, "s": 1, "d": 2, "f": 3, "h": 4, "g": 5, "z": 6, "x": 7, "c": 8, "v": 9,
    "b": 11, "q": 12, "w": 13, "e": 14, "r": 15, "y": 16, "t": 17,
    "1": 18, "2": 19, "3": 20, "4": 21, "6": 22, "5": 23, "=": 24, "9": 25, "7": 26,
    "-": 27, "8": 28, "0": 29, "]": 30, "o": 31, "u": 32, "[": 33, "i": 34, "p": 35,
    "return": 36, "l": 37, "j": 38, "'": 39, "k": 40, ";": 41, "\\": 42, ",": 43,
    "/": 44, "n": 45, "m": 46, ".": 47, "tab": 48, "space": 49, "`": 50,
    "delete": 51, "escape": 53,
    "f1": 122, "f2": 120, "f3": 99, "f4": 118, "f5": 96, "f6": 97, "f7": 98,
    "f8": 100, "f9": 101, "f10": 109, "f11": 103, "f12": 111,
}

MODIFIERS = {
    "ctrl": Q.kCGEventFlagMaskControl,
    "control": Q.kCGEventFlagMaskControl,
    "alt": Q.kCGEventFlagMaskAlternate,
    "opt": Q.kCGEventFlagMaskAlternate,
    "option": Q.kCGEventFlagMaskAlternate,
    "cmd": Q.kCGEventFlagMaskCommand,
    "command": Q.kCGEventFlagMaskCommand,
    "shift": Q.kCGEventFlagMaskShift,
}
MOD_MASK = (
    Q.kCGEventFlagMaskControl
    | Q.kCGEventFlagMaskAlternate
    | Q.kCGEventFlagMaskCommand
    | Q.kCGEventFlagMaskShift
)

# Reihenfolge wie in macOS-Menüs: ⌃ ⌥ ⇧ ⌘
MOD_SYMBOLS = (
    ("ctrl", Q.kCGEventFlagMaskControl, "⌃"),
    ("alt", Q.kCGEventFlagMaskAlternate, "⌥"),
    ("shift", Q.kCGEventFlagMaskShift, "⇧"),
    ("cmd", Q.kCGEventFlagMaskCommand, "⌘"),
)
KEY_SYMBOLS = {"tab": "⇥", "space": "Space", "return": "↩", "delete": "⌫", "escape": "⎋"}
KEY_NAMES = {code: name for name, code in KEYCODES.items()}


def parse_hotkey(text):
    """'alt+tab' -> (keycode, modifier_flags). Tasten ohne Namen als 'keycode:NN'."""
    keycode, mods = None, 0
    for part in text.lower().replace(" ", "").split("+"):
        if part in MODIFIERS:
            mods |= MODIFIERS[part]
        elif part in KEYCODES:
            keycode = KEYCODES[part]
        elif part.startswith("keycode:") and part[8:].isdigit():
            keycode = int(part[8:])
        else:
            raise ValueError(f"Unknown key in shortcut: {part!r}")
    if keycode is None:
        raise ValueError(f"Shortcut without a key: {text!r}")
    return keycode, mods


def hotkey_string(keycode, mods):
    """(keycode, flags) -> 'alt+tab' für config.json."""
    parts = [name for name, flag, _ in MOD_SYMBOLS if mods & flag]
    parts.append(KEY_NAMES.get(keycode, f"keycode:{keycode}"))
    return "+".join(parts)


def key_label(keycode):
    """Beschriftung einer Taste in der aktuellen Tastaturbelegung (z.B. 'Y' auf deutschen Tastaturen)."""
    name = KEY_NAMES.get(keycode)
    if name in KEY_SYMBOLS:
        return KEY_SYMBOLS[name]
    if name and name.startswith("f") and name[1:].isdigit():
        return name.upper()
    event = Q.CGEventCreateKeyboardEvent(None, keycode, True)
    Q.CGEventSetFlags(event, 0)
    _, chars = Q.CGEventKeyboardGetUnicodeString(event, 4, None, None)
    return chars.upper() if chars and chars.isprintable() else (name or f"#{keycode}").upper()


def format_hotkey(text):
    """'alt+tab' -> '⌥⇥' zur Anzeige."""
    keycode, mods = parse_hotkey(text)
    return "".join(sym for _, flag, sym in MOD_SYMBOLS if mods & flag) + key_label(keycode)


def is_function_key(keycode):
    name = KEY_NAMES.get(keycode, "")
    return name.startswith("f") and name[1:].isdigit()


class HotkeyTap:
    """Ruft Callbacks im Main-Thread auf (der Tap hängt am Main-Runloop).

    on_hotkey()                  – Hotkey gedrückt
    on_release()                 – Hotkey-Modifier losgelassen
    on_key(keycode, flags, down)->bool – sonstige Taste, True = verschlucken
    on_mouse(etype, point)       – linke Maustaste gedrückt/gezogen/losgelassen (nur beobachten)
    """

    def __init__(self, hotkey, on_hotkey, on_release, on_key, on_mouse):
        self.keycode, self.mods = parse_hotkey(hotkey)
        self.on_hotkey = on_hotkey
        self.on_release = on_release
        self.on_key = on_key
        self.on_mouse = on_mouse
        self._mods_down = False
        self._tap = None
        self._source = None
        # Modifier, die vor dem System versteckt werden (beim Einrasten: ⌥, damit
        # die macOS-eigene ⌥-Kachelung nicht dazwischenfunkt).
        self.hide_mods = 0
        self.recorder = None  # recorder(keycode, flags) – siehe Einstellungen

    def set_hotkey(self, hotkey):
        self.keycode, self.mods = parse_hotkey(hotkey)

    def start(self):
        mask = (
            Q.CGEventMaskBit(Q.kCGEventKeyDown)
            | Q.CGEventMaskBit(Q.kCGEventKeyUp)
            | Q.CGEventMaskBit(Q.kCGEventFlagsChanged)
            | Q.CGEventMaskBit(Q.kCGEventLeftMouseDragged)
            | Q.CGEventMaskBit(Q.kCGEventLeftMouseUp)
        )
        self._tap = Q.CGEventTapCreate(
            Q.kCGSessionEventTap,
            Q.kCGHeadInsertEventTap,
            Q.kCGEventTapOptionDefault,
            mask,
            self._callback,
            None,
        )
        if self._tap is None:
            return False
        self._source = Q.CFMachPortCreateRunLoopSource(None, self._tap, 0)
        Q.CFRunLoopAddSource(Q.CFRunLoopGetMain(), self._source, Q.kCFRunLoopCommonModes)
        Q.CGEventTapEnable(self._tap, True)
        return True

    def _callback(self, proxy, etype, event, refcon):
        try:
            return self._handle(etype, event)
        except Exception:
            log.exception("Fehler im Hotkey-Tap")
            return event

    def _hide_mods(self, event):
        if self.hide_mods:
            Q.CGEventSetFlags(event, Q.CGEventGetFlags(event) & ~self.hide_mods)

    def release_hidden_mods(self):
        """Dem System sofort "Modifier losgelassen" melden (blendet z.B. die macOS-Kachelvorschau aus)."""
        event = Q.CGEventCreateKeyboardEvent(None, 58, False)  # 58 = linke ⌥-Taste
        Q.CGEventSetFlags(event, Q.CGEventSourceFlagsState(Q.kCGEventSourceStateCombinedSessionState) & ~self.hide_mods)
        Q.CGEventPost(Q.kCGSessionEventTap, event)

    def _handle(self, etype, event):
        if etype in (Q.kCGEventTapDisabledByTimeout, Q.kCGEventTapDisabledByUserInput):
            Q.CGEventTapEnable(self._tap, True)
            return event

        if etype in (Q.kCGEventLeftMouseDragged, Q.kCGEventLeftMouseUp):
            self.on_mouse(etype, Q.CGEventGetLocation(event))
            self._hide_mods(event)
            return event  # Maus-Events nie verschlucken – das Fenster soll normal weitergezogen werden

        flags = Q.CGEventGetFlags(event) & MOD_MASK

        if etype == Q.kCGEventFlagsChanged:
            held = (flags & self.mods) == self.mods
            if self._mods_down and not held:
                self._mods_down = False
                self.on_release()
            self._hide_mods(event)
            return event

        keycode = Q.CGEventGetIntegerValueField(event, Q.kCGKeyboardEventKeycode)
        if self.recorder is not None:
            # Einstellungen nehmen gerade eine neue Tastenkombination auf.
            if etype == Q.kCGEventKeyDown and not Q.CGEventGetIntegerValueField(event, Q.kCGKeyboardEventAutorepeat):
                self.recorder(keycode, flags)
            return None
        if keycode == self.keycode and flags == self.mods:
            if etype == Q.kCGEventKeyDown:
                self._mods_down = self.mods != 0
                if not Q.CGEventGetIntegerValueField(event, Q.kCGKeyboardEventAutorepeat):
                    self.on_hotkey()
            return None  # Hotkey nie an die aktive App weitergeben

        if self.on_key(keycode, flags, etype == Q.kCGEventKeyDown):
            return None
        return event

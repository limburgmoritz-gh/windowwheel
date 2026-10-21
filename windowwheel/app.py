"""App-Steuerung: Hotkey -> Rad -> Zuweisung, plus Menüleisten-Icon."""

import logging
import os

import objc
import Quartz as Q
from AppKit import (
    NSAlert,
    NSAlertFirstButtonReturn,
    NSApp,
    NSApplication,
    NSApplicationActivationPolicyAccessory,
    NSImage,
    NSMakeRect,
    NSMenu,
    NSMenuItem,
    NSObject,
    NSScreen,
    NSStatusBar,
    NSTextField,
    NSURL,
    NSVariableStatusItemLength,
    NSWorkspace,
)
from PyObjCTools import AppHelper

from . import __version__, appbundle, autostart, ax
from . import config as cfg
from .assign import AssignMode
from .geometry import cocoa_to_cg_rect, gap_to_relative, intersection_area, screen_center_cg, screen_under_mouse
from .hotkey import HotkeyTap
from .overlay import Overlay
from .snap import SnapMode
from .thumbnails import ThumbnailLoader
from .wallpaper import wallpaper_image
from .wheel import WheelMode

log = logging.getLogger("windowwheel")


class Controller:
    def __init__(self):
        self.config = cfg.load_config()
        self.overlay = Overlay()
        self.mode = None
        self.holding = False
        self.saved_cursor = None
        self.prefetch = None
        self.state = cfg.load_state()
        self.tap = HotkeyTap(self.config.hotkey, self.on_hotkey, self.on_release, self.on_key, self.on_mouse)

    # --- Start / Konfiguration --------------------------------------------

    def start(self, attempt=0):
        # Systemdialog nur beim ersten Versuch, danach still alle 3 s erneut prüfen.
        if not ax.is_trusted(prompt=attempt == 0) or not self.tap.start():
            if attempt == 0:
                log.warning(
                    "Kein Bedienungshilfen-Zugriff. Bitte unter Systemeinstellungen › Datenschutz & "
                    "Sicherheit › Bedienungshilfen „Python“ (bzw. Terminal/VS Code) erlauben. "
                    "Ich warte, bis der Zugriff da ist …"
                )
            AppHelper.callLater(3.0, self.start, attempt + 1)
            return
        log.info("Bereit. Hotkey: %s  ·  Konfiguration: %s", self.config.hotkey, cfg.CONFIG_PATH)
        AppHelper.callLater(0.5, self._warm_up)

    def _warm_up(self):
        for screen in NSScreen.screens():
            wallpaper_image(screen)

    def reload_config(self, force=False):
        if not force and cfg.config_mtime() == self.config.mtime:
            return
        try:
            new = cfg.load_config()
            self.tap.set_hotkey(new.hotkey)
        except ValueError as exc:
            log.error("Konfiguration fehlerhaft: %s", exc)
            return
        self.config = new
        log.info("Konfiguration geladen (%d Layouts)", len(new.layouts))

    # --- Hotkey-Callbacks (laufen im Event-Tap, daher Arbeit verschieben) ---

    def on_hotkey(self):
        log.debug("Hotkey gedrückt")
        AppHelper.callAfter(self._hotkey_pressed)

    def on_release(self):
        if self.holding:
            self.holding = False
            AppHelper.callAfter(self._modifiers_released)

    def on_key(self, keycode, flags, down):
        mode = self.mode
        if mode is None or keycode not in mode.KEYS:
            return False
        if down:
            AppHelper.callAfter(self._key, mode, keycode, flags)
        return True

    def on_mouse(self, etype, point):
        if isinstance(self.mode, SnapMode):
            AppHelper.callAfter(self._snap_mouse, self.mode, etype, Q.CGPointMake(point.x, point.y))

    def _snap_mouse(self, mode, etype, point):
        if mode is self.mode:
            mode.mouse(etype, point)

    def _hotkey_pressed(self):
        if isinstance(self.mode, SnapMode):
            self.cancel()  # nochmal ⌥⇥: Felder weg, Fenster landet normal
        elif isinstance(self.mode, WheelMode):
            self.holding = True
            self.mode.cycle(1)
        elif self.mode is None and not self.overlay.closing:
            dragging = Q.CGEventSourceButtonState(Q.kCGEventSourceStateCombinedSessionState, Q.kCGMouseButtonLeft)
            if not (dragging and self.start_snap()):
                self.open_wheel()

    def _modifiers_released(self):
        if isinstance(self.mode, WheelMode):
            self.mode.modifiers_released()

    def _key(self, mode, keycode, flags):
        if mode is self.mode:
            mode.key(keycode, flags)

    # --- Ablauf ------------------------------------------------------------

    def open_wheel(self):
        self.reload_config()
        screen = screen_under_mouse()
        self.mode = WheelMode(self, self.config.layouts, screen)
        self.holding = True
        self.saved_cursor = Q.CGEventGetLocation(Q.CGEventCreate(None))
        self.overlay.show(screen, self.mode)
        log.info("Rad geöffnet auf %s", screen.localizedName())
        if self.config.center_cursor:
            Q.CGWarpMouseCursorPosition(screen_center_cg(screen))
            Q.CGAssociateMouseAndMouseCursorPosition(True)
        # Fenster + Vorschaubilder schon laden, während man im Rad zielt.
        self.prefetch = None
        AppHelper.callLater(0.03, self._prefetch, self.mode)

    def _prefetch(self, wheel):
        if self.mode is not wheel:
            return
        # Nur Fenster des Bildschirms, auf dem das Rad (also der Cursor) ist.
        windows = ax.list_windows(cocoa_to_cg_rect(wheel.screen.frame()))
        loader = ThumbnailLoader()
        loader.load([w.wid for w in windows])
        self.prefetch = (wheel, windows, loader)

    def select_layout(self, idx):
        if not isinstance(self.mode, WheelMode):
            return
        layout = self.config.layouts[idx]
        wheel = self.mode
        self.holding = False
        log.info("Layout gewählt: %s", layout.name)
        self._remember_layout(wheel.screen, layout)
        windows, loader = None, None
        if self.prefetch is not None and self.prefetch[0] is wheel:
            _, windows, loader = self.prefetch
        self.prefetch = None
        self.mode = AssignMode(self, layout, wheel.screen, self.config.gap, windows, loader)
        self.overlay.set_mode(self.mode)

    def cancel(self):
        mode = self.mode
        self.mode = None
        self.tap.hide_mods = 0
        self.holding = False
        self._drop_prefetch()
        if isinstance(mode, AssignMode):
            mode.exit(cancelled=True)
            AppHelper.callLater(0.3, self.overlay.fade_out, 0.2)
            return
        if isinstance(mode, WheelMode) and self.saved_cursor is not None and self.config.center_cursor:
            Q.CGWarpMouseCursorPosition(self.saved_cursor)
            Q.CGAssociateMouseAndMouseCursorPosition(True)
        self.overlay.fade_out(0.14)

    def finish_assign(self, mode):
        if mode is not self.mode:
            return
        self.mode = None
        self.holding = False
        mode.exit(cancelled=False, hide_others=self.config.hide_others)
        rel_gap = gap_to_relative(mode.gap, mode.screen)
        if mode.gap_changed and cfg.save_layout_gap(self.config.raw, mode.layout, rel_gap):
            log.info("Abstand für %r gespeichert: %s px (relativ %s)", mode.layout.name, mode.gap, rel_gap)
            self.reload_config(force=True)
        placed = [w for w in mode.assigned if w is not None]
        # Gesetzte Fenster (noch unter dem Overlay) nach vorne holen; Slot 1 bekommt zuletzt den Fokus.
        for step, window in enumerate(reversed(placed)):
            AppHelper.callLater(0.08 + 0.05 * step, ax.focus, window)
        AppHelper.callLater(0.4, self.overlay.fade_out, 0.22)

    # --- Einrasten: Fenster ziehen + Hotkey -------------------------------

    def _remember_layout(self, screen, layout):
        self.state.setdefault("last_layout", {})[screen.localizedName()] = layout.name
        self.state["last_layout_any"] = layout.name
        cfg.save_state(self.state)

    def _last_layout(self, screen):
        """Zuletzt im Rad gewähltes Layout für diesen Bildschirm (sonst irgendeins)."""
        last = self.state.get("last_layout", {})
        for name in (last.get(screen.localizedName()), self.state.get("last_layout_any")):
            for layout in self.config.layouts:
                if layout.name == name:
                    return layout
        return self.config.layouts[0]

    def _window_under(self, point):
        """Das gerade gezogene Fenster: das aktive Fenster der vorderen App unter dem Cursor."""
        window = ax.focused_window()
        if window is not None and ax._center_in((point.x, point.y, 0, 0), window.frame):
            return window
        # Fallback: oberstes normales Fenster unter dem Cursor. Vorschauflächen, Tooltips &
        # Co. (z.B. die macOS-Kachelvorschau beim Ziehen mit ⌥) werden übersprungen.
        for wid, (x, y, w, h) in ax.visible_window_frames():
            if x <= point.x <= x + w and y <= point.y <= y + h and w >= 150 and h >= 100:
                window = ax.window_by_id(wid)
                if window is not None and ax._attr(window.element, "AXSubrole") == "AXStandardWindow":
                    return window
        return None

    def start_snap(self):
        point = Q.CGEventGetLocation(Q.CGEventCreate(None))
        window = self._window_under(point)
        if window is None:
            return False
        self.reload_config()
        screen = screen_under_mouse()
        layout = self._last_layout(screen)
        self.mode = SnapMode(self, window, layout, screen, self.config.gap)
        self.overlay.show(screen, self.mode)
        # ⌥ ab jetzt vor macOS verstecken, sonst kachelt die eingebaute ⌥-Kachelung mit.
        self.tap.hide_mods = Q.kCGEventFlagMaskAlternate
        self.tap.release_hidden_mods()
        log.info("Einrasten: %s – Layout %s auf %s", window.app_name, layout.name, screen.localizedName())
        return True

    def snap_screen_changed(self, mode, point):
        screen = screen_under_mouse()
        if mode is not self.mode or screen == mode.screen:
            return
        self.mode = SnapMode(self, mode.window, self._last_layout(screen), screen, self.config.gap)
        self.overlay.show(screen, self.mode)
        self.mode.mouse(Q.kCGEventLeftMouseDragged, point)

    def finish_snap(self, mode):
        if mode is not self.mode:
            return
        self.mode = None
        self.tap.hide_mods = 0
        self.overlay.fade_out(0.12)
        if mode.highlight is not None:
            # Kurz warten, bis macOS das Ziehen abgeschlossen hat.
            AppHelper.callLater(0.06, self._snap_window, mode.window, mode.slots[mode.highlight])

    def _snap_window(self, window, rect, expected=None, attempt=0):
        if expected is None:
            ax.set_frame(window, rect)
            ax.focus(window)
            expected = ax.get_frame(window.element)
            log.info("Eingerastet: %s -> %s", window.app_name, rect)
        elif ax.get_frame(window.element) != expected:
            # Sicherheitsnetz: macOS (z.B. die eingebaute Kachelung) hat danach noch umgesetzt.
            log.info("Fenster wurde nachträglich verschoben – rücke es wieder ins Feld")
            ax.set_frame(window, rect)
        if attempt < 2:
            AppHelper.callLater(0.4, self._snap_window, window, rect, expected, attempt + 1)

    def _drop_prefetch(self):
        if self.prefetch is not None:
            self.prefetch[2].cancel()
            self.prefetch = None

    # --- Aktuelle Anordnung als Layout speichern ---------------------------

    def save_current_arrangement(self):
        screen = screen_under_mouse()
        vx, vy, vw, vh = cocoa_to_cg_rect(screen.visibleFrame())
        picked = []
        for _, (x, y, w, h) in ax.visible_window_frames():
            if w < 150 or h < 100:
                continue
            cx, cy = x + w / 2, y + h / 2
            if not (vx <= cx <= vx + vw and vy <= cy <= vy + vh):
                continue
            rect = (x, y, w, h)
            covered = sum(intersection_area(rect, p) for p in picked)
            if covered < 0.5 * w * h:  # nur Fenster, die überwiegend sichtbar sind
                picked.append(rect)
            if len(picked) == 9:
                break
        if not picked:
            self._alert("Keine Fenster gefunden", "Auf diesem Bildschirm sind keine passenden Fenster sichtbar.")
            return

        slots = []
        for x, y, w, h in picked:
            x0 = _snap(max(0.0, (x - vx) / vw))
            y0 = _snap(max(0.0, (y - vy) / vh))
            x1 = _snap(min(1.0, (x + w - vx) / vw))
            y1 = _snap(min(1.0, (y + h - vy) / vh))
            if x1 > x0 and y1 > y0:
                slots.append([x0, y0, round(x1 - x0, 4), round(y1 - y0, 4)])
        slots.sort(key=lambda s: (round(s[0], 2), round(s[1], 2)))

        name = self._ask_name(len(slots))
        if not name:
            return
        raw = dict(self.config.raw)
        raw["layouts"] = list(raw.get("layouts", [])) + [{"name": name, "slots": slots}]
        cfg.save_raw(raw)
        self.reload_config(force=True)
        log.info("Layout %r mit %d Slots gespeichert", name, len(slots))

    def _ask_name(self, count):
        alert = NSAlert.alloc().init()
        alert.setMessageText_("Anordnung als Layout speichern")
        alert.setInformativeText_(f"{count} Fenster erkannt. Wie soll das Layout heißen?")
        alert.addButtonWithTitle_("Speichern")
        alert.addButtonWithTitle_("Abbrechen")
        field = NSTextField.alloc().initWithFrame_(NSMakeRect(0, 0, 260, 24))
        field.setStringValue_(f"Eigenes Layout {len(self.config.layouts) + 1}")
        alert.setAccessoryView_(field)
        alert.window().setInitialFirstResponder_(field)
        NSApp.activateIgnoringOtherApps_(True)
        if alert.runModal() != NSAlertFirstButtonReturn:
            return None
        return field.stringValue().strip() or None

    def _alert(self, title, message):
        alert = NSAlert.alloc().init()
        alert.setMessageText_(title)
        alert.setInformativeText_(message)
        NSApp.activateIgnoringOtherApps_(True)
        alert.runModal()


def _snap(value):
    """Kanten auf "glatte" Anteile (1/24, 1/10) ziehen, damit Layouts symmetrisch werden."""
    candidates = [k / 24 for k in range(25)] + [k / 10 for k in range(11)]
    best = min(candidates, key=lambda c: abs(c - value))
    return round(best if abs(best - value) <= 0.02 else value, 4)


class AppDelegate(NSObject):
    def applicationDidFinishLaunching_(self, notification):
        self.controller = Controller()
        self._build_status_item()
        self.controller.start()

    @objc.python_method
    def _build_status_item(self):
        self.status_item = NSStatusBar.systemStatusBar().statusItemWithLength_(NSVariableStatusItemLength)
        button = self.status_item.button()
        icon = NSImage.imageWithSystemSymbolName_accessibilityDescription_("circle.grid.cross", "WindowWheel")
        if icon is not None:
            icon.setTemplate_(True)
            button.setImage_(icon)
        else:
            button.setTitle_("◎")

        menu = NSMenu.alloc().init()
        hotkey = self.controller.config.hotkey
        # Bei Homebrew kümmert sich `brew services` um den Autostart.
        autostart_item = (("Autostart: brew services start windowwheel", None) if autostart.installed_with_homebrew()
                          else ("Beim Anmelden starten", "toggleAutostart:"))
        for title, action in (
            (f"WindowWheel {__version__}", None),
            (None, None),
            (f"Rad öffnen  ({hotkey})", "openWheel:"),
            ("Aktuelle Anordnung als Layout speichern …", "saveArrangement:"),
            (None, None),
            ("Layouts bearbeiten (config.json)", "editConfig:"),
            ("Konfiguration neu laden", "reloadConfig:"),
            (None, None),
            autostart_item,
            ("WindowWheel beenden", "quit:"),
        ):
            if title is None:
                menu.addItem_(NSMenuItem.separatorItem())
                continue
            item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(title, action, "")
            item.setTarget_(self)
            item.setEnabled_(action is not None)
            if action == "toggleAutostart:":
                item.setState_(1 if autostart.is_enabled() else 0)
            menu.addItem_(item)
        self.status_item.setMenu_(menu)

    @objc.IBAction
    def openWheel_(self, sender):
        # Kurz verzögern, damit das Menü geschlossen ist.
        AppHelper.callLater(0.15, self._open_from_menu)

    @objc.python_method
    def _open_from_menu(self):
        if self.controller.mode is None:
            self.controller.open_wheel()
            self.controller.holding = False

    @objc.IBAction
    def saveArrangement_(self, sender):
        AppHelper.callLater(0.1, self.controller.save_current_arrangement)

    @objc.IBAction
    def editConfig_(self, sender):
        NSWorkspace.sharedWorkspace().openURL_(NSURL.fileURLWithPath_(str(cfg.CONFIG_PATH)))

    @objc.IBAction
    def reloadConfig_(self, sender):
        self.controller.reload_config(force=True)

    @objc.IBAction
    def toggleAutostart_(self, sender):
        if autostart.is_enabled():
            autostart.disable()
        else:
            autostart.enable()
        sender.setState_(1 if autostart.is_enabled() else 0)

    @objc.IBAction
    def quit_(self, sender):
        NSApp.terminate_(None)


def main():
    logging.basicConfig(level=logging.DEBUG if os.environ.get("WINDOWWHEEL_DEBUG") else logging.INFO, format="%(asctime)s  %(levelname)-7s %(message)s", datefmt="%H:%M:%S")
    if not autostart.acquire_single_instance():
        log.info("WindowWheel läuft bereits – beende diese zweite Instanz.")
        return
    appbundle.ensure_installed()
    app = NSApplication.sharedApplication()
    app.setActivationPolicy_(NSApplicationActivationPolicyAccessory)
    delegate = AppDelegate.alloc().init()
    app.setDelegate_(delegate)
    AppHelper.runEventLoop(installInterrupt=True)

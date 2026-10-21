"""Einstellungsfenster: Tastenkombination aufnehmen, Abstand, Verhalten."""

import objc
from AppKit import (
    NSApp,
    NSBackingStoreBuffered,
    NSButton,
    NSColor,
    NSFont,
    NSMakeRect,
    NSObject,
    NSSlider,
    NSTextField,
    NSWindow,
    NSWindowStyleMaskClosable,
    NSWindowStyleMaskTitled,
    NSWorkspace,
    NSURL,
)

from . import config as cfg
from .hotkey import format_hotkey, hotkey_string, is_function_key

KEY_ESCAPE, KEY_DELETE = 53, 51
DEFAULT_HOTKEY = cfg.DEFAULT_CONFIG["hotkey"]
W, H = 460, 330


def _label(text, frame, size=13, bold=False, gray=False, wrap=False):
    field = NSTextField.wrappingLabelWithString_(text) if wrap else NSTextField.labelWithString_(text)
    field.setFrame_(frame)
    field.setFont_(NSFont.boldSystemFontOfSize_(size) if bold else NSFont.systemFontOfSize_(size))
    if gray:
        field.setTextColor_(NSColor.secondaryLabelColor())
    return field


class SettingsWindow(NSObject):
    def initWithController_(self, controller):
        self = objc.super(SettingsWindow, self).init()
        if self is None:
            return None
        self.controller = controller
        self.window = None
        return self

    # --- Fenster ------------------------------------------------------------

    @objc.python_method
    def show(self):
        if self.window is None:
            self._build()
        self._refresh()
        self.window.center()
        NSApp.activateIgnoringOtherApps_(True)
        self.window.makeKeyAndOrderFront_(None)

    @objc.python_method
    def _build(self):
        win = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            NSMakeRect(0, 0, W, H), NSWindowStyleMaskTitled | NSWindowStyleMaskClosable, NSBackingStoreBuffered, False)
        win.setTitle_("WindowWheel Settings")
        win.setReleasedWhenClosed_(False)
        win.setDelegate_(self)
        view = win.contentView()
        x, y = 24, H - 48

        view.addSubview_(_label("Keyboard shortcut", NSMakeRect(x, y, 200, 20), bold=True))
        self.shortcut = NSButton.buttonWithTitle_target_action_("", self, "recordShortcut:")
        self.shortcut.setFrame_(NSMakeRect(x + 200, y - 6, 140, 32))
        view.addSubview_(self.shortcut)
        reset = NSButton.buttonWithTitle_target_action_("Reset", self, "resetShortcut:")
        reset.setFrame_(NSMakeRect(x + 344, y - 6, 70, 32))
        view.addSubview_(reset)
        self.hint = _label("", NSMakeRect(x, y - 44, W - 2 * x, 34), size=11, gray=True, wrap=True)
        view.addSubview_(self.hint)

        y -= 92
        view.addSubview_(_label("Default spacing", NSMakeRect(x, y, 200, 20), bold=True))
        self.gap = NSSlider.sliderWithValue_minValue_maxValue_target_action_(12, 0, 80, self, "gapChanged:")
        self.gap.setFrame_(NSMakeRect(x + 200, y - 2, 150, 24))
        self.gap.setContinuous_(True)
        view.addSubview_(self.gap)
        self.gap_value = _label("", NSMakeRect(x + 360, y, 60, 20))
        view.addSubview_(self.gap_value)
        view.addSubview_(_label("Used for layouts without their own spacing.",
                                NSMakeRect(x, y - 24, W - 2 * x, 18), size=11, gray=True))

        y -= 70
        self.center = NSButton.checkboxWithTitle_target_action_(
            "Center the cursor when the wheel opens", self, "toggleCenter:")
        self.center.setFrame_(NSMakeRect(x, y, W - 2 * x, 20))
        view.addSubview_(self.center)
        self.hide = NSButton.checkboxWithTitle_target_action_(
            "Move windows that weren't picked behind the arranged ones", self, "toggleHide:")
        self.hide.setFrame_(NSMakeRect(x, y - 28, W - 2 * x, 20))
        view.addSubview_(self.hide)

        edit = NSButton.buttonWithTitle_target_action_("Edit Layouts…", self, "editLayouts:")
        edit.setFrame_(NSMakeRect(x - 6, 16, 130, 32))
        view.addSubview_(edit)
        self.window = win

    @objc.python_method
    def _refresh(self):
        config = self.controller.config
        self.shortcut.setTitle_(format_hotkey(config.hotkey))
        self.hint.setStringValue_("Opens the layout wheel. Press it while dragging a window to snap the window "
                                  "into a slot. Click the field to record a new shortcut.")
        self.gap.setIntValue_(int(config.gap))
        self.gap_value.setStringValue_(f"{int(config.gap)} px")
        self.center.setState_(1 if config.center_cursor else 0)
        self.hide.setState_(1 if config.hide_others else 0)

    def windowWillClose_(self, notification):
        self._stop_recording()

    # --- Tastenkombination aufnehmen ---------------------------------------

    def recordShortcut_(self, sender):
        self.shortcut.setTitle_("Type shortcut…")
        self.hint.setStringValue_("Press the new combination (at least one of ⌃ ⌥ ⇧ ⌘, or a function key). "
                                  "Esc cancels.")
        self.controller.tap.recorder = self._recorded

    @objc.python_method
    def _recorded(self, keycode, flags):
        if keycode == KEY_ESCAPE and not flags:
            self._stop_recording()
            self._refresh()
            return
        if not flags and not is_function_key(keycode):
            self.hint.setStringValue_("Please include a modifier key (⌃ ⌥ ⇧ ⌘) or use a function key. Esc cancels.")
            return
        self._stop_recording()
        self.controller.update_settings(hotkey=hotkey_string(keycode, flags))
        self._refresh()

    @objc.python_method
    def _stop_recording(self):
        self.controller.tap.recorder = None

    def resetShortcut_(self, sender):
        self._stop_recording()
        self.controller.update_settings(hotkey=DEFAULT_HOTKEY)
        self._refresh()

    # --- Übrige Einstellungen ------------------------------------------------

    def gapChanged_(self, sender):
        value = int(sender.intValue())
        self.gap_value.setStringValue_(f"{value} px")
        self.controller.update_settings(gap=value)

    def toggleCenter_(self, sender):
        self.controller.update_settings(center_cursor=bool(sender.state()))

    def toggleHide_(self, sender):
        self.controller.update_settings(hide_others=bool(sender.state()))

    def editLayouts_(self, sender):
        NSWorkspace.sharedWorkspace().openURL_(NSURL.fileURLWithPath_(str(cfg.CONFIG_PATH)))

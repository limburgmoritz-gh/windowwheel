"""Fenster finden und verschieben über die macOS Accessibility-API."""

import logging
import os
import time
from dataclasses import dataclass

import ApplicationServices as AS
import objc
import Quartz as Q
from AppKit import (
    NSApplicationActivateIgnoringOtherApps,
    NSApplicationActivationPolicyRegular,
    NSRunningApplication,
    NSWorkspace,
)

log = logging.getLogger(__name__)

OWN_PID = os.getpid()
AX_TIMEOUT = 0.3  # Sekunden – hängende Apps sollen das Rad nicht blockieren

# Private, aber seit Jahren stabile Funktion: AX-Fenster -> CGWindowID.
# Damit lässt sich ein angeklicktes Fenster (CGWindowList) exakt dem
# verschiebbaren AX-Element zuordnen.
_fns = {}
try:
    _hiservices = objc.loadBundle(
        "HIServices",
        {},
        bundle_path="/System/Library/Frameworks/ApplicationServices.framework/Frameworks/HIServices.framework",
    )
    objc.loadBundleFunctions(_hiservices, _fns, [("_AXUIElementGetWindow", b"i@o^I")])
except Exception:  # pragma: no cover
    log.warning("_AXUIElementGetWindow nicht verfügbar – Zuordnung über Position")
_get_window_id = _fns.get("_AXUIElementGetWindow")

_icon_cache = {}


def is_trusted(prompt=False):
    return bool(AS.AXIsProcessTrustedWithOptions({AS.kAXTrustedCheckOptionPrompt: prompt}))


def _attr(element, name):
    err, value = AS.AXUIElementCopyAttributeValue(element, name, None)
    return value if err == 0 else None


def _set(element, name, value):
    return AS.AXUIElementSetAttributeValue(element, name, value) == 0


def get_frame(element):
    pos, size = _attr(element, "AXPosition"), _attr(element, "AXSize")
    if pos is None or size is None:
        return None
    _, p = AS.AXValueGetValue(pos, AS.kAXValueCGPointType, None)
    _, s = AS.AXValueGetValue(size, AS.kAXValueCGSizeType, None)
    return (p.x, p.y, s.width, s.height)


@dataclass(eq=False)
class Window:
    wid: int
    pid: int
    app_name: str
    title: str
    element: object
    frame: tuple
    minimized: bool = False

    def app(self):
        return NSRunningApplication.runningApplicationWithProcessIdentifier_(self.pid)

    def icon(self):
        if self.pid not in _icon_cache:
            app = self.app()
            _icon_cache[self.pid] = app.icon() if app else None
        return _icon_cache[self.pid]


def _window_order():
    """CGWindowID -> Z-Position (0 = vorderstes Fenster) aller sichtbaren Fenster."""
    infos = Q.CGWindowListCopyWindowInfo(
        Q.kCGWindowListOptionOnScreenOnly | Q.kCGWindowListExcludeDesktopElements,
        Q.kCGNullWindowID,
    ) or []
    return {
        info["kCGWindowNumber"]: idx
        for idx, info in enumerate(infos)
        if info.get("kCGWindowLayer") == 0
    }


def list_windows(screen_rect=None):
    """Normale Fenster aller Apps, sichtbare zuerst in Z-Reihenfolge.

    Mit screen_rect (Quartz) nur Fenster, deren Mitte auf diesem Bildschirm liegt.
    """
    order = _window_order()
    windows = []
    for app in NSWorkspace.sharedWorkspace().runningApplications():
        pid = app.processIdentifier()
        if pid == OWN_PID or app.activationPolicy() != NSApplicationActivationPolicyRegular:
            continue
        app_el = AS.AXUIElementCreateApplication(pid)
        AS.AXUIElementSetMessagingTimeout(app_el, AX_TIMEOUT)
        for el in _attr(app_el, "AXWindows") or []:
            subrole = _attr(el, "AXSubrole")
            if subrole != "AXStandardWindow":
                continue
            frame = get_frame(el)
            if frame is None or frame[2] < 80 or frame[3] < 60:
                continue
            if screen_rect is not None and not _center_in(frame, screen_rect):
                continue
            wid = 0
            if _get_window_id is not None:
                err, value = _get_window_id(el, None)
                wid = value if err == 0 else 0
            windows.append(
                Window(
                    wid=wid,
                    pid=pid,
                    app_name=app.localizedName() or "?",
                    title=_attr(el, "AXTitle") or "",
                    element=el,
                    frame=frame,
                    minimized=bool(_attr(el, "AXMinimized")),
                )
            )
    windows.sort(key=lambda w: (order.get(w.wid, 10_000), w.app_name.lower(), w.title.lower()))
    return windows


def set_frame(window, rect):
    x, y, w, h = rect
    el = window.element
    app = window.app()
    if app is not None and app.isHidden():
        app.unhide()
    if _attr(el, "AXMinimized"):
        _set(el, "AXMinimized", False)
        window.minimized = False
    app_el = AS.AXUIElementCreateApplication(window.pid)
    AS.AXUIElementSetMessagingTimeout(app_el, AX_TIMEOUT)
    # "Enhanced UI" (z.B. Chrome/Electron mit VoiceOver-Hooks) animiert und
    # verschluckt Größenänderungen – kurz abschalten, wie Rectangle das tut.
    enhanced = bool(_attr(app_el, "AXEnhancedUserInterface"))
    if enhanced:
        _set(app_el, "AXEnhancedUserInterface", False)
    # Größe -> Position -> Größe -> Position: Maximierte Fenster ignorieren eine
    # Höhenänderung, wenn sie zuerst verschoben werden; beim Wechsel auf einen
    # größeren Bildschirm begrenzt dagegen der alte Bildschirm die erste Größe.
    _set_size(el, w, h)
    _set_pos(el, x, y)
    _set_size(el, w, h)
    _set_pos(el, x, y)
    _fit(el, rect)
    if enhanced:
        _set(app_el, "AXEnhancedUserInterface", True)
    window.frame = get_frame(el) or rect


def _set_pos(el, x, y):
    _set(el, "AXPosition", AS.AXValueCreate(AS.kAXValueCGPointType, Q.CGPointMake(x, y)))


def _set_size(el, w, h):
    _set(el, "AXSize", AS.AXValueCreate(AS.kAXValueCGSizeType, Q.CGSizeMake(w, h)))


def _fit(el, rect):
    """Apps mit Rastergrößen (z.B. Terminal: ganze Zeilen/Spalten) passen nie exakt.

    Dann das Fenster so weit verkleinern, dass es nicht in den Abstand ragt,
    und mittig in den Slot setzen – die Ränder bleiben so symmetrisch.
    """
    x, y, w, h = rect
    got = get_frame(el)
    if got is not None and (got[2] > w + 0.5 or got[3] > h + 0.5):
        # Manche Apps (Firefox, Electron) übernehmen die Größe erst im zweiten Anlauf.
        time.sleep(0.04)
        _set_size(el, w, h)
        _set_pos(el, x, y)
        got = get_frame(el)
    req_w, req_h = w, h
    for _ in range(3):
        if got is None or (got[2] <= w + 0.5 and got[3] <= h + 0.5):
            break
        req_w -= max(0.0, got[2] - w)
        req_h -= max(0.0, got[3] - h)
        _set_size(el, req_w, req_h)
        got = get_frame(el)
    if got is None:
        return
    cx, cy = x + round((w - got[2]) / 2), y + round((h - got[3]) / 2)
    if abs(got[0] - cx) > 0.5 or abs(got[1] - cy) > 0.5:
        _set_pos(el, cx, cy)


def _center_in(frame, rect):
    cx, cy = frame[0] + frame[2] / 2, frame[1] + frame[3] / 2
    return rect[0] <= cx <= rect[0] + rect[2] and rect[1] <= cy <= rect[1] + rect[3]


def _contained(frame, rect, tolerance=1.0):
    return (frame[0] >= rect[0] - tolerance and frame[1] >= rect[1] - tolerance
            and frame[0] + frame[2] <= rect[0] + rect[2] + tolerance
            and frame[1] + frame[3] <= rect[1] + rect[3] + tolerance)


def tuck_behind(keep, windows, screen_rect, cover):
    """Nicht gewählte Fenster auf diesem Bildschirm hinter ein gewähltes Fenster schieben.

    Sie bekommen exakt den Rahmen eines gewählten Fensters (cover) und liegen
    dahinter – unsichtbar, aber weiterhin normale Fenster, die in Mission
    Control und im App-Umschalter erscheinen. Nur Fenster, die wegen einer
    Mindestgröße nicht ganz dahinter passen, werden minimiert.
    """
    keep_ids = {id(w) for w in keep}
    for w in windows:
        if id(w) in keep_ids or w.minimized or not _center_in(w.frame, screen_rect):
            continue
        app = w.app()
        if app is None or app.isHidden():
            continue
        set_frame(w, cover)
        if not _contained(w.frame, cover):
            _set(w.element, "AXMinimized", True)
            w.minimized = True


def focus(window):
    """Fenster nach vorne holen und dessen App aktivieren."""
    el = window.element
    AS.AXUIElementPerformAction(el, "AXRaise")
    _set(el, "AXMain", True)
    app_el = AS.AXUIElementCreateApplication(window.pid)
    _set(app_el, "AXFrontmost", True)
    app = window.app()
    if app is not None:
        app.activateWithOptions_(NSApplicationActivateIgnoringOtherApps)


def focused_window():
    """Aktives Fenster der vorderen App als Window, oder None."""
    app = NSWorkspace.sharedWorkspace().frontmostApplication()
    if app is None or app.processIdentifier() == OWN_PID:
        return None
    app_el = AS.AXUIElementCreateApplication(app.processIdentifier())
    AS.AXUIElementSetMessagingTimeout(app_el, AX_TIMEOUT)
    el = _attr(app_el, "AXFocusedWindow")
    if el is None or _attr(el, "AXSubrole") != "AXStandardWindow":
        return None
    wid = 0
    if _get_window_id is not None:
        err, value = _get_window_id(el, None)
        wid = value if err == 0 else 0
    return Window(wid=wid, pid=app.processIdentifier(), app_name=app.localizedName() or "?",
                  title=_attr(el, "AXTitle") or "", element=el, frame=get_frame(el) or (0, 0, 0, 0))


def window_by_id(wid):
    """Verschiebbares AX-Fenster zu einer CGWindowID, oder None."""
    if _get_window_id is None:
        return None
    infos = Q.CGWindowListCopyWindowInfo(Q.kCGWindowListOptionIncludingWindow, wid) or []
    if not infos:
        return None
    pid = infos[0]["kCGWindowOwnerPID"]
    app = NSRunningApplication.runningApplicationWithProcessIdentifier_(pid)
    app_el = AS.AXUIElementCreateApplication(pid)
    AS.AXUIElementSetMessagingTimeout(app_el, AX_TIMEOUT)
    for el in _attr(app_el, "AXWindows") or []:
        err, value = _get_window_id(el, None)
        if err == 0 and value == wid:
            return Window(wid=wid, pid=pid, app_name=(app.localizedName() if app else "?") or "?",
                          title=_attr(el, "AXTitle") or "", element=el, frame=get_frame(el) or (0, 0, 0, 0))
    return None


def visible_window_frames():
    """(wid, frame) aller sichtbaren fremden Fenster, vorderstes zuerst."""
    infos = Q.CGWindowListCopyWindowInfo(
        Q.kCGWindowListOptionOnScreenOnly | Q.kCGWindowListExcludeDesktopElements,
        Q.kCGNullWindowID,
    ) or []
    result = []
    for info in infos:
        if info.get("kCGWindowLayer") != 0 or info.get("kCGWindowOwnerPID") == OWN_PID:
            continue
        if info.get("kCGWindowAlpha", 1) <= 0.01:
            continue
        b = info["kCGWindowBounds"]
        result.append((info["kCGWindowNumber"], (b["X"], b["Y"], b["Width"], b["Height"])))
    return result

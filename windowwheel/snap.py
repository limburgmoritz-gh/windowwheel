"""Einrast-Modus: Fenster ziehen + Hotkey -> Slots des zuletzt gewählten Layouts.

Das Overlay lässt dabei alle Mausklicks durch (das Fenster wird ganz normal
weitergezogen); die Mausposition kommt über den Event-Tap.
"""

import logging

import Quartz as Q
from AppKit import NSBezierPath, NSMakeRect

from . import drawing as d
from . import layers as L
from .geometry import cg_to_view_rect, cocoa_to_cg_rect, gap_for_screen, slot_rects
from .wheel import KEY_ESC

log = logging.getLogger(__name__)



def _distance(rect, point):
    x, y, w, h = rect
    dx = max(x - point[0], 0, point[0] - (x + w))
    dy = max(y - point[1], 0, point[1] - (y + h))
    return (dx * dx + dy * dy) ** 0.5


class SnapMode:
    KEYS = {KEY_ESC}
    backdrop = False     # kein Hintergrundbild – man sieht seine Fenster
    passthrough = True   # Overlay nimmt keine Mausklicks an

    def __init__(self, controller, window, layout, screen, gap):
        self.controller = controller
        self.window = window
        self.layout = layout
        self.screen = screen
        self.slots = slot_rects(layout.slots, screen, gap_for_screen(layout.gap, screen, gap))
        self.highlight = None
        self._glass = []

    # --- Ebenen -------------------------------------------------------------

    def attach(self, overlay):
        sf = self.screen.frame()
        for rect in self.slots:
            g = L.glass(cg_to_view_rect(rect, sf), 18)
            overlay.add_below_view(g)
            self._glass.append(g)
        pill = self._pill(overlay.view)
        g = L.glass(pill, pill.size.height / 2)
        overlay.add_below_view(g)
        self._glass.append(g)

    def detach(self, overlay):
        for g in self._glass:
            g.removeFromSuperview()
        self._glass = []

    # --- Zeichnen -----------------------------------------------------------

    def _hint(self):
        return f"{self.layout.name}     Release to snap     {self.controller.hotkey_label} / esc  drop normally"

    def _pill(self, view):
        text = self._hint()
        w = d.text_width(text, 13) + 48
        vf, sf = self.screen.visibleFrame(), self.screen.frame()
        top = vf.origin.y - sf.origin.y + vf.size.height
        return NSMakeRect((view.bounds().size.width - w) / 2, top - 30 - 40, w, 40)

    def draw(self, view):
        d.rgba(0, 0, 0, 0.08).setFill()
        NSBezierPath.fillRect_(view.bounds())
        sf = self.screen.frame()
        for i, rect in enumerate(self.slots):
            r = cg_to_view_rect(rect, sf)
            if i == self.highlight:
                d.rounded(r, 18, fill=d.white(0.22), stroke=d.white(0.95), width=3)
            else:
                d.rounded(r, 18, stroke=d.white(0.35), width=1.5)
            d.text(str(i + 1), r, size=min(96, r.size.height * 0.25), weight=d.BOLD,
                   color=d.white(0.9 if i == self.highlight else 0.35), align="center")
        pill = self._pill(view)
        d.text(self._hint(), pill, size=13, color=d.white(0.92), align="center")

    # --- Eingabe (Mausposition aus dem Event-Tap) ----------------------------

    def _slot_at(self, point):
        inside = [i for i, r in enumerate(self.slots) if _distance(r, point) == 0]
        if inside:
            return inside[0]
        # In einem Abstand oder Rand: nächstgelegenes Feld.
        return min(range(len(self.slots)), key=lambda i: _distance(self.slots[i], point))

    def mouse(self, etype, point):
        screen_cg = cocoa_to_cg_rect(self.screen.frame())
        on_screen = (screen_cg[0] <= point.x < screen_cg[0] + screen_cg[2]
                     and screen_cg[1] <= point.y < screen_cg[1] + screen_cg[3])
        if not on_screen:
            self.controller.snap_screen_changed(self, point)
            return
        if etype == Q.kCGEventLeftMouseUp:
            self.controller.finish_snap(self)
            return
        idx = self._slot_at((point.x, point.y))
        if idx != self.highlight:
            self.highlight = idx
            self.controller.overlay.redraw()

    def key(self, keycode, flags):
        if keycode == KEY_ESC:
            self.controller.cancel()

"""Das Radmenü zur Layout-Auswahl (Liquid-Glass-Scheibe)."""

import math

from AppKit import NSAnimationContext, NSBezierPath, NSMakePoint, NSMakeRect

from . import drawing as d
from . import layers

KEY_ESC, KEY_RETURN, KEY_ENTER, KEY_TAB = 53, 36, 76, 48
KEY_LEFT, KEY_RIGHT, KEY_DOWN, KEY_UP = 123, 124, 125, 126
DIGITS = {18: 0, 19: 1, 20: 2, 21: 3, 23: 4, 22: 5, 26: 6, 28: 7, 25: 8}
SHIFT = 1 << 17


class WheelMode:
    KEYS = {KEY_ESC, KEY_RETURN, KEY_ENTER, KEY_TAB, KEY_LEFT, KEY_RIGHT, KEY_UP, KEY_DOWN, *DIGITS}

    def __init__(self, controller, layouts, screen):
        self.controller = controller
        self.layouts = layouts
        self.screen = screen
        vf = screen.visibleFrame()
        self.aspect = vf.size.width / max(vf.size.height, 1)
        self.highlight = None
        self._glass = []

    # --- Glas ---------------------------------------------------------------

    def attach(self, overlay):
        center, r_out, r_in = self._geometry(overlay.view)
        disk = layers.glass(NSMakeRect(center.x - r_out, center.y - r_out, 2 * r_out, 2 * r_out), r_out,
                            tint=d.rgba(0.05, 0.05, 0.08, 0.35))
        r = r_in - 8
        hub = layers.glass(NSMakeRect(center.x - r, center.y - r, 2 * r, 2 * r), r,
                           tint=d.rgba(0.02, 0.02, 0.04, 0.55))
        for g in (disk, hub):
            overlay.add_below_view(g)
        self._glass = [disk, hub]

    def detach(self, overlay):
        glass, self._glass = self._glass, []
        if not overlay.visible or overlay.closing:
            for g in glass:
                g.removeFromSuperview()
            return

        def changes(ctx):
            ctx.setDuration_(0.2)
            for g in glass:
                g.animator().setAlphaValue_(0.0)

        def done():
            for g in glass:
                g.removeFromSuperview()

        NSAnimationContext.runAnimationGroup_completionHandler_(changes, done)

    # --- Geometrie ----------------------------------------------------------

    def _geometry(self, view):
        b = view.bounds()
        center = NSMakePoint(b.size.width / 2, b.size.height / 2)
        r_out = min(330.0, 0.42 * min(b.size.width, b.size.height))
        r_in = r_out * 0.38
        return center, r_out, r_in

    def _segment(self):
        return 360.0 / len(self.layouts)

    def _index_at(self, view, point):
        center, r_out, r_in = self._geometry(view)
        dx, dy = point.x - center.x, point.y - center.y
        dist = math.hypot(dx, dy)
        if dist > r_out * 1.7:
            return None, dist
        if dist < r_in * 0.4:
            return self.highlight, dist  # Totzone in der Mitte: Auswahl behalten
        angle = math.degrees(math.atan2(dy, dx))
        idx = round((90.0 - angle) / self._segment()) % len(self.layouts)
        return idx, dist

    # --- Zeichnen -----------------------------------------------------------

    def _wedge(self, center, r_out, r_in, a0, a1):
        path = NSBezierPath.bezierPath()
        path.appendBezierPathWithArcWithCenter_radius_startAngle_endAngle_clockwise_(center, r_out, a0, a1, False)
        path.appendBezierPathWithArcWithCenter_radius_startAngle_endAngle_clockwise_(center, r_in, a1, a0, True)
        path.closePath()
        return path

    def draw(self, view):
        d.rgba(0, 0, 0, 0.12).setFill()
        NSBezierPath.fillRect_(view.bounds())

        center, r_out, r_in = self._geometry(view)
        n = len(self.layouts)
        seg = self._segment()
        band = r_out - r_in
        r_mid = (r_out + r_in) / 2

        # Trennlinien zwischen den Segmenten
        if n > 1:
            for i in range(n):
                a = math.radians(90.0 - i * seg + seg / 2)
                line = NSBezierPath.bezierPath()
                line.moveToPoint_(NSMakePoint(center.x + (r_in + 6) * math.cos(a), center.y + (r_in + 6) * math.sin(a)))
                line.lineToPoint_(NSMakePoint(center.x + (r_out - 10) * math.cos(a), center.y + (r_out - 10) * math.sin(a)))
                line.setLineWidth_(1.0)
                d.white(0.14).setStroke()
                line.stroke()

        for i, layout in enumerate(self.layouts):
            hl = i == self.highlight
            mid = 90.0 - i * seg
            if hl:
                inset = min(2.0, seg * 0.03)
                if n == 1:
                    path = NSBezierPath.bezierPathWithOvalInRect_(
                        NSMakeRect(center.x - r_out + 6, center.y - r_out + 6, 2 * r_out - 12, 2 * r_out - 12))
                else:
                    path = self._wedge(center, r_out - 6, r_in + 4, mid - seg / 2 + inset, mid + seg / 2 - inset)
                d.white(0.20).setFill()
                path.fill()
                d.white(0.55).setStroke()
                path.setLineWidth_(1.2)
                path.stroke()

            px = center.x + r_mid * math.cos(math.radians(mid))
            py = center.y + r_mid * math.sin(math.radians(mid))
            arc = math.radians(seg) * r_mid
            pw = min(150.0, arc * 0.62, band * 0.8)
            ph = pw / self.aspect
            if ph > band * 0.45:
                ph = band * 0.45
                pw = ph * self.aspect
            prect = NSMakeRect(px - pw / 2, py - ph / 2 + 10, pw, ph)
            d.layout_preview(
                prect,
                layout.slots,
                slot_fill=d.white(0.92 if hl else 0.38),
                frame_stroke=d.white(0.95 if hl else 0.45),
            )
            label_w = min(arc * 0.9, band * 1.1)
            d.text(layout.name, NSMakeRect(px - label_w / 2, prect.origin.y - 24, label_w, 18),
                   size=13, weight=d.SEMIBOLD, color=d.white(1.0 if hl else 0.85), align="center")
            if i < 9:
                d.text(str(i + 1), NSMakeRect(px - 20, prect.origin.y + ph + 3, 40, 14),
                       size=10, weight=d.BOLD, color=d.white(0.85 if hl else 0.4), align="center")

        self._draw_center(center, r_in)

    def _draw_center(self, c, r_in):
        r = r_in - 8
        if self.highlight is None:
            d.text("Layout wählen", NSMakeRect(c.x - r, c.y + 4, 2 * r, 24),
                   size=17, weight=d.BOLD, align="center")
            d.text("Maus bewegen · ⇥ · 1–9", NSMakeRect(c.x - r, c.y - 22, 2 * r, 18),
                   size=12, color=d.white(0.6), align="center")
            return

        layout = self.layouts[self.highlight]
        pw = r * 1.25
        ph = min(pw / self.aspect, r * 0.7)
        pw = ph * self.aspect if pw / self.aspect > ph else pw
        prect = NSMakeRect(c.x - pw / 2, c.y + 2, pw, ph)
        d.layout_preview(prect, layout.slots, slot_fill=d.white(0.35), frame_stroke=d.white(0.75),
                         numbers=True, number_color=d.white(0.95))
        d.text(layout.name, NSMakeRect(c.x - r + 10, c.y - 28, 2 * r - 20, 22),
               size=16, weight=d.BOLD, align="center")
        d.text(f"{len(layout.slots)} Fenster", NSMakeRect(c.x - r, c.y - 48, 2 * r, 16),
               size=12, color=d.white(0.6), align="center")

    # --- Eingabe ------------------------------------------------------------

    def _set_highlight(self, view, idx):
        if idx != self.highlight:
            self.highlight = idx
            view.setNeedsDisplay_(True)

    def mouse_moved(self, view, point):
        idx, _ = self._index_at(view, point)
        self._set_highlight(view, idx)

    def mouse_down(self, view, point):
        idx, dist = self._index_at(view, point)
        _, r_out, _ = self._geometry(view)
        if dist > r_out * 1.7:
            self.controller.cancel()
        elif idx is not None:
            self.controller.select_layout(idx)

    def right_mouse_down(self, view, point):
        self.controller.cancel()

    def cycle(self, step):
        n = len(self.layouts)
        self.highlight = 0 if self.highlight is None and step > 0 else ((self.highlight or 0) + step) % n
        self.controller.overlay.redraw()

    def modifiers_released(self):
        # GTA-Verhalten: Halten, zielen, loslassen. Ohne Ziel bleibt das Rad offen.
        if self.highlight is not None:
            self.controller.select_layout(self.highlight)

    def key(self, keycode, flags):
        if keycode == KEY_ESC:
            self.controller.cancel()
        elif keycode in (KEY_RETURN, KEY_ENTER):
            if self.highlight is not None:
                self.controller.select_layout(self.highlight)
        elif keycode == KEY_TAB:
            self.cycle(-1 if flags & SHIFT else 1)
        elif keycode in (KEY_RIGHT, KEY_DOWN):
            self.cycle(1)
        elif keycode in (KEY_LEFT, KEY_UP):
            self.cycle(-1)
        elif keycode in DIGITS and DIGITS[keycode] < len(self.layouts):
            self.controller.select_layout(DIGITS[keycode])

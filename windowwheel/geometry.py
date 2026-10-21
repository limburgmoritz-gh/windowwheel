"""Koordinaten-Umrechnung.

Cocoa (NSScreen, NSView) hat den Ursprung unten links des Hauptbildschirms.
Quartz/Accessibility (CGWindowList, AXPosition) haben ihn oben links.
Alle Fenster- und Slot-Rechtecke werden hier als (x, y, w, h) in
Quartz-Koordinaten geführt.
"""

from AppKit import NSEvent, NSMakeRect, NSPointInRect, NSScreen


def primary_height():
    return NSScreen.screens()[0].frame().size.height


def cocoa_to_cg_rect(rect):
    x, y = rect.origin.x, rect.origin.y
    w, h = rect.size.width, rect.size.height
    return (x, primary_height() - (y + h), w, h)


def cg_to_view_rect(rect, screen_frame):
    """Quartz-Rechteck -> Koordinaten einer View, die screen_frame abdeckt."""
    x, y, w, h = rect
    cocoa_y = primary_height() - (y + h)
    return NSMakeRect(x - screen_frame.origin.x, cocoa_y - screen_frame.origin.y, w, h)


def view_point_to_cg(point, screen_frame):
    gx = point.x + screen_frame.origin.x
    gy = point.y + screen_frame.origin.y
    return (gx, primary_height() - gy)


def screen_under_mouse():
    loc = NSEvent.mouseLocation()
    for screen in NSScreen.screens():
        if NSPointInRect(loc, screen.frame()):
            return screen
    return NSScreen.mainScreen()


def screen_center_cg(screen):
    x, y, w, h = cocoa_to_cg_rect(screen.frame())
    return (x + w / 2, y + h / 2)


def slot_rects(slots, screen, gap):
    """Anteils-Slots -> Pixel-Rechtecke (Quartz).

    gap ist ein Wert oder (horizontal, vertikal). Außenrand und Zwischenraum
    sind in jeder Richtung gleich groß – so bleibt alles symmetrisch.
    """
    gx, gy = gap if isinstance(gap, (tuple, list)) else (gap, gap)
    vx, vy, vw, vh = cocoa_to_cg_rect(screen.visibleFrame())
    hx, hy = gx / 2, gy / 2
    ax, ay, aw, ah = vx + hx, vy + hy, vw - gx, vh - gy
    rects = []
    for fx, fy, fw, fh in slots:
        x0 = round(ax + fx * aw + hx)
        y0 = round(ay + fy * ah + hy)
        x1 = round(ax + (fx + fw) * aw - hx)
        y1 = round(ay + (fy + fh) * ah - hy)
        rects.append((x0, y0, max(x1 - x0, 50), max(y1 - y0, 50)))
    return rects


def gap_for_screen(rel_gap, screen, default):
    """Layout-Abstand (Anteil von Breite/Höhe) -> px auf diesem Bildschirm.

    Relativ gespeichert sieht ein Layout auf Ultrawide und MacBook gleich aus.
    Gerade Werte, damit der halbe Abstand ganzzahlig und alles exakt symmetrisch bleibt.
    """
    if rel_gap is None:
        return (float(default), float(default))
    vf = screen.visibleFrame().size
    return (round(rel_gap[0] * vf.width / 2) * 2.0, round(rel_gap[1] * vf.height / 2) * 2.0)


def gap_to_relative(gap, screen):
    vf = screen.visibleFrame().size
    return (round(gap[0] / vf.width, 5), round(gap[1] / vf.height, 5))


def intersection_area(a, b):
    w = min(a[0] + a[2], b[0] + b[2]) - max(a[0], b[0])
    h = min(a[1] + a[3], b[1] + b[3]) - max(a[1], b[1])
    return w * h if w > 0 and h > 0 else 0


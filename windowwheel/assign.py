"""Zuweisungsmodus im Mission-Control-Stil.

Alle offenen Fenster erscheinen als Vorschaubilder im Raster (Core-Animation-
Layer mit Feder-Animationen), oben zeigt eine Glas-Karte das Layout mit dem
aktiven Slot. Ein Klick auf ein Vorschaubild lässt es in seinen Slot der
Mini-Karte fliegen, die übrigen Kacheln gleiten an ihre neuen Plätze.
"""

import logging
import math

import Quartz as Q
from AppKit import NSAnimationContext, NSBezierPath, NSFont, NSMakeRect, NSPointInRect
from PyObjCTools import AppHelper

from . import ax
from . import drawing as d
from . import layers as L
from .geometry import cg_to_view_rect, cocoa_to_cg_rect, gap_for_screen, slot_rects
from .live import LiveThumbnails
from .thumbnails import ThumbnailLoader
from .wheel import DIGITS, KEY_ENTER, KEY_ESC, KEY_RETURN, KEY_TAB

log = logging.getLogger(__name__)

KEY_SPACE, KEY_DELETE = 49, 51

CAPTION_H = 26.0     # Höhe der Beschriftung unter einem Vorschaubild
CAPTION_GAP = 10.0   # Abstand Vorschaubild -> Beschriftung
TILE_GAP = 40.0      # Abstand zwischen den Kacheln
MAX_TILE_W = 560.0   # damit wenige Fenster nicht riesig werden
TYPICAL_ASPECT = 1.6
ICON = 18.0
HINT = ("Klick  Fenster setzen     Ziehen  Abstand (2× klicken: zurücksetzen)     ␣  überspringen     "
        "⌫  zurück     ⏎  fertig     esc  abbrechen")
MIN_SLOT_W, MIN_SLOT_H = 280, 200  # so klein dürfen Fenster beim Abstand-Ziehen höchstens werden
DRAG_THRESHOLD = 3.0


class Tile:
    """Vorschaubild + Beschriftung eines Fensters als Core-Animation-Layer."""

    def __init__(self, window, host, scale):
        self.window = window
        self.in_map = False
        self.live = False

        img = Q.CALayer.layer()
        img.setCornerRadius_(12.0)
        img.setMasksToBounds_(True)
        img.setBorderWidth_(1.0)
        img.setBorderColor_(L.white(0.22))
        img.setBackgroundColor_(L.white(0.10))
        img.setContentsGravity_(Q.kCAGravityResizeAspectFill)
        img.setContentsScale_(scale)
        placeholder = Q.CALayer.layer()
        placeholder.setContents_(window.icon())
        placeholder.setContentsGravity_(Q.kCAGravityResizeAspect)
        img.addSublayer_(placeholder)

        caption = Q.CALayer.layer()
        caption.setCornerRadius_(CAPTION_H / 2)
        caption_icon = Q.CALayer.layer()
        caption_icon.setContents_(window.icon())
        caption_icon.setContentsGravity_(Q.kCAGravityResizeAspect)
        caption_icon.setContentsScale_(scale)
        text = Q.CATextLayer.layer()
        label = window.title or window.app_name
        if window.minimized:
            label += " · minimiert"
        text.setString_(label)
        text.setFont_(NSFont.systemFontOfSize_weight_(13, d.MEDIUM))
        text.setFontSize_(13)
        text.setForegroundColor_(L.white(0.95))
        text.setTruncationMode_(Q.kCATruncationEnd)
        text.setContentsScale_(scale)
        text.setShadowOpacity_(0.5)
        text.setShadowRadius_(3)
        text.setShadowOffset_(Q.CGSizeMake(0, -1))
        caption.addSublayer_(caption_icon)
        caption.addSublayer_(text)

        host.addSublayer_(img)
        host.addSublayer_(caption)
        self.img, self.placeholder, self.caption = img, placeholder, caption
        self.caption_icon, self.text = caption_icon, text
        self.text_w = d.text_width(label, 13, d.MEDIUM) + 2

    def set_image(self, image):
        """Standbild (Schnappschuss) – nur bis der Live-Stream läuft."""
        if self.live:
            return
        self._drop_placeholder()
        self.img.setContents_(image)  # implizite Überblendung

    def set_live(self, surface):
        """Live-Bild aus dem Stream; läuft auf einer Hintergrund-Queue."""
        Q.CATransaction.begin()
        Q.CATransaction.setDisableActions_(True)  # keine Überblendung pro Bild
        self.img.setContents_(surface)
        Q.CATransaction.commit()
        if not self.live:
            self.live = True
            AppHelper.callAfter(self._drop_placeholder)

    def _drop_placeholder(self):
        if self.placeholder is not None:
            self.placeholder.removeFromSuperlayer()
            self.placeholder = None

    def _caption_rect(self, thumb):
        w = min(self.text_w + ICON + 26, thumb.size.width + 40)
        return NSMakeRect(thumb.origin.x + (thumb.size.width - w) / 2,
                          thumb.origin.y - CAPTION_GAP - CAPTION_H, w, CAPTION_H)

    def place(self, thumb, animated=True, delay=0.0, from_rect=None):
        cap = self._caption_rect(thumb)

        def inner():
            self.caption_icon.setFrame_(Q.CGRectMake(10, (CAPTION_H - ICON) / 2, ICON, ICON))
            self.text.setFrame_(Q.CGRectMake(ICON + 16, 4, cap.size.width - ICON - 26, CAPTION_H - 8))
            if self.placeholder is not None:
                s = min(64.0, thumb.size.width * 0.4, thumb.size.height * 0.5)
                self.placeholder.setFrame_(Q.CGRectMake((thumb.size.width - s) / 2, (thumb.size.height - s) / 2, s, s))

        L.no_actions(inner)
        L.move(self.img, thumb, animated, delay, from_rect)
        L.move(self.caption, cap, animated and not self.in_map, delay)

    def set_hover(self, on):
        Q.CATransaction.begin()
        Q.CATransaction.setAnimationDuration_(0.18)
        self.img.setBorderWidth_(3.0 if on else 1.0)
        self.img.setBorderColor_(L.white(0.95 if on else 0.22))
        self.caption.setBackgroundColor_(L.white(0.24) if on else None)
        Q.CATransaction.commit()
        L.scale(self.img, 1.035 if on else 1.0)

    def to_map(self, rect):
        self.in_map = True
        self.set_hover(False)
        self.img.setZPosition_(10)
        L.move(self.img, rect, damping=24, stiffness=200)
        L.no_actions(lambda: self.img.setCornerRadius_(5.0))
        L.fade(self.caption, 0.0, 0.15)

    def place_in_map(self, rect):
        L.move(self.img, rect, animated=False)

    def from_map(self):
        self.in_map = False
        self.img.setZPosition_(5)
        L.no_actions(lambda: self.img.setCornerRadius_(12.0))
        L.fade(self.caption, 1.0, 0.25, delay=0.15)


class AssignMode:
    KEYS = {KEY_ESC, KEY_RETURN, KEY_ENTER, KEY_SPACE, KEY_DELETE, KEY_TAB, *DIGITS}

    def __init__(self, controller, layout, screen, gap, windows=None, loader=None):
        self.controller = controller
        self.layout = layout
        self.screen = screen
        vf = screen.visibleFrame()
        self.aspect = vf.size.width / max(vf.size.height, 1)
        self.default_gap = (float(gap), float(gap))
        self.initial_gap = gap_for_screen(layout.gap, screen, gap)
        self.gap = self.initial_gap
        self.slots = slot_rects(layout.slots, screen, self.gap)
        self._drag = None
        self.assigned = [None] * len(self.slots)
        self.skipped = set()
        self.history = []  # (slot, window, ursprünglicher Rahmen)
        self.active = 0
        self.hover = None  # Kachel unter der Maus
        self.closing = False
        if windows is None:
            windows = ax.list_windows(cocoa_to_cg_rect(screen.frame()))
        self.windows = windows
        self.loader = loader or ThumbnailLoader()
        self.loader.on_update = self._thumb_ready
        if loader is None:
            self.loader.load([w.wid for w in self.windows])
        self.tiles = {}
        self._tiles_by_wid = {}
        self.live = LiveThumbnails(self._live_frame)
        self._targets = []
        self._glass = []
        self.host = None
        self.view = None

    # --- Ebenen -------------------------------------------------------------

    def attach(self, overlay):
        view = self.view = overlay.view
        card, _, _ = self._map(view)
        pill = self._pill(view)
        self._glass = [L.glass(card, 28), L.glass(pill, pill.size.height / 2)]
        for g in self._glass:
            g.setAlphaValue_(0.0)
            overlay.add_below_view(g)
        NSAnimationContext.beginGrouping()
        NSAnimationContext.currentContext().setDuration_(0.25)
        for g in self._glass:
            g.animator().setAlphaValue_(1.0)
        NSAnimationContext.endGrouping()

        self.host = L.host_view(view.bounds())
        self.host.setAutoresizingMask_(view.autoresizingMask())
        overlay.add_above_view(self.host)

        scale = self.screen.backingScaleFactor()
        screen_cg = cocoa_to_cg_rect(self.screen.frame())
        self._targets = self._grid(view)
        for i, (window, rect) in enumerate(self._targets):
            tile = Tile(window, self.host.layer(), scale)
            self.tiles[id(window)] = tile
            self._tiles_by_wid[window.wid] = tile
            image = self.loader.images.get(window.wid)
            if image is not None:
                tile.set_image(image)
            # Wie Mission Control: von der echten Fensterposition ins Raster gleiten.
            if not window.minimized and ax._center_in(window.frame, screen_cg):
                start = cg_to_view_rect(window.frame, self.screen.frame())
                tile.place(rect, delay=i * 0.012, from_rect=start)
            else:
                tile.place(rect, animated=False)
                L.no_actions(lambda: tile.img.setOpacity_(0.0))
                L.fade(tile.img, 1.0, 0.3, delay=0.08)
            L.no_actions(lambda: tile.caption.setOpacity_(0.0))
            L.fade(tile.caption, 1.0, 0.3, delay=0.2)
        # Live-Vorschau: Fenster laufen in den Kacheln weiter (z.B. Videos).
        self.live.start([w.wid for w in self.windows if not w.minimized])

    def detach(self, overlay):
        self.loader.cancel()
        self.live.stop()
        for g in self._glass:
            g.removeFromSuperview()
        if self.host is not None:
            self.host.removeFromSuperview()
        self._glass, self.host, self.tiles, self._tiles_by_wid = [], None, {}, {}

    def _live_frame(self, wid, surface):
        tile = self._tiles_by_wid.get(wid)
        if tile is not None:
            tile.set_live(surface)

    def _thumb_ready(self, wid):
        for tile in self.tiles.values():
            if tile.window.wid == wid:
                tile.set_image(self.loader.images[wid])

    # --- Daten --------------------------------------------------------------

    def candidates(self):
        taken = set(map(id, filter(None, self.assigned)))
        return [w for w in self.windows if id(w) not in taken]

    # --- Aktionen -----------------------------------------------------------

    def assign(self, window):
        slot = self.active
        original = ax.get_frame(window.element) or window.frame
        self.assigned[slot] = window
        self.skipped.discard(slot)
        self.history.append((slot, window, original))
        log.info("Slot %d <- %s – %s", slot + 1, window.app_name, window.title)

        self.hover = None
        self.tiles[id(window)].to_map(self._map(self.view)[2][slot])
        self._relayout()
        Q.CATransaction.flush()  # Animation starten, bevor die AX-Aufrufe den Main-Thread belegen
        AppHelper.callLater(0.03, self._move, window, self.slots[slot])
        self._advance()

    def _move(self, window, rect):
        ax.set_frame(window, rect)
        self.live.resize(window.wid, rect[2], rect[3])
        # Standbild in der neuen Größe nachladen, falls kein Live-Stream läuft.
        AppHelper.callLater(0.2, self.loader.load, [window.wid])

    def _next_open_slot(self):
        n = len(self.slots)
        for step in range(1, n + 1):
            idx = (self.active + step) % n
            if self.assigned[idx] is None and idx not in self.skipped:
                return idx
        return None

    def _advance(self):
        nxt = self._next_open_slot()
        if nxt is None:
            self.controller.finish_assign(self)
            return
        self.active = nxt
        self.controller.overlay.redraw()

    def skip(self):
        self.skipped.add(self.active)
        self._advance()

    def _unassign(self, slot):
        for pos, (s, window, original) in enumerate(self.history):
            if s == slot:
                del self.history[pos]
                self.assigned[slot] = None
                self.tiles[id(window)].from_map()
                Q.CATransaction.flush()
                AppHelper.callLater(0.03, ax.set_frame, window, original)
                return True
        return False

    def undo(self):
        if not self.history:
            return
        slot = self.history[-1][0]
        self._unassign(slot)
        self.skipped.discard(slot)
        self.active = slot
        self.hover = None
        self._relayout()
        self.controller.overlay.redraw()

    def select_slot(self, idx):
        if idx >= len(self.slots):
            return
        if self.assigned[idx] is not None:
            # Belegten Slot neu vergeben: altes Fenster zurück an seinen Platz.
            self._unassign(idx)
            self._relayout()
        self.skipped.discard(idx)
        self.active = idx
        self.controller.overlay.redraw()

    def _relayout(self):
        if self.view is None:
            return
        self._targets = self._grid(self.view)
        for window, rect in self._targets:
            self.tiles[id(window)].place(rect)

    def exit(self, cancelled, hide_others=False):
        """Abschlussanimation. Danach blendet der Controller das Overlay aus."""
        self.closing = True
        if self.hover is not None:
            self.hover.set_hover(False)
        sf = self.screen.frame()
        NSAnimationContext.beginGrouping()
        NSAnimationContext.currentContext().setDuration_(0.2)
        for g in self._glass:
            g.animator().setAlphaValue_(0.0)
        NSAnimationContext.endGrouping()

        originals = {id(w): frame for _, w, frame in self.history}
        placed = [w for w in self.assigned if w is not None]
        for tile in self.tiles.values():
            L.fade(tile.caption, 0.0, 0.12)
            if cancelled:
                frame = originals.get(id(tile.window), tile.window.frame)
                L.move(tile.img, cg_to_view_rect(frame, sf), damping=30, stiffness=240)
            elif tile.in_map:
                slot = self.assigned.index(tile.window)
                L.no_actions(lambda: tile.img.setCornerRadius_(10.0))
                L.move(tile.img, cg_to_view_rect(self.slots[slot], sf), damping=30, stiffness=240)
            else:
                L.fade(tile.img, 0.0, 0.2)
                L.scale(tile.img, 0.92)
        Q.CATransaction.flush()

        if cancelled:
            AppHelper.callLater(0.02, self.restore_all)
        elif hide_others and placed:
            # Hinter den größten gesetzten Slot, damit möglichst jedes Fenster ganz verdeckt ist.
            cover = max((self.slots[i] for i, w in enumerate(self.assigned) if w is not None),
                        key=lambda r: r[2] * r[3])
            AppHelper.callLater(0.02, ax.tuck_behind, placed, self.windows, cocoa_to_cg_rect(sf), cover)

    def restore_all(self):
        while self.history:
            _, window, original = self.history.pop()
            ax.set_frame(window, original)

    # --- Geometrie ----------------------------------------------------------

    def _map(self, view):
        """Glas-Karte oben -> (Karte, Bildschirm-Miniatur, [Slot-Rechtecke])."""
        b = view.bounds()
        mw = min(440.0, b.size.width * 0.28)
        mh = mw / self.aspect
        if mh > 150:
            mh = 150.0
            mw = mh * self.aspect
        pad = 26.0
        card_w = max(mw, 300.0) + 2 * pad
        card_h = pad + 30 + 14 + mh + 12 + 18 + pad - 6
        card = NSMakeRect((b.size.width - card_w) / 2, b.size.height - 64 - card_h, card_w, card_h)
        screen = NSMakeRect((b.size.width - mw) / 2, card.origin.y + pad - 6 + 18 + 12, mw, mh)
        # Maßstabsgetreu aus den echten Slots – so sieht man den Abstand live.
        vx, vy, vw, vh = cocoa_to_cg_rect(self.screen.visibleFrame())
        sx, sy = mw / vw, mh / vh
        rects = [
            NSMakeRect(screen.origin.x + (x - vx) * sx, screen.origin.y + mh - (y - vy + h) * sy, w * sx, h * sy)
            for x, y, w, h in self.slots
        ]
        return card, screen, rects

    def _pill(self, view):
        w = d.text_width(HINT, 12.5) + 44
        vf, sf = self.screen.visibleFrame(), self.screen.frame()
        return NSMakeRect((view.bounds().size.width - w) / 2, vf.origin.y - sf.origin.y + 24, w, 36)

    def _grid(self, view):
        """Raster der Vorschaubilder -> [(Fenster, Bild-Rechteck)]."""
        cands = self.candidates()
        if not cands:
            return []
        b = view.bounds()
        card, _, _ = self._map(view)
        pill = self._pill(view)
        left, right = 90.0, b.size.width - 90.0
        bottom = pill.origin.y + pill.size.height + 40.0
        top = card.origin.y - 50.0
        W, H = right - left, top - bottom
        label = CAPTION_GAP + CAPTION_H
        n = len(cands)

        best = None
        for cols in range(1, n + 1):
            rows = math.ceil(n / cols)
            cw = (W - TILE_GAP * (cols - 1)) / cols
            ch = (H - TILE_GAP * (rows - 1)) / rows - label
            if cw <= 0 or ch <= 0:
                continue
            size = min(cw, ch * TYPICAL_ASPECT, MAX_TILE_W)
            if best is None or size > best[0] + 0.5:
                best = (size, cols, rows)
        if best is None:
            return []
        size, cols, rows = best
        cw, ch = size, size / TYPICAL_ASPECT
        grid_h = rows * (ch + label) + (rows - 1) * TILE_GAP
        y_top = bottom + (H + grid_h) / 2

        result = []
        for i, window in enumerate(cands):
            row, col = divmod(i, cols)
            in_row = min(cols, n - row * cols)
            row_w = in_row * cw + (in_row - 1) * TILE_GAP
            x = left + (W - row_w) / 2 + col * (cw + TILE_GAP)
            y = y_top - (row + 1) * (ch + label) - row * TILE_GAP + label
            fw, fh = window.frame[2], window.frame[3]
            s = min(cw / fw, ch / fh)
            tw, th = fw * s, fh * s
            result.append((window, NSMakeRect(x + (cw - tw) / 2, y + (ch - th) / 2, tw, th)))
        return result

    # --- Zeichnen -----------------------------------------------------------

    def draw(self, view):
        d.rgba(0, 0, 0, 0.10).setFill()
        NSBezierPath.fillRect_(view.bounds())
        if self.closing:
            return
        card, screen, rects = self._map(view)
        top = card.origin.y + card.size.height
        d.text(f"Fenster {self.active + 1} von {len(self.slots)}", NSMakeRect(card.origin.x, top - 26 - 30, card.size.width, 30),
               size=20, weight=d.BOLD, align="center")
        gx, gy = self.gap
        info = f"{self.layout.name}   ·   Abstand  ↔ {gx:.0f} px   ↕ {gy:.0f} px"
        d.text(info, NSMakeRect(card.origin.x, screen.origin.y - 12 - 18, card.size.width, 18), size=12.5,
               weight=d.SEMIBOLD if self._dragging() else d.REGULAR,
               color=d.white(0.95 if self._dragging() else 0.6), align="center")
        d.rounded(screen, 8, fill=d.rgba(0, 0, 0, 0.22), stroke=d.white(0.35), width=1.0)
        for i, r in enumerate(rects):
            if self.assigned[i] is not None:
                continue  # dort liegt das Vorschaubild des Fensters
            if i == self.active:
                d.rounded(r, 5, fill=d.white(0.30), stroke=d.white(0.95), width=2)
                d.text(str(i + 1), r, size=min(28, r.size.height * 0.45), weight=d.BOLD, align="center")
            elif i in self.skipped:
                d.rounded(r, 5, fill=d.white(0.03), stroke=d.white(0.18), width=1, dash=[3, 4])
            else:
                d.rounded(r, 5, fill=d.white(0.10), stroke=d.white(0.28), width=1)
                d.text(str(i + 1), r, size=min(22, r.size.height * 0.4), weight=d.BOLD,
                       color=d.white(0.5), align="center")

        d.text(HINT, self._pill(view), size=12.5, color=d.white(0.9), align="center")
        if not self.candidates():
            b = view.bounds()
            d.text("Keine weiteren Fenster – ⏎ zum Beenden", NSMakeRect(0, b.size.height / 2 - 60, b.size.width, 30),
                   size=16, color=d.white(0.7), align="center")

    # --- Eingabe ------------------------------------------------------------

    def _tile_at(self, point):
        for window, rect in self._targets:
            hit = NSMakeRect(rect.origin.x, rect.origin.y - CAPTION_GAP - CAPTION_H,
                             rect.size.width, rect.size.height + CAPTION_GAP + CAPTION_H)
            if NSPointInRect(point, hit):
                return self.tiles.get(id(window))
        return None

    def mouse_moved(self, view, point):
        if self.closing:
            return
        tile = self._tile_at(point)
        if tile is not self.hover:
            if self.hover is not None:
                self.hover.set_hover(False)
            if tile is not None:
                tile.set_hover(True)
            self.hover = tile

    def mouse_down(self, view, point):
        if self.closing:
            return
        tile = self._tile_at(point)
        if tile is not None:
            self.assign(tile.window)
            return
        # Außerhalb der Kacheln: Klick (Slot wählen) oder Ziehen (Abstand).
        self._drag = {"start": point, "gap": self.gap, "moved": False}

    def mouse_dragged(self, view, point):
        drag = self._drag
        if drag is None or self.closing:
            return
        dx, dy = point.x - drag["start"].x, point.y - drag["start"].y
        if not drag["moved"] and math.hypot(dx, dy) < DRAG_THRESHOLD:
            return
        drag["moved"] = True
        # Rechts = mehr horizontaler, oben = mehr vertikaler Abstand (1 px Maus = 1 px Abstand).
        self.set_gap(drag["gap"][0] + dx, drag["gap"][1] + dy)

    def mouse_up(self, view, point, clicks):
        drag, self._drag = self._drag, None
        if drag is None or self.closing:
            return
        log.debug("Ziehen von (%.0f, %.0f) nach (%.0f, %.0f) -> Abstand %s",
                  drag["start"].x, drag["start"].y, point.x, point.y, self.gap)
        if drag["moved"]:
            self._apply_gap()
        elif clicks >= 2:
            self.set_gap(*self.default_gap)
            self._apply_gap()
        else:
            for i, r in enumerate(self._map(view)[2]):
                if NSPointInRect(point, r):
                    self.select_slot(i)
                    return
        self.controller.overlay.redraw()

    # --- Abstand ------------------------------------------------------------

    def _dragging(self):
        return self._drag is not None and self._drag["moved"]

    @property
    def gap_changed(self):
        return self.gap != self.initial_gap

    def set_gap(self, gx, gy):
        # Gerade Werte: halber Abstand bleibt ganzzahlig, Ränder exakt gleich.
        gx, gy = max(0.0, round(gx / 2) * 2), max(0.0, round(gy / 2) * 2)
        while True:
            rects = slot_rects(self.layout.slots, self.screen, (gx, gy))
            narrow = gx > 0 and min(r[2] for r in rects) < MIN_SLOT_W
            flat = gy > 0 and min(r[3] for r in rects) < MIN_SLOT_H
            if not (narrow or flat):
                break
            gx, gy = (max(0.0, gx - 2) if narrow else gx), (max(0.0, gy - 2) if flat else gy)
        if (gx, gy) == self.gap:
            return
        self.gap, self.slots = (gx, gy), rects
        map_rects = self._map(self.view)[2]
        for slot, window in enumerate(self.assigned):
            if window is not None:
                self.tiles[id(window)].place_in_map(map_rects[slot])
        self.controller.overlay.redraw()

    def _apply_gap(self):
        """Bereits gesetzte Fenster an den neuen Abstand anpassen (liegen unter dem Overlay)."""
        for slot, window in enumerate(self.assigned):
            if window is not None:
                AppHelper.callLater(0.01 * slot, ax.set_frame, window, self.slots[slot])

    def right_mouse_down(self, view, point):
        if not self.closing:
            self.undo()

    def key(self, keycode, flags):
        if self.closing:
            return
        if keycode == KEY_ESC:
            self.controller.cancel()
        elif keycode in (KEY_RETURN, KEY_ENTER):
            self.controller.finish_assign(self)
        elif keycode in (KEY_SPACE, KEY_TAB):
            self.skip()
        elif keycode == KEY_DELETE:
            self.undo()
        elif keycode in DIGITS:
            self.select_slot(DIGITS[keycode])

"""Bildschirmfüllendes Overlay, das ein "Mode"-Objekt (Rad oder Zuweisung) anzeigt.

Ebenen von hinten nach vorne:
  backdrop  – Hintergrundbild des Bildschirms (klar, ohne Blur)
  (Glasflächen des Modes, per attach eingefügt)
  view      – OverlayView, zeichnet den Mode und nimmt Maus-Events an
  (Layer-Träger des Modes für animierte Kacheln, per attach eingefügt)

Ein Mode implementiert draw(view) und optional attach/detach(overlay),
mouse_moved/mouse_down/right_mouse_down/scroll(view, point[, delta]).
"""

import objc
from AppKit import (
    NSAnimationContext,
    NSAppearance,
    NSAppearanceNameDarkAqua,
    NSBackingStoreBuffered,
    NSColor,
    NSCompositingOperationClear,
    NSMakeRect,
    NSPanel,
    NSRectFillUsingOperation,
    NSScreenSaverWindowLevel,
    NSTrackingActiveAlways,
    NSTrackingArea,
    NSTrackingInVisibleRect,
    NSTrackingMouseMoved,
    NSView,
    NSViewHeightSizable,
    NSViewWidthSizable,
    NSWindowAbove,
    NSWindowBelow,
    NSWindowCollectionBehaviorCanJoinAllSpaces,
    NSWindowCollectionBehaviorFullScreenAuxiliary,
    NSWindowCollectionBehaviorIgnoresCycle,
    NSWindowCollectionBehaviorStationary,
    NSWindowStyleMaskBorderless,
    NSWindowStyleMaskNonactivatingPanel,
    NSZeroRect,
)

from .wallpaper import wallpaper_image

FADE_IN = 0.18
# Minimal unter 100 % Deckkraft: Für macOS gilt das Overlay dann nicht als verdeckend.
# Sonst halten Browser, Video-Player & Co. ihr Bild an ("Fenster ist verdeckt") und
# die Live-Vorschau würde einfrieren. Optisch ist kein Unterschied zu sehen.
OVERLAY_ALPHA = 0.995


class OverlayPanel(NSPanel):
    # Rahmenlose Panels dürfen sonst nicht Key-Window werden.
    def canBecomeKeyWindow(self):
        return True

    def canBecomeMainWindow(self):
        return False


class OverlayView(NSView):
    def initWithFrame_(self, frame):
        self = objc.super(OverlayView, self).initWithFrame_(frame)
        if self is None:
            return None
        self.mode = None
        area = NSTrackingArea.alloc().initWithRect_options_owner_userInfo_(
            NSZeroRect,
            NSTrackingMouseMoved | NSTrackingActiveAlways | NSTrackingInVisibleRect,
            self,
            None,
        )
        self.addTrackingArea_(area)
        return self

    def acceptsFirstMouse_(self, event):
        return True

    def acceptsFirstResponder(self):
        return True

    @objc.python_method
    def _point(self, event):
        return self.convertPoint_fromView_(event.locationInWindow(), None)

    @objc.python_method
    def _forward(self, name, *args):
        handler = getattr(self.mode, name, None)
        if handler is not None:
            handler(self, *args)

    def drawRect_(self, rect):
        NSColor.clearColor().set()
        NSRectFillUsingOperation(self.bounds(), NSCompositingOperationClear)
        if self.mode is not None:
            self.mode.draw(self)

    def mouseMoved_(self, event):
        self._forward("mouse_moved", self._point(event))

    def mouseDragged_(self, event):
        name = "mouse_dragged" if hasattr(self.mode, "mouse_dragged") else "mouse_moved"
        self._forward(name, self._point(event))

    def mouseUp_(self, event):
        self._forward("mouse_up", self._point(event), event.clickCount())

    def mouseDown_(self, event):
        self._forward("mouse_down", self._point(event))

    def rightMouseDown_(self, event):
        self._forward("right_mouse_down", self._point(event))

    def scrollWheel_(self, event):
        self._forward("scroll", self._point(event), event.scrollingDeltaY())


def _fill(view):
    view.setAutoresizingMask_(NSViewWidthSizable | NSViewHeightSizable)
    return view


class Overlay:
    def __init__(self):
        panel = OverlayPanel.alloc().initWithContentRect_styleMask_backing_defer_(
            NSMakeRect(0, 0, 400, 400),
            NSWindowStyleMaskBorderless | NSWindowStyleMaskNonactivatingPanel,
            NSBackingStoreBuffered,
            False,
        )
        panel.setOpaque_(False)
        panel.setBackgroundColor_(NSColor.clearColor())
        panel.setHasShadow_(False)
        panel.setFloatingPanel_(True)
        panel.setLevel_(NSScreenSaverWindowLevel)  # nach setFloatingPanel_, das setzt sonst Level 3
        panel.setHidesOnDeactivate_(False)
        panel.setBecomesKeyOnlyIfNeeded_(False)
        panel.setReleasedWhenClosed_(False)
        panel.setAcceptsMouseMovedEvents_(True)
        panel.setAppearance_(NSAppearance.appearanceNamed_(NSAppearanceNameDarkAqua))
        panel.setCollectionBehavior_(
            NSWindowCollectionBehaviorCanJoinAllSpaces
            | NSWindowCollectionBehaviorFullScreenAuxiliary
            | NSWindowCollectionBehaviorStationary
            | NSWindowCollectionBehaviorIgnoresCycle
        )

        container = NSView.alloc().initWithFrame_(panel.contentView().bounds())
        container.setWantsLayer_(True)

        backdrop = _fill(NSView.alloc().initWithFrame_(container.bounds()))
        backdrop.setWantsLayer_(True)
        backdrop.layer().setContentsGravity_("resizeAspectFill")  # wie "Bildschirm füllen"
        backdrop.layer().setBackgroundColor_(NSColor.colorWithWhite_alpha_(0.12, 1.0).CGColor())

        view = _fill(OverlayView.alloc().initWithFrame_(container.bounds()))
        for sub in (backdrop, view):
            container.addSubview_(sub)
        panel.setContentView_(container)

        self.panel = panel
        self.container = container
        self.backdrop = backdrop
        self.view = view
        self.screen = None
        self.closing = False

    @property
    def visible(self):
        return bool(self.panel.isVisible())

    # --- Ebenen für Modes ---------------------------------------------------

    def add_below_view(self, subview):
        self.container.addSubview_positioned_relativeTo_(subview, NSWindowBelow, self.view)

    def add_above_view(self, subview):
        self.container.addSubview_positioned_relativeTo_(subview, NSWindowAbove, self.view)

    # --- Anzeigen / Verstecken ---------------------------------------------

    def show(self, screen, mode):
        self.screen = screen
        self.closing = False
        self.panel.setFrame_display_(screen.frame(), False)
        self._set_backdrop()
        passthrough = getattr(mode, "passthrough", False)
        # Beim Einrasten laufen Klicks durch, damit das gezogene Fenster nichts merkt.
        self.panel.setIgnoresMouseEvents_(passthrough)
        if not self.visible:
            self.panel.setAlphaValue_(0.0)
            self.panel.orderFrontRegardless()
            if not passthrough:
                self.panel.makeKeyWindow()
            NSAnimationContext.beginGrouping()
            NSAnimationContext.currentContext().setDuration_(FADE_IN)
            self.panel.animator().setAlphaValue_(OVERLAY_ALPHA)
            NSAnimationContext.endGrouping()
        self.set_mode(mode)

    def _set_backdrop(self):
        # Klares Hintergrundbild; ohne lesbares Bild ein ruhiges Dunkelgrau.
        self.backdrop.layer().setContents_(wallpaper_image(self.screen))

    def set_mode(self, mode):
        old = self.view.mode
        if old is not None and old is not mode and hasattr(old, "detach"):
            old.detach(self)
        self.view.mode = mode
        if mode is not None:
            self.backdrop.setHidden_(not getattr(mode, "backdrop", True))
        if mode is not None and mode is not old and hasattr(mode, "attach"):
            mode.attach(self)
        self.redraw()

    def redraw(self):
        self.view.setNeedsDisplay_(True)

    def fade_out(self, duration=0.22, completion=None):
        self.closing = True

        def changes(ctx):
            ctx.setDuration_(duration)
            self.panel.animator().setAlphaValue_(0.0)

        def done():
            if self.closing:
                self.hide()
            if completion is not None:
                completion()

        NSAnimationContext.runAnimationGroup_completionHandler_(changes, done)

    def hide(self):
        self.closing = False
        self.set_mode(None)
        self.panel.orderOut_(None)
        self.panel.setAlphaValue_(1.0)
        self.panel.setIgnoresMouseEvents_(False)

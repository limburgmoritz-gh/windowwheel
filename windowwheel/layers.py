"""Core-Animation- und Liquid-Glass-Helfer."""

import objc
import Quartz as Q
from AppKit import (
    NSColor,
    NSValue,
    NSView,
    NSVisualEffectBlendingModeWithinWindow,
    NSVisualEffectMaterialHUDWindow,
    NSVisualEffectStateActive,
    NSVisualEffectView,
)

try:  # Liquid Glass gibt es erst ab macOS 26
    NSGlassEffectView = objc.lookUpClass("NSGlassEffectView")
except objc.nosuchclass_error:
    NSGlassEffectView = None
GLASS_STYLE_REGULAR = 0  # NSGlassEffectViewStyleRegular

# Feder wie bei macOS-Systemanimationen: schnell, ganz leicht nachschwingend.
DAMPING, STIFFNESS = 26.0, 260.0


def white(a):
    return NSColor.colorWithWhite_alpha_(1.0, a).CGColor()


def no_actions(fn):
    """Model-Werte ohne implizite Animation setzen."""
    Q.CATransaction.begin()
    Q.CATransaction.setDisableActions_(True)
    try:
        fn()
    finally:
        Q.CATransaction.commit()


def _center(rect):
    return Q.CGPointMake(rect.origin.x + rect.size.width / 2, rect.origin.y + rect.size.height / 2)


def _bounds(rect):
    return Q.CGRectMake(0, 0, rect.size.width, rect.size.height)


def spring(layer, key, from_value, to_value, delay=0.0, damping=DAMPING, stiffness=STIFFNESS):
    anim = Q.CASpringAnimation.animationWithKeyPath_(key)
    anim.setFromValue_(from_value)
    anim.setToValue_(to_value)
    anim.setDamping_(damping)
    anim.setStiffness_(stiffness)
    anim.setMass_(1.0)
    anim.setDuration_(anim.settlingDuration())
    if delay:
        anim.setBeginTime_(Q.CACurrentMediaTime() + delay)
        anim.setFillMode_(Q.kCAFillModeBackwards)
    layer.addAnimation_forKey_(anim, key)


def move(layer, rect, animated=True, delay=0.0, from_rect=None, **kw):
    """Layer per Feder-Animation auf rect bringen – startet dort, wo er gerade sichtbar ist."""
    if from_rect is not None:
        old_pos, old_bounds = _center(from_rect), _bounds(from_rect)
    else:
        shown = layer.presentationLayer() or layer
        old_pos, old_bounds = shown.position(), shown.bounds()
    new_pos, new_bounds = _center(rect), _bounds(rect)

    def apply():
        layer.setPosition_(new_pos)
        layer.setBounds_(new_bounds)

    no_actions(apply)
    if animated:
        spring(layer, "position", NSValue.valueWithPoint_(old_pos), NSValue.valueWithPoint_(new_pos), delay, **kw)
        spring(layer, "bounds", NSValue.valueWithRect_(old_bounds), NSValue.valueWithRect_(new_bounds), delay, **kw)


def fade(layer, opacity, duration=0.25, delay=0.0):
    shown = layer.presentationLayer() or layer
    old = shown.opacity()
    no_actions(lambda: layer.setOpacity_(opacity))
    anim = Q.CABasicAnimation.animationWithKeyPath_("opacity")
    anim.setFromValue_(old)
    anim.setToValue_(opacity)
    anim.setDuration_(duration)
    anim.setTimingFunction_(Q.CAMediaTimingFunction.functionWithName_(Q.kCAMediaTimingFunctionEaseOut))
    if delay:
        anim.setBeginTime_(Q.CACurrentMediaTime() + delay)
        anim.setFillMode_(Q.kCAFillModeBackwards)
    layer.addAnimation_forKey_(anim, "opacity")


def scale(layer, factor):
    """Sanftes Vergrößern (Hover) – implizite Animation reicht hier."""
    Q.CATransaction.begin()
    Q.CATransaction.setAnimationDuration_(0.22)
    layer.setTransform_(Q.CATransform3DMakeScale(factor, factor, 1.0))
    Q.CATransaction.commit()


def glass_shape(rect, path, tint=None):
    """Glasfläche in beliebiger Form: Glas über rect, zugeschnitten auf path (Koordinaten in rect)."""
    view = glass(rect, 0, tint)
    view.setWantsLayer_(True)
    mask = Q.CAShapeLayer.layer()
    mask.setPath_(path)
    view.layer().setMask_(mask)
    return view


def glass(rect, radius, tint=None):
    """Liquid-Glass-Fläche (macOS 26+), auf älteren Systemen klassisches Milchglas."""
    if NSGlassEffectView is None:
        view = NSVisualEffectView.alloc().initWithFrame_(rect)
        view.setMaterial_(NSVisualEffectMaterialHUDWindow)
        view.setBlendingMode_(NSVisualEffectBlendingModeWithinWindow)
        view.setState_(NSVisualEffectStateActive)
        view.setWantsLayer_(True)
        view.layer().setCornerRadius_(radius)
        view.layer().setMasksToBounds_(True)
        return view
    view = NSGlassEffectView.alloc().initWithFrame_(rect)
    view.setCornerRadius_(radius)
    view.setStyle_(GLASS_STYLE_REGULAR)
    if tint is not None:
        view.setTintColor_(tint)
    return view


class PassThroughView(NSView):
    """Layer-Träger, der Mausklicks an die View darunter durchlässt."""

    def hitTest_(self, point):
        return None

    @objc.python_method
    def setup(self):
        self.setWantsLayer_(True)
        return self


def host_view(frame):
    return PassThroughView.alloc().initWithFrame_(frame).setup()


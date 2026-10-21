"""Kleine Zeichen-Helfer für AppKit."""

from AppKit import (
    NSAttributedString,
    NSBezierPath,
    NSColor,
    NSCompositingOperationClear,
    NSCompositingOperationSourceOver,
    NSFont,
    NSFontAttributeName,
    NSForegroundColorAttributeName,
    NSGraphicsContext,
    NSLineBreakByTruncatingTail,
    NSMakeRect,
    NSMutableParagraphStyle,
    NSParagraphStyleAttributeName,
    NSTextAlignmentCenter,
    NSTextAlignmentLeft,
    NSTextAlignmentRight,
    NSZeroRect,
)

REGULAR, MEDIUM, SEMIBOLD, BOLD = 0.0, 0.23, 0.3, 0.4

_ALIGN = {"left": NSTextAlignmentLeft, "center": NSTextAlignmentCenter, "right": NSTextAlignmentRight}


def rgba(r, g, b, a=1.0):
    return NSColor.colorWithSRGBRed_green_blue_alpha_(r, g, b, a)


def white(a):
    return NSColor.colorWithWhite_alpha_(1.0, a)


def accent(a=1.0):
    return NSColor.controlAccentColor().colorWithAlphaComponent_(a)


def rounded(rect, radius, fill=None, stroke=None, width=1.0, dash=None):
    path = NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(rect, radius, radius)
    if fill is not None:
        fill.setFill()
        path.fill()
    if stroke is not None:
        stroke.setStroke()
        path.setLineWidth_(width)
        if dash:
            path.setLineDash_count_phase_(dash, len(dash), 0)
        path.stroke()
    return path


def clear(rect, radius=0):
    """Macht einen Bereich des Overlays wieder komplett durchsichtig."""
    ctx = NSGraphicsContext.currentContext()
    ctx.saveGraphicsState()
    ctx.setCompositingOperation_(NSCompositingOperationClear)
    NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(rect, radius, radius).fill()
    ctx.restoreGraphicsState()


def _attributed(text, size, weight, color, align):
    style = NSMutableParagraphStyle.alloc().init()
    style.setAlignment_(_ALIGN[align])
    style.setLineBreakMode_(NSLineBreakByTruncatingTail)
    attrs = {
        NSFontAttributeName: NSFont.systemFontOfSize_weight_(size, weight),
        NSForegroundColorAttributeName: color if color is not None else white(1.0),
        NSParagraphStyleAttributeName: style,
    }
    return NSAttributedString.alloc().initWithString_attributes_(text, attrs)


def text_width(text, size, weight=REGULAR):
    return _attributed(text, size, weight, None, "left").size().width


def text(s, rect, size=13, weight=REGULAR, color=None, align="left"):
    """Einzeiliger Text, vertikal zentriert in rect, bei Bedarf mit … gekürzt."""
    astr = _attributed(s, size, weight, color, align)
    h = astr.size().height
    astr.drawInRect_(
        NSMakeRect(rect.origin.x, rect.origin.y + (rect.size.height - h) / 2, rect.size.width, h)
    )


def image(img, rect, alpha=1.0):
    if img is not None:
        img.drawInRect_fromRect_operation_fraction_(rect, NSZeroRect, NSCompositingOperationSourceOver, alpha)


def layout_preview(rect, slots, slot_fill, frame_stroke, numbers=False, number_color=None):
    """Miniatur eines Layouts (Bildschirmrahmen + Slots)."""
    rounded(rect, 5, fill=rgba(0, 0, 0, 0.28), stroke=frame_stroke, width=1.2)
    pad, gap = 3.0, 2.5
    ix, iy = rect.origin.x + pad, rect.origin.y + pad
    iw, ih = rect.size.width - 2 * pad, rect.size.height - 2 * pad
    for idx, (fx, fy, fw, fh) in enumerate(slots):
        r = NSMakeRect(
            ix + fx * iw + gap / 2,
            iy + (1 - fy - fh) * ih + gap / 2,
            fw * iw - gap,
            fh * ih - gap,
        )
        rounded(r, 2.5, fill=slot_fill)
        if numbers and r.size.height > 14:
            text(str(idx + 1), r, size=min(16, r.size.height * 0.5), weight=BOLD,
                 color=number_color, align="center")

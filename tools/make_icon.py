"""Erzeugt das App-Icon (AppIcon.icns + icon.png) – reines Python/AppKit, keine Abhängigkeiten.

Aufruf:  .venv/bin/python tools/make_icon.py
"""

import math
import shutil
import subprocess
import tempfile
from pathlib import Path

from AppKit import (
    NSBezierPath,
    NSBitmapImageFileTypePNG,
    NSBitmapImageRep,
    NSCalibratedRGBColorSpace,
    NSColor,
    NSGradient,
    NSGraphicsContext,
    NSMakePoint,
    NSMakeRect,
    NSShadow,
    NSMakeSize,
)

ROOT = Path(__file__).resolve().parent.parent
OUT_ICNS = ROOT / "windowwheel" / "resources" / "AppIcon.icns"
OUT_PNG = ROOT / "docs" / "icon.png"


def rgb(r, g, b, a=1.0):
    return NSColor.colorWithSRGBRed_green_blue_alpha_(r / 255, g / 255, b / 255, a)


def wedge(c, r_out, r_in, a0, a1):
    p = NSBezierPath.bezierPath()
    p.appendBezierPathWithArcWithCenter_radius_startAngle_endAngle_clockwise_(c, r_out, a0, a1, False)
    p.appendBezierPathWithArcWithCenter_radius_startAngle_endAngle_clockwise_(c, r_in, a1, a0, True)
    p.closePath()
    return p


def draw(size):
    s = size / 1024.0
    # Apple-Raster: Icon-Körper 824 px in 1024 px, Eckradius ~ 185
    body = NSMakeRect(100 * s, 100 * s, 824 * s, 824 * s)
    squircle = NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(body, 185 * s, 185 * s)

    shadow = NSShadow.alloc().init()
    shadow.setShadowOffset_(NSMakeSize(0, -12 * s))
    shadow.setShadowBlurRadius_(28 * s)
    shadow.setShadowColor_(rgb(0, 0, 0, 0.35))
    NSGraphicsContext.currentContext().saveGraphicsState()
    shadow.set()
    rgb(20, 24, 48).setFill()
    squircle.fill()
    NSGraphicsContext.currentContext().restoreGraphicsState()

    # Hintergrund: tiefes Blau -> Violett
    NSGradient.alloc().initWithStartingColor_endingColor_(rgb(36, 58, 140), rgb(18, 16, 52)).drawInBezierPath_angle_(squircle, -70)

    NSGraphicsContext.currentContext().saveGraphicsState()
    squircle.addClip()
    c = NSMakePoint(512 * s, 512 * s)
    r_out, r_in = 330 * s, 150 * s
    n, gap = 8, 2.6
    seg = 360 / n
    for i in range(n):
        mid = 90 - i * seg
        p = wedge(c, r_out, r_in, mid - seg / 2 + gap, mid + seg / 2 - gap)
        if i == 1:  # hervorgehobenes Segment
            NSGradient.alloc().initWithStartingColor_endingColor_(rgb(255, 196, 92), rgb(255, 120, 72)).drawInBezierPath_angle_(p, -45)
        else:
            rgb(255, 255, 255, 0.13).setFill()
            p.fill()
            rgb(255, 255, 255, 0.22).setStroke()
            p.setLineWidth_(2 * s)
            p.stroke()

    # Mini-Layout im hervorgehobenen Segment (drei Spalten)
    mid = math.radians(90 - seg)
    rm = (r_out + r_in) / 2
    px, py = c.x + rm * math.cos(mid), c.y + rm * math.sin(mid)
    w, h, g = 96 * s, 60 * s, 6 * s
    for k in range(3):
        cw = (w - 2 * g) / 3
        r = NSMakeRect(px - w / 2 + k * (cw + g), py - h / 2, cw, h)
        rgb(255, 255, 255, 0.95).setFill()
        NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(r, 6 * s, 6 * s).fill()

    # Nabe in der Mitte
    hub = NSBezierPath.bezierPathWithOvalInRect_(NSMakeRect(c.x - 118 * s, c.y - 118 * s, 236 * s, 236 * s))
    NSGradient.alloc().initWithStartingColor_endingColor_(rgb(255, 255, 255, 0.95), rgb(214, 222, 255, 0.9)).drawInBezierPath_angle_(hub, -90)
    # Fenster-Symbol (2 Spalten) in der Nabe
    w, h = 120 * s, 84 * s
    frame = NSMakeRect(c.x - w / 2, c.y - h / 2, w, h)
    rgb(30, 40, 96).setStroke()
    outline = NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(frame, 12 * s, 12 * s)
    outline.setLineWidth_(9 * s)
    outline.stroke()
    divider = NSBezierPath.bezierPath()
    divider.moveToPoint_(NSMakePoint(c.x, c.y - h / 2))
    divider.lineToPoint_(NSMakePoint(c.x, c.y + h / 2))
    divider.setLineWidth_(9 * s)
    divider.stroke()
    NSGraphicsContext.currentContext().restoreGraphicsState()

    # feine Glaskante
    rgb(255, 255, 255, 0.18).setStroke()
    squircle.setLineWidth_(3 * s)
    squircle.stroke()


def render(size, path):
    rep = NSBitmapImageRep.alloc().initWithBitmapDataPlanes_pixelsWide_pixelsHigh_bitsPerSample_samplesPerPixel_hasAlpha_isPlanar_colorSpaceName_bytesPerRow_bitsPerPixel_(
        None, size, size, 8, 4, True, False, NSCalibratedRGBColorSpace, 0, 0)
    NSGraphicsContext.saveGraphicsState()
    NSGraphicsContext.setCurrentContext_(NSGraphicsContext.graphicsContextWithBitmapImageRep_(rep))
    draw(size)
    NSGraphicsContext.restoreGraphicsState()
    rep.representationUsingType_properties_(NSBitmapImageFileTypePNG, None).writeToFile_atomically_(str(path), True)


def main():
    OUT_ICNS.parent.mkdir(parents=True, exist_ok=True)
    OUT_PNG.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        iconset = Path(tmp) / "AppIcon.iconset"
        iconset.mkdir()
        for base in (16, 32, 128, 256, 512):
            render(base, iconset / f"icon_{base}x{base}.png")
            render(base * 2, iconset / f"icon_{base}x{base}@2x.png")
        subprocess.run(["iconutil", "-c", "icns", str(iconset), "-o", str(OUT_ICNS)], check=True)
        shutil.copy(iconset / "icon_512x512@2x.png", OUT_PNG)
    print(OUT_ICNS, OUT_PNG)


if __name__ == "__main__":
    main()

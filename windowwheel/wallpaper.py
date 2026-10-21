"""Hintergrundbild des Bildschirms als Overlay-Hintergrund (klar, ohne Blur)."""

import logging

from AppKit import NSImage, NSWorkspace

log = logging.getLogger(__name__)

_cache = {}


def wallpaper_image(screen):
    """NSImage des Hintergrundbilds für screen, oder None (z.B. dynamische Wallpaper)."""
    url = NSWorkspace.sharedWorkspace().desktopImageURLForScreen_(screen)
    if url is None or not url.isFileURL():
        return None
    path = url.path()
    if path not in _cache:
        image = NSImage.alloc().initWithContentsOfURL_(url)
        if image is None:
            log.warning("Cannot read wallpaper: %s", path)
        _cache[path] = image
    return _cache[path]

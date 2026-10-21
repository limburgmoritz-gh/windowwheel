"""Fenster-Vorschaubilder über ScreenCaptureKit (asynchron, wie in Mission Control)."""

import logging

import Quartz as Q
from PyObjCTools import AppHelper

log = logging.getLogger(__name__)

try:
    import ScreenCaptureKit as SCK
except ImportError:  # pragma: no cover
    SCK = None

MAX_WIDTH = 900  # Pixelbreite der Vorschaubilder


class ThumbnailLoader:
    """Hält Vorschaubilder je CGWindowID; on_update(wid) läuft im Main-Thread."""

    def __init__(self, on_update=None):
        self.on_update = on_update
        self.images = {}
        self.cancelled = False
        self._warned = False

    def load(self, wids):
        wids = {w for w in wids if w}
        if SCK is None or not wids or self.cancelled:
            return
        if not Q.CGPreflightScreenCaptureAccess():
            if not self._warned:
                self._warned = True
                log.warning(
                    "Keine Bildschirmaufnahme-Berechtigung – Vorschaubilder zeigen nur App-Icons. "
                    "Freigabe unter Systemeinstellungen › Datenschutz & Sicherheit › Bildschirmaufnahme."
                )
                Q.CGRequestScreenCaptureAccess()
            return
        SCK.SCShareableContent.getShareableContentExcludingDesktopWindows_onScreenWindowsOnly_completionHandler_(
            True, False, lambda content, error: self._got_content(wids, content, error)
        )

    def cancel(self):
        self.cancelled = True

    def _got_content(self, wids, content, error):
        if error is not None or content is None or self.cancelled:
            if error is not None:
                log.warning("ScreenCaptureKit: %s", error)
            return
        for scw in content.windows():
            wid = scw.windowID()
            if wid not in wids:
                continue
            frame = scw.frame()
            if frame.size.width < 1 or frame.size.height < 1:
                continue
            width = min(MAX_WIDTH, int(frame.size.width))
            config = SCK.SCStreamConfiguration.alloc().init()
            config.setWidth_(width)
            config.setHeight_(max(1, int(width * frame.size.height / frame.size.width)))
            config.setShowsCursor_(False)
            content_filter = SCK.SCContentFilter.alloc().initWithDesktopIndependentWindow_(scw)
            SCK.SCScreenshotManager.captureImageWithFilter_configuration_completionHandler_(
                content_filter, config, lambda image, err, wid=wid: self._captured(wid, image)
            )

    def _captured(self, wid, image):
        if image is not None and not self.cancelled:
            AppHelper.callAfter(self._store, wid, image)

    def _store(self, wid, image):
        if self.cancelled:
            return
        self.images[wid] = image  # CGImage – direkt als Layer-Inhalt nutzbar
        if self.on_update is not None:
            self.on_update(wid)

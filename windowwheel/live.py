"""Live-Vorschau der Fenster über ScreenCaptureKit-Streams (Videos laufen weiter).

Jedes Fenster bekommt einen eigenen Stream. Die Bilder kommen als IOSurface und
werden ohne Kopie direkt als Layer-Inhalt gesetzt – das hält es flüssig.
"""

import logging

import CoreMedia as CM
import objc
import Quartz as Q
from dispatch import dispatch_queue_create
from Foundation import NSObject

log = logging.getLogger(__name__)

try:
    import ScreenCaptureKit as SCK
except ImportError:  # pragma: no cover
    SCK = None

FPS = 30
MAX_WIDTH = 900  # Pixelbreite der Live-Bilder


def _ignore(err):
    pass


class _FrameSink(NSObject, protocols=[objc.protocolNamed("SCStreamOutput")]):
    def initWithHandler_(self, handler):
        self = objc.super(_FrameSink, self).init()
        if self is None:
            return None
        self.handler = handler
        return self

    def stream_didOutputSampleBuffer_ofType_(self, stream, sample, kind):
        if kind != SCK.SCStreamOutputTypeScreen:
            return
        pixels = CM.CMSampleBufferGetImageBuffer(sample)
        if pixels is None:
            return  # Fenster unverändert – kein neues Bild
        surface = Q.CVPixelBufferGetIOSurface(pixels)
        if surface is not None:
            self.handler(surface)


class LiveThumbnails:
    """on_frame(wid, surface) läuft auf einer Hintergrund-Queue."""

    def __init__(self, on_frame):
        self.on_frame = on_frame
        self.streams = {}
        self.stopped = False
        self.queue = dispatch_queue_create(b"windowwheel.live", None)

    def start(self, wids):
        wids = {w for w in wids if w}
        if SCK is None or not wids or not Q.CGPreflightScreenCaptureAccess():
            return
        SCK.SCShareableContent.getShareableContentExcludingDesktopWindows_onScreenWindowsOnly_completionHandler_(
            True, True, lambda content, error: self._got_content(wids, content, error)
        )

    def _got_content(self, wids, content, error):
        if error is not None or content is None or self.stopped:
            return
        for scw in content.windows():
            if scw.windowID() in wids and scw.windowID() not in self.streams:
                self._start_stream(scw)

    def _config(self, width, height):
        config = SCK.SCStreamConfiguration.alloc().init()
        w = max(1, min(MAX_WIDTH, int(width)))
        config.setWidth_(w)
        config.setHeight_(max(1, int(w * height / max(width, 1))))
        config.setMinimumFrameInterval_(CM.CMTimeMake(1, FPS))
        config.setQueueDepth_(4)
        config.setShowsCursor_(False)
        config.setPixelFormat_(Q.kCVPixelFormatType_32BGRA)
        return config

    def _start_stream(self, scw):
        wid, frame = scw.windowID(), scw.frame()
        content_filter = SCK.SCContentFilter.alloc().initWithDesktopIndependentWindow_(scw)
        stream = SCK.SCStream.alloc().initWithFilter_configuration_delegate_(
            content_filter, self._config(frame.size.width, frame.size.height), None
        )
        sink = _FrameSink.alloc().initWithHandler_(lambda surface: self._frame(wid, surface))
        ok, error = stream.addStreamOutput_type_sampleHandlerQueue_error_(
            sink, SCK.SCStreamOutputTypeScreen, self.queue, None
        )
        if not ok:
            log.warning("Live-Vorschau für Fenster %s nicht möglich: %s", wid, error)
            return
        self.streams[wid] = (stream, sink)

        def started(err):  # Blocks an ScreenCaptureKit müssen None zurückgeben
            if err is not None:
                log.debug("Stream %s: %s", wid, err)

        stream.startCaptureWithCompletionHandler_(started)

    def _frame(self, wid, surface):
        if not self.stopped:
            self.on_frame(wid, surface)

    def resize(self, wid, width, height):
        """Nach dem Verschieben/Skalieren eines Fensters das Seitenverhältnis nachziehen."""
        entry = self.streams.get(wid)
        if entry is not None:
            entry[0].updateConfiguration_completionHandler_(self._config(width, height), _ignore)

    def stop(self):
        self.stopped = True
        for stream, _ in list(self.streams.values()):
            stream.stopCaptureWithCompletionHandler_(_ignore)
        self.streams.clear()

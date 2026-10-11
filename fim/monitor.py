"""Debounced watchdog observer with periodic reconciliation."""
import logging
import threading
import time
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

LOG = logging.getLogger(__name__)


class _Handler(FileSystemEventHandler):
    def __init__(self, wake):
        self.wake = wake

    def on_any_event(self, event):
        self.wake.set()


class Monitor:
    def __init__(self, directory, scan_callback, interval=60):
        self.directory = directory
        self.scan_callback = scan_callback
        self.interval = interval
        self.wake = threading.Event()
        self.stop_event = threading.Event()
        self.paused = threading.Event()
        self.observer = None
        self.thread = None

    def start(self):
        if self.thread and self.thread.is_alive():
            return
        self.stop_event.clear()
        self.paused.clear()
        self.observer = Observer()
        self.observer.schedule(_Handler(self.wake), self.directory, recursive=True)
        self.observer.start()
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()

    def _loop(self):
        last = time.monotonic()
        while not self.stop_event.is_set():
            self.wake.wait(timeout=max(0.1, self.interval - (time.monotonic() - last)))
            if self.stop_event.is_set():
                break
            if self.paused.is_set():
                self.wake.clear()
                continue
            if self.wake.is_set():
                self.wake.clear()
                if self.stop_event.wait(0.5):
                    break
                self.wake.clear()
            try:
                self.scan_callback()
            except Exception:
                LOG.exception("Monitoring scan failed")
            finally:
                last = time.monotonic()

    def pause(self):
        self.paused.set()

    def resume(self):
        self.paused.clear()
        self.wake.set()

    def stop(self):
        self.stop_event.set()
        self.wake.set()
        if self.observer:
            self.observer.stop()
            self.observer.join(timeout=5)
        if self.thread:
            self.thread.join(timeout=5)

"""Cross-process advisory lock for local storage transactions."""
import os
import threading
from contextlib import contextmanager


class FileLock:
    def __init__(self, path):
        self.path = path
        self._thread_lock = threading.RLock()
        self._local = threading.local()

    @contextmanager
    def hold(self):
        with self._thread_lock:
            if getattr(self._local, "held", False):
                yield
                return
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            with open(self.path, "a+b") as handle:
                if os.name == "nt":
                    import msvcrt
                    handle.seek(0, os.SEEK_END)
                    if handle.tell() == 0:
                        handle.write(b"0")
                        handle.flush()
                    handle.seek(0)
                    msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
                else:
                    import fcntl
                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
                self._local.held = True
                try:
                    yield
                finally:
                    self._local.held = False
                    if os.name == "nt":
                        handle.seek(0)
                        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                    else:
                        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

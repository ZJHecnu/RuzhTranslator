"""Cross-platform file locking for shared project directories."""

import os
import time
from pathlib import Path


class FileLock:
    """Simple cross-platform file lock using a .lock marker file.

    Usage:
        lock = FileLock("/path/to/project.lock")
        if lock.acquire():
            try:
                # do work
                pass
            finally:
                lock.release()
    """

    def __init__(self, lock_path: str, timeout: float = 10.0):
        """Initialize the file lock.

        Args:
            lock_path: Path to the lock file.
            timeout: Maximum seconds to wait for the lock.
        """
        self.lock_path = Path(lock_path)
        self.timeout = timeout
        self._locked = False

    def acquire(self) -> bool:
        """Try to acquire the lock.

        Returns:
            True if lock was acquired, False if timed out.
        """
        start = time.time()
        while time.time() - start < self.timeout:
            try:
                # Create lock file exclusively (atomic on most filesystems)
                fd = os.open(
                    self.lock_path,
                    os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                )
                with os.fdopen(fd, "w") as f:
                    f.write(f"locked by pid={os.getpid()} at {time.ctime()}\n")
                self._locked = True
                return True
            except FileExistsError:
                # Check if the lock is stale (> 60 seconds old)
                try:
                    mtime = self.lock_path.stat().st_mtime
                    if time.time() - mtime > 60:
                        self.lock_path.unlink(missing_ok=True)
                        continue
                except FileNotFoundError:
                    continue
                time.sleep(0.5)
        return False

    def release(self):
        """Release the lock."""
        if self._locked:
            self.lock_path.unlink(missing_ok=True)
            self._locked = False

    @property
    def is_locked(self) -> bool:
        """Check if the lock file exists."""
        return self.lock_path.exists()

    def __enter__(self):
        if not self.acquire():
            raise TimeoutError(f"Could not acquire lock: {self.lock_path}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()
        return False

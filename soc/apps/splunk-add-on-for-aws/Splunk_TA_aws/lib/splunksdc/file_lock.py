#
# Copyright 2025 Splunk Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

"""Cross-platform file locking implementation.

This module provides a robust file locking mechanism that works across
Windows, Linux, and macOS platforms. It enables applications to prevent
multiple instances from running simultaneously using platform-specific
file locking techniques.

Key capabilities:
- Cross-platform compatibility (Windows, Linux, macOS)
- Non-blocking lock acquisition with conflict detection
- Process identification for lock holders
- Context manager support for clean resource management
- Comprehensive error handling and logging

Example usage:
    with file_lock("/tmp/myapp.lock") as lock_result:
        if not lock_result.acquired:
            print(f"Another instance running: PID {lock_result.other_pid}")
            return
        # Your application code here
"""

import abc
import contextlib
import os
import platform
from dataclasses import dataclass
from typing import Generator, Optional, Tuple

from splunksdc import log as logging

logger = logging.get_module_logger()

# Determine platform once at module level to avoid repeated checks
IS_WINDOWS = platform.system() == "Windows"

# Platform-specific imports
if IS_WINDOWS:
    import msvcrt

    try:
        import winerror
    except ImportError:
        # Define the constant if winerror is not available
        class WinError:
            ERROR_LOCK_VIOLATION = 33

        winerror = WinError()
else:
    import errno
    import fcntl


@dataclass
class LockResult:
    """Result of a lock operation."""

    acquired: bool
    other_pid: Optional[int] = None

    @property
    def success(self) -> bool:
        """True if lock was successfully acquired."""
        return self.acquired and self.other_pid is None


class LockError(Exception):
    """Base exception for lock errors."""

    pass


class LockAcquisitionError(LockError):
    """Raised when lock acquisition fails."""

    def __init__(self, message: str, pid: Optional[int] = None):
        super().__init__(message)
        self.pid = pid


class BaseLock(abc.ABC):
    """Abstract base class for platform-specific lock implementations."""

    def __init__(self, lock_file_path: str):
        self.lock_file_path = lock_file_path
        self.lock_fd: Optional[int] = None

    def acquire(self) -> Tuple[Optional[int], Optional[int]]:
        """Acquire the lock and write current PID to lock file.

        Returns:
            Tuple of (other_pid, lock_fd) where other_pid is None if lock acquired
        """
        lock_fd = None
        try:
            lock_fd = os.open(self.lock_file_path, os.O_CREAT | os.O_RDWR)
            self.platform_specific_acquire(lock_fd)

            # Clear previous PID and write current PID
            os.ftruncate(lock_fd, 0)
            os.lseek(lock_fd, 0, os.SEEK_SET)

            pid_bytes = f"{os.getpid()}".encode()
            os.write(lock_fd, pid_bytes)
            os.fsync(lock_fd)

            self.lock_fd = lock_fd
            return None, self.lock_fd
        except Exception as e:
            if self.platform_specific_acquire_exception(e):
                self.release_soft(lock_fd)
                return self._get_lock_holder_pid(), None
            else:
                self.release_soft(lock_fd)
                raise LockAcquisitionError(f"Failed to acquire lock: {e}") from e

    def platform_specific_acquire(self, lock_fd: int) -> None:
        """Platform-specific lock acquisition implementation."""
        assert lock_fd is not None, "Lock file descriptor must be initialized before acquiring lock"

    @abc.abstractmethod
    def platform_specific_acquire_exception(self, e: Exception) -> bool:
        """Check if exception indicates lock is held by another process."""
        pass

    def release_soft(self, lock_fd) -> None:
        """Close file descriptor without removing lock file."""
        if lock_fd is not None:
            os.close(lock_fd)
        self.lock_fd = None

    def release(self) -> None:
        """Release lock and clean up lock file."""
        if self.lock_fd is not None:
            self.release_soft(self.lock_fd)
            with contextlib.suppress(OSError):
                os.unlink(self.lock_file_path)

    def __del__(self) -> None:
        self.release()

    def _get_lock_holder_pid(self) -> Optional[int]:
        """Get the PID of the process holding the lock.

        Returns:
            PID of the lock holder, or -1 if unknown/invalid
        """
        try:
            with open(self.lock_file_path) as f:
                pid_data = f.read().strip()
                if pid_data:
                    return int(pid_data)
        except (ValueError, FileNotFoundError, PermissionError) as e:
            logger.debug(f"Could not read lock file: {e}")
        return -1


class WindowsLock(BaseLock):
    """Windows-specific single instance lock using msvcrt.locking."""

    def platform_specific_acquire(self, lock_fd: int) -> None:
        super().platform_specific_acquire(lock_fd)
        msvcrt.locking(lock_fd, msvcrt.LK_NBLCK, 1)

    def platform_specific_acquire_exception(self, e: Exception) -> bool:
        if isinstance(e, OSError):
            return hasattr(winerror, "ERROR_LOCK_VIOLATION") and e.errno == winerror.ERROR_LOCK_VIOLATION
        return False

    def release(self) -> None:
        if self.lock_fd is not None:
            os.lseek(self.lock_fd, 0, os.SEEK_SET)
            msvcrt.locking(self.lock_fd, msvcrt.LK_UNLCK, 1)
            super().release()


class UnixLock(BaseLock):
    """Unix-specific single instance lock using fcntl.flock."""

    def platform_specific_acquire(self, lock_fd: int):
        super().platform_specific_acquire(lock_fd)
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)

    def platform_specific_acquire_exception(self, e: Exception) -> bool:
        if isinstance(e, IOError):
            return e.errno in (errno.EAGAIN, errno.EACCES)
        return False

    def release(self) -> None:
        if self.lock_fd is not None:
            fcntl.flock(self.lock_fd, fcntl.LOCK_UN)
            super().release()


@contextlib.contextmanager
def file_lock(lock_file_path: str) -> Generator["LockResult", None, None]:
    """Context manager for file-based locking.

    This is a low-level utility for creating file locks.
    For single instance locks, consider using single_instance_lock instead.

    Args:
        lock_file_path: Path to the lock file

    Yields:
        LockResult indicating success/failure and other process PID
    """
    lock = WindowsLock(lock_file_path) if IS_WINDOWS else UnixLock(lock_file_path)
    lock_fd = None
    try:
        other_pid, lock_fd = lock.acquire()
        if other_pid is None and lock_fd is not None:
            logger.info(f"Acquired lock for {lock_file_path} (PID: {os.getpid()})")
            yield LockResult(acquired=True)
        else:
            logger.warning(f"Lock held by PID {other_pid}")
            yield LockResult(acquired=False, other_pid=other_pid)
    except Exception as e:
        logger.error(f"Lock acquisition failed: {e}")
        yield LockResult(acquired=False)
    finally:
        if lock_fd is not None:
            lock.release()

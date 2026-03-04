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

"""The loop object responses for firing events and watching signals.

Currently, only watching signals is implemented. The name may change in
future.
"""

import multiprocessing
import os
import signal
import threading
from typing import Any

from splunksdc import log as logging

logger = logging.get_module_logger()


class LoopFactory:
    @classmethod
    def create(cls):
        loop_type = BasicLoop
        if os.name == "posix":
            loop_type = PosixLoop
        loop = loop_type()
        loop.setup()
        return loop


class BasicLoop:
    def __init__(self):
        self._aborted = multiprocessing.Event()
        self._stopped = False

    def setup(self):
        signal.signal(signal.SIGINT, self.abort)
        signal.signal(signal.SIGTERM, self.abort)
        # for windows machine
        if os.name == "nt":
            signal.signal(signal.SIGBREAK, self.abort)

    def is_aborted(self):
        if not self._stopped and self._aborted.is_set():
            self._stopped = True
            logger.info("Loop has been aborted.")
        return self._stopped

    def abort(self, *args, **kwargs):
        self._aborted.set()


class PosixLoop(BasicLoop):
    def __init__(self):
        super().__init__()

    def setup(self):
        super().setup()
        signal.signal(signal.SIGHUP, self.abort)
        signal.siginterrupt(signal.SIGINT, False)
        signal.siginterrupt(signal.SIGTERM, False)
        signal.siginterrupt(signal.SIGHUP, False)

    def is_aborted(self):
        super().is_aborted()
        if not self._stopped and self._is_orphan():
            self._stopped = True
            logger.info("Parent process has been terminated.")
        return self._stopped

    @staticmethod
    def _is_orphan():
        return os.getppid() == 1


class ThreadSignalHandler:
    """Signal handler for the threads."""

    def __init__(self, logger: Any):
        self._aborted = threading.Event()
        self._stopped = False
        self._logger = logger

    def setup(self) -> None:
        """setup method to register the signals."""
        signal.signal(signal.SIGINT, self.abort)
        signal.signal(signal.SIGTERM, self.abort)

        # for windows machine
        if os.name == "nt":
            signal.signal(signal.SIGBREAK, self.abort)

    def is_aborted(self) -> bool:
        """Check whether signal is received and need to abort."""
        if not self._stopped and self._aborted.is_set():
            self._stopped = True
            self._logger.info("Loop has been aborted.")
        return self._stopped

    def abort(self, *args, **kwargs) -> None:
        """Set the internal thread event flag to true."""
        self._aborted.set()

    @staticmethod
    def register(logger: Any) -> "ThreadSignalHandler":
        """Create class object and setup the signals.

        Args:
            logger (Any): Logger object

        Returns:
            ThreadSignalHandler: returns ThreadSignalHandler object
        """
        loop = ThreadSignalHandler(logger)
        loop.setup()
        return loop

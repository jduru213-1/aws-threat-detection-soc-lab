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

import queue
import threading
import time
from collections.abc import Iterable

from splunksdc import log as logging
from splunksdc.utils import LogWith

_DEFAULT_MAX_NUMBER_OF_THREAD = 4


class BatchExecutorExit:
    def __init__(self, exhausted):
        self.exhausted = exhausted


class BatchExecutor:
    def __init__(self, **kwargs):
        self._number_of_worker = kwargs.pop("number_of_threads", _DEFAULT_MAX_NUMBER_OF_THREAD)
        self._completed_queue = queue.Queue(self._number_of_worker)
        self._pending_queue = queue.Queue()
        self._stopped = threading.Event()
        self._main_context = logging.ThreadLocalLoggingStack.top()

    def _spawn(self, delegate):
        workers = []
        for _ in range(self._number_of_worker):
            resources = delegate.allocate()
            args = [delegate.do]
            if not isinstance(resources, Iterable):
                resources = [resources]
            args.extend(resources)
            worker = threading.Thread(
                target=self._worker_procedure,
                args=args,
            )
            worker.daemon = True
            workers.append(worker)
        for worker in workers:
            worker.start()
        return workers

    def run(self, delegate):
        self._stopped.clear()
        exhausted = False
        workers = self._spawn(delegate)

        for jobs in delegate.discover():
            if isinstance(jobs, BatchExecutorExit):
                exhausted = jobs.exhausted
                break

            number_of_pending = 0
            for job in jobs:
                self._pending_queue.put(job)
                number_of_pending += 1

            while number_of_pending > 0:
                if delegate.is_aborted():
                    break
                try:
                    job, result = self._completed_queue.get(timeout=3)
                    delegate.done(job, result)
                    number_of_pending -= 1
                except queue.Empty:
                    pass

            if delegate.is_aborted():
                break

        self._stopped.set()

        time.sleep(10)
        for worker in workers:
            if worker.is_alive():
                time.sleep(300)
                break

        return exhausted

    @property
    def main_context(self):
        return self._main_context

    @LogWith(prefix=main_context)
    def _worker_procedure(self, procedure, *args):
        while not self._stopped.is_set():
            try:
                job = self._pending_queue.get(timeout=3)
                result = procedure(job, *args)
                self._completed_queue.put((job, result))
            except queue.Empty:
                pass
        return

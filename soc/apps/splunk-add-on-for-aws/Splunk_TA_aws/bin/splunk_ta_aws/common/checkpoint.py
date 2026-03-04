"""
Thread safe checkpoint.
"""
#
# SPDX-FileCopyrightText: 2021 Splunk, Inc. <sales@splunk.com>
# SPDX-License-Identifier: LicenseRef-Splunk-8-2021
#
#


import threading

from splunksdc.checkpoint import LocalKVStore


class LocalKVService:
    """Class for local KV Service."""

    @classmethod
    def create(cls, filename):
        """Creates local KV service."""
        store = LocalKVStore.open_always(filename)
        server = cls(store)
        return server

    def __init__(self, store):
        self._lock = threading.Lock()
        self._store = store

    def set(self, key, value, flush=True):
        """Sets up the checkpoint."""
        with self._lock:
            return self._store.set(key, value, flush=flush)

    def get(self, key):
        """Gets the checkpoint."""
        with self._lock:
            return self._store.get(key)

    def delete(self, key):
        """Deletes the checkpoint."""
        with self._lock:
            return self._store.delete(key)

    def flush(self):
        """Flushes the checkpoint."""
        with self._lock:
            return self._store.flush()

    def range(self, minimum=None, maximum=None, policy=(True, True), reverse=False):
        """Returns key within the specified range."""
        # pylint: disable=unnecessary-comprehension

        with self._lock:
            return [
                key
                for key in self._store.range(
                    minimum=minimum, maximal=maximum, policy=policy, reverse=reverse
                )
            ]

    def prefix(self, prefix, reverse=False):
        """Prefixes the checkpoint file."""
        # pylint: disable=unnecessary-comprehension
        with self._lock:
            return [key for key in self._store.prefix(prefix, reverse)]

    def sweep(self):
        """Sweeps the checkpoint file."""
        with self._lock:
            return self._store.sweep()

    def close(self, sweep=False):
        """Closes the checkpoint file."""
        return self._store.close(sweep)

    def close_and_remove(self):
        """Closes and removes the checkpoint file."""
        return self._store.close_and_remove()

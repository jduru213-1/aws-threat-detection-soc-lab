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

import copy
import json
import time
from datetime import datetime

from splunksdc import log as logging

logger = logging.get_module_logger()


class ConfigurationError(Exception):
    def __init__(self, response):
        super().__init__(response.content)
        self._response = response


class ConfigManager:
    def __init__(self, service):
        self._service = service
        self._cache = {}
        self._watch_list = set()
        self._last_check = 0
        self._has_expired = False

    def clear(self, name, stanza=None, virtual=False):
        path = self._make_path(name, stanza, virtual)
        self._clear_cache(path)

    def load(self, name, stanza=None, virtual=False, clear_cred=False, use_cred=False):
        path = self._make_path(name, stanza, virtual)
        content = self._cached_load(path, clear_cred, use_cred)
        if stanza:
            content = content.get(stanza)
        return copy.deepcopy(content)

    def _enable_cache(self, path, content):
        self._cache[path] = content
        self._watch_list.add(path)
        return

    def _cached_load(self, path, clear_cred=False, use_cred=False):
        if path in self._cache:
            return self._cache[path]

        content = self._fresh_load(path, clear_cred, use_cred)
        if not clear_cred:
            self._enable_cache(path, content)
        return content

    def _clear_cache(self, path):
        if path in self._cache:
            del self._cache[path]
        if path in self._watch_list:
            self._watch_list.remove(path)

    def _fresh_load(self, path, clear_cred=False, use_cred=False):
        # This condition is added to resolve ADDON-24459
        query = {"output_mode": "json", "count": 0}
        if clear_cred:
            query["--get-clear-credential--"] = "1"
        # This condition is added for MSCS support
        if use_cred:
            query["--cred--"] = "1"
        elements = self._get(path, query)
        return {item["name"]: item["content"] for item in elements}

    def _get(self, path, query):
        response = self._service.get(path, **query)
        if response.get("status", None) != 200:
            raise ConfigurationError(response)
        content = json.loads(response.body.read())
        return content.get("entry", [])

    def _check(self):
        for path in self._watch_list:
            if not self._validate_cache(path):
                logger.info("Content has been modified.", path=path)
                return True
        return False

    def has_expired(self):
        now = time.time()
        if now - self._last_check > 30:
            self._last_check = now
            self._has_expired = self._check()
        return self._has_expired

    def _validate_cache(self, path):
        if path in self._cache:
            cache = self._cache[path]
            fresh = self._fresh_load(path)
            if self._modified(cache, fresh):
                return False
        return True

    @staticmethod
    def _make_path(name, stanza, virtual):
        prefix = ""
        suffix = ""
        if not virtual:
            prefix = "configs/conf-"
        if stanza:
            suffix = "/" + stanza
        path = prefix + name + suffix
        return path

    @staticmethod
    def _modified(cache, fresh):
        cache = json.dumps(cache, sort_keys=True)
        fresh = json.dumps(fresh, sort_keys=True)
        return cache != fresh


class Arguments:
    def __init__(self, document):
        self.__dict__.update(document)

    def __getattr__(self, name):
        # Make pylint happy.
        raise AttributeError(f"{self!r} instance has no attribute {name!r}")


class StanzaParser:
    def __init__(self, fields):
        self._fields = fields

    def parse(self, content):
        stanza = {}
        for field in self._fields:
            stanza[field.key] = field.parse(content)
        return Arguments(stanza)


class Field:
    def __init__(self, key, **kwargs):
        self._key = key
        self._required = kwargs.pop("required", False)
        self._default = kwargs.pop("default", None)
        self._rename = kwargs.pop("rename", None)

    def parse(self, document):
        if self._required and self._key not in document:
            raise KeyError(f"{self._key} not exists")
        return document.get(self._key, self._default)

    @property
    def key(self):
        if self._rename:
            return self._rename
        return self._key


class IntegerField(Field):
    def __init__(self, key, **kwargs):
        super().__init__(key, **kwargs)
        self._lower = kwargs.pop("lower", None)
        self._upper = kwargs.pop("upper", None)

    def parse(self, document):
        value = super().parse(document)
        value = int(value)
        if self._lower is not None:
            value = max(self._lower, value)
        if self._upper is not None:
            value = min(self._upper, value)
        return value


class StringField(Field):
    def __init__(self, key, **kwargs):
        super().__init__(key, **kwargs)
        self._fillempty = kwargs.get("fillempty")

    def parse(self, document):
        value = super().parse(document)
        if not value and self._fillempty:
            value = self._fillempty
        return value


class BooleanField(Field):
    def __init__(self, key, **kwargs):
        super().__init__(key, **kwargs)
        self._reverse = kwargs.get("reverse", False)

    def parse(self, document):
        value = super().parse(document)
        if isinstance(value, str):
            value = value.lower()
            value = value in ["yes", "on", "true", "ok", "1"]
        else:
            value = bool(value)
        if self._reverse:
            value = not value
        return value


class LogLevelField(Field):
    def __init__(self, key, **kwargs):
        super().__init__(key, **kwargs)

    def parse(self, document):
        value = super().parse(document)
        lookup = {"INFO": logging.INFO, "DEBUG": logging.DEBUG, "ERROR": logging.ERROR}
        return lookup.get(value, logging.WARNING)


class DateTimeField(Field):
    def __init__(self, key, **kwargs):
        super().__init__(key, **kwargs)
        self._fmt = kwargs.pop("fmt", "%Y-%m-%d")

    def parse(self, document):
        value = super().parse(document)
        return datetime.strptime(value, self._fmt)

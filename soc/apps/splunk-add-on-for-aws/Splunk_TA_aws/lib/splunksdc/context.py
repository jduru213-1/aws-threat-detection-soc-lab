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

import urllib.parse

from splunklib.client import Service
from splunklib.modularinput.input_definition import InputDefinition

from splunksdc import environ
from splunksdc import log as logging

logger = logging.get_module_logger()


class Stanza:
    def __init__(self, kind, name, content):
        self.kind = kind
        self.name = name
        self.content = content
        self.content = {key: value.strip() for key, value in self.content.items() if value is not None}


class Context:
    @classmethod
    def from_url(cls, server_uri, stanza):
        parts = urllib.parse.urlparse(server_uri)
        scheme = parts.scheme
        host = parts.hostname
        port = parts.port

        service = Service(
            scheme=scheme,
            host=host,
            port=port,
            username=parts.username,
            password=parts.password,
        )
        service.login()

        server_scheme = scheme
        server_host = host
        server_port = port
        token = service.token
        log_dir = environ.get_log_folder()

        kind, name = cls._split_stanza(stanza)
        inputs = []
        for item in service.inputs:
            if item.kind != kind:
                continue
            if item.name != name and name:
                continue
            stanza = Stanza(item.kind, item.name, item.content)
            inputs.append(stanza)

        checkpoint_dir = environ.get_checkpoint_folder(kind)
        return cls(
            server_scheme,
            server_host,
            server_port,
            token,
            checkpoint_dir,
            log_dir,
            inputs,
        )

    @classmethod
    def from_stream(cls, stream):
        definition = InputDefinition.parse(stream)

        metadata = definition.metadata
        parts = urllib.parse.urlparse(metadata["server_uri"])
        scheme = parts.scheme
        host = parts.hostname
        port = parts.port
        token = metadata["session_key"]

        server_scheme = scheme
        server_host = host
        server_port = port
        token = token
        log_dir = environ.get_log_folder()

        inputs = []
        for name, params in definition.inputs.items():
            kind, name = cls._split_stanza(name)
            stanza = Stanza(kind, name, params)
            inputs.append(stanza)

        checkpoint_dir = metadata["checkpoint_dir"]
        return cls(
            server_scheme,
            server_host,
            server_port,
            token,
            checkpoint_dir,
            log_dir,
            inputs,
        )

    @staticmethod
    def _split_stanza(name):
        pos = name.find("://")
        if pos == -1:
            return name, ""

        kind = name[:pos]
        name = name[pos + 3 :]
        return kind, name

    def __init__(
        self,
        server_scheme,
        server_host,
        server_port,
        token,
        checkpoint_dir,
        log_dir,
        inputs,
    ):
        self._server_scheme = server_scheme
        self._server_host = server_host
        self._server_port = server_port
        self._token = token
        self._checkpoint_dir = checkpoint_dir
        self._log_dir = log_dir
        self._inputs = inputs

    @property
    def server_scheme(self):
        return self._server_scheme

    @property
    def server_host(self):
        return self._server_host

    @property
    def server_port(self):
        return self._server_port

    @property
    def token(self):
        return self._token

    @property
    def checkpoint_dir(self):
        return self._checkpoint_dir

    @property
    def log_dir(self):
        return self._log_dir

    @property
    def inputs(self):
        return self._inputs

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

import os


class SplunkEnviron:
    def __init__(self, environ=None):
        if not environ:
            environ = os.environ
        self._home = environ.get("SPLUNK_HOME", os.getcwd())

    def get_splunk_home(self):
        return self._home

    def get_log_folder(self):
        path = os.path.join(self._home, "var", "log", "splunk")
        return path

    def get_checkpoint_folder(self, schema):
        path = os.path.join(self._home, "var", "lib", "splunk", "modinputs", schema)
        return path


_environ = SplunkEnviron()


def get_log_folder():
    return _environ.get_log_folder()


def get_checkpoint_folder(schema):
    return _environ.get_checkpoint_folder(schema)

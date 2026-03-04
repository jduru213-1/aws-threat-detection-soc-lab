#
# SPDX-FileCopyrightText: 2021 Splunk, Inc. <sales@splunk.com>
# SPDX-License-Identifier: LicenseRef-Splunk-8-2021
#
#
"""
Add common libs to sys.path
"""

import logging
import os
import os.path
import re
import sys

# Import the Splunk-shipped library before adding TA paths to sys.path to ensure it is cached.
# This way, even if the TA path added to sys.path contains urllib3,
# Python will always reference the already cached urllib3 from the Splunk Python path.
try:
    import urllib3
except Exception as e:
    pass


def setup_python_path():
    """Sets up path for python modules."""
    # Exclude folder beneath other apps, Fix bug for rest_handler.py
    ta_name = os.path.basename(os.path.dirname(os.path.dirname(__file__)))
    pattern = re.compile(r"[\\/]etc[\\/]apps[\\/][^\\/]+[\\/]bin[\\/]?$")
    new_paths = [
        path for path in sys.path if not pattern.search(path) or ta_name in path
    ]
    new_paths.insert(0, os.path.dirname(__file__))
    sys.path = new_paths

    package_dir = os.path.dirname(os.path.dirname(__file__))
    # We sort the precedence in a decending order since sys.path.insert(0, ...)
    # do the reversing.
    # Insert library folder
    sharedpath = os.path.join(package_dir, "lib")
    sys.path.insert(0, sharedpath)

    # inserted commited splunktalib as first priority on path
    path_to_splunktalib = os.path.join(sharedpath, "splunktalib_helper")
    sys.path.insert(0, path_to_splunktalib)

    # insert os dependent lib as first priority on path
    libdir_tp_root_dir = os.path.join(sharedpath, "3rdparty")
    if sys.platform.startswith("win32"):
        platform_dir = "windows_x86_64"
    elif sys.platform.startswith("darwin"):
        platform_dir = "darwin_x86_64"
    else:
        platform_dir = "linux_x86_64"

    tp_dir = os.path.join(
        libdir_tp_root_dir,
        platform_dir,
        f"python{sys.version_info.major}{sys.version_info.minor}",
    )
    sys.path.insert(0, tp_dir)


# preventing splunklib initialize an unexpected root handler
def setup_null_handler():
    """Sets up logging handler."""
    logging.root.addHandler(logging.NullHandler())


def run_module(name):
    """Runs the main module."""
    from boto3.compat import filter_python_deprecation_warnings

    filter_python_deprecation_warnings()
    instance = __import__(name, fromlist=["main"])
    instance.main()


setup_python_path()
setup_null_handler()

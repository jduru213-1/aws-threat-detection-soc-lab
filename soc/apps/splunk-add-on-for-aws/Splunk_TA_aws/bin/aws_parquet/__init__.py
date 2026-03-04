#
# SPDX-FileCopyrightText: 2021 Splunk, Inc. <sales@splunk.com>
# SPDX-License-Identifier: LicenseRef-Splunk-8-2021
#
#

import subprocess
import platform
import os
from splunksdc import logging

logger = logging.get_module_logger()

SUPPORTED_SYSTEMS = {
    ("Linux", "x86_64"): "parquet_decoder_linux_amd64",
    ("Linux", "arm64"): "parquet_decoder_linux_arm64",
    ("Darwin", "x86_64"): "./parquet_decoder_darwin_amd64",
    ("Darwin", "arm64"): "parquet_decoder_darwin_arm64",
    ("Windows", "AMD64"): "parquet_decoder_windows_amd64.exe",
}


def stream_parquet(parquet_file):
    parser_cmdline = get_parser_cmdline(parquet_file)
    extra_args = {}

    if platform.system() == "Linux":
        parser_cmdline.insert(
            0, "nice"
        )  # Ensure we start decoding with nice value of 10

    if platform.system() == "Windows":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.BELOW_NORMAL_PRIORITY_CLASS
        extra_args["startupinfo"] = startupinfo

    try:
        process = subprocess.Popen(
            parser_cmdline, text=True, stdout=subprocess.PIPE, bufsize=1, **extra_args
        )
        for line in process.stdout:
            yield line

        return_code = process.wait()

        if return_code != 0:
            raise subprocess.CalledProcessError(return_code, parser_cmdline)

    except subprocess.CalledProcessError as parser_error:
        logger.error(f"there was an error within the parquet parser: {parser_error}")
        raise parser_error


def get_parser_cmdline(parquet_file):
    parser_exec = get_parser_exec()
    return [parser_exec, parquet_file]


def get_parser_exec():
    parser_exec = SUPPORTED_SYSTEMS[(platform.system(), platform.machine())]
    parser_exec = f"{os.path.realpath(os.path.dirname(__file__))}/{parser_exec}"
    return parser_exec

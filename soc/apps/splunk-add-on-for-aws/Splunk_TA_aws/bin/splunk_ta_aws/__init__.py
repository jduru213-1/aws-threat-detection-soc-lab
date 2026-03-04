#
# SPDX-FileCopyrightText: 2021 Splunk, Inc. <sales@splunk.com>
# SPDX-License-Identifier: LicenseRef-Splunk-8-2021
#
#
"""init file for splunk_ta_aws"""

import splunksdc
import splunksdc.log as logging

logger = logging.get_module_logger()
logger.set_level(logging.INFO)


def set_log_level(level):
    """Sets log level."""
    logger.set_level(level)
    splunksdc.set_log_level(level)

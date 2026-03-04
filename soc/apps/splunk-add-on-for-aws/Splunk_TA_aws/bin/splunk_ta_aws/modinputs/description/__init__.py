#!/usr/bin/python

"""
This is the main entry point for AWS Description TA
"""
#
# SPDX-FileCopyrightText: 2021 Splunk, Inc. <sales@splunk.com>
# SPDX-License-Identifier: LicenseRef-Splunk-8-2021
#
#


import splunk_ta_aws.common.ta_aws_consts as tac
import splunksdc.log as logging

logger = logging.get_module_logger()


def main():
    """
    Main entry point
    """
    # description is single-instance, output to one log file
    logging.setup_root_logger(app_name=tac.splunk_ta_aws, modular_name="description")
    logger.warning(
        "Description (Boto2) (aws:description) input for AWS TA has been deprecated."
    )
    return True


if __name__ == "__main__":
    main()

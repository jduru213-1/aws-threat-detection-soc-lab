#!/usr/bin/python

"""
This is the main entry point for My TA
"""
#
# SPDX-FileCopyrightText: 2021 Splunk, Inc. <sales@splunk.com>
# SPDX-License-Identifier: LicenseRef-Splunk-8-2021
#
#


import time

import splunk_ta_aws.common.ta_aws_common as tacommon
import splunk_ta_aws.common.ta_aws_consts as tac
import splunksdc.log as logging
import splunktalib.common.util as utils
import splunktalib.orphan_process_monitor as opm

from . import aws_kinesis_consts as akc

logger = logging.get_module_logger()


def print_scheme():
    """Print kinesis scheme."""
    title = "Splunk AddOn for AWS"
    description = "Collect and index Kinesis data for AWS"
    tacommon.print_scheme(title, description)


@utils.catch_all(logger, False)
def run():
    """
    Main loop. Run this TA forever
    """
    from splunk_ta_aws.common.aws_concurrent_data_loader import (  # isort: skip   # pylint: disable=import-outside-toplevel
        AwsDataLoaderManager,
    )
    from splunk_ta_aws.modinputs.kinesis.aws_kinesis_conf import (  # isort: skip   # pylint: disable=import-outside-toplevel
        AWSKinesisConf,
        create_conf_monitor,
    )

    logger.info("Start Kinesis TA")
    _, _, tasks = tacommon.get_configs(AWSKinesisConf, "aws_kinesis", logger)

    if not tasks:
        return

    loader = AwsDataLoaderManager(tasks, "splunk_ta_aws", "kinesis")

    conf_change_handler = tacommon.get_file_change_handler(loader, logger)
    conf_monitor = create_conf_monitor(conf_change_handler)
    loader.add_timer(conf_monitor, time.time(), 10)

    orphan_checker = opm.OrphanProcessChecker(loader.stop)
    loader.add_timer(orphan_checker.check_orphan, time.time(), 1)

    # monitor shard changes
    # Disable it for ADDON-9537
    # streams = list(set([t[akc.stream_name] for t in tasks]))
    # shard_checker = akconf.ShardChangesChecker(tasks[0], streams, loader.stop)
    # loader.add_timer(shard_checker, time.time(), 120)

    loader.start()
    logger.info("End Kinesis TA")


def main():
    """
    Main entry point
    """
    # kinesis is single instance, output to one log file
    logging.setup_root_logger(app_name=tac.splunk_ta_aws, modular_name=akc.mod_name)
    tacommon.main(print_scheme, run)


if __name__ == "__main__":
    main()

"""
Modular Input for AWS CloudTrail Lake
"""

#
# SPDX-FileCopyrightText: 2021 Splunk, Inc. <sales@splunk.com>
# SPDX-License-Identifier: LicenseRef-Splunk-8-2021
#
#

from splunklib import modularinput as smi
from splunktalib.common.util import extract_datainput_name
from splunk_ta_aws.common.ta_aws_consts import splunk_ta_aws
from .aws_cloudtrail_lake_data_loader import CloudTrailLakeDataCollector
import sys
import traceback
import splunksdc.log as logging
import splunk_ta_aws.common.ta_aws_consts as taconsts

logger = logging.get_module_logger()


class CloudTrailLake(smi.Script):
    def __init__(self):
        super(CloudTrailLake, self).__init__()

    def get_scheme(self):
        scheme = smi.Scheme("aws_cloudtrail_lake")
        scheme.description = "CloudTrail Lake"
        scheme.use_external_validation = True
        scheme.streaming_mode_xml = True
        scheme.use_single_instance = False

        basic_arguments = [
            ("name", True),
            ("aws_account", True),
            ("aws_iam_role", False),
            ("aws_region", True),
            ("private_endpoint_enabled", False),
            ("cloudtrail_private_endpoint_url", False),
            ("sts_private_endpoint_url", False),
            ("input_mode", True),
            ("event_data_store", True),
            ("start_date_time", True),
            ("end_date_time", False),
            ("query_window_size", True),
            ("delay_throttle", False),
        ]

        for name, is_required in basic_arguments:
            scheme.add_argument(smi.Argument(name, required_on_create=is_required))

        return scheme

    def validate_input(self, definition):
        return

    def stream_events(self, inputs, ew):
        input_name, input_items = inputs.inputs.popitem()
        datainput_name = extract_datainput_name(input_name)
        logging.setup_root_logger(
            app_name=splunk_ta_aws,
            modular_name="cloudtrail-lake",
            stanza_name=datainput_name,
        )
        with logging.LogContext(datainput=datainput_name):
            try:
                logger.info(f"Modular input started.")
                CloudTrailLakeDataCollector(
                    self._input_definition.metadata[taconsts.server_uri],
                    self._input_definition.metadata[taconsts.session_key],
                    datainput_name,
                    input_items,
                    self.service,
                ).run()
            except Exception:
                logger.error(
                    f"An error occurred while collecting the data {traceback.format_exc()}."
                )
            finally:
                logger.info(f"Modular input exited.")


def main():
    exit_code = CloudTrailLake().run(sys.argv)
    sys.exit(exit_code)

"""
Modular Input for AWS Billing to grab AWS monthly CSV report and index into Splunk
"""

#
# SPDX-FileCopyrightText: 2021 Splunk, Inc. <sales@splunk.com>
# SPDX-License-Identifier: LicenseRef-Splunk-8-2021
#
#


import sys

import splunksdc.log as logging
import splunktalib.common.util as scutil
from splunklib import modularinput as smi

logger = logging.get_module_logger()


# pylint: disable=invalid-name
class MyScript(smi.Script):  # pylint: disable=too-many-instance-attributes
    """Class for myscript."""

    def __init__(self):
        super(MyScript, self).__init__()

    def get_scheme(self):
        """overloaded splunklib modularinput method"""

        scheme = smi.Scheme("AWS Billing")
        scheme.description = "Collect and index billing report of AWS in CSV format located in AWS S3 bucket."
        scheme.use_external_validation = True
        scheme.streaming_mode_xml = True
        scheme.use_single_instance = False

        scheme.add_argument(
            smi.Argument(
                "name",
                title="Name",
                description="Choose an ID or nickname for this configuration",
                required_on_create=True,
            )
        )
        return scheme

    def stream_events(self, inputs, ew):
        """overloaded splunklib modularinput method"""
        # for multiple instance modinput, inputs dic got only one key
        input_name = scutil.extract_datainput_name(list(inputs.inputs.keys())[0])
        logging.setup_root_logger(
            app_name="splunk_ta_aws", modular_name="billing", stanza_name=input_name
        )
        with logging.LogContext(datainput=input_name):
            logger.warning(
                "Billing (Legacy) input for AWS TA has been deprecated. Configure Billing (Cost and Usage Report) input to collect the billing data."
            )
            return


def main():
    """Main method for billing dbr input."""
    exitcode = MyScript().run(sys.argv)
    sys.exit(exitcode)

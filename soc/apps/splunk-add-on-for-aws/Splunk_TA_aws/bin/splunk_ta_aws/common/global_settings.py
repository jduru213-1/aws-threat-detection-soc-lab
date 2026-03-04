#
# SPDX-FileCopyrightText: 2021 Splunk, Inc. <sales@splunk.com>
# SPDX-License-Identifier: LicenseRef-Splunk-8-2021
#
#
from splunksdc.config import StanzaParser, IntegerField, ConfigManager, Arguments


class GlobalInputsSettings:
    """
    This utility class is responsible for holding Global Settings related to inputs
    """

    @classmethod
    def load(cls, config: ConfigManager) -> "GlobalInputsSettings":
        """Loads Global Inputs settings."""
        content = config.load("aws_global_settings", stanza="aws_inputs_settings")
        parser = StanzaParser(
            [
                IntegerField(
                    "cloudwatch_dimensions_max_threads", default=1, lower=1, upper=64
                ),
                IntegerField("sqs_max_threads", default=4, lower=1, upper=64),
            ]
        )
        global_settings = parser.parse(content)
        return cls(global_settings)

    def __init__(self, global_settings: Arguments):
        self._global_settings = global_settings

    def get_cloudwatch_dimensions_max_threads(self) -> int:
        """Get CloudWatch Max Threads."""
        return self._global_settings.cloudwatch_dimensions_max_threads

    def get_sqs_max_threads(self) -> int:
        """Get SQS Max Threads."""
        return self._global_settings.sqs_max_threads

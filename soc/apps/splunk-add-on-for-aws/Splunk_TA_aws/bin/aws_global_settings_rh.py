#
# SPDX-FileCopyrightText: 2021 Splunk, Inc. <sales@splunk.com>
# SPDX-License-Identifier: LicenseRef-Splunk-8-2021
#
#

import aws_bootstrap_env  # noqa: F401 # pylint: disable=unused-import


import splunk.admin as admin

from splunktalib.rest_manager import base, multimodel, normaliser, validator


class AWSConnection(base.BaseModel):
    requiredArgs = {"is_secure"}
    defaultVals = {"is_secure": "1"}
    normalisers = {"is_secure": normaliser.Boolean()}
    validators = {"is_secure": validator.Enum(("0", "1"))}

    outputExtraFields = ("eai:acl", "acl", "eai:appName", "eai:userName")


class AWSInputsSettings(base.BaseModel):
    requiredArgs = {"cloudwatch_dimensions_max_threads", "sqs_max_threads"}
    defaultVals = {"cloudwatch_dimensions_max_threads": "1", "sqs_max_threads": "4"}
    validators = {  # This validator does not include the max value, required to keep expected max value(64) + 1
        "cloudwatch_dimensions_max_threads": validator.Range(
            max_val=65,
            min_val=1,
        )
    }

    outputExtraFields = (
        "eai:acl",
        "acl",
        "eai:attributes",
        "eai:appName",
        "eai:userName",
    )


class Globals(multimodel.MultiModel):
    endpoint = "configs/conf-aws_global_settings"
    modelMap = {
        "aws_connection": AWSConnection,
        "aws_inputs_settings": AWSInputsSettings,
    }


if __name__ == "__main__":
    admin.init(multimodel.ResourceHandler(Globals), admin.CONTEXT_APP_AND_USER)

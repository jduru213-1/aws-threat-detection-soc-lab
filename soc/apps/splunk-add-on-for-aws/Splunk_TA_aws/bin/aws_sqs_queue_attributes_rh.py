#
# SPDX-FileCopyrightText: 2021 Splunk, Inc. <sales@splunk.com>
# SPDX-License-Identifier: LicenseRef-Splunk-8-2021
#
#


import aws_bootstrap_env  # noqa: F401 # pylint: disable=unused-import
import aws_common_validator as acv
import splunk
import splunk.admin
import splunk_ta_aws.common.proxy_conf as pc
import splunk_ta_aws.common.ta_aws_common as tacommon
from botocore.exceptions import ClientError, ConnectTimeoutError
from solnlib.splunkenv import get_splunkd_access_info
from splunk_ta_aws.common.credentials import (
    AWSCredentialsCache,
    AWSCredentialsProviderFactory,
)
from splunk_ta_aws.common.sqs import SQSQueue
from splunklib.client import Service
from splunksdc.config import ConfigManager
from splunktalib.rest_manager.error_ctl import RestHandlerError


def query_queue_attributes(  # pylint: disable=too-many-arguments
    session_key,
    aws_account,
    aws_iam_role,
    region_name,
    sqs_queue_url,
    sqs_endpoint_url,
    sts_endpoint_url,
):
    """Returns the query queue attributes."""
    scheme, host, port = get_splunkd_access_info(session_key)
    service = Service(scheme=scheme, host=host, port=port, token=session_key)
    config = ConfigManager(service)
    factory = AWSCredentialsProviderFactory(config, region_name, sts_endpoint_url)
    provider = factory.create(aws_account, aws_iam_role)
    credentials_cache = AWSCredentialsCache(provider)
    client = credentials_cache.client("sqs", region_name, endpoint_url=sqs_endpoint_url)
    queue = SQSQueue(sqs_queue_url, region_name)
    return queue.get_attributes(client)


class SqsQueueAtrributesHandler(splunk.admin.MConfigHandler):
    def setup(self):
        """Setup method for SQS queue attribute handler."""
        self.supportedArgs.addReqArg("aws_account")
        self.supportedArgs.addOptArg("aws_iam_role")
        self.supportedArgs.addReqArg("aws_region")
        self.supportedArgs.addReqArg("sqs_queue_url")
        self.supportedArgs.addOptArg("private_endpoint_enabled")
        self.supportedArgs.addOptArg("sqs_private_endpoint_url")
        self.supportedArgs.addOptArg("sts_private_endpoint_url")

    def handleList(self, confInfo):  # pylint: disable=invalid-name
        """Called when user invokes the "list" action."""
        # Set proxy for boto3
        proxy = pc.get_proxy_info(self.getSessionKey())
        tacommon.set_proxy_env(proxy)
        if int(self.callerArgs.data.get("private_endpoint_enabled", [0])[0]):
            endpoint_urls = {
                "sqs_private_endpoint_url": self.callerArgs.data.get(
                    "sqs_private_endpoint_url", [""]
                )[0],
                "sts_private_endpoint_url": self.callerArgs.data.get(
                    "sts_private_endpoint_url", [""]
                )[0],
            }
            if (
                endpoint_urls["sqs_private_endpoint_url"]
                and endpoint_urls["sts_private_endpoint_url"]
            ):
                acv.on_fetch_validate_urls(endpoint_urls)
                sqs_endpoint_url = endpoint_urls["sqs_private_endpoint_url"]
                sts_endpoint_url = endpoint_urls["sts_private_endpoint_url"]
            else:
                return
        else:
            sts_endpoint_url = None
            sqs_endpoint_url = None
        try:
            attrs = query_queue_attributes(
                self.getSessionKey(),
                self.callerArgs.data["aws_account"][0],
                self.callerArgs.data.get("aws_iam_role", [None])[0],
                self.callerArgs.data["aws_region"][0],
                self.callerArgs.data["sqs_queue_url"][0],
                sqs_endpoint_url,
                sts_endpoint_url,
            )
        except (ClientError, ConnectTimeoutError) as exc:
            RestHandlerError.ctl(400, msgx=exc)
            return
        confInfo["Attributes"]["VisibilityTimeout"] = attrs.visibility_timeout
        confInfo["Attributes"]["RedrivePolicy"] = attrs.redrive_policy


def main():
    """Main method for SQS queue attribute RH."""
    splunk.admin.init(SqsQueueAtrributesHandler, splunk.admin.CONTEXT_NONE)


if __name__ == "__main__":
    main()

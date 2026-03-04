#
# SPDX-FileCopyrightText: 2021 Splunk, Inc. <sales@splunk.com>
# SPDX-License-Identifier: LicenseRef-Splunk-8-2021
#
#


import aws_bootstrap_env  # noqa: F401 # pylint: disable=unused-import
import aws_common_validator as acv
import splunk.admin as admin
import splunk_ta_aws.common.proxy_conf as pc
import splunk_ta_aws.common.ta_aws_common as tacommon
import splunk_ta_aws.common.ta_aws_consts as tac
import splunk_ta_aws.modinputs.kinesis.aws_kinesis_common as akc
import splunktalib.common.pattern as scp
from solnlib.splunkenv import get_splunkd_uri
from splunksdc import log as logging

logger = logging.get_module_logger()


class KinesisStreams(admin.MConfigHandler):
    valid_params = [tac.region, tac.account]

    def setup(self):
        """Setup method for Kinesis streams RH."""
        for param in self.valid_params:
            self.supportedArgs.addOptArg(param)
        self.supportedArgs.addOptArg(tac.aws_iam_role)
        self.supportedArgs.addOptArg("private_endpoint_enabled")
        self.supportedArgs.addOptArg("sts_private_endpoint_url")
        self.supportedArgs.addOptArg("kinesis_private_endpoint_url")

    @scp.catch_all(logger)
    def handleList(self, conf_info):  # pylint: disable=invalid-name
        """Called when user invokes the "list" action."""
        logger.info("start listing kinesis streams")
        for required in self.valid_params:
            if not self.callerArgs or not self.callerArgs.get(required):
                logger.error('Missing "%s"', required)
                raise Exception(
                    'Missing "{}"'.format(required)
                )  # pylint: disable=consider-using-f-string

        aws_account = ""
        if self.callerArgs[tac.account] is not None:
            aws_account = self.callerArgs[tac.account][0]

        aws_iam_role = None
        if self.callerArgs.get(tac.aws_iam_role) is not None:
            aws_iam_role = self.callerArgs[tac.aws_iam_role][0]
        if int(self.callerArgs.get("private_endpoint_enabled", [0])[0]):
            endpoint_urls = {
                "kinesis_private_endpoint_url": self.callerArgs.get(
                    "kinesis_private_endpoint_url", [""]
                )[0],
                "sts_private_endpoint_url": self.callerArgs.get(
                    "sts_private_endpoint_url", [""]
                )[0],
            }
            if (
                endpoint_urls["kinesis_private_endpoint_url"]
                and endpoint_urls["sts_private_endpoint_url"]
            ):
                acv.on_fetch_validate_urls(endpoint_urls)
                kinesis_endpoint_url = endpoint_urls["kinesis_private_endpoint_url"]
                sts_endpoint_url = endpoint_urls["sts_private_endpoint_url"]
            else:
                return
        else:
            sts_endpoint_url = None
            kinesis_endpoint_url = tacommon.format_default_endpoint_url(
                "kinesis", self.callerArgs[tac.region][0]
            )

        # Set proxy for boto3
        proxy = pc.get_proxy_info(self.getSessionKey())
        tacommon.set_proxy_env(proxy)

        cred_service = tacommon.create_credentials_service(
            get_splunkd_uri(self.getSessionKey()), self.getSessionKey()
        )
        cred = cred_service.load(
            aws_account,
            aws_iam_role,
            self.callerArgs[tac.region][0],
            endpoint_url=sts_endpoint_url,
        )

        proxy[tac.server_uri] = get_splunkd_uri(self.getSessionKey())
        proxy[tac.session_key] = self.getSessionKey()
        proxy[tac.aws_account] = aws_account
        proxy[tac.aws_iam_role] = aws_iam_role
        proxy[tac.region] = self.callerArgs[tac.region][0]
        proxy[tac.key_id] = cred.aws_access_key_id
        proxy[tac.secret_key] = cred.aws_secret_access_key
        proxy["aws_session_token"] = cred.aws_session_token
        proxy["kinesis_endpoint_url"] = kinesis_endpoint_url
        proxy["sts_endpoint_url"] = sts_endpoint_url
        client = akc.KinesisClient(proxy, logger)
        streams = client.list_streams()

        for stream in streams:
            conf_info[stream].append("stream_names", stream)

        logger.info("end of listing kinesis streams")


def main():
    """Main method for Kinesis Streams RH"""
    admin.init(KinesisStreams, admin.CONTEXT_NONE)


if __name__ == "__main__":
    main()

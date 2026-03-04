"""
Custom REST Endpoint for enumerating AWS S3 Bucket.
"""

#
# SPDX-FileCopyrightText: 2021 Splunk, Inc. <sales@splunk.com>
# SPDX-License-Identifier: LicenseRef-Splunk-8-2021
#
#


import re

import aws_bootstrap_env  # noqa: F401 # pylint: disable=unused-import
import aws_common_validator as acv
import boto3
import splunk
import splunk.admin
import splunk_ta_aws.common.proxy_conf as pc
import splunk_ta_aws.common.ta_aws_common as tacommon
import splunk_ta_aws.common.ta_aws_consts as tac
from botocore.config import Config
from botocore.exceptions import ClientError
from solnlib.splunkenv import get_splunkd_uri
from splunktaucclib.rest_handler.error import RestError

BAD_REQ_STATUS_CODE = 400
READ_TIMEOUT_SEC = 25
DEFAULT_REGION = "us-east-1"


class ConfigHandler(splunk.admin.MConfigHandler):
    def setup(self):
        """Setup method for aws s3 buckets RH."""
        self.supportedArgs.addReqArg("aws_account")
        self.supportedArgs.addOptArg("aws_iam_role")
        self.supportedArgs.addOptArg("aws_s3_region")
        self.supportedArgs.addOptArg("private_endpoint_enabled")
        self.supportedArgs.addOptArg("sts_private_endpoint_url")
        self.supportedArgs.addOptArg("s3_private_endpoint_url")

    def handleList(self, confInfo):  # pylint: disable=invalid-name, too-many-branches
        """Called when user invokes the "edit" action."""
        aws_account = None
        aws_account_category = tac.RegionCategory.COMMERCIAL

        if self.callerArgs["aws_account"] is not None:
            aws_account = self.callerArgs["aws_account"][0]

        aws_iam_role = None
        if self.callerArgs.get("aws_iam_role") is not None:
            aws_iam_role = self.callerArgs["aws_iam_role"][0]

        if not aws_account:
            confInfo["bucket_name"].append("bucket_name", [])
            return

        if self.callerArgs.get("aws_s3_region") and self.callerArgs.get(
            "aws_s3_region"
        ) != [None]:
            region = self.callerArgs["aws_s3_region"][0]
        else:
            region = None
        if int(self.callerArgs.get("private_endpoint_enabled", [0])[0]):
            if not self.callerArgs.get("aws_s3_region", [None])[0]:
                raise RestError(
                    400, "Field AWS Region is required to use private endpoints"
                )
            endpoint_urls = {
                "s3_private_endpoint_url": self.callerArgs.get(
                    "s3_private_endpoint_url", [""]
                )[0],
                "sts_private_endpoint_url": self.callerArgs.get(
                    "sts_private_endpoint_url", [""]
                )[0],
            }
            if (
                endpoint_urls["s3_private_endpoint_url"]
                and endpoint_urls["sts_private_endpoint_url"]
            ):
                acv.on_fetch_validate_urls(endpoint_urls)
                s3_endpoint_url = endpoint_urls["s3_private_endpoint_url"]
                sts_endpoint_url = endpoint_urls["sts_private_endpoint_url"]
            else:
                return
        else:
            sts_endpoint_url = None
            s3_endpoint_url = None
        # Set proxy for boto3
        proxy = pc.get_proxy_info(self.getSessionKey())
        tacommon.set_proxy_env(proxy)

        cred_service = tacommon.create_credentials_service(
            get_splunkd_uri(self.getSessionKey()), self.getSessionKey()
        )

        try:
            cred = cred_service.load(
                aws_account, aws_iam_role, region, endpoint_url=sts_endpoint_url
            )
            aws_account_category = cred.category
        except ClientError as err:
            err_msg = str(err)
            if "Credential should be scoped to a valid region" not in str(err):
                err_msg = (
                    err_msg
                    + ". Please make sure the AWS Account and Assume Role are correct."
                )
            raise RestError(400, err_msg)  # pylint: disable=raise-missing-from
        except Exception as ex:
            raise RestError(
                BAD_REQ_STATUS_CODE, ex
            )  # pylint: disable=raise-missing-from
        host_name = tac.CATEGORY_HOST_NAME_MAP.get(
            aws_account_category,
            tac.CATEGORY_HOST_NAME_MAP[tac.RegionCategory.COMMERCIAL],
        )
        if not region:
            pattern = r"s3[.-]([\w-]+)\.amazonaws.com"
            matched = re.search(pattern, host_name)
            if matched:
                region = matched.group(1)
            else:
                region = DEFAULT_REGION
        if not s3_endpoint_url:
            s3_endpoint_url = tacommon.format_default_endpoint_url("s3", region)
        s3_conn = boto3.client(
            "s3",
            aws_access_key_id=cred.aws_access_key_id,
            aws_secret_access_key=cred.aws_secret_access_key,
            aws_session_token=cred.aws_session_token,
            region_name=region,
            config=Config(
                signature_version="s3v4",
                read_timeout=READ_TIMEOUT_SEC,
                retries={"max_attempts": 0},
            ),
            endpoint_url=s3_endpoint_url,
        )

        buckets = {}
        try:
            buckets = s3_conn.list_buckets()
        except Exception as ex:
            raise RestError(
                BAD_REQ_STATUS_CODE, ex
            )  # pylint: disable=raise-missing-from

        buckets = [bucket.get("Name") for bucket in buckets.get("Buckets", [])]

        for bucket in buckets:
            confInfo[bucket].append("bucket_name", bucket)
            confInfo[bucket].append("host_name", host_name)


def main():
    """Main method for aws s3 buckets RH."""
    splunk.admin.init(ConfigHandler, splunk.admin.CONTEXT_NONE)


if __name__ == "__main__":
    main()

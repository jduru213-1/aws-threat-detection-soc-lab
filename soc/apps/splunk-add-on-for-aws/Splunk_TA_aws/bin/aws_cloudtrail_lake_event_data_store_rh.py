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
MAX_RESULTS = 1000


class ConfigHandler(splunk.admin.MConfigHandler):
    def setup(self):
        """Setup method for aws Cloudtrail Lake event data store RH."""
        self.supportedArgs.addReqArg("aws_account")
        self.supportedArgs.addOptArg("aws_iam_role")
        self.supportedArgs.addOptArg("aws_region")
        self.supportedArgs.addOptArg("private_endpoint_enabled")
        self.supportedArgs.addOptArg("sts_private_endpoint_url")
        self.supportedArgs.addOptArg("cloudtrail_private_endpoint_url")

    def handleList(self, confInfo):  # pylint: disable=invalid-name, too-many-branches
        """Called when user invokes the "edit" action."""
        aws_account = self.callerArgs.get("aws_account")
        aws_iam_role = self.callerArgs.get("aws_iam_role")

        if aws_account:
            aws_account = aws_account[0]
        else:
            confInfo["event_data_store"].append("event_data_store", [])
            return

        if aws_iam_role:
            aws_iam_role = aws_iam_role[0]

        if self.callerArgs["aws_region"] is not None:
            region = self.callerArgs["aws_region"][0]
        else:
            raise RestError(400, "AWS region is required to list the event data store.")
        if int(self.callerArgs.get("private_endpoint_enabled", [0])[0]):
            if not self.callerArgs.get("aws_region", [None])[0]:
                raise RestError(
                    400, "Field AWS Region is required to use private endpoints"
                )
            endpoint_urls = {
                "cloudtrail_private_endpoint_url": self.callerArgs.get(
                    "cloudtrail_private_endpoint_url", [""]
                )[0],
                "sts_private_endpoint_url": self.callerArgs.get(
                    "sts_private_endpoint_url", [""]
                )[0],
            }
            if (
                endpoint_urls["cloudtrail_private_endpoint_url"]
                and endpoint_urls["sts_private_endpoint_url"]
            ):
                acv.on_fetch_validate_urls(endpoint_urls)
                cloudtrail_private_endpoint_url = endpoint_urls[
                    "cloudtrail_private_endpoint_url"
                ]
                sts_endpoint_url = endpoint_urls["sts_private_endpoint_url"]
            else:
                return confInfo
        else:
            sts_endpoint_url = None
            cloudtrail_private_endpoint_url = None
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

        if not cloudtrail_private_endpoint_url:
            cloudtrail_private_endpoint_url = tacommon.format_default_endpoint_url(
                "cloudtrail", region
            )
        cloudtrail_conn = boto3.client(
            "cloudtrail",
            aws_access_key_id=cred.aws_access_key_id,
            aws_secret_access_key=cred.aws_secret_access_key,
            aws_session_token=cred.aws_session_token,
            region_name=region,
            config=Config(
                signature_version="s3v4",
                read_timeout=READ_TIMEOUT_SEC,
                retries={"max_attempts": 0},
            ),
            endpoint_url=cloudtrail_private_endpoint_url,
        )

        event_data_stores = []
        try:
            event_data_stores = self.list_event_data_store(cloudtrail_conn)
        except Exception as ex:
            raise RestError(
                BAD_REQ_STATUS_CODE, ex
            )  # pylint: disable=raise-missing-from

        for data_store in event_data_stores:
            confInfo[data_store].append("label", data_store)

    def list_event_data_store(self, client):
        params = {"MaxResults": MAX_RESULTS}
        data_store_list = []
        next_token = None
        while True:
            if next_token is not None:
                params["NextToken"] = next_token
            try:
                data_stores = client.list_event_data_stores(**params)
            except Exception as ex:
                raise RestError(
                    BAD_REQ_STATUS_CODE, ex
                )  # pylint: disable=raise-missing-from
            data_store_list += [
                data_store.get("Name")
                for data_store in data_stores.get("EventDataStores", [])
            ]
            next_token = data_stores.get("NextToken")
            if not next_token:
                break
        return data_store_list


def main():
    """Main method for aws cloudtrail lake event data store RH."""
    splunk.admin.init(ConfigHandler, splunk.admin.CONTEXT_NONE)


if __name__ == "__main__":
    main()

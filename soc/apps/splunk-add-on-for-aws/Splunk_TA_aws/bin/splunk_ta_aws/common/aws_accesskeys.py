#
# SPDX-FileCopyrightText: 2021 Splunk, Inc. <sales@splunk.com>
# SPDX-License-Identifier: LicenseRef-Splunk-8-2021
#
#
"""
This should probably be rewritten to just use SplunkAppObjModel directly...
"""


import re

import requests

APPNAME = "Splunk_TA_aws"
KEY_NAMESPACE = APPNAME
KEY_OWNER = "-"

import json

import splunk.clilib.cli_common as scc
import splunktalib.splunk_cluster as sc
from botocore.utils import InstanceMetadataFetcher
from splunksdc import logging

from .credentials_manager import CredentialManager

from botocore.exceptions import (  # isort: skip # pylint: disable=ungrouped-imports
    ConnectionClosedError,
    ConnectTimeoutError,
    EndpointConnectionError,
    ReadTimeoutError,
)


logger = logging.get_module_logger()

RETRYABLE_HTTP_ERRORS = (
    ReadTimeoutError,
    EndpointConnectionError,
    ConnectionClosedError,
    ConnectTimeoutError,
)

# reference taken from botocore/utils.py
DEFAULT_METADATA_SERVICE_TIMEOUT = 1


def extract_region_category(token):
    """Extract region category."""
    METADATA_AZ_URL = "http://169.254.169.254/latest/meta-data/placement/availability-zone"  # pylint: disable=invalid-name

    category = ""
    try:
        http_headers = {"X-aws-ec2-metadata-token": token}
        response = requests.get(
            METADATA_AZ_URL,
            headers=http_headers,
            timeout=DEFAULT_METADATA_SERVICE_TIMEOUT,
        )
        if response.status_code == 200:
            az = response.text  # pylint: disable=invalid-name
            if az:
                if "cn-north" in az:
                    category = 4
                elif "us-gov" in az:
                    category = 2
                else:
                    category = 1
        else:
            logger.debug(
                "error while making metadata service request to %s: %s",
                METADATA_AZ_URL,
                response.text,
            )
    except RETRYABLE_HTTP_ERRORS as e:  # pylint: disable=invalid-name
        logger.error(
            "Caught retryable HTTP exception while making metadata service request to %s: %s",
            METADATA_AZ_URL,
            e,
        )
    except Exception as ex:  # pylint: disable=broad-except
        logger.error(
            "Caught exception while making metadata service request to %s: %s",
            METADATA_AZ_URL,
            ex,
        )

    return category


def extract_account_id(token):
    """Extract account id."""
    METADATA_IAM_INFO_URL = "http://169.254.169.254/latest/meta-data/iam/info"  # pylint: disable=invalid-name

    act_id = ""
    try:
        http_headers = {
            "X-aws-ec2-metadata-token": token,
            "content-type": "application/json",
        }
        response = requests.get(
            METADATA_IAM_INFO_URL,
            headers=http_headers,
            timeout=DEFAULT_METADATA_SERVICE_TIMEOUT,
        )
        if response.status_code == 200:
            try:
                arn_json = response.json()
                # arn:aws(-cn):iam::012233333330:instance-profile/dummy-ec2-iam
                act_id = re.search(r"iam:.*:(\d+):", arn_json["InstanceProfileArn"])
            except json.decoder.JSONDecodeError as ve:  # pylint: disable=invalid-name
                logger.error(
                    "Error while parsing json response %s: %s",
                    METADATA_IAM_INFO_URL,
                    ve,
                )
        else:
            logger.debug(
                "error while making metadata service request to %s: %s",
                METADATA_IAM_INFO_URL,
                response.text,
            )
    except RETRYABLE_HTTP_ERRORS as e:  # pylint: disable=invalid-name
        logger.error(
            "Caught retryable HTTP exception while making metadata service request to %s: %s",
            METADATA_IAM_INFO_URL,
            e,
        )
    except Exception as ex:  # pylint: disable=broad-except
        logger.error(
            "Caught exception while making metadata service request to %s: %s",
            METADATA_IAM_INFO_URL,
            ex,
        )

    if act_id:
        return act_id.group(1)
    else:
        return "0" * 12


# reference taken from botocore/utils.py
def fetch_metadata_token():
    """Fetch metadata token."""
    TOKEN_URL = (  # pylint: disable=invalid-name
        "http://169.254.169.254/latest/api/token"
    )
    http_headers = {"X-aws-ec2-metadata-token-ttl-seconds": "21600"}

    auth_token = ""
    try:
        response = requests.put(
            TOKEN_URL, headers=http_headers, timeout=DEFAULT_METADATA_SERVICE_TIMEOUT
        )
        if response.status_code == 200:
            auth_token = response.text
        else:
            logger.debug(
                "error while making metadata service request to %s: %s",
                TOKEN_URL,
                response.text,
            )
    except RETRYABLE_HTTP_ERRORS as e:  # pylint: disable=invalid-name
        logger.error(
            "Caught retryable HTTP exception while making metadata service request to %s: %s",
            TOKEN_URL,
            e,
        )
    except Exception as ex:  # pylint: disable=invalid-name,broad-except
        logger.error(
            "Caught exception while making metadata service request to %s: %s",
            TOKEN_URL,
            ex,
        )

    return auth_token


def get_ec2_iam_role_creds():
    """Return ec2 role creds."""
    fetcher = InstanceMetadataFetcher(timeout=5.0, num_attempts=10)
    credentials = fetcher.retrieve_iam_role_credentials()

    # Check credentials in returning result
    _REQUIRED_CREDENTIAL_FIELDS = (  # pylint: disable=invalid-name
        "access_key",
        "secret_key",
        "token",
    )
    for field in _REQUIRED_CREDENTIAL_FIELDS:
        if field not in credentials:
            logger.debug(
                "Retrieved credentials is missing required field: %s \n", field
            )
            return None

    # fetching metadata_token as the existing token availabe in the credentials
    # is not working while fetching the account_id and region_category
    metadata_token = fetch_metadata_token()
    if not metadata_token:
        return None

    account_id = extract_account_id(metadata_token)
    region_category = extract_region_category(metadata_token)

    if not region_category or not account_id:
        return None

    cred = {
        "AccessKeyId": credentials["access_key"],
        "SecretAccessKey": credentials["secret_key"],
        "Token": credentials["token"],
        "RegionCategory": region_category,
        "Name": credentials["role_name"],
        "AccountId": account_id,
    }
    return cred


class AwsAccessKey:
    """Class for AWS Access key."""

    def __init__(  # pylint: disable=too-many-arguments
        self,
        key_id,
        secret_key,
        name="default",
        region_category=0,
        token="",
        account_id="",
        is_iam=0,
    ):
        self.name = name
        self.key_id = (  # pylint: disable=consider-using-ternary
            key_id and key_id.strip() or ""
        )
        self.secret_key = (  # pylint: disable=consider-using-ternary
            secret_key and secret_key.strip() or ""
        )
        self.category = region_category
        self.token = token
        self.iam = is_iam
        self.account_id = account_id


class AwsAccessKeyManager:
    """Class for Access key manager."""

    def __init__(self, namespace, owner, session_key):
        self.namespace = namespace
        self.owner = owner
        self._session_key = session_key
        self._cred_mgr = CredentialManager(sessionKey=session_key)

    def set_accesskey(self, key_id, secret_key, name="default"):
        """Sets accesskeys."""
        if name is None:
            name = ""
        # create_or_set() will raise if empty username or password strings are passed
        key_id = (  # pylint: disable=consider-using-ternary
            key_id and key_id.strip() or " "
        )
        secret_key = (  # pylint: disable=consider-using-ternary
            secret_key and secret_key.strip() or " "
        )
        cred = self.get_accesskey(name)
        if cred and cred.key_id != key_id:
            self.delete_accesskey(name)
        self._cred_mgr.create_or_set(
            key_id, name, secret_key, self.namespace, self.owner
        )

    def get_accesskey(self, name="default"):
        """Gets all accesskeys."""
        keys = self.all_accesskeys()
        for key in keys:
            if key.name == name:
                return key
        else:  # pylint: disable=useless-else-on-loop
            return None

    def all_accesskeys(self):
        """Returns access keys."""

        class AccessKeyIterator:
            """Class for Access key iterator."""

            def __init__(self, mgr):
                self.creds = (
                    mgr._cred_mgr.all()
                    .filter_by_app(mgr.namespace)
                    .filter_by_user(mgr.owner)
                )
                self._session_key = mgr._session_key

            def __iter__(self):
                for cred in self.creds:
                    if cred.realm.startswith("__REST_CREDENTIAL__#"):
                        continue

                    yield AwsAccessKey(cred.username, cred.clear_password, cred.realm)

                try:
                    requests.put(
                        "http://169.254.169.254/latest/api/token",
                        headers={"X-aws-ec2-metadata-token-ttl-seconds": "60"},
                        timeout=5,
                    )
                except IOError:
                    logger.debug(
                        "Not running on EC2 instance, skip instance role discovery."
                    )
                    return

                server_info = sc.ServerInfo(scc.getMgmtUri(), self._session_key)
                if not server_info.is_cloud_instance():
                    cred = get_ec2_iam_role_creds()
                    if cred:
                        yield AwsAccessKey(
                            cred["AccessKeyId"],
                            cred["SecretAccessKey"],
                            cred["Name"],
                            cred["RegionCategory"],
                            cred["Token"],
                            cred["AccountId"],
                            1,
                        )

        return AccessKeyIterator(self)

    def delete_accesskey(self, name="default"):
        """Deletes access keys."""
        if name is None:
            name = ""
        cred = self.get_accesskey(name)
        if cred:
            self._cred_mgr.delete(cred.key_id, cred.name, self.namespace, self.owner)

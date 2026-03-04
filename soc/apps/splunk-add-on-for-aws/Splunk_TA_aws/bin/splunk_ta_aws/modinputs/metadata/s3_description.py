#
# SPDX-FileCopyrightText: 2021 Splunk, Inc. <sales@splunk.com>
# SPDX-License-Identifier: LicenseRef-Splunk-8-2021
#
#
"""
File for S3 description of metadata input
"""


import datetime

import boto3
import splunk_ta_aws.common.ta_aws_common as tacommon
import splunk_ta_aws.common.ta_aws_consts as tac
import splunksdc.log as logging
from botocore.client import Config
from botocore.exceptions import ClientError

from . import description as desc

logger = logging.get_module_logger()

skipped_error_code_list = [
    "NoSuchLifecycleConfiguration",
    "NoSuchCORSConfiguration",
    "NoSuchTagSet",
    "UnsupportedArgument",
    "MethodNotAllowed",
]

CREDENTIAL_THRESHOLD = datetime.timedelta(minutes=20)


class S3ConnectionPool:
    """
    S3 connection pool for different regions.
    """

    def __init__(self):
        self._region_conn_pool = {}

    def get_conn(self, config, region):
        """Return s3 connection to region where bucket is located."""
        if region not in self._region_conn_pool:
            retry_dict = tacommon.configure_retry(
                config.get(tac.retry_max_attempts), True
            )
            self._region_conn_pool[region] = boto3.client(
                "s3",
                aws_access_key_id=config[tac.key_id],
                aws_secret_access_key=config[tac.secret_key],
                aws_session_token=config.get("aws_session_token"),
                region_name=region,
                config=Config(signature_version="s3v4", retries=retry_dict),
                endpoint_url=tacommon.format_default_endpoint_url("s3", region),
            )
        else:
            desc.refresh_credentials(
                config, CREDENTIAL_THRESHOLD, self._region_conn_pool[region]
            )

        return self._region_conn_pool[region]


@desc.generate_credentials
@desc.decorate
def s3_buckets(config):
    """Yields S3 buckets."""
    conn_pool = S3ConnectionPool()
    s3_client = conn_pool.get_conn(config, region=config.get(tac.region))
    bucket_arr = s3_client.list_buckets()["Buckets"]
    s3_bucket_client = None

    if bucket_arr is not None and len(bucket_arr) > 0:
        for bucket in bucket_arr:

            try:
                bucket_region = None
                response = s3_client.get_bucket_location(Bucket=bucket["Name"])
                response.pop("ResponseMetadata", None)

                # http://docs.aws.amazon.com/AmazonS3/latest/API/RESTBucketGETlocation.html#RESTBucketGETlocation-responses-response-elements
                # if location is us-east-1, it will return None
                if response.get("LocationConstraint") is None:
                    response["LocationConstraint"] = "us-east-1"

                bucket_region = response.get("LocationConstraint")
                bucket.update(response)

                s3_bucket_client = conn_pool.get_conn(config, region=bucket_region)
            except Exception:  # pylint: disable=broad-except
                logger.exception(
                    "An error occurred when getting bucket location for %s bucket."  # pylint: disable=consider-using-f-string
                    % (bucket["Name"])
                )
                s3_bucket_client = s3_client
            # add other info
            for operation in [
                "get_bucket_accelerate_configuration",
                "get_bucket_cors",
                "get_bucket_lifecycle",
                "get_bucket_logging",
                "get_bucket_tagging",
            ]:
                try:
                    response = getattr(s3_bucket_client, operation)(
                        Bucket=bucket["Name"]
                    )
                    response.pop("ResponseMetadata", None)

                    bucket.update(response)

                except ClientError as client_error:
                    if (
                        "Code" not in client_error.response["Error"]
                        or client_error.response["Error"]["Code"]
                        not in skipped_error_code_list
                    ):
                        logger.exception(
                            "%s operation is invalid in %s bucket."  # pylint: disable=consider-using-f-string
                            % (operation, bucket["Name"])
                        )
                    continue

                except Exception:  # pylint: disable=broad-except
                    logger.exception(
                        "An error occurred when attempting %s operation on %s bucket."  # pylint: disable=consider-using-f-string
                        % (operation, bucket["Name"])
                    )
                    continue

            bucket["Region"] = bucket.get("LocationConstraint")

            yield bucket
            desc.refresh_credentials(config, CREDENTIAL_THRESHOLD, s3_client)

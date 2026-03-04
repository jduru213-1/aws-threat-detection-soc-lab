#
# SPDX-FileCopyrightText: 2021 Splunk, Inc. <sales@splunk.com>
# SPDX-License-Identifier: LicenseRef-Splunk-8-2021
#
#
"""
File for AWS generic S3 input.
"""


import codecs
import re
from collections import namedtuple

import botocore
import splunksdc.log as logging
from . import aws_s3_consts as asc

logger = logging.get_module_logger()
BOTO_DATE_FORMAT = r"%Y-%m-%dT%H:%M:%S.000Z"
NOT_FOUND_STATUS = 404

sourcetype_to_keyname_regex = {
    asc.aws_cloudtrail: r"\d+_CloudTrail_[\w-]+_\d{4}\d{2}\d{2}T\d{2}\d{2}Z_.{16}\.json\.gz$",
    asc.aws_elb_accesslogs: r".*\d+_elasticloadbalancing_[\w-]+_.+\.log(\.gz)?$",
    asc.aws_cloudfront_accesslogs: r".+\.\d{4}-\d{2}-\d{2}-\d{2}\..+\.gz$",
    asc.aws_s3_accesslogs: r".+\d{4}-\d{2}-\d{2}-\d{2}-\d{2}-\d{2}-.+$",
}


def _build_regex(regex_str):
    if regex_str:
        exact_str = regex_str if regex_str[-1] == "$" else regex_str + "$"
        return re.compile(exact_str)
    else:
        return None


def _match_regex(white_matcher, black_matcher, key):
    if white_matcher is not None:
        if white_matcher.search(key["Key"]):
            return True
    else:
        if black_matcher is None or not black_matcher.search(key["Key"]):
            return True
    return False


class TupleMaker:
    """Class for Tuple Maker."""

    def __init__(self, typename, recipe):
        self._recipe = recipe
        self._type = namedtuple(typename, recipe.keys())

    def __call__(self, record, **kwargs):
        params = {key: getter(record) for key, getter in self._recipe.items()}
        params.update(kwargs)
        return self._type(**params)

    @classmethod
    def boto_key_adaptor(cls, arg):
        """Adaptor layer for using boto style access."""
        adaptor = cls(
            "BotoKeyAdaptor",
            {
                "body": lambda _: _.get("Body"),
                "name": lambda _: _.get("Key"),
                "size": lambda _: _.get("Size", _.get("ContentLength")),
                "etag": lambda _: _.get("ETag", "").strip('"'),
                "last_modified": lambda _: _["LastModified"].strftime(BOTO_DATE_FORMAT),
                "storage_class": lambda _: _.get("StorageClass"),
            },
        )
        return adaptor(arg)


def get_keys(  # pylint: disable=too-many-locals, too-many-arguments
    refresh_creds_func,
    s3_conn,
    bucket,
    prefix="",
    whitelist=None,
    blacklist=None,
    last_modified=None,
    storage_classes=("STANDARD", "STANDARD_IA", "REDUCED_REDUNDANCY"),
):
    """Returns keys."""
    if prefix is None:
        prefix = ""
    black_matcher = _build_regex(blacklist)
    white_matcher = _build_regex(whitelist)

    scanned_keys = 0
    total_scanned_keys = 0

    paginator = s3_conn.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for key in page.get("Contents", []):
            total_scanned_keys += 1
            scanned_keys += 1

            # Warning for the skipped keys when 1 million keys are scanned
            if scanned_keys == 1000000:
                logger.warning(
                    f"Scan is in progress. {scanned_keys} keys are scanned. Amazon S3 bucket with an excessive "
                    "number of files or abundant size will result in significant performance degradation and "
                    "ingestion delays. It is recommended to use SQS-Based S3 input instead of Generic S3 to ingest "
                    "the Amazon S3 bucket data."
                )
                scanned_keys = 0

            key_last_modified = key["LastModified"].strftime(BOTO_DATE_FORMAT)

            if (not last_modified) or (key_last_modified >= last_modified):

                if _match_regex(white_matcher, black_matcher, key):

                    if storage_classes and key["StorageClass"] not in storage_classes:
                        logger.warning(
                            "Skipped this key because storage class does not match"
                            "(only supports STANDARD, STANDARD_IA and REDUCED_REDUNDANCY).",
                            key_name=key["Key"],
                            storage_class=key["StorageClass"],
                        )
                        continue

                    yield TupleMaker.boto_key_adaptor(key)

        refresh_creds_func()

    # Warning for the total scanned keys in one interval
    logger.info(
        f"Total {total_scanned_keys} keys are scanned. Amazon S3 bucket with an excessive number of "
        "files or abundant size will result in significant performance degradation and ingestion delays. "
        "It is recommended to use SQS-Based S3 input instead of Generic S3 to ingest the Amazon S3 bucket data."
    )


def get_key(s3_conn, bucket, key, byte_range=None):
    """Returns key"""
    try:
        res = {}
        if byte_range:
            res = s3_conn.get_object(Bucket=bucket, Key=key, Range=byte_range)
        else:
            res = s3_conn.get_object(Bucket=bucket, Key=key)
        res["Key"] = key
        return TupleMaker.boto_key_adaptor(res)
    except botocore.exceptions.ClientError as err:
        if err.response["ResponseMetadata"]["HTTPStatusCode"] == NOT_FOUND_STATUS:
            return None
        raise


def detect_unicode_by_bom(data):
    """Detects encoding."""
    if data[:2] == b"\xFE\xFF":
        return "UTF-16BE"
    if data[:2] == b"\xFF\xFE":
        return "UTF-16LE"
    if data[:4] == b"\x00\x00\xFE\xFF":
        return "UTF-32BE"
    if data[:4] == b"\xFF\xFE\x00\x00":
        return "UTF-32LE"
    return "UTF-8"


def get_decoder(encoding, data):
    """Returns decoder."""
    if not encoding:
        if data:
            encoding = detect_unicode_by_bom(data)
        else:
            encoding = "UTF-8"

    try:
        decoder = codecs.getincrementaldecoder(encoding)(errors="replace")
        return decoder, encoding
    except LookupError:
        decoder = codecs.getincrementaldecoder("UTF-8")(errors="replace")
        return decoder, encoding

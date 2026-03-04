#
# SPDX-FileCopyrightText: 2021 Splunk, Inc. <sales@splunk.com>
# SPDX-License-Identifier: LicenseRef-Splunk-8-2021
#
#
"""
File for description input.
"""


import datetime
import json
import time

import splunk_ta_aws.common.ta_aws_consts as tac
import splunksdc.log as logging
from botocore.credentials import Credentials
from botocore.exceptions import ClientError
from dateutil.tz import tzutc
from splunk_ta_aws.common.ta_aws_common import load_credentials_from_cache

_MIN_TTL = datetime.timedelta(minutes=5)

logger = logging.get_module_logger()


_BUILT_IN_TYPES = (
    type(None),
    bool,
    int,
    int,
    float,
    bytes,
    str,
    list,
    dict,
)

DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%S.%f"


class _ExtendedEncoder(json.JSONEncoder):
    def default(self, obj):  # pylint: disable=arguments-renamed
        # check datetime
        if isinstance(obj, datetime.datetime):
            # ISO 8601 time format
            if obj.utcoffset() is None or obj.utcoffset().total_seconds() == 0:
                return obj.strftime(DATETIME_FORMAT)[:-3] + "Z"
            else:
                return obj.strftime(DATETIME_FORMAT)[:-3] + obj.strftime("%z")

        if not isinstance(obj, _BUILT_IN_TYPES):
            return str(obj)

        return json.JSONEncoder.default(self, obj)


def decorate(func):
    """Decorator to add common metadata for each item."""

    def wrapper(config, *args, **kwargs):
        for item in func(config, *args, **kwargs):
            # SPL-219983: remove adding AccountID and Region to each item
            yield serialize(item)

    return wrapper


def serialize(value):
    """Serialises value."""
    return json.dumps(value, cls=_ExtendedEncoder)


def generate_credentials(func):
    """
    Decorator for refreshing credentials.

    :param func:
    :return:
    """

    def wrapper(config, *args, **kwargs):
        load_credentials(config)
        return func(config, *args, **kwargs)

    return wrapper


def load_credentials(config):
    """Loads new credentials."""
    credentials = load_credentials_from_cache(
        config[tac.server_uri],
        config[tac.session_key],
        config[tac.aws_account],
        config.get(tac.aws_iam_role),
        config.get(tac.region),
    )
    config[tac.key_id] = credentials.aws_access_key_id
    config[tac.secret_key] = credentials.aws_secret_access_key
    config["aws_session_token"] = credentials.aws_session_token
    config[tac.account_id] = credentials.account_id
    config["token_expiration"] = credentials.expiration


def refresh_credentials(config, credential_threshold, client):
    """Refreshes credentials."""
    if need_retire(config["token_expiration"], credential_threshold):
        logger.info("Refresh credentials of S3 connection.")
        load_credentials(config)
        # Change credentails dynamically inside boto3 client
        client._request_signer._credentials = (  # pylint: disable=protected-access
            Credentials(
                config[tac.key_id], config[tac.secret_key], config["aws_session_token"]
            )
        )


def need_retire(expiration, threshold=_MIN_TTL):
    """Checks if it is expired or not."""
    if not expiration:
        return False
    now = datetime.datetime.utcnow().replace(tzinfo=tzutc())
    delta = expiration - now
    return delta < threshold

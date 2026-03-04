#
# SPDX-FileCopyrightText: 2021 Splunk, Inc. <sales@splunk.com>
# SPDX-License-Identifier: LicenseRef-Splunk-8-2021
#
#
"""
File for Firehose description for metadata input.
"""


import datetime

from . import description as desc
from . import aws_description_helper_functions as helper

CREDENTIAL_THRESHOLD = datetime.timedelta(minutes=20)


def firehose_list_delivery_streams(config):
    """
    This function implements pagination for fetching all
    delivery stream names because the boto3 python sdk
    does not provide pagination by default for this API.

    :param config(dict): AWS credentials and session information
    :yield delivery_stream_name(str): Delivery stream name
    """
    # Indicate there are more pages
    has_more_delivery_streams = True
    # Indicate stream name to be used for pagination
    exclusive_start_delivery_stream_name = None
    while has_more_delivery_streams:
        params = dict()
        if exclusive_start_delivery_stream_name:
            params[
                "ExclusiveStartDeliveryStreamName"
            ] = exclusive_start_delivery_stream_name
        response = helper.metadata_list_helper(
            config, "firehose", "list_delivery_streams", "DeliveryStreamNames", params
        )
        paginated_delivery_stream_names = list(response)
        yield from paginated_delivery_stream_names
        if paginated_delivery_stream_names:
            exclusive_start_delivery_stream_name = paginated_delivery_stream_names[-1]
        else:
            has_more_delivery_streams = False


@desc.generate_credentials
@desc.decorate
def firehose_describe_delivery_streams(config):
    """Yields Firehose delivery stream description."""
    delivery_stream_names = firehose_list_delivery_streams(config)
    for delivery_stream_name in delivery_stream_names:
        response = helper.metadata_list_helper(
            config,
            "firehose",
            "describe_delivery_stream",
            "DeliveryStreamDescription",
            {"DeliveryStreamName": delivery_stream_name},
        )
        # Get item from generator object
        delivery_stream_description = next(response)
        yield delivery_stream_description


@desc.generate_credentials
@desc.decorate
def firehose_list_tags_for_resource(config):
    """Yields Firehose delivery stream with tags."""
    events = helper.list_tags_for_resource(config, "firehose")
    for event in events:
        yield event

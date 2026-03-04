#
# SPDX-FileCopyrightText: 2021 Splunk, Inc. <sales@splunk.com>
# SPDX-License-Identifier: LicenseRef-Splunk-8-2021
#
#
"""
File for Kinesis description for metadata input.
"""


import datetime

from . import description as desc
from . import aws_description_helper_functions as helper

CREDENTIAL_THRESHOLD = datetime.timedelta(minutes=20)


@desc.generate_credentials
@desc.decorate
def kinesis_stream(config):
    """Yields Kinesis data stream."""
    kinesis_data_streams = helper.metadata_list_helper(
        config, "kinesis", "list_streams", "StreamSummaries"
    )
    for stream in kinesis_data_streams:
        response = helper.metadata_list_helper(
            config,
            "kinesis",
            "describe_stream_summary",
            "StreamDescriptionSummary",
            {"StreamARN": stream["StreamARN"]},
        )
        # Get item from generator object
        stream_description_summary = next(response)
        yield stream_description_summary


@desc.generate_credentials
@desc.decorate
def kinesis_list_shards(config):
    """Yields shard for each Kinesis data stream."""
    kinesis_data_streams = helper.metadata_list_helper(
        config, "kinesis", "list_streams", "StreamSummaries"
    )
    for stream in kinesis_data_streams:
        shards = helper.metadata_list_helper(
            config,
            "kinesis",
            "list_shards",
            "Shards",
            {"StreamARN": stream["StreamARN"]},
        )
        for shard in shards:
            shard["StreamARN"] = stream["StreamARN"]
            shard["StreamName"] = stream["StreamName"]
            yield shard


@desc.generate_credentials
@desc.decorate
def kinesis_describe_stream_consumers(config):
    """Yields consumer for each Kinesis data stream."""
    kinesis_data_streams = helper.metadata_list_helper(
        config, "kinesis", "list_streams", "StreamSummaries"
    )
    for stream in kinesis_data_streams:
        consumers = helper.metadata_list_helper(
            config,
            "kinesis",
            "list_stream_consumers",
            "Consumers",
            {"StreamARN": stream["StreamARN"]},
        )
        for consumer in consumers:
            response = helper.metadata_list_helper(
                config,
                "kinesis",
                "describe_stream_consumer",
                "ConsumerDescription",
                {
                    "StreamARN": stream["StreamARN"],
                    "ConsumerARN": consumer["ConsumerARN"],
                },
            )
            # Get item from generator object
            consumer_description = next(response)
            yield consumer_description


@desc.generate_credentials
@desc.decorate
def kinesis_list_tags_for_resource(config):
    """Yields Kinesis data stream with tags."""
    events = helper.list_tags_for_resource(config, "kinesis")
    for event in events:
        yield event


@desc.generate_credentials
@desc.decorate
def kinesis_describe_limits(config):
    kinesis_conn = helper.get_conn(config, "kinesis")
    limits = kinesis_conn.describe_limits()
    # Remove metadata of response
    limits.pop("ResponseMetadata", None)
    yield limits

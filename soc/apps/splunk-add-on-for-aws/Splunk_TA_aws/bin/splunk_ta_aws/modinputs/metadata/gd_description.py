#
# SPDX-FileCopyrightText: 2021 Splunk, Inc. <sales@splunk.com>
# SPDX-License-Identifier: LicenseRef-Splunk-8-2021
#
#
"""
File for GuardDuty description for metadata input.
"""


import splunk_ta_aws.common.ta_aws_consts as tac

from . import description as desc
from . import aws_description_helper_functions as helper


@desc.generate_credentials
@desc.decorate
def gd_list_detectors(config):
    """Fetches GuardDuty Detectors"""
    event = dict()
    event["Region"] = config[tac.region]
    detectors = helper.metadata_list_helper(
        config, "guardduty", "list_detectors", "DetectorIds"
    )
    event["DetectorIds"] = [detector for detector in detectors]
    yield event


@desc.generate_credentials
@desc.decorate
def gd_describe_publishing_destination(config):
    gd_client = helper.get_conn(config, "guardduty")
    """Fetches detectors """
    gd_detectors = helper.metadata_list_helper(
        config, "guardduty", "list_detectors", "DetectorIds"
    )
    for detector in gd_detectors:
        resp = gd_client.list_publishing_destinations(DetectorId=detector)
        pub_destinations = resp["Destinations"]
        for dest in pub_destinations:
            desc_pub_dest = gd_client.describe_publishing_destination(
                DetectorId=detector, DestinationId=dest["DestinationId"]
            )
            desc_pub_dest.pop("ResponseMetadata", None)
            yield desc_pub_dest


@desc.generate_credentials
@desc.decorate
def gd_list_tags_for_resource(config):
    events = helper.list_tags_for_resource(config, "guardduty")
    for event in events:
        yield event

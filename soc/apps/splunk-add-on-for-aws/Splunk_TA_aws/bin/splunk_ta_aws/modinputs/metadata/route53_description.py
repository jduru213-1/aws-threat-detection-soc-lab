#
# SPDX-FileCopyrightText: 2021 Splunk, Inc. <sales@splunk.com>
# SPDX-License-Identifier: LicenseRef-Splunk-8-2021
#
#
"""
File for Route 53 description for metadata input.
"""


import copy

import splunk_ta_aws.common.ta_aws_consts as tac
from . import description as desc
from . import aws_description_helper_functions as helper

ROUTE53_SERVICE = "route53"


@desc.generate_credentials
@desc.decorate
def route53_list_health_checks(config):
    """Yields Route 53 health check."""
    health_checks = helper.metadata_list_helper(
        config, ROUTE53_SERVICE, "list_health_checks", "HealthChecks"
    )
    yield from health_checks


@desc.generate_credentials
@desc.decorate
def route53_list_hosted_zones(config):
    """Yields Route 53 hosted zone."""
    hosted_zones = helper.metadata_list_helper(
        config, ROUTE53_SERVICE, "list_hosted_zones", "HostedZones"
    )
    yield from hosted_zones


@desc.generate_credentials
@desc.decorate
def route53_list_hosted_zones_by_vpc(config):
    """
    Yields Route 53 hosted zone by vpc.

    For fetching hosted zones by vpc, the list of all available vpcs need
    to be fetched first using ec2 service. Then hosted zones will be fetched
    for all available vpcs.
    """
    # Fetch all available vpcs
    all_vpcs = []
    regions = helper.metadata_list_helper(config, "ec2", "describe_regions", "Regions")
    region_config = {
        tac.key_id: config.get(tac.key_id),
        tac.secret_key: config.get(tac.secret_key),
        "aws_session_token": config.get("aws_session_token"),
        "token_expiration": config.get("token_expiration"),
        tac.retry_max_attempts: config.get(tac.retry_max_attempts),
    }
    for region in regions:
        region_config[tac.region] = region["RegionName"]
        vpcs = helper.metadata_list_helper(
            region_config, "ec2", "describe_vpcs", "Vpcs"
        )
        for vpc in vpcs:
            vpc_info = {"VPCId": vpc["VpcId"], "VPCRegion": region["RegionName"]}
            all_vpcs.append(vpc_info)

    # Fetch hosted zones by vpc
    for vpc in all_vpcs:
        hosted_zones_by_vpc = helper.metadata_pagination_helper(
            config,
            ROUTE53_SERVICE,
            "list_hosted_zones_by_vpc",
            "HostedZoneSummaries",
            "NextToken",
            "NextToken",
            vpc,
        )
        for hosted_zone in hosted_zones_by_vpc:
            hosted_zone["VPCId"] = vpc["VPCId"]
            hosted_zone["VPCRegion"] = vpc["VPCRegion"]
            yield hosted_zone


@desc.generate_credentials
@desc.decorate
def route53_list_reusable_delegation_sets(config):
    """Yields Route 53 reusable delegation set."""
    reusable_delegation_sets = helper.metadata_pagination_helper(
        config,
        ROUTE53_SERVICE,
        "list_reusable_delegation_sets",
        "DelegationSets",
        "IsTruncated",
        ["Marker", "NextMarker"],
    )
    yield from reusable_delegation_sets


@desc.generate_credentials
@desc.decorate
def route53_list_query_logging_configs(config):
    """Yields Route 53 DNS query logging config."""
    query_logging_configs = helper.metadata_list_helper(
        config, ROUTE53_SERVICE, "list_query_logging_configs", "QueryLoggingConfigs"
    )
    yield from query_logging_configs


@desc.generate_credentials
@desc.decorate
def route53_list_traffic_policies(config):
    """Yields Route 53 traffic policy."""
    traffic_policies = helper.metadata_pagination_helper(
        config,
        ROUTE53_SERVICE,
        "list_traffic_policies",
        "TrafficPolicySummaries",
        "IsTruncated",
        "TrafficPolicyIdMarker",
    )
    yield from traffic_policies


@desc.generate_credentials
@desc.decorate
def route53_list_traffic_policy_versions(config):
    """Yields Route 53 traffic policy version."""
    traffic_policies = helper.metadata_pagination_helper(
        config,
        ROUTE53_SERVICE,
        "list_traffic_policies",
        "TrafficPolicySummaries",
        "IsTruncated",
        "TrafficPolicyIdMarker",
    )
    for traffic_policy in traffic_policies:
        traffic_policy_versions = helper.metadata_pagination_helper(
            config,
            ROUTE53_SERVICE,
            "list_traffic_policy_versions",
            "TrafficPolicies",
            "IsTruncated",
            "TrafficPolicyVersionMarker",
            {"Id": traffic_policy["Id"]},
        )
        yield from traffic_policy_versions


@desc.generate_credentials
@desc.decorate
def route53_list_traffic_policy_instances(config):
    """Yields Route 53 traffic policy instance."""
    traffic_policy_instances = helper.metadata_pagination_helper(
        config,
        ROUTE53_SERVICE,
        "list_traffic_policy_instances",
        "TrafficPolicyInstances",
        "IsTruncated",
        "TrafficPolicyInstanceNameMarker",
    )
    yield from traffic_policy_instances


@desc.generate_credentials
@desc.decorate
def route53_list_resource_record_sets(config):
    """Yields Route 53 resource record set."""
    hosted_zones = helper.metadata_list_helper(
        config, ROUTE53_SERVICE, "list_hosted_zones", "HostedZones"
    )
    for hosted_zone in hosted_zones:
        resource_record_sets = helper.metadata_list_helper(
            config,
            ROUTE53_SERVICE,
            "list_resource_record_sets",
            "ResourceRecordSets",
            {"HostedZoneId": hosted_zone["Id"]},
        )
        for resource_record_set in resource_record_sets:
            resource_record_set["HostedZoneName"] = hosted_zone["Name"]
            resource_record_set["HostedZoneId"] = hosted_zone["Id"]
            yield resource_record_set


@desc.generate_credentials
@desc.decorate
def route53_list_tags_for_resource(config):
    """Yields Route 53 resources with tags."""
    events = helper.list_tags_for_resource(config, ROUTE53_SERVICE)
    yield from events

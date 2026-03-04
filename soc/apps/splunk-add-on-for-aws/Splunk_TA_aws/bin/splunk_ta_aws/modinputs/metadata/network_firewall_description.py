#
# SPDX-FileCopyrightText: 2021 Splunk, Inc. <sales@splunk.com>
# SPDX-License-Identifier: LicenseRef-Splunk-8-2021
#
#
"""
File for Network firewall description for metadata input.
"""


import datetime
import json

import splunksdc.log as logging
from . import description as desc
from . import aws_description_helper_functions as helper

logger = logging.get_module_logger()

CREDENTIAL_THRESHOLD = datetime.timedelta(minutes=20)
NETWORK_FIREWALL_SERVICE = "network-firewall"


@desc.generate_credentials
@desc.decorate
def network_firewall_describe_firewalls(config):
    """Yields network firewall description."""
    firewalls = helper.metadata_list_helper(
        config, NETWORK_FIREWALL_SERVICE, "list_firewalls", "Firewalls"
    )
    for firewall in firewalls:
        response = helper.metadata_list_helper(
            config,
            NETWORK_FIREWALL_SERVICE,
            "describe_firewall",
            ["Firewall", "FirewallStatus"],
            {"FirewallArn": firewall["FirewallArn"]},
        )
        yield from response


@desc.generate_credentials
@desc.decorate
def network_firewall_describe_logging_configurations(config):
    """Yields network firewall logging configuration."""
    firewalls = helper.metadata_list_helper(
        config, NETWORK_FIREWALL_SERVICE, "list_firewalls", "Firewalls"
    )
    for firewall in firewalls:
        response = helper.metadata_list_helper(
            config,
            NETWORK_FIREWALL_SERVICE,
            "describe_logging_configuration",
            None,
            {"FirewallArn": firewall["FirewallArn"]},
        )
        yield from response


@desc.generate_credentials
@desc.decorate
def network_firewall_describe_firewall_policies(config):
    """Yields network firewall policy description."""
    firewall_policies = helper.metadata_list_helper(
        config, NETWORK_FIREWALL_SERVICE, "list_firewall_policies", "FirewallPolicies"
    )
    for firewall_policy in firewall_policies:
        response = helper.metadata_list_helper(
            config,
            NETWORK_FIREWALL_SERVICE,
            "describe_firewall_policy",
            ["FirewallPolicy", "FirewallPolicyResponse"],
            {"FirewallPolicyArn": firewall_policy["Arn"]},
        )
        yield from response


@desc.generate_credentials
@desc.decorate
def network_firewall_describe_rule_groups(config):
    """Yields network firewall rule group description."""
    rule_groups = helper.metadata_list_helper(
        config, NETWORK_FIREWALL_SERVICE, "list_rule_groups", "RuleGroups"
    )
    for rule_group in rule_groups:
        response = helper.metadata_list_helper(
            config,
            NETWORK_FIREWALL_SERVICE,
            "describe_rule_group",
            ["RuleGroup", "RuleGroupResponse"],
            {"RuleGroupArn": rule_group["Arn"]},
        )
        yield from response


@desc.generate_credentials
@desc.decorate
def network_firewall_list_tags_for_resource(config):
    """Yields network firewall resources with tags."""
    events = helper.list_tags_for_resource(config, NETWORK_FIREWALL_SERVICE)
    for event in events:
        yield event


@desc.generate_credentials
@desc.decorate
def network_firewall_describe_resource_policies(config):
    """Yields network firewall resource policy."""

    def describe_resource_policy(resource):
        try:
            generator = helper.metadata_list_helper(
                config,
                NETWORK_FIREWALL_SERVICE,
                "describe_resource_policy",
                "Policy",
                {"ResourceArn": resource["Arn"]},
            )
            response = list(generator)
            if response:
                # Get item from list and convert str to dict
                # for json field extraction in Splunk
                resource_policy = json.loads(response[0])
                data = {"ResourceARN": resource["Arn"], "Policy": resource_policy}
                return data
        except Exception as e:
            if "ResourceNotFoundException" in str(e):
                logger.info(
                    "Skipping resource {} as it does not have resource policy attached.".format(
                        resource["Name"]
                    )
                )
                return
            raise e

    # For firewall policies
    firewall_policies = helper.metadata_list_helper(
        config, NETWORK_FIREWALL_SERVICE, "list_firewall_policies", "FirewallPolicies"
    )
    for firewall_policy in firewall_policies:
        resource_policy = describe_resource_policy(firewall_policy)
        if resource_policy:
            yield resource_policy

    # For rule groups
    rule_groups = helper.metadata_list_helper(
        config, NETWORK_FIREWALL_SERVICE, "list_rule_groups", "RuleGroups"
    )
    for rule_group in rule_groups:
        resource_policy = describe_resource_policy(rule_group)
        if resource_policy:
            yield resource_policy

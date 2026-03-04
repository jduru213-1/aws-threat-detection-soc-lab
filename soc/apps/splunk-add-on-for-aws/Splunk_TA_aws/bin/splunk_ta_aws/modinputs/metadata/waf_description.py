#
# SPDX-FileCopyrightText: 2021 Splunk, Inc. <sales@splunk.com>
# SPDX-License-Identifier: LicenseRef-Splunk-8-2021
#
#
"""
File for WAF Classic and WAFv2 metadata input.
"""


import datetime


import splunksdc.log as logging

from . import description as desc
from . import aws_description_helper_functions as helper

logger = logging.get_module_logger()

CREDENTIAL_THRESHOLD = datetime.timedelta(minutes=20)

########## WAF (Classic) APIs ##########


@desc.generate_credentials
@desc.decorate
def list_geo_match_sets(config):
    """Yields GEO match sets."""
    geo_match_sets = helper.metadata_list_helper(
        config, "waf", "list_geo_match_sets", "GeoMatchSets"
    )
    yield from geo_match_sets


@desc.generate_credentials
@desc.decorate
def list_byte_match_sets(config):
    """Yields byte_match_sets."""
    byte_match_sets = helper.metadata_list_helper(
        config, "waf", "list_byte_match_sets", "ByteMatchSets"
    )
    yield from byte_match_sets


@desc.generate_credentials
@desc.decorate
def list_activated_rules_in_rule_group(config):
    """Yields activated_rules_in_rule_group."""
    list_rule_groups = helper.metadata_list_helper(
        config, "waf", "list_rule_groups", "RuleGroups"
    )
    for rule in list_rule_groups:
        activated_rules = helper.metadata_list_helper(
            config,
            "waf",
            "list_activated_rules_in_rule_group",
            "ActivatedRules",
            {"RuleGroupId": rule["RuleGroupId"]},
        )
        yield from activated_rules


@desc.generate_credentials
@desc.decorate
def list_rules(config):
    """Yields rules."""
    rules = helper.metadata_list_helper(config, "waf", "list_rules", "Rules")
    yield from rules


@desc.generate_credentials
@desc.decorate
def list_rule_groups(config):
    """Yields rule groups."""
    rule_groups = helper.metadata_list_helper(
        config, "waf", "list_rule_groups", "RuleGroups"
    )
    yield from rule_groups


@desc.generate_credentials
@desc.decorate
def list_regex_match_sets(config):
    """Yields an array of Regex Match Set Summary objects."""
    match_sets = helper.metadata_list_helper(
        config, "waf", "list_regex_match_sets", "RegexMatchSets"
    )
    yield from match_sets


@desc.generate_credentials
@desc.decorate
def list_regex_pattern_sets(config):
    """Yields an array of Regex Pattern Set Summary objects."""
    pattern_sets = helper.metadata_list_helper(
        config, "waf", "list_regex_pattern_sets", "RegexPatternSets"
    )
    yield from pattern_sets


@desc.generate_credentials
@desc.decorate
def list_ip_sets(config):
    """Yields list-ip-sets."""
    ip_sets = helper.metadata_list_helper(config, "waf", "list_ip_sets", "IPSets")
    yield from ip_sets


@desc.generate_credentials
@desc.decorate
def list_rate_based_rules(config):
    """Yields list-rate-based-rules."""
    rate_based_rules = helper.metadata_list_helper(
        config, "waf", "list_rate_based_rules", "Rules"
    )
    yield from rate_based_rules


@desc.generate_credentials
@desc.decorate
def list_logging_configurations(config):
    """Yields list-logging-configurations."""
    logging_configurations = helper.metadata_list_helper(
        config,
        "waf",
        "list_logging_configurations",
        "LoggingConfigurations",
        {"Limit": 100},
    )
    yield from logging_configurations


@desc.generate_credentials
@desc.decorate
def list_web_acls(config):
    """Yields list_web_acls."""
    web_acls = helper.metadata_list_helper(config, "waf", "list_web_acls", "WebACLs")
    yield from web_acls


@desc.generate_credentials
@desc.decorate
def list_size_constraint_sets(config):
    """Yields list_size_constraint_sets."""
    size_constraint_sets = helper.metadata_list_helper(
        config, "waf", "list_size_constraint_sets", "SizeConstraintSets"
    )
    yield from size_constraint_sets


@desc.generate_credentials
@desc.decorate
def list_xss_match_sets(config):
    """Yields list_xss_match_sets."""
    xss_match_sets = helper.metadata_list_helper(
        config, "waf", "list_xss_match_sets", "XssMatchSets"
    )
    yield from xss_match_sets


@desc.generate_credentials
@desc.decorate
def list_sql_injection_match_sets(config):
    """Yields list_sql_injection_match_sets."""
    sql_injection_match_sets = helper.metadata_list_helper(
        config, "waf", "list_sql_injection_match_sets", "SqlInjectionMatchSets"
    )
    yield from sql_injection_match_sets


@desc.generate_credentials
@desc.decorate
def list_tags_for_resource(config):
    """Yields tags for all WAF resources."""
    events = helper.list_tags_for_resource(config, "waf")
    yield from events


########## WAF v2 APIs ##########


@desc.generate_credentials
@desc.decorate
def wafv2_list_available_managed_rule_group_versions_regional(config):
    """Yields list_available_managed_rule_group_versions REGIONAL scope."""
    managed_rule_groups = helper.metadata_list_helper(
        config,
        "wafv2",
        "list_available_managed_rule_groups",
        "ManagedRuleGroups",
        {"Scope": "REGIONAL"},
    )
    for managed_rule_group in managed_rule_groups:
        managed_rule_groups_versions = helper.metadata_list_helper(
            config,
            "wafv2",
            "list_available_managed_rule_group_versions",
            "Versions",
            {
                "VendorName": managed_rule_group["VendorName"],
                "Name": managed_rule_group["Name"],
                "Scope": "REGIONAL",
            },
        )
        versions_list = []
        for managed_rule_groups_version in managed_rule_groups_versions:
            versions_list.append(managed_rule_groups_version)
        managed_rule_group["Versions"] = versions_list
        yield managed_rule_group


@desc.generate_credentials
@desc.decorate
def wafv2_list_available_managed_rule_group_versions_cloudfront(config):
    """Yields list_available_managed_rule_group_versions CLOUDFRONT scope."""
    managed_rule_groups = helper.metadata_list_helper(
        config,
        "wafv2",
        "list_available_managed_rule_groups",
        "ManagedRuleGroups",
        {"Scope": "CLOUDFRONT"},
    )
    for managed_rule_group in managed_rule_groups:
        managed_rule_groups_versions = helper.metadata_list_helper(
            config,
            "wafv2",
            "list_available_managed_rule_group_versions",
            "Versions",
            {
                "VendorName": managed_rule_group["VendorName"],
                "Name": managed_rule_group["Name"],
                "Scope": "CLOUDFRONT",
            },
        )
        versions_list = []
        for managed_rule_groups_version in managed_rule_groups_versions:
            versions_list.append(managed_rule_groups_version)
        managed_rule_group["Versions"] = versions_list
        yield managed_rule_group


@desc.generate_credentials
@desc.decorate
def wafv2_list_logging_configurations_regional(config):
    """Yields WAFv2 logging configurations."""
    logging_configurations_regional = helper.metadata_pagination_helper(
        config,
        "wafv2",
        "list_logging_configurations",
        "LoggingConfigurations",
        "NextMarker",
        "NextMarker",
        {"Scope": "REGIONAL"},
    )
    yield from logging_configurations_regional


@desc.generate_credentials
@desc.decorate
def wafv2_list_logging_configurations_cloudfront(config):
    """Yields WAFv2 logging configurations."""
    logging_configurations_cloudfront = helper.metadata_pagination_helper(
        config,
        "wafv2",
        "list_logging_configurations",
        "LoggingConfigurations",
        "NextMarker",
        "NextMarker",
        {"Scope": "CLOUDFRONT"},
    )
    yield from logging_configurations_cloudfront


@desc.generate_credentials
@desc.decorate
def wafv2_list_ip_sets_regional(config):
    """Yields WAFv2 IP sets."""
    ip_sets_regional = helper.metadata_pagination_helper(
        config,
        "wafv2",
        "list_ip_sets",
        "IPSets",
        "NextMarker",
        "NextMarker",
        {"Scope": "REGIONAL"},
    )
    yield from ip_sets_regional


@desc.generate_credentials
@desc.decorate
def wafv2_list_ip_sets_cloudfront(config):
    """Yields WAFv2 IP sets."""
    ip_sets_cloudfront = helper.metadata_pagination_helper(
        config,
        "wafv2",
        "list_ip_sets",
        "IPSets",
        "NextMarker",
        "NextMarker",
        {"Scope": "CLOUDFRONT"},
    )
    yield from ip_sets_cloudfront


@desc.generate_credentials
@desc.decorate
def wafv2_list_tags_for_resource(config):
    """Yields tags for all WAFv2 resources."""
    events = helper.list_tags_for_resource(config, "wafv2")
    yield from events

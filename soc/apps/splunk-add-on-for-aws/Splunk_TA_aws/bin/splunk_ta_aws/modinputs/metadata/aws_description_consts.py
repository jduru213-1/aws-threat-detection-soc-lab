#
# SPDX-FileCopyrightText: 2021 Splunk, Inc. <sales@splunk.com>
# SPDX-License-Identifier: LicenseRef-Splunk-8-2021
#
#
# pylint: disable=invalid-name
"""
Constants file for AWS metadata input.
"""
description_log = "splunk_aws_metadata"
description_log_ns = "splunk_ta_aws_metadata"
mod_name = "metadata"
apis = "apis"
api = "api"

global_resources = [
    "s3_buckets",
    "iam_users",
    "cloudfront_distributions",
    "iam_list_mfa_devices",
    "iam_list_policy",
    "iam_list_policy_local_and_only_attached",
    "iam_list_role_policies",
    "iam_server_certificates",
    "route53_list_health_checks",
    "route53_list_hosted_zones",
    "route53_list_hosted_zones_by_vpc",
    "route53_list_query_logging_configs",
    "route53_list_resource_record_sets",
    "route53_list_reusable_delegation_sets",
    "route53_list_traffic_policies",
    "route53_list_traffic_policy_instances",
    "route53_list_traffic_policy_versions",
    "waf_list_activated_rules_in_rule_group",
    "waf_list_geo_match_sets",
    "waf_list_ip_sets",
    "waf_list_logging_configurations",
    "waf_list_rate_based_rules",
    "waf_list_regex_match_sets",
    "waf_list_regex_pattern_sets",
    "waf_list_rule_groups",
    "waf_list_rules",
    "waf_list_size_constraint_sets",
    "waf_list_sql_injection_match_sets",
    "waf_list_web_acls",
    "waf_list_xss_match_sets",
]

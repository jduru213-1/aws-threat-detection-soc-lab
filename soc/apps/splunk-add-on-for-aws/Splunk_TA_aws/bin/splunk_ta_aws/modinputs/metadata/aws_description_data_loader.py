#
# SPDX-FileCopyrightText: 2021 Splunk, Inc. <sales@splunk.com>
# SPDX-License-Identifier: LicenseRef-Splunk-8-2021
#
#
# isort: off
"""
File for AWS Description Data loader.
"""


import time

import splunk_ta_aws.common.ta_aws_consts as tac
import splunksdc.log as logging

from . import aws_description_consts as adc
from . import aws_description_util

logger = logging.get_module_logger()


def get_supported_description_apis():
    """Returns supported description APIs."""

    from . import (  # isort:skip # pylint: disable=import-outside-toplevel
        cloudfront_description as acd,
    )
    from . import ec2_description as ade  # pylint: disable=import-outside-toplevel
    from . import elb_description as aed  # pylint: disable=import-outside-toplevel
    from . import iam_description as aid  # pylint: disable=import-outside-toplevel
    from . import kinesis_description as akd  # pylint: disable=import-outside-toplevel
    from . import lambda_description as ald  # pylint: disable=import-outside-toplevel
    from . import rds_description as ard  # pylint: disable=import-outside-toplevel
    from . import s3_description as asd  # pylint: disable=import-outside-toplevel
    from . import vpc_description as avd  # pylint: disable=import-outside-toplevel
    from . import waf_description as awd  # pylint: disable=import-outside-toplevel
    from . import gd_description as agd  # pylint: disable=import-outside-toplevel
    from . import eks_description as eks  # pylint: disable=import-outside-toplevel
    from . import firehose_description as afd  # pylint: disable=import-outside-toplevel
    from . import (
        network_firewall_description as nfd,
    )  # pylint: disable=import-outside-toplevel
    from . import route53_description as r53d  # pylint: disable=import-outside-toplevel
    from . import emr_description as aemrd  # pylint: disable=import-outside-toplevel
    from . import (
        elasticache_description as aecd,
    )  # pylint: disable=import-outside-toplevel

    return {
        "ec2_instances": ade.ec2_instances,
        "ec2_reserved_instances": ade.ec2_reserved_instances,
        "ebs_snapshots": ade.ec2_ebs_snapshots,
        "ec2_volumes": ade.ec2_volumes,
        "ec2_security_groups": ade.ec2_security_groups,
        "ec2_key_pairs": ade.ec2_key_pairs,
        "ec2_images": ade.ec2_images,
        "ec2_addresses": ade.ec2_addresses,
        "elastic_load_balancers": aed.classic_load_balancers,  # forward-compatibility
        "classic_load_balancers": aed.classic_load_balancers,
        "application_load_balancers": aed.application_load_balancers,
        "vpcs": avd.vpcs,
        "vpc_subnets": avd.vpc_subnets,
        "vpc_network_acls": avd.vpc_network_acls,
        "vpn_gateways": avd.vpn_gateways,
        "internet_gateways": avd.internet_gateways,
        "customer_gateways": avd.customer_gateways,
        "nat_gateways": avd.nat_gateways,
        "local_gateways": avd.local_gateways,
        "carrier_gateways": avd.carrier_gateways,
        "transit_gateways": avd.transit_gateways,
        "cloudfront_distributions": acd.cloudfront_distributions,
        "rds_instances": ard.rds_instances,
        "rds_reserved_instances": ard.rds_reserved_instances,
        "lambda_functions": ald.lambda_functions,
        "s3_buckets": asd.s3_buckets,
        "iam_users": aid.iam_users,
        "iam_list_policy": aid.iam_list_policy,
        "iam_list_policy_local_and_only_attached": aid.iam_list_policy_local_and_only_attached,
        "iam_server_certificates": aid.iam_server_certificates,
        "iam_list_role_policies": aid.iam_list_role_policies,
        "iam_list_mfa_devices": aid.iam_list_mfa_devices,
        "iam_list_signing_certificates": aid.iam_list_signing_certificates,
        "iam_list_ssh_public_keys": aid.iam_list_ssh_public_keys,
        "kinesis_stream": akd.kinesis_stream,
        "kinesis_list_shards": akd.kinesis_list_shards,
        "kinesis_describe_stream_consumers": akd.kinesis_describe_stream_consumers,
        "kinesis_list_tags_for_resource": akd.kinesis_list_tags_for_resource,
        "kinesis_describe_limits": akd.kinesis_describe_limits,
        "firehose_describe_delivery_streams": afd.firehose_describe_delivery_streams,
        "firehose_list_tags_for_resource": afd.firehose_list_tags_for_resource,
        "waf_list_rules": awd.list_rules,
        "waf_list_rule_groups": awd.list_rule_groups,
        "waf_list_geo_match_sets": awd.list_geo_match_sets,
        "waf_list_byte_match_sets": awd.list_byte_match_sets,
        "waf_list_activated_rules_in_rule_group": awd.list_activated_rules_in_rule_group,
        "waf_list_regex_match_sets": awd.list_regex_match_sets,
        "waf_list_regex_pattern_sets": awd.list_regex_pattern_sets,
        "waf_list_ip_sets": awd.list_ip_sets,
        "waf_list_rate_based_rules": awd.list_rate_based_rules,
        "waf_list_logging_configurations": awd.list_logging_configurations,
        "waf_list_web_acls": awd.list_web_acls,
        "waf_list_size_constraint_sets": awd.list_size_constraint_sets,
        "waf_list_xss_match_sets": awd.list_xss_match_sets,
        "waf_list_sql_injection_match_sets": awd.list_sql_injection_match_sets,
        "waf_list_tags_for_resource": awd.list_tags_for_resource,
        "wafv2_list_available_managed_rule_group_versions_regional": awd.wafv2_list_available_managed_rule_group_versions_regional,
        "wafv2_list_available_managed_rule_group_versions_cloudfront": awd.wafv2_list_available_managed_rule_group_versions_cloudfront,
        "wafv2_list_logging_configurations_regional": awd.wafv2_list_logging_configurations_regional,
        "wafv2_list_logging_configurations_cloudfront": awd.wafv2_list_logging_configurations_cloudfront,
        "wafv2_list_ip_sets_regional": awd.wafv2_list_ip_sets_regional,
        "wafv2_list_ip_sets_cloudfront": awd.wafv2_list_ip_sets_cloudfront,
        "wafv2_list_tags_for_resource": awd.wafv2_list_tags_for_resource,
        "gd_describe_publishing_destination": agd.gd_describe_publishing_destination,
        "gd_list_detectors": agd.gd_list_detectors,
        "gd_list_tags_for_resource": agd.gd_list_tags_for_resource,
        "eks_describe_clusters": eks.eks_describe_clusters,
        "eks_list_nodegroups": eks.eks_list_nodegroups,
        "eks_describe_nodegroups": eks.eks_describe_nodegroups,
        "eks_describe_update": eks.eks_describe_update,
        "eks_list_tags_for_resource": eks.eks_list_tags_for_resource,
        "eks_list_addon": eks.eks_list_addon,
        "eks_describe_addon": eks.eks_describe_addon,
        "eks_describe_fargate_profile": eks.eks_describe_fargate_profile,
        "eks_describe_identity_provider_config": eks.eks_describe_identity_provider_config,
        "eks_describe_addon_versions": eks.eks_describe_addon_versions,
        "network_firewall_describe_firewalls": nfd.network_firewall_describe_firewalls,
        "network_firewall_describe_logging_configurations": nfd.network_firewall_describe_logging_configurations,
        "network_firewall_describe_firewall_policies": nfd.network_firewall_describe_firewall_policies,
        "network_firewall_describe_rule_groups": nfd.network_firewall_describe_rule_groups,
        "network_firewall_list_tags_for_resource": nfd.network_firewall_list_tags_for_resource,
        "network_firewall_describe_resource_policies": nfd.network_firewall_describe_resource_policies,
        "route53_list_health_checks": r53d.route53_list_health_checks,
        "route53_list_hosted_zones": r53d.route53_list_hosted_zones,
        "route53_list_hosted_zones_by_vpc": r53d.route53_list_hosted_zones_by_vpc,
        "route53_list_reusable_delegation_sets": r53d.route53_list_reusable_delegation_sets,
        "route53_list_query_logging_configs": r53d.route53_list_query_logging_configs,
        "route53_list_traffic_policies": r53d.route53_list_traffic_policies,
        "route53_list_traffic_policy_versions": r53d.route53_list_traffic_policy_versions,
        "route53_list_traffic_policy_instances": r53d.route53_list_traffic_policy_instances,
        "route53_list_resource_record_sets": r53d.route53_list_resource_record_sets,
        "route53_list_tags_for_resource": r53d.route53_list_tags_for_resource,
        "emr_describe_clusters": aemrd.emr_describe_clusters,
        "emr_describe_release_labels": aemrd.emr_describe_release_labels,
        "emr_describe_steps": aemrd.emr_describe_steps,
        "emr_list_instances": aemrd.emr_list_instances,
        "emr_list_instance_fleets": aemrd.emr_list_instance_fleets,
        "emr_describe_notebook_executions": aemrd.emr_describe_notebook_executions,
        "emr_describe_studios": aemrd.emr_describe_studios,
        "emr_describe_security_configurations": aemrd.emr_describe_security_configurations,
        "elasticache_describe_cache_clusters": aecd.elasticache_describe_cache_clusters,
        "elasticache_describe_cache_engine_versions": aecd.elasticache_describe_cache_engine_versions,
        "elasticache_describe_cache_parameter_groups": aecd.elasticache_describe_cache_parameter_groups,
        "elasticache_describe_cache_parameters": aecd.elasticache_describe_cache_parameters,
        "elasticache_describe_cache_subnet_groups": aecd.elasticache_describe_cache_subnet_groups,
        "elasticache_describe_engine_default_parameters": aecd.elasticache_describe_engine_default_parameters,
        "elasticache_describe_events": aecd.elasticache_describe_events,
        "elasticache_describe_global_replication_groups": aecd.elasticache_describe_global_replication_groups,
        "elasticache_describe_replication_groups": aecd.elasticache_describe_replication_groups,
        "elasticache_describe_reserved_cache_nodes_offerings": aecd.elasticache_describe_reserved_cache_nodes_offerings,
        "elasticache_describe_reserved_cache_nodes": aecd.elasticache_describe_reserved_cache_nodes,
        "elasticache_describe_service_updates": aecd.elasticache_describe_service_updates,
        "elasticache_describe_snapshots": aecd.elasticache_describe_snapshots,
        "elasticache_describe_update_actions": aecd.elasticache_describe_update_actions,
        "elasticache_describe_user_groups": aecd.elasticache_describe_user_groups,
        "elasticache_describe_users": aecd.elasticache_describe_users,
        "elasticache_list_tags_for_resource": aecd.elasticache_list_tags_for_resource,
    }


class DescriptionDataLoader:
    """Class for Description Data Loader."""

    def __init__(self, task_config):
        """
        :task_config: dict object
        {
        "interval": 30,
        "api": "ec2_instances" etc,
        "source": xxx,
        "sourcetype": yyy,
        "index": zzz,
        }
        """

        self._task_config = task_config
        self._supported_desc_apis = get_supported_description_apis()
        self._api = self._supported_desc_apis.get(task_config[adc.api], None)
        if self._api is None:
            logger.error(
                "Unsupported service.",
                service=task_config[adc.api],
                ErrorCode="ConfigurationError",
                ErrorDetail="Service is unsupported.",
                datainput=task_config[tac.datainput],
            )

    def __call__(self):
        with logging.LogContext(
            datainput=self._task_config[tac.datainput],
            service=self._task_config[adc.api],
            region=self._task_config[tac.region],
        ):
            self.index_data()

    def index_data(self):
        """Starts indexing data."""
        logger.info("Start collecting description data")
        try:
            self._do_index_data()
        except Exception as ex:  # pylint: disable=broad-except
            logger.exception(
                "Failed to collect description data",
                error=ex,
            )
        logger.info("End of collecting description data")

    def _do_index_data(self):
        if self._api is None:
            return

        evt_fmt = (
            "<stream><event>"
            "<time>{time}</time>"
            "<source>{source}</source>"
            "<sourcetype>{sourcetype}</sourcetype>"
            "<index>{index}</index>"
            "<data>{data}</data>"
            "</event></stream>"
        )

        task = self._task_config
        results = self._api(task)
        # SPL-219983: overwrite _assign_source() to add AccountId
        source_assign = "{account_id}:{region}:{api}".format(  # pylint: disable=consider-using-f-string
            **task
        )

        events = []
        size_total = 0
        for result in results:
            event = evt_fmt.format(
                source=source_assign,
                sourcetype=task[tac.sourcetype],
                index=task[tac.index],
                data=aws_description_util.escape_cdata(result),
                time=time.time(),
            )
            size_total += len(event)
            events.append(event)
        logger.info(
            "Send data for indexing.",
            size=size_total,
            records=len(events),
        )

        task["writer"].write_events("".join(events))

    def get_interval(self):
        """Returns input interval."""
        return self._task_config[tac.interval]

    def stop(self):
        """Stops the input."""
        pass  # pylint: disable=unnecessary-pass

    def get_props(self):
        """Returns configs."""
        return self._task_config

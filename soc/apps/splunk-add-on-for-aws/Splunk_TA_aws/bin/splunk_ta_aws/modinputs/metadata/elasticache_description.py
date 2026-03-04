#
# SPDX-FileCopyrightText: 2021 Splunk, Inc. <sales@splunk.com>
# SPDX-License-Identifier: LicenseRef-Splunk-8-2021
#
#
"""
File for ElastiCache description for metadata input.
"""


from . import description as desc
from . import aws_description_helper_functions as helper

ELASTICACHE_SERVICE = "elasticache"


@desc.generate_credentials
@desc.decorate
def elasticache_describe_cache_clusters(config):
    """Yields description of ElastiCache cache clusters."""
    cache_clusters = helper.metadata_list_helper(
        config, ELASTICACHE_SERVICE, "describe_cache_clusters", "CacheClusters"
    )
    yield from cache_clusters


@desc.generate_credentials
@desc.decorate
def elasticache_describe_cache_engine_versions(config):
    """Yields description of ElastiCache cache engine versions."""
    cache_engine_versions = helper.metadata_list_helper(
        config,
        ELASTICACHE_SERVICE,
        "describe_cache_engine_versions",
        "CacheEngineVersions",
    )
    yield from cache_engine_versions


@desc.generate_credentials
@desc.decorate
def elasticache_describe_cache_parameter_groups(config):
    """Yields description of ElastiCache cache parameter groups."""
    cache_parameter_groups = helper.metadata_list_helper(
        config,
        ELASTICACHE_SERVICE,
        "describe_cache_parameter_groups",
        "CacheParameterGroups",
    )
    yield from cache_parameter_groups


@desc.generate_credentials
@desc.decorate
def elasticache_describe_cache_parameters(config):
    """Yields description of ElastiCache cache parameters."""
    cache_parameter_groups = helper.metadata_list_helper(
        config,
        ELASTICACHE_SERVICE,
        "describe_cache_parameter_groups",
        "CacheParameterGroups",
    )
    for cache_parameter_group in cache_parameter_groups:
        cache_parameter_group_name = cache_parameter_group["CacheParameterGroupName"]
        cache_parameters = helper.metadata_list_helper(
            config,
            ELASTICACHE_SERVICE,
            "describe_cache_parameters",
            ["Parameters", "CacheNodeTypeSpecificParameters"],
            {"CacheParameterGroupName": cache_parameter_group_name},
        )
        for cp in cache_parameters:
            cp["CacheParameterGroupName"] = cache_parameter_group_name
            yield cp


@desc.generate_credentials
@desc.decorate
def elasticache_describe_cache_subnet_groups(config):
    """Yields description of ElastiCache cache subnet groups."""
    cache_subnet_groups = helper.metadata_list_helper(
        config, ELASTICACHE_SERVICE, "describe_cache_subnet_groups", "CacheSubnetGroups"
    )
    yield from cache_subnet_groups


@desc.generate_credentials
@desc.decorate
def elasticache_describe_engine_default_parameters(config):
    """Yields description of ElastiCache engine default parameters."""
    processed_cache_parameter_group_families = []
    cache_parameter_groups = helper.metadata_list_helper(
        config,
        ELASTICACHE_SERVICE,
        "describe_cache_parameter_groups",
        "CacheParameterGroups",
    )
    for cache_parameter_group in cache_parameter_groups:
        cache_parameter_group_family = cache_parameter_group[
            "CacheParameterGroupFamily"
        ]
        if cache_parameter_group_family not in processed_cache_parameter_group_families:
            engine_default_parameters = helper.metadata_list_helper(
                config,
                ELASTICACHE_SERVICE,
                "describe_engine_default_parameters",
                "EngineDefaults",
                {"CacheParameterGroupFamily": cache_parameter_group_family},
            )
            # Remove Marker (used for pagination) from response
            for edp in engine_default_parameters:
                edp.pop("Marker", None)
                yield edp
            processed_cache_parameter_group_families.append(
                cache_parameter_group_family
            )


@desc.generate_credentials
@desc.decorate
def elasticache_describe_events(config):
    """Yields description of ElastiCache events."""
    events = helper.metadata_list_helper(
        config, ELASTICACHE_SERVICE, "describe_events", "Events"
    )
    yield from events


@desc.generate_credentials
@desc.decorate
def elasticache_describe_global_replication_groups(config):
    """Yields description of ElastiCache global replication groups."""
    global_replication_groups = helper.metadata_list_helper(
        config,
        ELASTICACHE_SERVICE,
        "describe_global_replication_groups",
        "GlobalReplicationGroups",
    )
    yield from global_replication_groups


@desc.generate_credentials
@desc.decorate
def elasticache_describe_replication_groups(config):
    """Yields description of ElastiCache replication groups."""
    replication_groups = helper.metadata_list_helper(
        config, ELASTICACHE_SERVICE, "describe_replication_groups", "ReplicationGroups"
    )
    yield from replication_groups


@desc.generate_credentials
@desc.decorate
def elasticache_describe_reserved_cache_nodes_offerings(config):
    """Yields description of ElastiCache reserved cache nodes offerings."""
    reserved_cache_nodes_offerings = helper.metadata_list_helper(
        config,
        ELASTICACHE_SERVICE,
        "describe_reserved_cache_nodes_offerings",
        "ReservedCacheNodesOfferings",
    )
    yield from reserved_cache_nodes_offerings


@desc.generate_credentials
@desc.decorate
def elasticache_describe_service_updates(config):
    """Yields description of ElastiCache service updates."""
    service_updates = helper.metadata_list_helper(
        config, ELASTICACHE_SERVICE, "describe_service_updates", "ServiceUpdates"
    )
    yield from service_updates


@desc.generate_credentials
@desc.decorate
def elasticache_describe_snapshots(config):
    """Yields description of ElastiCache snapshots."""
    snapshots = helper.metadata_list_helper(
        config, ELASTICACHE_SERVICE, "describe_snapshots", "Snapshots"
    )
    yield from snapshots


@desc.generate_credentials
@desc.decorate
def elasticache_describe_update_actions(config):
    """Yields description of ElastiCache update actions."""
    update_actions = helper.metadata_list_helper(
        config, ELASTICACHE_SERVICE, "describe_update_actions", "UpdateActions"
    )
    yield from update_actions


@desc.generate_credentials
@desc.decorate
def elasticache_describe_user_groups(config):
    """Yields description of ElastiCache user groups."""
    user_groups = helper.metadata_list_helper(
        config, ELASTICACHE_SERVICE, "describe_user_groups", "UserGroups"
    )
    yield from user_groups


@desc.generate_credentials
@desc.decorate
def elasticache_describe_users(config):
    """Yields description of ElastiCache users."""
    users = helper.metadata_list_helper(
        config, ELASTICACHE_SERVICE, "describe_users", "Users"
    )
    yield from users


@desc.generate_credentials
@desc.decorate
def elasticache_describe_reserved_cache_nodes(config):
    """Yields description of ElastiCache reserved cache nodes."""
    reserved_cache_nodes = helper.metadata_list_helper(
        config,
        ELASTICACHE_SERVICE,
        "describe_reserved_cache_nodes",
        "ReservedCacheNodes",
    )
    yield from reserved_cache_nodes


@desc.generate_credentials
@desc.decorate
def elasticache_list_tags_for_resource(config):
    """Yields tags of ElastiCache resources."""
    events = helper.list_tags_for_resource(config, ELASTICACHE_SERVICE)
    yield from events

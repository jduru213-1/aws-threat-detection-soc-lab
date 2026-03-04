#
# SPDX-FileCopyrightText: 2021 Splunk, Inc. <sales@splunk.com>
# SPDX-License-Identifier: LicenseRef-Splunk-8-2021
#
#
"""
File for EKS description for metadata input.
"""


import datetime

from . import description as desc
from . import aws_description_helper_functions as helper

CREDENTIAL_THRESHOLD = datetime.timedelta(minutes=20)


@desc.generate_credentials
@desc.decorate
def eks_list_clusters(config):
    """Fetches eks clusters"""
    clusters = helper.metadata_list_helper(config, "eks", "list_clusters", "clusters")
    clusters_list = [cluster for cluster in clusters]
    if clusters_list:
        yield {"clustersList": clusters_list}


@desc.generate_credentials
@desc.decorate
def eks_describe_clusters(config):
    """Fetches describe cluster data"""
    clusters = helper.metadata_list_helper(config, "eks", "list_clusters", "clusters")
    for cluster in clusters:
        describe_cluster = helper.metadata_list_helper(
            config, "eks", "describe_cluster", "cluster", {"name": cluster}
        )
        for dc in describe_cluster:
            yield {"cluster": dc}


@desc.generate_credentials
@desc.decorate
def eks_list_nodegroups(config):
    """Fetches list nodegroups data"""
    clusters = helper.metadata_list_helper(config, "eks", "list_clusters", "clusters")
    for cluster in clusters:
        nodegroups = helper.metadata_list_helper(
            config, "eks", "list_nodegroups", "nodegroups", {"clusterName": cluster}
        )
        ng_list = [nodegroup for nodegroup in nodegroups]
        yield {"clusterName": cluster, "nodegroups": ng_list}


@desc.generate_credentials
@desc.decorate
def eks_describe_nodegroups(config):
    """Fetches describe nodegroups data"""
    clusters = helper.metadata_list_helper(config, "eks", "list_clusters", "clusters")
    for cluster in clusters:
        nodegroups = helper.metadata_list_helper(
            config, "eks", "list_nodegroups", "nodegroups", {"clusterName": cluster}
        )
        for nodegroup in nodegroups:
            describe_nodegroup = helper.metadata_list_helper(
                config,
                "eks",
                "describe_nodegroup",
                "nodegroup",
                {"clusterName": cluster, "nodegroupName": nodegroup},
            )
            for ng in describe_nodegroup:
                yield {"nodegroup": ng}


@desc.generate_credentials
@desc.decorate
def eks_describe_update(config):
    """Returns updates associated with an EKS cluster, managed node group, or addon"""
    describe_updates = {}

    # clusters
    clusters = helper.metadata_list_helper(config, "eks", "list_clusters", "clusters")
    for cluster in clusters:
        list_cluster_updates = helper.metadata_list_helper(
            config, "eks", "list_updates", "updateIds", {"name": cluster}
        )
        cu_list = [list_cluster for list_cluster in list_cluster_updates]

        # describe updates for clusters
        for idx, value in enumerate(cu_list):
            res_cu_updates = helper.metadata_list_helper(
                config,
                "eks",
                "describe_update",
                "update",
                {"name": cluster, "updateId": value},
            )
            cu_list[idx] = next(res_cu_updates)
        describe_updates = {"clusterName": cluster, "updateIds": cu_list}

        # describe updates for node groups
        ng_updates_list = []
        nodegroups = helper.metadata_list_helper(
            config, "eks", "list_nodegroups", "nodegroups", {"clusterName": cluster}
        )
        for nodegroup in nodegroups:
            list_nodegroups_updates = helper.metadata_list_helper(
                config,
                "eks",
                "list_updates",
                "updateIds",
                {"name": cluster, "nodegroupName": nodegroup},
            )
            ng_list = [list_nodegroup for list_nodegroup in list_nodegroups_updates]
            for idx, value in enumerate(ng_list):
                res_ng_updates = helper.metadata_list_helper(
                    config,
                    "eks",
                    "describe_update",
                    "update",
                    {"name": cluster, "updateId": value, "nodegroupName": nodegroup},
                )
                ng_list[idx] = next(res_ng_updates)
            ng_updates_list.append({"NodeGroupName": nodegroup, "updateIds": ng_list})
            describe_updates["NodeGroups"] = ng_updates_list

        # describe updates for addons
        addons_updates_list = []
        addons = helper.metadata_list_helper(
            config, "eks", "list_addons", "addons", {"clusterName": cluster}
        )
        for addon in addons:
            list_addons_updates = helper.metadata_list_helper(
                config,
                "eks",
                "list_updates",
                "updateIds",
                {"name": cluster, "addonName": addon},
            )
            ad_list = [list_addon for list_addon in list_addons_updates]
            for idx, value in enumerate(ad_list):
                res_ad_updates = helper.metadata_list_helper(
                    config,
                    "eks",
                    "describe_update",
                    "update",
                    {"name": cluster, "updateId": value, "addonName": addon},
                )
                ad_list[idx] = next(res_ad_updates)
            addons_updates_list.append({"addonName": addon, "updateIds": ad_list})
            describe_updates["Addons"] = addons_updates_list
        yield describe_updates


@desc.generate_credentials
@desc.decorate
def eks_list_tags_for_resource(config):
    events = helper.list_tags_for_resource(config, "eks")
    for event in events:
        yield event


@desc.generate_credentials
@desc.decorate
def eks_list_addon(config):
    """Fetches list addon data"""
    clusters = helper.metadata_list_helper(config, "eks", "list_clusters", "clusters")
    for cluster in clusters:
        addons = helper.metadata_list_helper(
            config, "eks", "list_addons", "addons", {"clusterName": cluster}
        )
        addon_list = [addon for addon in addons]
        yield {"clusterName": cluster, "addons": addon_list}


@desc.generate_credentials
@desc.decorate
def eks_describe_addon(config):
    """Fetches describe addon data"""
    clusters = helper.metadata_list_helper(config, "eks", "list_clusters", "clusters")
    for cluster in clusters:
        addons = helper.metadata_list_helper(
            config, "eks", "list_addons", "addons", {"clusterName": cluster}
        )
        for addon in addons:
            describe_addon = helper.metadata_list_helper(
                config,
                "eks",
                "describe_addon",
                "addon",
                {"clusterName": cluster, "addonName": addon},
            )
            for da in describe_addon:
                yield {"addon": da}


@desc.generate_credentials
@desc.decorate
def eks_describe_fargate_profile(config):
    """Fetches describe fargate profile data"""
    clusters = helper.metadata_list_helper(config, "eks", "list_clusters", "clusters")
    for cluster in clusters:
        list_farget_profile = helper.metadata_list_helper(
            config,
            "eks",
            "list_fargate_profiles",
            "fargateProfileNames",
            {"clusterName": cluster},
        )
        for fargate_profile in list_farget_profile:
            profile = helper.metadata_list_helper(
                config,
                "eks",
                "describe_fargate_profile",
                "fargateProfile",
                {"clusterName": cluster, "fargateProfileName": fargate_profile},
            )
            yield from profile


@desc.generate_credentials
@desc.decorate
def eks_describe_identity_provider_config(config):
    """Fetches describe identity provider config data"""
    clusters = helper.metadata_list_helper(config, "eks", "list_clusters", "clusters")
    for cluster in clusters:
        list_identity_provider = helper.metadata_list_helper(
            config,
            "eks",
            "list_identity_provider_configs",
            "identityProviderConfigs",
            {"clusterName": cluster},
        )

        for identity in list_identity_provider:
            describe_identity = helper.metadata_list_helper(
                config,
                "eks",
                "describe_identity_provider_config",
                "identityProviderConfig",
                {"clusterName": cluster, "identityProviderConfig": identity},
            )

            yield from describe_identity


@desc.generate_credentials
@desc.decorate
def eks_describe_addon_versions(config):
    """Fetches describe addon version data"""
    describe_addon_version = helper.metadata_list_helper(
        config, "eks", "describe_addon_versions", "addons"
    )

    for addon in describe_addon_version:
        yield addon

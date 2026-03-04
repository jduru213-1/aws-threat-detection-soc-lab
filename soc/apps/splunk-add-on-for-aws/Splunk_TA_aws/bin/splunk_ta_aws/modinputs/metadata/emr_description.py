#
# SPDX-FileCopyrightText: 2021 Splunk, Inc. <sales@splunk.com>
# SPDX-License-Identifier: LicenseRef-Splunk-8-2021
#
#
"""
File for EMR (Elastic MapReduce) description for metadata input.
"""


from . import description as desc
from . import aws_description_helper_functions as helper

EMR_SERVICE = "emr"


@desc.generate_credentials
@desc.decorate
def emr_describe_clusters(config):
    """Yields description of EMR clusters."""
    clusters = helper.metadata_list_helper(
        config, EMR_SERVICE, "list_clusters", "Clusters"
    )
    for cluster in clusters:
        cluster_description = helper.metadata_list_helper(
            config,
            EMR_SERVICE,
            "describe_cluster",
            "Cluster",
            {"ClusterId": cluster["Id"]},
        )
        yield from cluster_description


@desc.generate_credentials
@desc.decorate
def emr_describe_release_labels(config):
    """Yields description of EMR release labels."""
    release_labels = helper.metadata_pagination_helper(
        config,
        EMR_SERVICE,
        "list_release_labels",
        "ReleaseLabels",
        "NextToken",
        "NextToken",
    )
    for release_label in release_labels:
        release_label_description = helper.metadata_list_helper(
            config,
            EMR_SERVICE,
            "describe_release_label",
            ["ReleaseLabel", "Applications", "AvailableOSReleases"],
            {"ReleaseLabel": release_label},
        )
        yield from release_label_description


@desc.generate_credentials
@desc.decorate
def emr_describe_steps(config):
    """Yields description of EMR cluster steps."""
    clusters = helper.metadata_list_helper(
        config, EMR_SERVICE, "list_clusters", "Clusters"
    )
    for cluster in clusters:
        steps = helper.metadata_list_helper(
            config, EMR_SERVICE, "list_steps", "Steps", {"ClusterId": cluster["Id"]}
        )
        for step in steps:
            step_description = helper.metadata_list_helper(
                config,
                EMR_SERVICE,
                "describe_step",
                "Step",
                {"ClusterId": cluster["Id"], "StepId": step["Id"]},
            )
            yield from step_description


@desc.generate_credentials
@desc.decorate
def emr_list_instances(config):
    """Yields description of EMR cluster instances."""
    clusters = helper.metadata_list_helper(
        config, EMR_SERVICE, "list_clusters", "Clusters"
    )
    for cluster in clusters:
        instances = helper.metadata_list_helper(
            config,
            EMR_SERVICE,
            "list_instances",
            "Instances",
            {"ClusterId": cluster["Id"]},
        )
        yield from instances


@desc.generate_credentials
@desc.decorate
def emr_list_instance_fleets(config):
    """Yields description of EMR cluster instance fleets."""
    clusters = helper.metadata_list_helper(
        config, EMR_SERVICE, "list_clusters", "Clusters"
    )
    for cluster in clusters:
        response = list(
            helper.metadata_list_helper(
                config,
                EMR_SERVICE,
                "describe_cluster",
                "Cluster",
                {"ClusterId": cluster["Id"]},
            )
        )
        if response:
            cluster_description = response[0]
            if cluster_description.get("InstanceCollectionType") == "INSTANCE_FLEET":
                instance_fleets = helper.metadata_list_helper(
                    config,
                    EMR_SERVICE,
                    "list_instance_fleets",
                    "InstanceFleets",
                    {"ClusterId": cluster["Id"]},
                )
                yield from instance_fleets


@desc.generate_credentials
@desc.decorate
def emr_describe_notebook_executions(config):
    """Yields description of EMR notebook executions."""
    notebook_executions = helper.metadata_list_helper(
        config, EMR_SERVICE, "list_notebook_executions", "NotebookExecutions"
    )
    for notebook_execution in notebook_executions:
        notebook_execution_description = helper.metadata_list_helper(
            config,
            EMR_SERVICE,
            "describe_notebook_execution",
            "NotebookExecution",
            {"NotebookExecutionId": notebook_execution["NotebookExecutionId"]},
        )
        yield from notebook_execution_description


@desc.generate_credentials
@desc.decorate
def emr_describe_studios(config):
    """Yields description of EMR studios."""
    studios = helper.metadata_list_helper(
        config, EMR_SERVICE, "list_studios", "Studios"
    )
    for studio in studios:
        studio_description = helper.metadata_list_helper(
            config,
            EMR_SERVICE,
            "describe_studio",
            "Studio",
            {"StudioId": studio["StudioId"]},
        )
        yield from studio_description


@desc.generate_credentials
@desc.decorate
def emr_describe_security_configurations(config):
    """Yields description of EMR security configurations."""
    security_configurations = helper.metadata_list_helper(
        config, EMR_SERVICE, "list_security_configurations", "SecurityConfigurations"
    )
    for security_configuration in security_configurations:
        security_configuration_description = helper.metadata_list_helper(
            config,
            EMR_SERVICE,
            "describe_security_configuration",
            None,
            {"Name": security_configuration["Name"]},
        )
        yield from security_configuration_description

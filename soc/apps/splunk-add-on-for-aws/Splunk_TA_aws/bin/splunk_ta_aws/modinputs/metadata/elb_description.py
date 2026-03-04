#
# SPDX-FileCopyrightText: 2021 Splunk, Inc. <sales@splunk.com>
# SPDX-License-Identifier: LicenseRef-Splunk-8-2021
#
#
"""
File for ELB description of metadata input.
"""


import datetime

import boto3
import splunk_ta_aws.common.ta_aws_consts as tac
import splunk_ta_aws.common.ta_aws_common as tacommon
import splunksdc.log as logging
from botocore.exceptions import ClientError

from . import description as desc
from . import aws_description_helper_functions as helper

logger = logging.get_module_logger()

CREDENTIAL_THRESHOLD = datetime.timedelta(minutes=20)
CHUNK_SIZE = 20
PAGE_SIZE_FOR_ELB_DESCRIPTION = 400


def describe_load_balancer_tags(
    client, load_balancers, load_balancer_map, resource_type
):
    """
    Describe tags for Elastic Load Balancers.

    Parameters:
    - client (boto3.client): An initialized Boto3 client for ELB and ELBv2.
    - load_balancers (list): A list of dictionaries representing Elastic Load Balancers.
    - load_balancer_map (dict): A dictionary mapping LoadBalancerName/ResourceArn to load balancer objects.
    - resource_type (str): The type of resource, either 'elb' for Elastic Load Balancer or 'elbv2'
                           for Elastic Load Balancing V2.

    Returns:
    - list: A list of load balancers with updated 'Tags' information.
    """

    load_balancer_identifier = ""
    if resource_type == "elb":
        identifier_field = tac.LoadBalancerNames
        load_balancer_identifier = tac.LoadBalancerName
        load_balancer_names = [elb["LoadBalancerName"] for elb in load_balancers]

    elif resource_type == "elbv2":
        identifier_field = tac.ResourceArns
        load_balancer_identifier = tac.ResourceArn
        load_balancer_names = [elb["LoadBalancerArn"] for elb in load_balancers]
    else:
        logger.error("Invalid resource_type. Supported values are 'elb' and 'elbv2'.")
        return load_balancers

    # Describe the tags
    try:
        tags_arr = client.describe_tags(**{identifier_field: load_balancer_names}).get(
            "TagDescriptions", None
        )
    except ClientError as err:
        tags_arr = None
        logger.exception(
            "Error in describing classic load balancer tags.",
            load_balancer_name=elb["LoadBalancerName"],
        )

    if tags_arr is not None and len(tags_arr) > 0:
        for tags_info in tags_arr:
            load_balancer_name = tags_info.get(load_balancer_identifier, "")
            load_balancer = load_balancer_map.get(load_balancer_name)
            if load_balancer:
                load_balancer["Tags"] = tags_info.get("Tags", [])

    return load_balancers


def describe_classic_load_balancers(elb_client, load_balancers):
    """
    Describe Elastic Load Balancers and update instance information.

    Parameters:
    - elb_client (boto3.client): An initialized Boto3 client for Elastic Load Balancing.
    - load_balancers (list): A list of dictionaries representing Elastic Load Balancers.

    Returns:
    - list: A list of load balancers with updated 'instances' and tags information.
    """

    # Map LoadBalancerName to its corresponding object for correct association of tags
    load_balancer_map = {elb["LoadBalancerName"]: elb for elb in load_balancers}

    # Describe the instance and their health
    for elb in load_balancers:
        try:
            instances = elb_client.describe_instance_health(
                LoadBalancerName=elb.get("LoadBalancerName", None)
            ).get("InstanceStates", None)
        except Exception:  # pylint: disable=broad-except
            logger.exception(
                "Ignore ELB due to exception", ELB=elb.get("LoadBalancerName")
            )
            continue
        instances_trans = []
        for instance in instances:
            instance_trans = {
                "InstanceId": instance.get("InstanceId", None),
                "State": instance.get("State", None),
            }
            instances_trans.append(instance_trans)
        elb["instances"] = instances_trans

    # describe tags
    return describe_load_balancer_tags(
        elb_client, load_balancers, load_balancer_map, "elb"
    )


@desc.generate_credentials
@desc.decorate
def classic_load_balancers(config):
    """Describes classic load balancers."""
    elb_client = helper.get_conn(config, "elb")
    paginator = elb_client.get_paginator("describe_load_balancers")

    for page in paginator.paginate(
        PaginationConfig={"PageSize": PAGE_SIZE_FOR_ELB_DESCRIPTION}
    ):
        all_elbs = page.get("LoadBalancerDescriptions", None)
        if all_elbs is None or len(all_elbs) <= 0:
            continue

        total_load_balancers = len(all_elbs)
        chunk_size = CHUNK_SIZE

        for load_balancers in range(0, total_load_balancers, chunk_size):
            batch_load_balancers = all_elbs[
                load_balancers : load_balancers + chunk_size
            ]
            yield from describe_classic_load_balancers(elb_client, batch_load_balancers)

        desc.refresh_credentials(config, CREDENTIAL_THRESHOLD, elb_client)


def describe_application_load_balancers(elb_v2_client, app_load_balancers):
    """
    Describe the application load balancer with their tags, targetgroups, and listners's information

    Parameters:
    - elb_v2_client (boto3.client): An initialized Boto3 client for Elastic Load Balancing V2.
    - app_load_balancers (list): A list of dictionaries representing Elastic Load Balancers.

    Returns:
    - list: A list of load balancers with updated target groups, tags, and listners information.
    """

    # Map LoadBalancerArn to its corresponding object for correct association of tags
    app_load_balancer_map = {alb["LoadBalancerArn"]: alb for alb in app_load_balancers}

    # describe tags
    app_load_balancers = describe_load_balancer_tags(
        elb_v2_client, app_load_balancers, app_load_balancer_map, "elbv2"
    )

    # fetch target groups
    target_groups_paginator = elb_v2_client.get_paginator("describe_target_groups")

    # fetch listners of load balancer
    listeners_paginator = elb_v2_client.get_paginator("describe_listeners")

    for alb in app_load_balancers:

        target_group_list = []

        for target_group_page in target_groups_paginator.paginate(
            LoadBalancerArn=alb["LoadBalancerArn"],
            PaginationConfig={"PageSize": PAGE_SIZE_FOR_ELB_DESCRIPTION},
        ):
            target_groups = target_group_page["TargetGroups"]
            if target_groups is not None and len(target_groups) > 0:
                for target_group in target_groups:
                    # fetch target health
                    target_health_description = elb_v2_client.describe_target_health(
                        TargetGroupArn=target_group["TargetGroupArn"]
                    )
                    target_group[
                        "TargetHealthDescriptions"
                    ] = target_health_description["TargetHealthDescriptions"]

                    target_group_list.append(target_group)

        alb["TargetGroups"] = target_group_list

        try:
            listener_list = []

            for listener_page in listeners_paginator.paginate(
                LoadBalancerArn=alb["LoadBalancerArn"],
                PaginationConfig={"PageSize": PAGE_SIZE_FOR_ELB_DESCRIPTION},
            ):
                listeners = listener_page["Listeners"]
                if listeners is not None and len(listeners) > 0:
                    listener_list.extend(listeners)

            alb["Listeners"] = listener_list

        except ClientError as err:
            if (
                "Code" in err.response["Error"]
                and err.response["Error"]["Code"] == "AccessDenied"
            ):
                logger.warn(  # pylint: disable=deprecated-method
                    'Failed to describe classic load balancer listeners. It requires "elasticloadbalancing:DescribeListeners" IAM policy.'  # pylint: disable=line-too-long
                )
        yield alb


@desc.generate_credentials
@desc.decorate
def application_load_balancers(config):  # pylint: disable=too-many-locals
    """Yields application load balancers."""
    elb_v2_client = helper.get_conn(config, "elbv2")
    alb_paginator = elb_v2_client.get_paginator("describe_load_balancers")

    for page in alb_paginator.paginate(
        PaginationConfig={"PageSize": PAGE_SIZE_FOR_ELB_DESCRIPTION}
    ):
        all_albs = page.get("LoadBalancers", None)
        length_of_albs = len(all_albs)
        if all_albs is None and length_of_albs <= 0:
            continue

        total_application_load_balancers = length_of_albs
        chunk_size = CHUNK_SIZE

        for application_lbs in range(0, total_application_load_balancers, chunk_size):
            batch_application_load_balancers = all_albs[
                application_lbs : application_lbs + chunk_size
            ]
            yield from describe_application_load_balancers(
                elb_v2_client, batch_application_load_balancers
            )

        desc.refresh_credentials(config, CREDENTIAL_THRESHOLD, elb_v2_client)

#
# SPDX-FileCopyrightText: 2021 Splunk, Inc. <sales@splunk.com>
# SPDX-License-Identifier: LicenseRef-Splunk-8-2021
#
#
"""
File for metadata input helper functions
"""


import datetime

import boto3
import splunk_ta_aws.common.ta_aws_consts as tac
import splunk_ta_aws.common.ta_aws_common as tacommon
from . import description as desc

CREDENTIAL_THRESHOLD = datetime.timedelta(minutes=20)


def get_conn(config, service):
    """
    Create an AWS service client by name using config parsed from UI.

    Parameters
    ----------
    config: dict
        AWS account configurations including region, access_key_ID, and
        secret_access_key
    service: str
        Name of AWS service

    Returns
    ----------
    botocore.client.BaseClient
        Service client instance
    """
    retry_config = tacommon.configure_retry(config.get(tac.retry_max_attempts))
    boto_client = boto3.client(
        service,
        region_name=config[tac.region],
        aws_access_key_id=config.get(tac.key_id),
        aws_secret_access_key=config.get(tac.secret_key),
        aws_session_token=config.get("aws_session_token"),
        config=retry_config,
    )
    return boto_client


def metadata_list_helper(config, service, api, list_field, params=None):
    """
    Fetches metadata through REST calls to specified AWS service and API.

    Connects to AWS 'services'. If specified API is a paginating operation, paginates
    through the results to build full response. Otherwise, calls the specified API
    directly to retrieve available response. The function then retrieves the
    specified 'list_field' from response.

    Parameters
    ----------
    config: dict
        AWS account configurations including region, access_key_ID, and
        secrete_access_key
    service: str
        Name of AWS service
    api: str
        Name of REST metadata API
    list_field: str | list | None
        Name of the field(s) to return from API responses. If None, return entire response
    params: dict optional
        Additional parameter and value required for the API

    Yields
    ----------
    dict
        Metadata event
    """
    params = {} if params is None else params
    client = get_conn(config, service)
    response = None
    if client.can_paginate(api):
        paginator = client.get_paginator(api)
        response = paginator.paginate(**params).build_full_result()
    else:
        method = getattr(client, api)
        response = method(**params)

    if list_field is None:
        # Remove metadata of response
        response.pop("ResponseMetadata", None)
        yield response
    elif isinstance(list_field, list):
        data = dict()
        for key in list_field:
            if key in response.keys():
                data[key] = response[key]
        yield data
    else:
        item_lists = response.get(list_field, [])
        if item_lists is None:
            raise Exception(
                "Got unexpected value for {} as {}".format(list_field, item_lists)
            )
        elif isinstance(item_lists, (list, tuple, set)):
            for item in item_lists:
                yield item
        else:
            yield item_lists

    desc.refresh_credentials(config, CREDENTIAL_THRESHOLD, client)


def metadata_pagination_helper(
    config,
    service,
    api,
    list_field,
    pagination_indicator,
    pagination_token_name,
    params=None,
):
    """
    Fetches metadata through REST calls to specified AWS service and API.

    Implements manual pagination for APIs for which the SDK does not support
    default pagination.

    Parameters
    ----------
    config: dict
        AWS account configurations including region, access_key_ID, and
        secrete_access_key
    service: str
        Name of AWS service
    api: str
        Name of REST metadata API
    list_field: str | list | None
        Name of the field(s) to return from API responses. If None, return entire response
    pagination_indicator: str
        Name of the field in response which indicates whether pagination is completed or pending
    pagination_token_name: str | list
        Name of the field(s) in response which hold tokens for paginating
    params: dict optional
        Additional parameter and value required for the API

    Yields
    ----------
    dict
        Metadata event
    """
    params = {} if params is None else params
    indicator = True
    token_val = None
    if isinstance(pagination_token_name, list):
        requests_token = pagination_token_name[0]
        response_token = pagination_token_name[1]
    else:
        requests_token = response_token = pagination_token_name
    while indicator:
        if token_val:
            params[requests_token] = token_val
        generator = metadata_list_helper(
            config,
            service,
            api,
            [list_field, pagination_indicator, response_token],
            params,
        )
        response = list(generator)
        if response:
            data = response[0]
            item_list = data.get(list_field)
            indicator = data.get(pagination_indicator)
            token_val = data.get(response_token)
            yield from item_list
        else:
            break


def list_tags_for_resource(config, resource):
    """
    Fetches specified resource's resource-arn and tags.

    Calls AWS ResourceGroupsTaggingAPI service's 'get_resources' API to retrieve
    the specified resource and its tags. This API returns tagged and previous
    tagged resources. This function only yields resources that are currently tagged.

    Parameters
    ----------
    config: dict
        AWS account configurations including region, access_key_ID, and
        secrete_access_key
    resource: str
        Name of AWS service

    Yields
    ----------
    dict
        Resource ARN and its tags
    """
    events = metadata_list_helper(
        config,
        "resourcegroupstaggingapi",
        "get_resources",
        "ResourceTagMappingList",
        {"ResourceTypeFilters": [resource]},
    )
    for event in events:
        if len(event["Tags"]) > 0:
            yield event

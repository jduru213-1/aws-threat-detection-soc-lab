#
# SPDX-FileCopyrightText: 2021 Splunk, Inc. <sales@splunk.com>
# SPDX-License-Identifier: LicenseRef-Splunk-8-2021
#
#
"""
File for AWS SNS publisher
"""
import json

import boto3
import splunk_ta_aws.common.proxy_conf as pc
import splunk_ta_aws.common.ta_aws_common as tacommon
from splunk_ta_aws.common.ta_aws_consts import splunk_ta_aws
from splunktalib.common import util as scutil

from splunk_ta_aws.common.ta_aws_common import (  # isort: skip # pylint: disable=ungrouped-imports
    is_http_ok,
    load_config,
    make_splunk_endpoint,
)


def get_aws_sns_client(splunkd_uri, session_key, aws_account, region):
    """
    Get AWS SNS client for given account and region.

    :param splunkd_uri:
    :param session_key:
    :param aws_account:
    :param region:
    :return:
    """
    url = make_splunk_endpoint(
        splunkd_uri, "splunk_ta_aws/settings/all_accounts", app=splunk_ta_aws
    )
    aws_accounts = load_config(url, session_key, "AWS Accounts")
    try:
        aws_account_cont = aws_accounts[aws_account]
    except KeyError:
        raise SNSPublisherError(  # pylint: disable=raise-missing-from
            'AWS account "%s" not found'  # pylint: disable=consider-using-f-string
            % aws_account
        )

    is_iam = scutil.is_true(aws_account_cont.get("iam"))
    params = (
        {}
        if is_iam
        else {
            "aws_access_key_id": aws_account_cont.get("key_id"),
            "aws_secret_access_key": aws_account_cont.get("secret_key"),
        }
    )
    return boto3.client("sns", region_name=region, **params)


def get_aws_sns_topic_arn(client, topic_name):
    """
    Get AWS SNS topic ARN for given SNS client and topic name.

    :param client:
    :param topic_name:
    :return:
    """
    params = {}
    while True:
        resp = client.list_topics(**params)
        if "Topics" not in resp:
            raise SNSPublisherError(resp.get("Failed", resp))
        for topic in resp["Topics"]:
            if topic["TopicArn"].endswith(":" + topic_name):
                return topic["TopicArn"]
        if resp.get("NextToken"):
            params["NextToken"] = resp.get("NextToken")
        else:
            break
    raise SNSPublisherError(  # pylint: disable=raise-missing-from
        'AWS SNS topic "%s" not found'  # pylint: disable=consider-using-f-string
        % topic_name
    )


class SNSPublisherError(Exception):
    """
    SNS publisher error.
    """

    pass  # pylint: disable=unnecessary-pass


class SNSMessageContent:  # pylint: disable=too-many-instance-attributes
    """
    SNS message.
    """

    def __init__(  # pylint: disable=too-many-arguments
        self,
        message,
        timestamp,
        entity,
        correlation_id,
        source,
        event,
        search_name,
        results_link,
        app,
        owner,
    ):
        self.message = message
        self.timestamp = timestamp
        self.entity = entity
        self.correlation_id = correlation_id
        self.source = source
        self.event = event
        self.search_name = search_name
        self.results_link = results_link
        self.app = app
        self.owner = owner

    def __str__(self):
        msg_cont = {
            "message": self.message,
            "timestamp": self.timestamp,
            "entity": self.entity,
            "correlation_id": self.correlation_id,
            "source": self.source,
            "event": self.event,
            "search_name": self.search_name,
            "results_link": self.results_link,
            "app": self.app,
            "owner": self.owner,
        }
        return json.dumps(msg_cont)


class SNSPublisher:
    """Class for SNS publisher."""

    _aws_account = None
    _client = None
    _topic_name = None
    _topic_arn = None

    def publish(  # pylint: disable=too-many-arguments
        self, splunkd_uri, session_key, aws_account, region, topic_name, *args, **kwargs
    ):
        """
        Publish message.

        :param splunkd_uri:
        :param session_key:
        :param aws_account:
        :param region:
        :param topic_name:
        :param args: for making subject and message content.
        :param kwargs: for making subject and message content.
        :return:
        """

        required_args = {
            "aws_account": aws_account,
            "region": region,
            "topic_name": topic_name,
        }
        errs = [key for key, val in required_args.items() if not val]
        if errs:
            raise SNSPublisherError(
                "Required arguments are missed: %s"  # pylint: disable=consider-using-f-string
                % json.dumps(errs)
            )

        self._prepare(splunkd_uri, session_key, aws_account, region, topic_name)

        msg_cont = self.make_message(*args, **kwargs)
        if not msg_cont.message:
            raise SNSPublisherError(
                "Alert isn't published to SNS due to empty message content"
            )
        return self.publish_message(
            topic_arn=self._topic_arn,
            subject=self.make_subject(*args, **kwargs),
            message=str(msg_cont),
        )

    def make_subject(self, *args, **kwargs):
        """
        Make message subject.
        :return:
        :rtype: str
        """
        raise NotImplementedError()

    def make_message(self, *args, **kwargs):
        """
        Make message content.
        :return: an SNSMessageContent object
        :rtype: SNSMessageContent
        """
        raise NotImplementedError()

    @scutil.retry(retries=3, reraise=True, logger=None)
    def publish_message(self, topic_arn, subject, message):
        """Publish SNS message."""
        resp = self._client.publish(
            TargetArn=topic_arn,
            Subject=subject,
            Message=message,
            MessageStructure="string",
        )
        if not is_http_ok(resp):
            raise SNSPublisherError(json.dumps(resp))
        return resp

    def _prepare(
        self, splunkd_uri, session_key, aws_account, region, topic_name
    ):  # pylint: disable=too-many-arguments
        # Set proxy
        proxy = pc.get_proxy_info(session_key)
        tacommon.set_proxy_env(proxy)

        if self._aws_account != aws_account:
            self._aws_account = aws_account
            self._client = get_aws_sns_client(
                splunkd_uri, session_key, aws_account, region
            )
            self._topic_name = topic_name
            self._topic_arn = get_aws_sns_topic_arn(self._client, topic_name)

        if self._aws_account != aws_account or self._topic_name != topic_name:
            self._topic_name = topic_name
            self._topic_arn = get_aws_sns_topic_arn(self._client, topic_name)

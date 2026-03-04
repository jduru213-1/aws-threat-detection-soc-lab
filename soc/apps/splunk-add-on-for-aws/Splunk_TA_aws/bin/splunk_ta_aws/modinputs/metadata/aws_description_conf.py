#
# SPDX-FileCopyrightText: 2021 Splunk, Inc. <sales@splunk.com>
# SPDX-License-Identifier: LicenseRef-Splunk-8-2021
#
#
"""
File for AWS Description Conf.
"""


import os.path as op

import splunk_ta_aws.common.proxy_conf as tpc
import splunk_ta_aws.common.ta_aws_common as tacommon
import splunk_ta_aws.common.ta_aws_consts as tac
import splunklib
import splunksdc.log as logging
from urllib import parse as urlparse
from splunk_ta_aws import set_log_level

from . import aws_description_consts as adc
from . import aws_description_util

logger = logging.get_module_logger()


def create_conf_monitor(callback):
    """Returns task conf monitor."""
    files = (
        AWSDescribeConf.app_file,
        AWSDescribeConf.conf_file_w_path,
        AWSDescribeConf.task_file_w_path,
        AWSDescribeConf.passwords_file_w_path,
    )

    return aws_description_util.FileMonitor(callback, files)


class AWSDescribeConf:
    """Class for AWS description conf."""

    app_dir = aws_description_util.get_app_path(op.abspath(__file__))
    app_file = op.join(app_dir, "local", "app.conf")
    conf_file = "aws_metadata"
    conf_file_w_path = op.join(app_dir, "local", conf_file + ".conf")
    task_file = "aws_metadata_tasks"
    task_file_w_path = op.join(app_dir, "local", task_file + ".conf")
    passwords = "passwords"
    passwords_file_w_path = op.join(app_dir, "local", passwords + ".conf")

    def __init__(self):
        self.metas, self.stanza_configs = tacommon.get_modinput_configs()
        self.metas[tac.app_name] = tac.splunk_ta_aws

    def get_tasks(self):
        """Returns description conf tasks."""
        parts = urlparse.urlparse(self.metas[tac.server_uri])
        _ = parts.scheme
        _ = parts.hostname
        _ = parts.port

        client = splunklib.client.connect(
            scheme=parts.scheme,
            host=parts.hostname,
            port=parts.port,
            token=self.metas[tac.session_key],
            autologin=True,
            app=self.metas[tac.app_name],
        )
        tasks = self._get_description_tasks(client)

        logging_settings = {}
        if self.conf_file in client.confs:
            if tac.log_stanza in client.confs[self.conf_file]:
                logging_settings = client.confs[self.conf_file][tac.log_stanza].content

        # set logging level for our logger
        set_log_level(logging_settings.get(tac.log_level, logging.INFO))

        proxy_info = tpc.get_proxy_info(self.metas[tac.session_key])

        # Set proxy for loading credentials by boto3
        tacommon.set_proxy_env(proxy_info)

        for task in tasks:
            task[tac.log_level] = logging_settings.get(tac.log_level, logging.INFO)
            task.update(proxy_info)

        self._assign_source(tasks)
        return tasks

    def _get_description_tasks(self, conf_mgr):
        stanzas = []
        if self.task_file in conf_mgr.confs:
            stanzas = conf_mgr.confs[self.task_file]

        tasks, creds = [], {}
        for stanza in stanzas:
            name = stanza.name
            stanza = stanza.content
            if aws_description_util.is_true(stanza.get(tac.disabled)):
                continue

            # Normalize tac.account to tac.aws_account
            stanza[tac.aws_account] = stanza.get(tac.account)
            tasks.extend(self._expand_tasks(name, stanza, creds))
        return tasks

    def _filter_iam_polices_apis(self, api_intervals):
        search_iam_policy = "iam_list_policy"
        iam_list_policy_apis = [
            api for api in api_intervals if search_iam_policy in api
        ]
        if len(iam_list_policy_apis) == 2:
            for ilp in iam_list_policy_apis:
                if "iam_list_policy_local_and_only_attached" in ilp:
                    api_intervals.remove(ilp)
                    logger.info(
                        "Skipping the iam_list_policy_local_and_only_attached API, as the required data will be collected by the selected iam_list_policy API."
                    )
                    break

    def _expand_tasks(self, name, stanza, creds):  # pylint: disable=unused-argument
        tasks = []
        api_intervals = stanza[adc.apis].split(",")
        retry_attempts = stanza.get(tac.retry_max_attempts)
        if not retry_attempts:
            retry_attempts = tac.DEFAULT_RETRY_MAX_ATTEMPTS

        self._filter_iam_polices_apis(api_intervals)

        for api_interval in api_intervals:
            api_interval = api_interval.split("/")
            api_name = api_interval[0].strip()
            api_interval = int(api_interval[1].strip())
            regions = stanza[tac.regions].split(",")
            for region in regions:
                region = region.strip()
                tasks.append(
                    {
                        tac.server_uri: self.metas[tac.server_uri],
                        tac.session_key: self.metas[tac.session_key],
                        tac.aws_account: stanza[tac.aws_account],
                        tac.aws_iam_role: stanza.get(tac.aws_iam_role),
                        tac.region: region,
                        adc.api: api_name,
                        tac.interval: api_interval,
                        tac.is_secure: True,
                        tac.index: stanza[tac.index],
                        tac.sourcetype: stanza[tac.sourcetype],
                        tac.datainput: name,
                        tac.retry_max_attempts: int(retry_attempts),
                    }
                )

                if api_name in adc.global_resources:
                    break

        return tasks

    def _assign_source(self, tasks):
        """Assigns source to task"""
        for task in tasks:
            if not task.get(tac.source):
                task[
                    tac.source
                ] = "{region}:{api}".format(  # pylint: disable=consider-using-f-string
                    **task
                )

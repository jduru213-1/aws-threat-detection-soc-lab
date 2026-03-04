#
# SPDX-FileCopyrightText: 2021 Splunk, Inc. <sales@splunk.com>
# SPDX-License-Identifier: LicenseRef-Splunk-8-2021
#
#
"""
File for AWS Cloudwatchlogs Conf.
"""


import os.path as op
import re
import threading
import traceback
from datetime import datetime

# Legacy code started
import splunk_ta_aws.common.proxy_conf as tpc
import splunk_ta_aws.common.ta_aws_common as tacommon
import splunk_ta_aws.common.ta_aws_consts as tac
import splunktalib.conf_manager.conf_manager as cm
import splunktalib.file_monitor as fm
from splunk_ta_aws import set_log_level
from splunksdc import logging
from splunktalib.common import util as scutil

from . import aws_cloudwatch_logs_consts as aclc

# Legacy code done
logger = logging.get_module_logger()


def create_conf_monitor(callback):
    """Returns file conf monitor."""
    files = (
        AWSCloudWatchLogsConf.app_file,
        AWSCloudWatchLogsConf.conf_file_w_path,
        AWSCloudWatchLogsConf.task_file_w_path,
        AWSCloudWatchLogsConf.passwords_file_w_path,
    )
    return fm.FileMonitor(callback, files)


class AWSCloudWatchLogsConf:
    """Class for AWS Cloudwatchlogs Conf."""

    app_dir = scutil.get_app_path(op.abspath(__file__))
    app_file = op.join(app_dir, "local", "app.conf")
    conf_file = "aws_cloudwatch_logs"
    conf_file_w_path = op.join(app_dir, "local", conf_file + ".conf")
    task_file = "aws_cloudwatch_logs_tasks"
    task_file_w_path = op.join(app_dir, "local", task_file + ".conf")
    passwords = "passwords"
    passwords_file_w_path = op.join(app_dir, "local", passwords + ".conf")

    def __init__(self):
        self.metas, self.stanza_configs = tacommon.get_modinput_configs()
        self.metas[tac.app_name] = tac.splunk_ta_aws

    def get_tasks(self):
        """Returns AWS cloudwatchlogs tasks."""
        conf_mgr = cm.ConfManager(
            self.metas[tac.server_uri], self.metas[tac.session_key]
        )
        tasks = self._get_cloudwatch_logs_tasks(conf_mgr)

        logging_settings = conf_mgr.get_stanza(
            self.conf_file, tac.log_stanza, do_reload=False
        )

        set_log_level(logging_settings[tac.log_level])

        proxy_info = tpc.get_proxy_info(self.metas[tac.session_key])
        tacommon.set_proxy_env(proxy_info)

        for task in tasks:
            task[tac.log_level] = logging_settings[tac.log_level]
            task.update(proxy_info)
        return tasks

    def _get_cloudwatch_logs_tasks(self, conf_mgr):
        stanzas = conf_mgr.all_stanzas(self.task_file, do_reload=False)

        tasks, creds = [], {}
        for stanza in stanzas:
            if scutil.is_true(stanza.get(tac.disabled)):
                continue

            # Normalize tac.account to tac.aws_account
            stanza[tac.aws_account] = stanza.get(tac.account)
            try:
                expanded = self._expand_tasks(stanza, creds)
            except Exception:  # pylint: disable=broad-except
                logger.error(
                    "Failed to parse configuration, error=%s", traceback.format_exc()
                )
                continue
            tasks.extend(expanded)
        return tasks

    def _expand_tasks(self, stanza, creds):
        with logging.LogContext(datainput=stanza[tac.stanza_name]):
            try:
                key_id, secret_key = tacommon.get_aws_creds(stanza, self.metas, creds)
                groups = stanza[aclc.groups].split(",")
                date_fmt = "%Y-%m-%dT%H:%M:%S"
                try:
                    date_time = datetime.strptime(
                        stanza[aclc.only_after].strip(), date_fmt
                    )
                except ValueError:
                    logger.error(
                        "Invalid datetime=%s, expected format=%s",
                        stanza[aclc.only_after],
                        date_fmt,
                    )
                    return []

                only_after = scutil.datetime_to_seconds(date_time) * 1000
                stream_matcher = re.compile(
                    stanza.get(aclc.stream_matcher, "").strip() or ".*"
                )

                query_window_size = int(
                    stanza.get(aclc.query_window_size, aclc.DEAFULT_QUERY_WINDOW_SIZE)
                )

                tasks = []
                for log_group_name in groups:
                    log_group_name = log_group_name.strip()
                    tasks.append(
                        {
                            aclc.lock: threading.Lock(),
                            tac.region: stanza[tac.region],
                            tac.account: stanza[tac.account],
                            tac.aws_iam_role: stanza.get(tac.aws_iam_role),
                            tac.interval: float(stanza[tac.interval].strip()),
                            tac.key_id: key_id,
                            tac.secret_key: secret_key,
                            tac.is_secure: True,
                            tac.index: stanza[tac.index],
                            tac.sourcetype: stanza[tac.sourcetype],
                            tac.checkpoint_dir: self.metas[tac.checkpoint_dir],
                            tac.stanza_name: stanza[tac.stanza_name],
                            aclc.log_group_name: log_group_name,
                            aclc.stream_matcher: stream_matcher,
                            aclc.only_after: only_after,
                            aclc.delay: stanza[aclc.delay],
                            tac.app_name: self.metas[tac.app_name],
                            "private_endpoint_enabled": stanza.get(
                                "private_endpoint_enabled"
                            ),
                            "sts_private_endpoint_url": stanza.get(
                                "sts_private_endpoint_url"
                            ),
                            "logs_private_endpoint_url": stanza.get(
                                "logs_private_endpoint_url"
                            ),
                            aclc.query_window_size: query_window_size,
                        }
                    )
                return tasks
            except Exception:
                logger.error(
                    "Failure occurred while expanding tasks for cloudwatch logs input, error=%s",
                    traceback.format_exc(),
                )
                return []

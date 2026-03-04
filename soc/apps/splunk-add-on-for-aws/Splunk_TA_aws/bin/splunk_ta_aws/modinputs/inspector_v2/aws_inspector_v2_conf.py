#
# SPDX-FileCopyrightText: 2021 Splunk, Inc. <sales@splunk.com>
# SPDX-License-Identifier: LicenseRef-Splunk-8-2021
#
#
"""File for AWS Inspector v2 conf"""


import copy
import os.path as op
import urllib

import splunk_ta_aws.common.proxy_conf as tpc
import splunk_ta_aws.common.ta_aws_common as tacommon
import splunk_ta_aws.common.ta_aws_consts as tac
import splunktalib.conf_manager.conf_manager as cm
from splunklib.client import Service
import splunktalib.file_monitor as fm
from splunk_ta_aws import set_log_level
from splunksdc import log as logging
from splunktalib import state_store
from splunktalib.common import util as scutil
from . import aws_inspector_v2_consts as aiconsts
from splunk_ta_aws.common.kv_checkpoint import KVStoreCheckpoint

logger = logging.get_module_logger()


def create_conf_monitor(callback):
    """Returns file conf monitor."""
    files = (
        AWSInspectorV2Conf.app_file,
        AWSInspectorV2Conf.task_file_w_path,
        AWSInspectorV2Conf.passwords_file_w_path,
        AWSInspectorV2Conf.conf_file_w_path,
    )

    return fm.FileMonitor(callback, files)


class AWSInspectorV2Conf:
    """Class for AWS Inspector_v2 Conf."""

    app_dir = scutil.get_app_path(op.abspath(__file__))
    app_file = op.join(app_dir, "local", "app.conf")
    passwords = "passwords"
    passwords_file_w_path = op.join(app_dir, "local", passwords + ".conf")
    task_file = "aws_inspector_v2_tasks"
    task_file_w_path = op.join(app_dir, "local", task_file + ".conf")
    conf_file = "aws_inspector_v2"
    conf_file_w_path = op.join(app_dir, "local", conf_file + ".conf")

    def __init__(self):
        self.metas, self.stanza_configs = tacommon.get_modinput_configs()
        self.metas[tac.app_name] = tac.splunk_ta_aws

    def get_tasks(self):
        """Returns aws inspector v2 tasks."""
        conf_mgr = cm.ConfManager(
            self.metas[tac.server_uri], self.metas[tac.session_key]
        )
        stanzas = conf_mgr.all_stanzas(self.task_file, do_reload=False)
        settings = conf_mgr.all_stanzas_as_dicts(self.conf_file, do_reload=False)
        proxy_info = tpc.get_proxy_info(self.metas[tac.session_key])
        # set proxy here for validating credentials
        tacommon.set_proxy_env(proxy_info)

        level = settings[tac.log_stanza][tac.log_level]
        set_log_level(level)

        all_tasks, valid_tasks = self._get_inspector_v2_tasks(
            stanzas, settings, proxy_info
        )

        config = {}
        config.update(self.metas)
        config.update(settings[tac.global_settings])
        _cleanup_checkpoints(all_tasks, config)
        tasks = [
            task for task in valid_tasks if not scutil.is_true(task.get("disabled"))
        ]
        return tacommon.handle_hec(tasks, "aws_inspector_v2")

    def _get_inspector_v2_tasks(self, stanzas, settings, proxy_info):
        valid_tasks = []
        all_tasks = []
        for stanza in stanzas:
            merged = dict(self.metas)
            merged[tac.log_level] = settings[tac.log_stanza][tac.log_level]
            merged.update(settings[tac.global_settings])
            merged.update(proxy_info)
            # Make sure the 'disabled' field not to be overridden accidentally.
            merged.update(stanza)
            # Normalize tac.account to tac.aws_account
            merged[tac.aws_account] = merged.get(tac.account)
            all_task, valid_task = self._expand_tasks(merged)
            valid_tasks.extend(valid_task)
            all_tasks.extend(all_task)

        return all_tasks, valid_tasks

    def _expand_tasks(self, stanza):
        valid_tasks = []
        all_tasks = []
        regions = stanza[tac.regions].split(",")

        for region in regions:
            task = copy.copy(stanza)
            task[tac.region] = region.strip()
            task[tac.polling_interval] = float(stanza[tac.polling_interval])
            task[tac.is_secure] = True
            task[tac.datainput] = task[tac.stanza_name]
            all_tasks.append(task)
            try:
                tacommon.get_service_client(task, tac.inspector_v2)
                valid_tasks.append(task)
            except (
                Exception
            ) as exc:  # noqa: F841 # pylint: disable=unused-variable, broad-except
                input_name = scutil.extract_datainput_name(task[tac.name])
                logger.exception(
                    "Failed to load credentials, ignore this input.",
                    datainput=input_name,
                    region=region,
                )
        return all_tasks, valid_tasks


def make_findings_ckpt_key(config):
    """Returns checkpoint key."""
    return "findings_v2_{}_{}".format(config[tac.datainput], config[tac.region])


def create_service_obj(config):
    """
    This Method is used to create config service object
    """
    server_uri = config["server_uri"]
    token = config["session_key"]
    appname = config["appName"]
    parts = urllib.parse.urlparse(server_uri)
    scheme = parts.scheme
    server_host = parts.hostname
    server_port = parts.port
    service = Service(
        scheme=scheme,
        host=server_host,
        port=server_port,
        token=token,
        owner="nobody",
        app=appname,
    )

    return service


def _cleanup_checkpoints(tasks, config):
    service = create_service_obj(config)

    collection_name = aiconsts.inspector_v2_log_ns
    collection = KVStoreCheckpoint(collection_name=collection_name, service=service)
    collection.load_collection()

    previous_ckpts = collection.get_collection_data()
    valid_ckpts = {make_findings_ckpt_key(task) for task in tasks}
    if previous_ckpts:
        for ckpt in previous_ckpts:
            if ckpt["_key"] not in valid_ckpts:
                collection.delete_by_id(ckpt["_key"])
                logger.debug(
                    "Deleted the checkpoint entry for input {}".format(ckpt["_key"])
                )

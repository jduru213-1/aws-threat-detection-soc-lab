#
# SPDX-FileCopyrightText: 2021 Splunk, Inc. <sales@splunk.com>
# SPDX-License-Identifier: LicenseRef-Splunk-8-2021
#
#
"""
File for SQS data loader.
"""


import copy
import json
import os
import re
import traceback
from datetime import timedelta

from splunk_ta_aws.common.global_settings import GlobalInputsSettings

import splunksdc.log as logging
from splunk_ta_aws import set_log_level
from splunk_ta_aws.common.proxy import ProxySettings
from splunksdc.config import StanzaParser, StringField
from splunksdc.scheduler import TaskSchedulerMultiThreaded
from splunktalib.common import util as scutil

from .aws_sqs_collector import SQSCollector, get_sqs_queue_url

from splunk_ta_aws.common.credentials import (  # isort: skip # pylint: disable=ungrouped-imports
    AWSCredentialsCache,
    AWSCredentialsProviderFactory,
)


logger = logging.get_module_logger()
import threading

worker_abort_event = threading.Event()


def ingest(messages, portal):
    """Ingests events."""
    # try to unescape the "Body" attribute as "BodyJson" (Plain String or JSON-Format String)
    for message in messages:
        body_value = message["Body"]
        try:
            body_json_value = json.loads(body_value)
            message["BodyJson"] = body_json_value
        except ValueError:
            pass

    portal.write_events([json.dumps(message) for message in messages])


class Input:
    """Class for SQS inputs."""

    _SQS_TASKS = "aws_sqs_tasks"
    _SEP = "``splunk_ta_aws_sqs_sep``"
    _MIN_TTL = timedelta(seconds=600)

    def __call__(self, app, config):
        self._app = app
        return self.prepare(config)

    def prepare(self, config):  # pylint: disable=inconsistent-return-statements
        """Prepares scheduler."""
        settings = config.load("aws_sqs")

        # Set Logging
        self.level = settings[  # pylint: disable=attribute-defined-outside-init
            "logging"
        ]["log_level"]
        set_log_level(self.level)

        inputs = config.load("aws_sqs_tasks")

        # If config is empty, do nothing and return.
        if not inputs:
            logger.info("No Task Configured")
            return

        logger.debug("AWS SQS input discovered", count=len(inputs))

        # Set Proxy
        self.proxy = (  # pylint: disable=attribute-defined-outside-init
            ProxySettings.load(config)
        )
        self.proxy.hook_boto3_get_proxies()

        global_inputs_settings = GlobalInputsSettings.load(config)
        sqs_threads_worker = global_inputs_settings.get_sqs_max_threads()
        logger.info(f"SQS max thread workers={sqs_threads_worker}")
        scheduler = TaskSchedulerMultiThreaded(sqs_threads_worker, self.perform)

        # Generate Tasks
        for name, item in inputs.items():
            if scutil.is_true(item.get("disabled", "0")):
                continue
            item["datainput"] = name
            self.generate_tasks(name, item, scheduler)

        # Custom abort checker that propagates abort state to worker threads
        def check_abort_and_propagate():
            if self._app.is_aborted():
                worker_abort_event.set()
                return True
            return False

        scheduler.run([check_abort_and_propagate, config.has_expired])

        worker_abort_event.set()
        scheduler._executor.shutdown()
        return 0

    def generate_tasks(self, input_name, input_item, scheduler):
        """Returns tasks."""
        sqs_queues = re.split(r"\s*,\s*", input_item.get("sqs_queues", ""))
        for sqs_queue in sqs_queues:
            item_new = copy.deepcopy(input_item)
            del item_new["sqs_queues"]
            item_new["sqs_queue"] = sqs_queue
            task_name = input_name + Input._SEP + sqs_queue
            interval = float(item_new.get("interval", "30"))
            scheduler.add_task(task_name, item_new, interval)

    @staticmethod
    def log(params, msg, level=logging.DEBUG, **kwargs):
        """Logs input information."""
        logger.log(
            level,
            msg,
            data_input=params["datainput"],
            aws_account=params["aws_account"],
            aws_region=params["aws_region"],
            sqs_queue=params["sqs_queue"],
            **kwargs,
        )

    def perform(self, params):  # pylint: disable=unused-argument, too-many-locals
        """Performs event writing operations."""
        Input.log(params, "AWS SQS input started data collection for ")
        if os.name == "nt":
            set_log_level(self.level)
            self.proxy.hook_boto3_get_proxies()

        parser = StanzaParser(
            [
                StringField("aws_account", required=True),
                StringField("aws_iam_role"),
            ]
        )
        args = parser.parse(params)
        aws_region = params["aws_region"]
        try:
            config = self._app.create_config_service()
            factory = AWSCredentialsProviderFactory(config, aws_region)
            provider = factory.create(args.aws_account, args.aws_iam_role)
            credentials = AWSCredentialsCache(provider)
            if credentials.need_retire(self._MIN_TTL):
                credentials.refresh()
            queue_url = get_sqs_queue_url(credentials, params["sqs_queue"], aws_region)
        except Exception:  # pylint: disable=broad-except
            Input.log(
                params,
                "Failed to get SQS queue url",
                logging.ERROR,
                error=traceback.format_exc(),
            )
            return

        sourcetype = params.get("sourcetype", "aws:sqs")
        index = params.get("index", "default")
        source = queue_url

        portal = self._app.create_event_writer(
            index=index, sourcetype=sourcetype, source=source
        )
        collector = SQSCollector(
            queue_url, aws_region, credentials, logger, handler=ingest, portal=portal
        )
        result = collector.run(worker_abort_event)
        if result is not True:
            Input.log(params, "SQS queue fetching failed", logging.ERROR)
        Input.log(params, "AWS SQS input finished data collection for ")

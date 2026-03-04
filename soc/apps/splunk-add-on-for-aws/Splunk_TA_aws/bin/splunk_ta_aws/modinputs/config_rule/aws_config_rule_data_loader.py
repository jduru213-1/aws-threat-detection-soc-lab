#
# SPDX-FileCopyrightText: 2021 Splunk, Inc. <sales@splunk.com>
# SPDX-License-Identifier: LicenseRef-Splunk-8-2021
#
#
"""
File for AWS config rule data loader.
"""


import threading
import time
import traceback

import splunk_ta_aws.common.ta_aws_common as tacommon
import splunk_ta_aws.common.ta_aws_consts as tac
from botocore.exceptions import ClientError
from splunksdc import logging

from . import aws_config_rule_checkpointer as ackpt

logger = logging.get_module_logger()


class ConfigRuleDataLoader:  # pylint: disable=too-many-instance-attributes
    """Class for Config rule data loader."""

    def __init__(self, config):
        """
        :config: dict object
        {
        "interval": 30,
        "sourcetype": yyy,
        "index": zzz,
        }
        """

        self._config = config
        self._stopped = False
        self._client, self._credentials = tacommon.get_service_client(
            config, tac.config
        )
        self._lock = threading.Lock()
        self._ckpt = ackpt.AWSConfigRuleCheckpointer(config)
        account_id = self._credentials.account_id
        region = config[tac.region]
        self._source_config_rules = (
            "{}:{}:configRule".format(  # pylint: disable=consider-using-f-string
                account_id, region
            )
        )
        self._source_status = self._source_config_rules + ":evaluationStatus"
        self._source_detail = self._source_config_rules + ":complianceDetail"
        self._source_summary = self._source_config_rules + ":complianceSummary"

    def __call__(self):
        self.index_data()

    def index_data(self):
        """Start indexing data for AWS config rule."""
        if self._lock.locked():
            logger.info(
                "Last round of data collecting for config rule "
                "region=%s, datainput=%s is not done yet",
                self._config[tac.region],
                self._config[tac.datainput],
            )
            return

        logger.info(
            "Start collecting config rule for region=%s, datainput=%s",
            self._config[tac.region],
            self._config[tac.datainput],
        )
        try:
            with self._lock:
                self._do_index_data()
        except Exception:  # pylint: disable=broad-except
            logger.error(
                "Failed to collect config rule for region=%s, "
                "datainput=%s, error=%s",
                self._config[tac.region],
                self._config[tac.datainput],
                traceback.format_exc(),
            )
        logger.info(
            "End of collecting config rule for region=%s, datainput=%s",
            self._config[tac.region],
            self._config[tac.datainput],
        )

    def _last_evaluation_times(self, rule_name=""):
        writer = self._config[tac.event_writer]
        response = self._client.describe_config_rule_evaluation_status(
            ConfigRuleNames=[rule_name]
        )
        if not tacommon.is_http_ok(response):
            logger.error(
                "Failed to describe config rule evaluation status, " "errorcode=%s",
                tacommon.http_code(response),
            )
            return None

        statuses = response.get("ConfigRulesEvaluationStatus")
        if not statuses:
            return None

        dkeys = [
            "LastSuccessfulInvocationTime",
            "LastFailedInvocationTime",
            "LastSuccessfulEvaluationTime",
            "LastFailedEvaluationTime",
            "FirstActivatedTime",
        ]
        sourcetype = self._config.get(tac.sourcetype, "aws:config:rule")
        last_times, events = [], []
        for status in statuses:
            if status.get("LastSuccessfulEvaluationTime"):
                evt_time = tacommon.total_seconds(
                    status["LastSuccessfulEvaluationTime"]
                )
            else:
                evt_time = ""

            ckpt_time = self._ckpt.last_evaluation_time(
                status["ConfigRuleName"],
            )
            if ckpt_time == None:
                ckpt_time, self.file_ckpt = self._ckpt.get_ckpt_from_file_checkpoint(
                    self._config[tac.datainput], status["ConfigRuleName"]
                )
            last_times.append((evt_time, ckpt_time))
            if ckpt_time == evt_time:
                continue

            for key in dkeys:
                if key in status:
                    status[
                        key
                    ] = "{}".format(  # pylint: disable=consider-using-f-string
                        status[key]
                    )
            event = writer.create_event(
                index=self._config.get(tac.index, "default"),
                host=self._config.get(tac.host, ""),
                source=self._source_status,
                sourcetype=sourcetype,
                time=evt_time,
                unbroken=False,
                done=False,
                events=status,
            )
            events.append(event)

        if events:
            writer.write_events(events)
        return last_times

    def _do_index_data(self):
        if self._credentials.need_retire():
            self._client, self._credentials = tacommon.get_service_client(
                self._config, tac.config
            )
        next_token = ""
        rule_names = self._config.get("rule_names", [])
        while 1:
            try:
                response = self._client.describe_config_rules(
                    ConfigRuleNames=rule_names, NextToken=next_token
                )
            except ClientError as err:
                error_code = err.response["Error"].get("Code", "Unknown")
                error_message = err.response["Error"].get("Message", "Unknown")

                if (
                    error_code == "NoSuchConfigRuleException"
                    and error_message.startswith("The ConfigRule")
                ):
                    invalid_rule = error_message.split("'")[1]
                    rule_names.remove(invalid_rule)
                    logger.info(
                        "Neglect invalid rule and retry.", invalid_rule=invalid_rule
                    )
                    if rule_names:  # pylint: disable=no-else-continue
                        next_token = ""
                        continue
                    else:
                        # empty rule_names will list all,
                        # directly returns to avoid
                        logger.info(
                            "No valid config rule found.",
                            region=self._config[tac.region],
                            datainput=self._config[tac.datainput],
                        )
                        return
                else:
                    logger.exception(
                        "Unknown error code returned when describing config rules.",
                        region=self._config[tac.region],
                        datainput=self._config[tac.datainput],
                    )
                    return

            except Exception:  # pylint: disable=broad-except
                logger.exception(
                    "Unknown exception happened when describing config rules.",
                    region=self._config[tac.region],
                    datainput=self._config[tac.datainput],
                )
                return

            if not tacommon.is_http_ok(response):
                logger.error(
                    "Failed to describe config rules, errorcode=%s",
                    tacommon.http_code(response),
                )
                return

            rules = response.get("ConfigRules")
            if not rules:
                return

            self._index_rules(rules)
            next_token = response.get("NextToken")
            if not next_token:
                return

    def _index_rules(self, rules):
        writer = self._config[tac.event_writer]
        for rule in rules:
            rule_name = rule["ConfigRuleName"]
            is_migrated = self._ckpt.get_migration_status(rule_name)
            if is_migrated:
                self._ckpt.sweep_file_checkpoint(
                    is_migrated, self._config[tac.datainput], rule_name
                )
            last_times = self._last_evaluation_times(rule_name)
            if last_times and last_times[0][0] == last_times[0][1]:
                logger.info(
                    "No new evaluation for rule=%s, region=%s, " "datainput=%s",
                    rule_name,
                    self._config[tac.region],
                    self._config[tac.datainput],
                )
                if not is_migrated and self.file_ckpt:
                    self._ckpt.migrate_ckpt(last_times[0][0], rule_name)
                continue

            event = writer.create_event(
                index=self._config.get(tac.index, "default"),
                host=self._config.get(tac.host, ""),
                source=self._source_config_rules,
                sourcetype=self._config.get(tac.sourcetype, "aws:config:rule"),
                time="",
                unbroken=False,
                done=False,
                events=rule,
            )
            writer.write_events((event,))

            self._index_compliance_details(rule_name)
            self._index_compliance_summary(rule_name)
            if not is_migrated and self.file_ckpt:
                self._ckpt.migrate_ckpt(last_times[0][0], rule_name)
            else:
                self._ckpt.set_last_evaluation_time(
                    last_times[0][0],
                )

    def _index_compliance_details(self, rule_name):
        sourcetype = self._config.get(tac.sourcetype, "aws:config:rule")
        writer = self._config[tac.event_writer]

        next_token = ""
        while 1:
            response = self._client.get_compliance_details_by_config_rule(
                ConfigRuleName=rule_name, NextToken=next_token
            )
            if not tacommon.is_http_ok(response):
                logger.error(
                    "Failed to collect compliance details for " "rule=%s, errorcode=%s",
                    rule_name,
                    tacommon.http_code(response),
                )
                return

            compliances = response.get("EvaluationResults")
            if not compliances:
                return

            events = []
            for compliance in compliances:
                evt_time = compliance["ResultRecordedTime"]
                compliance[
                    "ResultRecordedTime"
                ] = "{}".format(  # pylint: disable=consider-using-f-string
                    evt_time
                )
                compliance[
                    "ConfigRuleInvokedTime"
                ] = "{}".format(  # pylint: disable=consider-using-f-string
                    compliance["ConfigRuleInvokedTime"]
                )
                compliance["EvaluationResultIdentifier"][
                    "OrderingTimestamp"
                ] = "{}".format(  # pylint: disable=consider-using-f-string
                    compliance["EvaluationResultIdentifier"]["OrderingTimestamp"]
                )
                evt_time = tacommon.total_seconds(evt_time)

                event = writer.create_event(
                    index=self._config.get(tac.index, "default"),
                    host=self._config.get(tac.host, ""),
                    source=self._source_detail,
                    sourcetype=sourcetype,
                    time=evt_time,
                    unbroken=False,
                    done=False,
                    events=compliance,
                )
                events.append(event)
            writer.write_events(events)

            next_token = response.get("NextToken")
            if not next_token:
                return

    def _index_compliance_summary(self, rule_name):
        writer = self._config[tac.event_writer]
        sourcetype = self._config.get(tac.sourcetype, "aws:config:rule")

        response = self._client.get_compliance_summary_by_config_rule(
            ConfigRuleName=rule_name
        )
        if not tacommon.is_http_ok(response):
            logger.error(
                "Failed to collect compliance summary for " "rule=%s, errorcode=%s",
                rule_name,
                tacommon.http_code(response),
            )
            return

        summary = response.get("ComplianceSummary")
        if not summary:
            return

        evt_time = tacommon.total_seconds(summary["ComplianceSummaryTimestamp"])
        summary[
            "ComplianceSummaryTimestamp"
        ] = "{}".format(  # pylint: disable=consider-using-f-string
            summary["ComplianceSummaryTimestamp"]
        )
        summary["ConfigRuleName"] = rule_name
        event = writer.create_event(
            index=self._config.get(tac.index, "default"),
            host=self._config.get(tac.host, ""),
            source=self._source_summary,
            sourcetype=sourcetype,
            time=evt_time,
            unbroken=False,
            done=False,
            events=summary,
        )
        writer.write_events((event,))

    def get_interval(self):
        """Returns data input polling interval."""
        return self._config[tac.polling_interval]

    def stop(self):
        """Stops the input."""
        self._stopped = True

    def stopped(self):
        """Returns if the input is stopped or not."""
        return self._stopped or self._config[tac.data_loader_mgr].stopped()

    def get_props(self):
        """Returns config."""
        return self._config

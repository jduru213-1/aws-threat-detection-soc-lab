#
# SPDX-FileCopyrightText: 2021 Splunk, Inc. <sales@splunk.com>
# SPDX-License-Identifier: LicenseRef-Splunk-8-2021
#
#
"""
File for AWS inspector data loader.
"""


import datetime
import threading
import time
import sys
import os
import traceback


import splunk_ta_aws.common.ta_aws_common as tacommon
import splunk_ta_aws.common.ta_aws_consts as tac
from . import aws_inspector_conf as aiconf
from splunk_ta_aws.common.aws_checkpoint_migration_dlm import (
    CheckpointMigrationDLM,
    InspectorStrategy,
)
from splunktalib import state_store
from splunksdc import log as logging
from splunk_ta_aws.common.kv_checkpoint import KVStoreCheckpoint

logger = logging.get_module_logger()

INGESTED_EVENTS = 100


class ExitGraceFully(Exception):
    pass


class AWSInspectorAssessmentRunsDataLoader:  # pylint: disable=too-many-instance-attributes
    """Class for AWS Inspector Assesment Data Loader."""

    def __init__(self, config, client, account_id, collection):
        self._cli = client
        self._collection = collection
        self._config = config
        self._assessment_arns = []
        self._last_check_at = 0
        region = config[tac.region]
        data_input = config[tac.datainput]
        self._source = "{}:{}:inspector:assessmentRun".format(  # pylint: disable=consider-using-f-string
            account_id, region
        )
        self._source_type = self._config.get(tac.sourcetype, "aws::inspector")
        self._ckpt_key = "assessment_runs_{}_{}".format(data_input, region)

    @property
    def _writer(self):
        return self._config[tac.event_writer]

    def run(self):
        """Run method for input"""
        self._load()
        if not self._has_completed_arn():
            self._schedule()
        try:
            assessment_runs_ingested_events = 0
            while self._has_completed_arn():
                if self._config[tac.data_loader_mgr].stopped():
                    raise ExitGraceFully
                arn = self._assessment_arns[-1]
                run = self._collect_run(arn)
                if run is None:
                    continue
                self._index_run(run)
                assessment_runs_ingested_events += 1
                arn = self._pop_completed_arn()
                if assessment_runs_ingested_events == INGESTED_EVENTS:
                    self._save()
                    assessment_runs_ingested_events = 0
        except ExitGraceFully:
            logger.info(
                "Saving checkpoint for input before termination due to SIGTERM."
            )
        finally:
            self._save()
            if self._config[tac.data_loader_mgr].stopped():
                logger.info("Modular input exited with SIGTERM.")
                sys.exit(0)

    def _schedule(self):
        end = int(time.time()) - 120
        begin = self._last_check_at
        if end - begin < 30:
            return

        arns = self._list_completed_runs_in_time_window(begin, end)
        if arns is None:
            return

        self._assessment_arns.extend(arns)
        self._last_check_at = end

    def _index_run(self, data):
        etime = tacommon.total_seconds(data["completedAt"])
        event = self._writer.create_event(
            index=self._config.get(tac.index, "default"),
            host=self._config.get(tac.host, ""),
            source=self._source,
            sourcetype=self._source_type,
            time=etime,
            unbroken=False,
            done=False,
            events=data,
        )
        self._writer.write_events((event,))

    def _has_completed_arn(self):
        return len(self._assessment_arns) > 0

    def _pop_completed_arn(self):
        return self._assessment_arns.pop()

    def _collect_run(self, arn):
        response = self._cli.describe_assessment_runs(assessmentRunArns=[arn])
        if not tacommon.is_http_ok(response):
            return None
        run = response.get("assessmentRuns")[0]
        template_arn = run["assessmentTemplateArn"]
        package_arns = run["rulesPackageArns"]
        response = self._cli.describe_assessment_templates(
            assessmentTemplateArns=[template_arn]
        )
        if not tacommon.is_http_ok(response):
            return None
        template = response.get("assessmentTemplates")[0]
        response = self._cli.describe_rules_packages(rulesPackageArns=package_arns)
        if not tacommon.is_http_ok(response):
            return None
        packages = response.get("rulesPackages")
        run["assessmentTemplate"] = template
        run["rulesPackages"] = packages
        return run

    def _list_completed_runs_in_time_window(  # pylint: disable=invalid-name
        self, begin, end
    ):
        # boto3 do not accept unix timestamp on windows
        # cast to datetime by hand
        begin = datetime.datetime.utcfromtimestamp(begin)
        end = datetime.datetime.utcfromtimestamp(end)
        params = {
            "filter": {"completionTimeRange": {"beginDate": begin, "endDate": end}}
        }
        arns = []
        while True:
            response = self._cli.list_assessment_runs(**params)
            if not tacommon.is_http_ok(response):
                return None
            items = response["assessmentRunArns"]
            arns.extend(items)
            next_token = response.get("nextToken")
            if next_token is None:
                return arns
            params["nextToken"] = next_token

    def _save(self):
        self.ckpt_data["unprocessed_assessment_arns"] = self._assessment_arns
        self.ckpt_data["last_check_at"] = self._last_check_at
        self._collection.batch_save([self.ckpt_data])

    def _load(self):
        self.ckpt_data = self._collection.get(self._ckpt_key)
        if self.ckpt_data:
            self._assessment_arns = self.ckpt_data.get(
                "unprocessed_assessment_arns", []
            )
            self._last_check_at = self.ckpt_data.get("last_check_at", 0)


class AWSInspectorFindingsDataLoader:  # pylint: disable=too-many-instance-attributes
    """Class for AWS inspector findings data loader."""

    def __init__(self, config, client, account_id, collection):
        # jscpd:ignore-start
        self._cli = client
        self._collection = collection
        self._config = config
        self._finding_arns = []
        # jscpd:ignore-end

        self._last_check_at = 0
        region = config[tac.region]
        data_input = config[tac.datainput]
        self._source = (
            "{}:{}:inspector:finding".format(  # pylint: disable=consider-using-f-string
                account_id, region
            )
        )
        self._source_type = self._config.get(tac.sourcetype, "aws::inspector")
        self._ckpt_key = "findings_{}_{}".format(data_input, region)

    @property
    def _writer(self):
        return self._config[tac.event_writer]

    def run(self):
        """Run method for input"""
        self._load()
        if not self._has_finding_arns():
            self._schedule()
        try:
            findings_ingested_events = 0
            while self._has_finding_arns():
                if self._config[tac.data_loader_mgr].stopped():
                    raise ExitGraceFully
                arns = self._finding_arns[len(self._finding_arns) - 10 :]
                findings = self._collect_findings(arns)
                if findings is None:
                    continue
                self._index_findings(findings)
                findings_ingested_events += 10
                del self._finding_arns[len(self._finding_arns) - 10 :]
                if findings_ingested_events == INGESTED_EVENTS:
                    self._save()
                    findings_ingested_events = 0
        except ExitGraceFully:
            logger.info(
                "Saving checkpoint for input before termination due to SIGTERM."
            )
        finally:
            self._save()
            if self._config[tac.data_loader_mgr].stopped():
                logger.info("Modular input exited with SIGTERM.")
                sys.exit(0)

    def _schedule(self):
        end = int(time.time()) - 120
        begin = self._last_check_at
        if end - begin < 30:
            return

        arns = self._list_findings_by_time_window(begin, end)
        if arns is None:
            return

        self._finding_arns.extend(arns)
        self._last_check_at = end

    def _index_findings(self, findings):
        # jscpd:ignore-start
        for item in findings:
            etime = tacommon.total_seconds(item["updatedAt"])
            event = self._writer.create_event(
                index=self._config.get(tac.index, "default"),
                host=self._config.get(tac.host, ""),
                source=self._source,
                sourcetype=self._source_type,
                time=etime,
                unbroken=False,
                done=False,
                events=item,
            )
            self._writer.write_events((event,))
        # jscpd:ignore-end

    def _has_finding_arns(self):
        return len(self._finding_arns) > 0

    def _collect_findings(self, arns):
        response = self._cli.describe_findings(findingArns=arns)
        if not tacommon.is_http_ok(response):
            return None
        return response.get("findings")

    def _list_findings_by_time_window(self, begin, end):
        # boto3 do not accept unix timestamp on windows
        # cast to datetime by hand
        begin = datetime.datetime.utcfromtimestamp(begin)
        end = datetime.datetime.utcfromtimestamp(end)
        params = {"filter": {"creationTimeRange": {"beginDate": begin, "endDate": end}}}
        arns = []
        # jscpd:ignore-start
        while True:
            response = self._cli.list_findings(**params)
            if not tacommon.is_http_ok(response):
                return None
            items = response.get("findingArns")
            arns.extend(items)
            next_token = response.get("nextToken")
            if next_token is None:
                return arns
            params["nextToken"] = next_token
        # jscpd:ignore-end

    def _save(self):
        self.ckpt_data["unprocessed_findings_arns"] = self._finding_arns
        self.ckpt_data["last_check_at"] = self._last_check_at
        self._collection.batch_save([self.ckpt_data])

    def _load(self):
        self.ckpt_data = self._collection.get(self._ckpt_key)
        if self.ckpt_data:
            self._finding_arns = self.ckpt_data.get("unprocessed_findings_arns", [])
            self._last_check_at = self.ckpt_data.get("last_check_at", 0)


class AWSInspectorDataLoader:
    """Class for AWS inspector data loader."""

    def __init__(self, config):
        self._config = config
        self._stopped = False
        self._lock = threading.Lock()
        self._cli, self._credentials = tacommon.get_service_client(
            self._config, tac.inspector
        )

    def create_state_store(self):
        """
        This Method is used to create the state object to access the File Checkpoint
        """
        self._state_store = state_store.get_state_store(
            self._config,
            self._config[tac.app_name],
            collection_name="inspector",
            use_kv_store=self._config.get(tac.use_kv_store),
        )

    def create_state_key(self, file_type):
        """
        This Method is used to create the state object to access the File Checkpoint

        Args:
            file_type (str): Assessment file or findings file
        """
        if file_type == "assessment_runs":
            self._state_key = tacommon.b64encode_text(
                "assessment_runs_{}_{}".format(  # pylint: disable=consider-using-f-string
                    self._config[tac.datainput], self._config[tac.region]
                )
            )
        else:
            self._state_key = tacommon.b64encode_text(
                "findings_{}_{}".format(  # pylint: disable=consider-using-f-string
                    self._config[tac.datainput], self._config[tac.region]
                )
            )

        self._file_path = os.path.join(
            self._config[tac.checkpoint_dir], self._state_key
        )

    def update_migrate_flag_ckpt(self, key):
        """
        Update/Add migration flag in the KVStore

        Args:
            key (str): checkpoint key stored in the KVStore Collection
        """
        ckpt_data = {"_key": key, "is_migrated": 1}
        self._collection.save(ckpt_data)

    def get_migration_status(self, key):
        """
        Get migration flag value

        Args:
            key (str): KVStore checkpoint key

        Returns:
            bool: 0 or 1
        """
        ckpt = self._collection.get(key)
        if ckpt:
            return ckpt.get("is_migrated", 0)
        return 0

    def migrate_checkpoint(self, file_type):
        """
        This method is used to migrate the checkpoint to KVStore if required.

        Args:
            file_type (str): Assessment file or findings file
        """

        if file_type == "assessment_runs":
            self.kv_ckpt_key = "assessment_runs_{}_{}".format(
                self._config[tac.datainput], self._config[tac.region]
            )
        else:
            self.kv_ckpt_key = "findings_{}_{}".format(
                self._config[tac.datainput], self._config[tac.region]
            )

        is_migrated = self.get_migration_status(self.kv_ckpt_key)

        self.create_state_key(file_type)

        is_sweep_req = self.ckpt_obj._is_sweep_required(is_migrated, self._file_path)

        if is_sweep_req:
            self.ckpt_obj.remove_file(self._file_path)

        if not is_migrated:
            self.peform_migration(file_type)

        internals_filepath = os.path.join(self._config[tac.checkpoint_dir], "internals")
        if os.path.exists(internals_filepath):
            self.ckpt_obj.remove_file(internals_filepath)

    def peform_migration(self, file_type):
        load_file_ckpt = self.ckpt_obj._load_file_ckpt_req(self._file_path)

        if load_file_ckpt:
            self.create_state_store()
            logger.info(f"Migration started for input {self.kv_ckpt_key}.")
            self.ckpt_obj.load_checkpoint(self._state_store, self._state_key)
            logger.info(
                "Successfully loaded the {} checkpoint for input: {}".format(
                    file_type, self._config[tac.datainput]
                )
            )
            self.ckpt_obj.migrate(key=self.kv_ckpt_key, file_type=file_type)
            logger.info(f"Migration completed for input {self.kv_ckpt_key}.")
        else:
            self.update_migrate_flag_ckpt(self.kv_ckpt_key)

    def _do_indexing(self):
        if self._credentials.need_retire():
            self._cli, self._credentials = tacommon.get_service_client(
                self._config, tac.inspector
            )
        account_id = self._credentials.account_id

        # Create the config service object
        service = aiconf.create_service_obj(self._config)
        collection_name = "_".join([tac.splunk_ta_aws, tac.inspector])
        self._collection = KVStoreCheckpoint(
            collection_name=collection_name, service=service
        )
        self._collection.load_collection()

        # Create the object of the CheckpointMigrationDLM class
        self.ckpt_obj = CheckpointMigrationDLM(
            self._config, self._collection, InspectorStrategy()
        )

        # Migrate the assessment_runs file checkpoint to KVStore Checkpoint.
        self.migrate_checkpoint("assessment_runs")
        AWSInspectorAssessmentRunsDataLoader(
            self._config, self._cli, account_id, self._collection
        ).run()

        # Migrate the findings file checkpoint to KVStore Checkpoint.
        self.migrate_checkpoint("findings")
        AWSInspectorFindingsDataLoader(
            self._config, self._cli, account_id, self._collection
        ).run()

    def __call__(self):
        if self._lock.locked():
            logger.info(
                "Last round of data collecting for inspector findings"
                "region=%s, datainput=%s is not done yet",
                self._config[tac.region],
                self._config[tac.datainput],
            )
            return

        logger.info(
            "Start collecting inspector findings for region=%s, datainput=%s",
            self._config[tac.region],
            self._config[tac.datainput],
        )

        try:
            with self._lock:
                self._do_indexing()
        except Exception:  # pylint: disable=broad-except
            logger.error(
                "Failed to collect inspector findings for region=%s, "
                "datainput=%s, error=%s",
                self._config[tac.region],
                self._config[tac.datainput],
                traceback.format_exc(),
            )

        logger.info(
            "End of collecting inspector findings for region=%s, datainput=%s",
            self._config[tac.region],
            self._config[tac.datainput],
        )

    def get_interval(self):
        """Returns input polling interval."""
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

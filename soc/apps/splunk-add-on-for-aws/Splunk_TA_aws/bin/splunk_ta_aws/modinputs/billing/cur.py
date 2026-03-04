#
# SPDX-FileCopyrightText: 2021 Splunk, Inc. <sales@splunk.com>
# SPDX-License-Identifier: LicenseRef-Splunk-8-2021
#
#
"""
File for AWS Billing Cur input.
"""


import csv
import itertools
import json
import json.encoder
import logging as log4py
import re
import tempfile
import time
import os
import threading
from datetime import timedelta

import splunk_ta_aws.common.ta_aws_common as tacommon
import splunk_ta_aws.common.ta_aws_consts as tac
from io import BytesIO
from splunk_ta_aws import set_log_level
from splunk_ta_aws.common.proxy import ProxySettings
from splunk_ta_aws.common.s3 import S3Bucket
from splunk_ta_aws.common.kv_checkpoint import KVStoreCheckpoint
from splunk_ta_aws.common.checkpoint_migration import (
    CheckpointMigration,
    BillingStrategy,
)
from splunksdc import logging
from splunksdc.archive import ArchiveFactory
from splunksdc.collector import SimpleCollectorV1

from splunk_ta_aws.common.credentials import (  # isort: skip # pylint: disable=ungrouped-imports
    AWSCredentialsCache,
    AWSCredentialsProviderFactory,
)
from splunksdc.config import (  # isort: skip # pylint: disable=ungrouped-imports
    DateTimeField,
    LogLevelField,
    StanzaParser,
    StringField,
)
from splunksdc.utils import (  # isort: skip
    LogExceptions,
    LogWith,
)

logger = logging.get_module_logger()

# Avoid debug noise of each function call
ew_logger = log4py.getLogger("splunksdc.event_writer")
ew_logger.setLevel(log4py.ERROR)

ckpt_logger = log4py.getLogger("splunksdc.checkpoint")
ckpt_logger.setLevel(log4py.ERROR)


class AWSBillingSettings:
    """Class for AWS Billling settings."""

    @classmethod
    def load(cls, config):
        """Loads AWS settings."""
        content = config.load("aws_settings", stanza="aws_billing_cur")
        parser = StanzaParser([LogLevelField("log_level", default="WARNING")])
        settings = parser.parse(content)
        return cls(settings)

    def __init__(self, settings):
        self._settings = settings

    def setup_log_level(self):
        """Sets log level."""
        set_log_level(self._settings.log_level)


class AWSBillingDataInput:
    """Class for AWS billing data input."""

    def __init__(self, stanza):
        self._kind = stanza.kind
        self._name = stanza.name
        self._args = stanza.content
        self._start_time = int(time.time())

    @property
    def name(self):
        """Returns name."""
        return self._name

    @property
    def start_time(self):
        """Returns start time."""
        return self._start_time

    @LogWith(datainput=name, start_time=start_time)
    @LogExceptions(
        logger, "Data input was interrupted by an unhandled exception.", lambda e: -1
    )
    def run(self, app, config):
        """Runs input."""
        settings = AWSBillingSettings.load(config)
        settings.setup_log_level()
        proxy = ProxySettings.load(config)
        proxy.hook_boto3_get_proxies()

        credentials = self._create_credentials(config)
        bucket = self._create_bucket()
        options = self._create_options()
        event_writer = self._create_event_writer(app)
        sourcetype = self._create_sourcetype()

        # Load/Create KV collection
        self._collection_name = "_".join([tac.splunk_ta_aws, self._kind, self._name])
        self._collection = KVStoreCheckpoint(
            collection_name=self._collection_name, service=config._service
        )
        self._collection.load_collection()

        file_name = "".join([self._name, ".ckpt"])
        file_path = os.path.join(app.workspace(), file_name)

        is_migrated = self._get_migration_status()
        is_sweep_req = self._is_sweep_required(is_migrated, file_path)

        if not is_migrated:
            self._perform_migration(app, config, file_path)

        if is_sweep_req:
            self._sweep_file_checkpoint(file_path)

        with app.open_checkpoint(self._name + "_tmp") as interrupt_checkpoint:
            handler = AWSCostUsageReportHandler(
                self._collection,
                interrupt_checkpoint,
                credentials,
                bucket,
                event_writer,
                sourcetype,
                options,
            )
            return handler.run(app, config)

    def _get_migration_status(self):
        """
        Get migration flag value

        Returns:
            bool: 0 or 1
        """
        ckpt = self._collection.get(self._name)
        if ckpt:
            return ckpt.get("is_migrated", 0)
        return 0

    def _load_file_ckpt_req(self, file_path):
        """
        Check loading file based checkpoint is required or not

        Args:
            file_path (Any): path of the chekpoint file

        Returns:
            bool: True or False
        """
        if os.path.exists(file_path):
            return True
        return False

    def _update_migrate_flag_ckpt(self):
        """
        Update/Add migration flag in the KVStore
        """
        ckpt_data = {"_key": self._name, "is_migrated": 1}
        self._collection.save(ckpt_data)

    def _perform_migration(self, app, config, file_path):
        """
        Perform migration of file checkpoint to KVStore

        Args:
            app (Any): App object
            config (Any): Config object
        """
        migrate_ckpt = CheckpointMigration(
            self._collection, app, config, self._kind, self._name, BillingStrategy()
        )
        load_file_ckpt = self._load_file_ckpt_req(file_path)
        if load_file_ckpt:
            logger.info(f"Migration started for input {self._name}.")
            migrate_ckpt.load_checkpoint(self._name)
            migrate_ckpt.migrate()
            self._update_migrate_flag_ckpt()
            migrate_ckpt.send_notification(
                f"Migration Completed for input {self._name} {time.time()}.",
                "Splunk Add-on for Amazon Web Services: Checkpoint for {} input is now migrated to KV Store.".format(
                    self._name
                ),
            )
            logger.info(f"Migration completed for input {self._name}.")
        else:
            self._update_migrate_flag_ckpt()

    def _is_sweep_required(self, is_migrated, file_path):
        """
        Check sweeping file checkpoint is required or not

        Args:
            is_migrated (bool): migration flag value - 0 or 1
            file_path (Any): file path value

        Returns:
            bool: True or False
        """
        if is_migrated and os.path.exists(file_path):
            return True
        return False

    def _sweep_file_checkpoint(self, file_path):
        """
        Sweep file checkpoint once migration is completed

        Args:
            file_path (Any): file path value
        """
        thread = threading.Thread(
            target=CheckpointMigration.remove_file(file_path), daemon=True
        )
        thread.start()

    def _create_credentials(self, config):
        parser = StanzaParser(
            [
                StringField("aws_account", required=True),
                StringField("aws_iam_role"),
            ]
        )
        args = self._extract_arguments(parser)
        sts_endpoint_url = tacommon.get_endpoint_url(
            self._args, "sts_private_endpoint_url"
        )
        factory = AWSCredentialsProviderFactory(
            config, self._args.get("aws_s3_region"), sts_endpoint_url
        )
        provider = factory.create(args.aws_account, args.aws_iam_role)
        credentials = AWSCredentialsCache(provider)
        return credentials

    def _create_bucket(self):
        parser = StanzaParser(
            [
                StringField("bucket_name", required=True),
                StringField("bucket_region", required=True),
            ]
        )
        s3_endpoint_url = tacommon.get_endpoint_url(
            self._args, "s3_private_endpoint_url"
        )
        args = self._extract_arguments(parser)
        return S3Bucket(args.bucket_name, args.bucket_region, s3_endpoint_url)

    def _create_options(self):
        parser = StanzaParser(
            [
                StringField(
                    "report_prefix",
                    default="",  # pylint: disable=redundant-u-string-prefix
                ),
                StringField("temp_folder", default=None),
                DateTimeField("start_date", default="1970-01", fmt="%Y-%m"),
                StringField("report_names", default=r".*"),
            ]
        )
        return self._extract_arguments(parser)

    def _create_event_writer(self, app):
        stanza = self._kind + "://" + self._name
        parser = StanzaParser(
            [
                StringField("index"),
                StringField("host"),
                StringField("stanza", fillempty=stanza),
            ]
        )
        args = self._extract_arguments(parser)
        return app.create_event_writer(**vars(args))

    def _create_sourcetype(self):
        parser = StanzaParser(
            [
                StringField("sourcetype", default="aws:billing:cur"),
            ]
        )
        args = self._extract_arguments(parser)
        return args.sourcetype

    def _extract_arguments(self, parser):
        return parser.parse(self._args)


class AWSCostUsageReportJournal:
    """Class for AWS Cost Usage Report Journal."""

    def __init__(self, store):
        self._store = store

    def is_done(self, item):
        """Checks if done."""
        ckpt = self._store.get(item.key)
        if not ckpt or ckpt.get("value") == None:
            return False
        return self._compare(ckpt["value"], item.etag)

    def mark_done(self, item):
        """Marks as done."""
        ckpt_data = {"_key": item.key, "value": item.etag}
        self._store.batch_save([ckpt_data])

    @staticmethod
    def _compare(a, b, encoding="ascii"):  # pylint: disable=invalid-name
        # backward compatible with ckpt created by 4.6.x
        if isinstance(a, bytes):
            a = a.decode(encoding)
        if isinstance(b, bytes):
            b = b.decode(encoding)
        a = a.strip('"')
        b = b.strip('"')
        return a == b


class InterrupReportJournal:
    """Checkpoint for handling interrupt"""

    _DEFAULT_VALUE = 0

    def __init__(self, store, manifest):
        """Initialize the object."""
        self._store = store
        self._key = self._generate_key(manifest)
        self._value = self._get(self._key)

    @staticmethod
    def _generate_key(manifest):
        """Generate checkpoint key."""
        return f"{manifest.key}|{manifest.etag}"

    def _get(self, key):
        """Return the current checkpoint value."""
        value = {}
        try:
            pair = self._store.find(key)
            if pair and isinstance(pair.value, dict):
                value = pair.value
        except Exception as ex:  # pylint: disable=broad-except
            logger.error(f"Error occured while getting ingested event count: {ex}")
        return value

    def get_ingested_event_count(self, report_uri):
        """Return ingested event count for given report."""
        if report_uri in self._value:
            return self._value[report_uri]
        else:
            return self._DEFAULT_VALUE

    def update_ingested_event_count(self, report_uri, count):
        """Update the event count for given report."""
        self._value[report_uri] = count
        self._store.set(self._key, self._value, flush=True)

    def mark_manifest_done(self):
        """Delete the given report from checkpoint."""
        self._store.delete(self._key)

    def sweep(self):
        """Remove unncessary data from checkpoint."""
        self._store.sweep()


class BatchEventWriter:  # pylint: disable=too-many-instance-attributes
    """Class for Batch Event writer."""

    def __init__(self, writer, source, sourcetype, **kwargs):
        self._writer = writer
        self._source = source
        self._sourcetype = sourcetype
        self._cache_lines = []
        self._cache_size = 0
        self._cache_threshold = 4 * 1024 * 1024
        self._meta_keys = list(kwargs.keys())
        self._meta_values = list(kwargs.values())
        self.is_flushed = False

    def write(self, data):
        """Writes data."""
        self._append(data)
        self._commit()

    def _append(self, line):
        self._cache_lines.append(line)
        self._cache_size += len(line)

    def _commit(self, flush=False):
        self.is_flushed = False
        if not self._cache_size:
            return
        if self._cache_size >= self._cache_threshold or flush:
            logger.debug("Start writing events.", count=len(self._cache_lines))
            data = "\n".join(itertools.chain(self._cache_lines, [""]))
            self._writer.write_fileobj(
                data, source=self._source, sourcetype=self._sourcetype
            )
            self.is_flushed = True
            self._cache_lines = []
            self._cache_size = 0
            logger.debug("Write events done.", volume=len(data))

    def flush(self):
        """Flush method."""
        self._commit(flush=True)


class CSVParser:
    """Class for CSV parser."""

    def __init__(self, **kwargs):
        self._meta_keys = list(kwargs.keys())
        self._meta_values = list(kwargs.values())

    def parse(self, member):
        """Yields parsed data."""
        reader = csv.reader(member)
        fields = next(reader)  # pylint: disable=stop-iteration-return
        keys = tuple(itertools.chain(fields, self._meta_keys))
        for row in reader:
            values = itertools.chain(row, self._meta_values)
            data = self._render(list(zip(keys, values)))
            yield data

    @classmethod
    def _render(cls, pairs):
        segments = []
        for key, value in pairs:
            if not value:
                continue
            # encoding the value if whitespaces or quotes were found in value.
            if re.search(r'[ "]', value):
                value = json.encoder.encode_basestring(value)
            segments.append(
                "{0}={1}".format(key, value)  # pylint: disable=consider-using-f-string
            )
        return ", ".join(segments)


def _utf8_line_decoding(fileobj):
    for line in fileobj:
        yield line.decode("utf-8")


class AWSCostUsageReportHandler:  # pylint: disable=too-many-instance-attributes
    """Class for AWS Cost Usage Report Handler."""

    _MIN_TTL = timedelta(minutes=30)

    def __init__(  # pylint: disable=too-many-arguments
        self,
        checkpoint,
        interrupt_checkpoint,
        credentials,
        bucket,
        event_writer,
        sourcetype,
        options,
    ):
        self._credentials = credentials
        self._bucket = bucket
        self._checkpoint = checkpoint
        self._interrupt_checkpoint = interrupt_checkpoint
        self._event_writer = event_writer
        self._prefix = options.report_prefix
        self._sourcetype = sourcetype
        self._start_date = options.start_date.strftime("%Y%m")
        self._temp_folder = options.temp_folder
        self._selector = re.compile(options.report_names)
        self._archive = ArchiveFactory.create_default_instance()

    def _is_interested_report(self, name):
        if name == "/":
            return False
        return self._selector.search(name)

    def _discover_reports(self):
        logger.info("Start discovering reports.")
        prefix = self._prefix
        if prefix and not prefix.endswith("/"):
            prefix += "/"
        bucket = self._bucket
        credentials = self._keep_credentials_alive()
        s3_bkt = bucket.client(credentials)
        folders = bucket.list_folders(s3_bkt, prefix)
        reports = [name for name in folders if self._is_interested_report(name)]
        logger.info("Discover reports done.", reports=reports)
        return reports

    def _discover_manifests(self, report, start_date):
        logger.info("Start discovering manifests.", report=report)
        date_range_pattern = re.compile(r"\d{8}-\d{8}")
        bucket = self._bucket
        credentials = self._keep_credentials_alive()
        s3_bkt = bucket.client(credentials)
        marker = report + start_date
        manifests = []
        while True:
            files = bucket.list_files(s3_bkt, report, marker)
            if not files:
                break
            marker = files[-1].key
            for item in files:
                parts = item.key.split("/")
                if not parts[-1].endswith("-Manifest.json"):
                    continue
                report_date = parts[-2]
                if not date_range_pattern.match(report_date):
                    continue
                if start_date > report_date:
                    continue
                logger.info("Manifest file is found.", key=item.key, etag=item.etag)
                manifests.append(item)
        logger.info("Discovering manifests is done.", report=report)
        return manifests

    def _get_manifest(self, manifest):
        bucket = self._bucket
        credentials = self._keep_credentials_alive()
        s3_bkt = bucket.client(credentials)
        content = BytesIO()
        bucket.fetch(s3_bkt, manifest.key, content)
        return json.load(content)

    def _ingest_report(self, manifest, interrupt_journal):
        try:
            # use epoch time as transaction id
            txid = str(int(time.time()))
            content = self._get_manifest(manifest)
            count = 0

            for key in content.get("reportKeys", []):
                bucket = self._bucket
                credentials = self._keep_credentials_alive()
                s3_bkt = bucket.client(credentials)
                with self._open_temp_file() as cache:
                    _ = bucket.transfer(s3_bkt, key, cache)
                    uri = self._make_uri(key)
                    count += self._index_report(uri, cache, txid, interrupt_journal)

            self._index_digest(manifest, content, txid, count)
            return True
        except Exception:  # pylint: disable=broad-except
            logger.exception(
                "An error occurred while ingesting report.", mainfiest=manifest.key
            )
            return False

    def _keep_credentials_alive(self):
        if self._credentials.need_retire(self._MIN_TTL):
            self._credentials.refresh()
        return self._credentials

    def _open_temp_file(self):
        return tempfile.NamedTemporaryFile(dir=self._temp_folder)

    def _make_uri(self, key):
        uri = "s3://" + self._bucket.name + "/" + key
        return uri

    def _index_report(self, report_uri, cache, txid, interrupt_journal):
        logger.info("Start sending events for indexing", report_uri=report_uri)
        count = 0
        for (
            member,
            uri,  # pylint: disable=redefined-argument-from-local
        ) in self._archive.open(cache, report_uri):
            batch = BatchEventWriter(
                self._event_writer, source=uri, sourcetype=self._sourcetype
            )
            skip_events = interrupt_journal.get_ingested_event_count(uri)
            parser = CSVParser(_txid=txid)
            lines = _utf8_line_decoding(member)

            for event in parser.parse(lines):
                if skip_events and count < skip_events:
                    count += 1
                    continue

                batch.write(event)
                count += 1

                if batch.is_flushed:
                    interrupt_journal.update_ingested_event_count(uri, count)

            batch.flush()
            interrupt_journal.update_ingested_event_count(uri, count)

        logger.info(
            "Sent report for indexing done.",
            report_uri=report_uri,
            number_of_event=count,
        )
        return count

    def _index_digest(self, header, content, txid, count):
        # ingest the digest file
        uri = self._make_uri(header.key)
        logger.info(
            "Start sending manifest for indexing",
            uri=uri,
            size=header.size,
            etag=header.etag.strip('"'),
        )
        # by default, the sourcetype of the digest file is the original sourcetype plus ":digest"
        # e.g. aws:billing:cur -> aws:billing:cur:digest
        content["lastModified"] = header.last_modified.replace(tzinfo=None).isoformat()
        content["txid"] = txid
        content["eventCount"] = count
        sourcetype = self._sourcetype + ":digest"
        data = json.dumps(content)
        self._event_writer.write_fileobj(data, source=uri, sourcetype=sourcetype)
        logger.info("Sent digest for indexing done.", uri=uri, size=len(data))

    def run(self, app, config):  # pylint: disable=unused-argument
        """Runs input."""
        start_date = self._start_date
        journal = AWSCostUsageReportJournal(self._checkpoint)

        for container in self._discover_reports():
            for manifest in self._discover_manifests(container, start_date):
                if app.is_aborted():
                    return 0
                if journal.is_done(manifest):
                    continue

                interrupt_journal = InterrupReportJournal(
                    self._interrupt_checkpoint, manifest
                )
                if self._ingest_report(manifest, interrupt_journal):
                    journal.mark_done(manifest)
                    interrupt_journal.mark_manifest_done()
                    interrupt_journal.sweep()
        return 0


def modular_input_run(app, config):
    """Runs billing modular input."""
    inputs = app.inputs()
    datainput = AWSBillingDataInput(inputs[0])
    return datainput.run(app, config)


def main():
    """Main method for billing current module."""
    arguments = {
        "aws_account": {"title": "The name of AWS account."},
        "aws_iam_role": {"title": "The name of IAM user would be assumed."},
        "aws_s3_region": {"title": "Region to use for regional endpoint"},
        "private_endpoint_enabled": {
            "title": "To enable/disable use of private endpoint"
        },
        "s3_private_endpoint_url": {
            "title": "Private endpoint url to connect with s3 service"
        },
        "sts_private_endpoint_url": {
            "title": "Private endpoint url to connect with sts service"
        },
        "bucket_name": {"title": "What is the name of bucket."},
        "bucket_region": {"title": "Where is the bucket located."},
        "report_names": {"title": "A regex pattern for selecting reports."},
        "report_prefix": {"title": "The report prefix."},
        "start_date": {"title": "Monitoring reports later than the date."},
        "temp_folder": {"title": "An alternative temp folder path."},
    }

    SimpleCollectorV1.main(
        modular_input_run,
        title="AWS Billing (Cost And Usage Report)",
        use_single_instance=False,
        arguments=arguments,
    )

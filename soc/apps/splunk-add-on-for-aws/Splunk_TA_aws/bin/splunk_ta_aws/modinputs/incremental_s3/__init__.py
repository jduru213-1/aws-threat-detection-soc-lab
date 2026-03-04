#
# SPDX-FileCopyrightText: 2021 Splunk, Inc. <sales@splunk.com>
# SPDX-License-Identifier: LicenseRef-Splunk-8-2021
#
#
"""
File for init module for incremental S3 inputs.
"""


import os
import shutil
import time
import splunk_ta_aws.common.ta_aws_consts as tac
import splunk.rest as rest

import splunk_ta_aws.common.ta_aws_common as tacommon
from splunk_ta_aws import set_log_level
from splunk_ta_aws.common.proxy import ProxySettings
from splunk_ta_aws.common.s3 import S3Bucket
from splunksdc import environ, logging
from splunksdc.collector import SimpleCollectorV1
from splunksdc.utils import LogExceptions, LogWith

from .cloudfront_access_logs import CloudFrontAccessLogsDelegate
from .cloudtrail_logs import CloudTrailLogsDelegate
from .elb_access_logs import ELBAccessLogsDelegate
from .handler import AWSLogsHandler
from .s3_access_logs import S3AccessLogsDelegate

from splunk_ta_aws.common.credentials import (  # isort: skip # pylint: disable=ungrouped-imports
    AWSCredentialsCache,
    AWSCredentialsProviderFactory,
)
from splunksdc.config import (  # isort: skip # pylint: disable=ungrouped-imports
    DateTimeField,
    IntegerField,
    LogLevelField,
    StanzaParser,
    StringField,
)
from splunktalib.kv_client import KVClient
from solnlib.splunkenv import get_splunkd_access_info


logger = logging.get_module_logger()


class UnsupportedLogType(Exception):
    """Class for Unsupported Log type Exception."""

    pass  # pylint: disable=unnecessary-pass


class AWSLogsSettings:
    """Class for AWS logs settings."""

    @classmethod
    def load(cls, config):
        """Loads aws log settings."""
        content = config.load("aws_settings", stanza="splunk_ta_aws_logs")
        parser = StanzaParser([LogLevelField("log_level", default="WARNING")])
        settings = parser.parse(content)
        return cls(settings)

    def __init__(self, settings):
        self._settings = settings

    def setup_log_level(self):
        """Sets log level."""
        set_log_level(self._settings.log_level)


class AWSLogsProfile:
    """Class for AWS logs profile."""

    def __init__(self, log_type, delegate):
        self._type = log_type
        self._sourcetype = "aws:" + log_type
        self._delegate = delegate

    @property
    def type(self):
        """Returns type."""
        return self._type

    @property
    def sourcetype(self):
        """Returns sourcetype."""
        return self._sourcetype

    def create_delegate(self, args):
        """Returns delegate."""
        return self._delegate.build(args)


class AWSLogsDataInput:
    """ "Class for AWS Logs data input."""

    def __init__(self, stanza, registry):
        self._stanza = stanza
        self._name = stanza.name
        self._start_time = int(time.time())
        self._lookup = {}
        for profile in registry:
            self._lookup[profile.type] = profile

    def create_log_profile(self):
        """Returns log profile."""
        log_type = self._stanza.content.get("log_type", "")
        log_type = log_type.lower()
        profile = self._lookup.get(log_type)
        if not profile:
            raise UnsupportedLogType(log_type)
        return profile

    def parse_options(self):
        """Returns parsed options."""
        parser = StanzaParser(
            [
                IntegerField("max_retries", default=-1, lower=-1, upper=1000),
                IntegerField("max_fails", default=10000, lower=0, upper=10000),
                IntegerField("max_number_of_process", default=2, lower=1, upper=64),
                IntegerField("max_number_of_thread", default=4, lower=1, upper=64),
            ]
        )
        return self._extract(parser)

    def parse_extra(self):
        """Returns extracted config fields."""
        parser = StanzaParser(
            [
                StringField("log_file_prefix", default=""),
                DateTimeField("log_start_date", default="1970-1-1"),
                StringField("log_name_format", default=""),
                StringField("log_path_format", default=tac.account_level),
                StringField("log_partitions", default=""),
            ]
        )
        return self._extract(parser)

    def create_event_metadata(self, profile):
        """Returns event metadata."""
        stanza_name = self._assemble_stanza_id()
        parser = StanzaParser(
            [
                StringField("index"),
                StringField("host"),
                StringField("sourcetype", fillempty=profile.sourcetype),
                StringField("stanza", fillempty=stanza_name),
            ]
        )
        return self._extract(parser)

    def create_credentials(self, config):
        """Returns AWS credetials."""
        parser = StanzaParser(
            [
                StringField("aws_account", required=True),
                StringField("aws_iam_role"),
            ]
        )
        args = self._extract(parser)
        sts_endpoint_url = tacommon.get_endpoint_url(
            self._stanza.content, "sts_private_endpoint_url"
        )
        factory = AWSCredentialsProviderFactory(
            config, self._stanza.content.get("aws_s3_region"), sts_endpoint_url
        )
        provider = factory.create(args.aws_account, args.aws_iam_role)
        return AWSCredentialsCache(provider)

    def create_bucket(self):
        """Creates AWS S3 buckets."""
        parser = StanzaParser(
            [
                StringField("bucket_name", required=True),
                StringField("bucket_region", required=True),
            ]
        )
        args = self._extract(parser)
        s3_endpoint_url = tacommon.get_endpoint_url(
            self._stanza.content, "s3_private_endpoint_url"
        )
        return S3Bucket(args.bucket_name, args.bucket_region, s3_endpoint_url)

    def _extract(self, parser):
        return parser.parse(self._stanza.content)

    def _assemble_stanza_id(self):
        stanza = self._stanza
        return stanza.kind + "://" + stanza.name

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
        """Runs modular input."""
        settings = AWSLogsSettings.load(config)
        settings.setup_log_level()
        proxy = ProxySettings.load(config)
        proxy.hook_boto3_get_proxies()

        data_input_name = self._name
        profile = self.create_log_profile()
        extras = self.parse_extra()
        delegate = profile.create_delegate(extras)
        metadata = self.create_event_metadata(profile)
        options = self.parse_options()
        credentials = self.create_credentials(config)
        bucket = self.create_bucket()

        handler = AWSLogsHandler(
            settings,
            proxy,
            data_input_name,
            metadata,
            options,
            bucket,
            delegate,
            credentials,
        )
        return handler.run(app, config)


def modular_input_main(app, config):
    """Runs incremental s3 modinput."""
    inputs = app.inputs()
    datainput = AWSLogsDataInput(
        inputs[0],
        [
            AWSLogsProfile("cloudtrail", CloudTrailLogsDelegate),
            AWSLogsProfile("elb:accesslogs", ELBAccessLogsDelegate),
            AWSLogsProfile("cloudfront:accesslogs", CloudFrontAccessLogsDelegate),
            AWSLogsProfile("s3:accesslogs", S3AccessLogsDelegate),
        ],
    )
    return datainput.run(app, config)


def main():
    """Main method for init module of incremental s3 input."""
    arguments = {
        "aws_account": {"title": "The AWS account name."},
        "aws_iam_role": {"title": "Assume Role.", "required_on_create": False},
        "log_type": {"title": "What is kind of log."},
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
        "bucket_name": {"title": "Where are the logs located."},
        "bucket_region": {"title": "Where is the bucket located."},
        "host_name": {
            "title": "Host the bucket located. Used to detect bucket_region."
        },
        "log_file_prefix": {"title": "Please read document for details."},
        "log_start_date": {
            "title": "The logs earlier than this date would not be ingested."
        },
        "log_name_format": {"title": "Please Read document for details."},
        "log_path_format": {"title": "Please Read document for details."},
        "max_retries": {"title": "Max Retries", "required_on_create": False},
        "max_fails": {"title": "Max Fails", "required_on_create": False},
        "max_number_of_process": {
            "title": "How many worker processes could be running in parallel for each input",
            "required_on_create": False,
        },
        "max_number_of_thread": {
            "title": "How many worker threads could be running in parallel for each process",
            "required_on_create": False,
        },
    }

    SimpleCollectorV1.main(
        modular_input_main,
        title="AWS S3 Incremental Logs",
        use_single_instance=False,
        arguments=arguments,
        log_file_sharding=True,
    )


def create_data_input(name, *args, **kwargs):  # pylint: disable=unused-argument
    """Creates data inputs."""
    remove_checkpoints(name, *args, **kwargs)


def delete_data_input(name, *args, **kwargs):  # pylint: disable=unused-argument
    """Deletes checkpoints"""
    remove_checkpoints(name, *args, **kwargs)


def remove_checkpoints(name, *args, **kwargs):
    """Deletes checkpoints for incremental s3 input."""
    root = environ.get_checkpoint_folder("splunk_ta_aws_logs")
    path = os.path.join(root, name)

    # try remove files for cloudtrail and elb
    if os.path.isdir(path):
        shutil.rmtree(path, ignore_errors=True)

    # try remove files for s3 and cloudfront
    path += ".ckpt"
    if os.path.isfile(path):
        os.remove(path)

    session_key = kwargs.get("session_key", None)
    if session_key:
        collection_name = "_".join([tac.splunk_ta_aws, "splunk_ta_aws_logs", name])
        scheme, host, port = get_splunkd_access_info(session_key)
        splunkd_host = scheme + "://" + host + ":" + str(port)
        kv_client = KVClient(splunkd_host, session_key)
        kv_client.delete_collection(collection_name, tac.splunk_ta_aws)

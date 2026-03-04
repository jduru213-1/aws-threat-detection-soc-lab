#
# SPDX-FileCopyrightText: 2021 Splunk, Inc. <sales@splunk.com>
# SPDX-License-Identifier: LicenseRef-Splunk-8-2021
#
#
"""
File for handling AWS credentials.
"""


from datetime import datetime, timedelta

import boto3
import boto3.session
import botocore.client
import splunk_ta_aws.common.ta_aws_common as tacommon
from botocore.utils import InstanceMetadataFetcher
from dateutil.parser import parse as parse_datetime
from dateutil.tz import tzutc
from splunksdc import log as logging

from splunksdc.config import (  # isort: skip
    BooleanField,
    IntegerField,
    StanzaParser,
    StringField,
)

logger = logging.get_module_logger()


class AWSCredentialsError(Exception):
    """Class for AWS credentials exception."""

    pass  # pylint: disable=unnecessary-pass


class AWSRawCredentials:
    """Class for AWS Credentials."""

    def __init__(
        self,
        aws_access_key_id,
        aws_secret_access_key,
        aws_session_token=None,
        expiration=None,
    ):
        """

        :param aws_access_key_id:
        :param aws_secret_access_key:
        :param aws_session_token:
        :param expiration: A datetime object
        """
        self._aws_access_key_id = aws_access_key_id
        self._aws_secret_access_key = aws_secret_access_key
        self._aws_session_token = aws_session_token
        self._expiration = expiration

    def client(
        self,
        service_name,
        region_name,
        boto_session=None,
        endpoint_url=None,
        config=None,
    ):
        """Returns client."""
        if not boto_session:
            boto_session = boto3
        params = {
            "region_name": region_name,
            "aws_access_key_id": self._aws_access_key_id,
            "aws_secret_access_key": self._aws_secret_access_key,
            "aws_session_token": self._aws_session_token,
            "config": config,
        }
        if service_name == "s3v4":
            params["config"] = botocore.client.Config(signature_version="s3v4")
            service_name = "s3"

        # endpoint_url will be used for connecting to specific service for API call.
        # It can be either a valid vpce endpoint or a standard regional endpoint
        if not endpoint_url:
            if service_name not in ["cloudwatch", "elb", "elbv2"]:
                params["endpoint_url"] = tacommon.format_default_endpoint_url(
                    service_name, region_name
                )
        else:
            params["endpoint_url"] = endpoint_url

        return boto_session.client(service_name, **params)

    @property
    def aws_access_key_id(self):
        """Returns access key id."""
        return self._aws_access_key_id

    @property
    def aws_secret_access_key(self):
        """Returns aws secret access key."""
        return self._aws_secret_access_key

    @property
    def aws_session_token(self):
        """Returns aws session token."""
        return self._aws_session_token

    @property
    def expiration(self):
        """Returns expiration."""
        return self._expiration


class EC2InstanceRoleProvider:
    """
    Query Role Credentials by EC2 instance metadata service
    """

    def __call__(self):
        logger.info("Fetch ec2 instance credentials.")
        fetcher = InstanceMetadataFetcher(timeout=5.0, num_attempts=10)
        response = fetcher.retrieve_iam_role_credentials()
        if not response:
            # There's no way to know exactly reason,
            # because botocore doesn't pass back the response.
            # What only we can do here is raise a general error.
            raise AWSCredentialsError("Retrieve ec2 instance credentials failed.")
        key_id = response["access_key"]
        secret_key = response["secret_key"]
        token = response["token"]
        expiration = response["expiry_time"]
        if not isinstance(expiration, datetime):
            expiration = parse_datetime(expiration)

        return AWSRawCredentials(key_id, secret_key, token, expiration)


class StaticAccessKeyProvider:
    """Class for static access key provider."""

    def __init__(self, key_id, secret_key):
        self._key_id = key_id
        self._secret_key = secret_key

    def __call__(self):
        return AWSRawCredentials(self._key_id, self._secret_key)


class AWSAccount:
    """Class for AWS account."""

    DEFAULT_REGION = {
        1: "us-east-1",
        2: "us-gov-west-1",
        4: "cn-north-1",
    }

    def __init__(self, profile):
        self._profile = profile

    def get_default_region(self):
        """Returns default region."""
        return self.DEFAULT_REGION.get(self._profile.category)

    def _create_credentials_provider(self):
        profile = self._profile
        if profile.iam:
            return EC2InstanceRoleProvider()
        return StaticAccessKeyProvider(profile.key_id, profile.secret_key)

    def load_raw_credentials(self):
        """Loads Raw credentials."""
        provider = self._create_credentials_provider()
        credentials = provider()
        return credentials

    def load_credentials(self, boto_session=None, region_name=None, endpoint_url=None):
        """Loads credentials."""
        credentials = self.load_raw_credentials()
        if not region_name:
            region_name = self.get_default_region()
        sts = credentials.client("sts", region_name, boto_session, endpoint_url)
        identity = sts.get_caller_identity()
        arn = identity.get("Arn")

        return AWSCredentials(
            aws_access_key_id=credentials.aws_access_key_id,
            aws_secret_access_key=credentials.aws_secret_access_key,
            aws_session_token=credentials.aws_session_token,
            expiration=credentials.expiration,
            arn=arn,
        )


class AWSIAMRole:
    """Class for AWS IAM role."""

    def __init__(self, profile):
        self._arn = profile.arn

    def load_credentials(  # pylint: disable=too-many-arguments
        self, account, duration, boto_session=None, region_name=None, endpoint_url=None
    ):
        """Loads credentials."""
        arn = self._arn
        source = account.load_raw_credentials()
        if not region_name:
            region_name = account.get_default_region()
        sts = source.client("sts", region_name, boto_session, endpoint_url)
        logger.info("request role credentials", arn=arn, duration=duration, sts=sts)

        response = sts.assume_role(
            RoleArn=arn, RoleSessionName="splunk_ta_aws", DurationSeconds=duration
        )
        content = response["Credentials"]

        return AWSCredentials(
            aws_access_key_id=content["AccessKeyId"],
            aws_secret_access_key=content["SecretAccessKey"],
            aws_session_token=content["SessionToken"],
            expiration=content["Expiration"],
            arn=arn,
        )


class AWSCredentials(AWSRawCredentials):
    """Class for AWS Credentials."""

    _MIN_TTL = timedelta(minutes=5)

    def __init__(  # pylint: disable=too-many-arguments
        self,
        aws_access_key_id,
        aws_secret_access_key,
        aws_session_token,
        expiration,
        arn,
    ):
        super(AWSCredentials, self).__init__(  # pylint: disable=super-with-arguments
            aws_access_key_id, aws_secret_access_key, aws_session_token, expiration
        )
        self._arn = arn
        parts = arn.split(":")
        self._partition = parts[1]
        self._account_id = parts[4]

    @property
    def arn(self):
        """Returns ARN."""
        return self._arn

    @property
    def account_id(self):
        """Returns account id."""
        return self._account_id

    @property
    def partition(self):
        """Returns partition."""
        return self._partition

    def need_retire(self, threshold=_MIN_TTL):
        """Returns if the credentials need to refresh or not."""
        if not self.expiration:
            return False
        now = datetime.utcnow().replace(tzinfo=tzutc())
        delta = self.expiration - now
        return delta < threshold


class AWSCredentialsProviderFactory:
    """Class for AWS Credentials provider factory."""

    def __init__(self, config, region_name=None, endpoint_url=None):
        self._config = config
        self.region_name = region_name
        self.endpoint_url = endpoint_url

    def create(self, aws_account_name, aws_iam_role_name):
        """Creates AWS account."""
        settings = self._load_assume_role_settings()
        aws_account = self._load_aws_account(aws_account_name)
        if aws_iam_role_name:
            aws_iam_role = self._load_aws_iam_role(aws_iam_role_name)
            return AWSAssumedRoleProvider(
                settings, aws_account, aws_iam_role, self.region_name, self.endpoint_url
            )

        return AWSAccountProvider(aws_account, self.region_name, self.endpoint_url)

    def _load_aws_account(self, aws_account_name):
        if not aws_account_name:
            raise AWSCredentialsError("The name of account is invalid.")

        name = "splunk_ta_aws/settings/all_accounts"
        content = self._config.load(name, stanza=aws_account_name, virtual=True)
        parser = StanzaParser(
            [
                BooleanField("iam", default=False),
                StringField("key_id"),
                StringField("secret_key"),
                IntegerField("category", default=0),
            ]
        )
        profile = parser.parse(content)
        return AWSAccount(profile)

    def _load_aws_iam_role(self, aws_iam_role_name):
        if not aws_iam_role_name:
            raise AWSCredentialsError("The name of IAM role is invalid.")

        name = "splunk_ta_aws/settings/splunk_ta_aws_iam_role"
        content = self._config.load(name, stanza=aws_iam_role_name, virtual=True)
        parser = StanzaParser([StringField("arn")])
        profile = parser.parse(content)
        return AWSIAMRole(profile)

    def _load_assume_role_settings(self):
        stanza = self._config.load("aws_settings", stanza="assume_role")
        parser = StanzaParser(
            [IntegerField("duration", default=3600, lower=900, upper=3600)]
        )
        return parser.parse(stanza)


class AWSCredentialsProvider:
    """Class for AWS credentials provider."""

    def load(self):
        """Load method."""
        pass  # pylint: disable=unnecessary-pass


class AWSAccountProvider(AWSCredentialsProvider):
    """Class for AWS account provider."""

    def __init__(self, aws_account, region_name=None, endpoint_url=None):
        self._aws_account = aws_account
        self.region_name = region_name
        self.endpoint_url = endpoint_url

    def load(self):
        """
        Get credentials of an account
        :return: An instance of AWSCredentials
        """
        return self._aws_account.load_credentials(
            region_name=self.region_name, endpoint_url=self.endpoint_url
        )


class AWSAssumedRoleProvider(AWSCredentialsProvider):
    """Class for AWS assume role provider."""

    def __init__(  # pylint: disable=too-many-arguments
        self, settings, aws_account, aws_iam_role, region_name=None, endpoint_url=None
    ):
        self._settings = settings
        self._aws_account = aws_account
        self._aws_iam_role = aws_iam_role
        self.region_name = region_name
        self.endpoint_url = endpoint_url

    def load(self):
        """
        Get credentials of an IAM role
        :return: An instance of AWSCredentials
        """

        logger.info("Begin loading assumed role credentials.")
        aws_account = self._aws_account
        aws_iam_role = self._aws_iam_role
        assume_role_duration = self._settings.duration
        credentials = aws_iam_role.load_credentials(
            aws_account,
            assume_role_duration,
            region_name=self.region_name,
            endpoint_url=self.endpoint_url,
        )
        return credentials


class AWSCredentialsCache:
    """Class for AWS credentials cache."""

    def __init__(self, provider):
        self._provider = provider
        self._credentials = provider.load()

    def refresh(self):
        """Sets credentials value."""
        self._credentials = self._provider.load()

    def need_retire(self, ttl):
        """Returns credentials need retire."""
        return self._credentials.need_retire(ttl)

    def client(
        self,
        service_name,
        region_name,
        boto_session=None,
        endpoint_url=None,
        config=None,
    ):
        """Returns client."""
        return self._credentials.client(
            service_name, region_name, boto_session, endpoint_url, config
        )

    @property
    def account_id(self):
        """Returns account id."""
        return self._credentials.account_id

    @property
    def partition(self):
        """Returns credentials partition."""
        return self._credentials.partition

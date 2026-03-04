# Generic consts
#
# SPDX-FileCopyrightText: 2021 Splunk, Inc. <sales@splunk.com>
# SPDX-License-Identifier: LicenseRef-Splunk-8-2021
#
#
# pylint: disable=invalid-name

"""
File for setting AWS generic constants.
"""
source = "source"
sourcetype = "sourcetype"
index = "index"
interval = "interval"
server_uri = "server_uri"
server_host = "server_host"
session_key = "session_key"
checkpoint_dir = "checkpoint_dir"
app_name = "app_name"
disabled = "disabled"
stanza_name = "stanza"
meta_app_name = "appName"
meta_user_name = "userName"
host = "host"

# Incremental s3
account_level = "account_level"
organization_level = "organization_level"

data_loader_mgr = "data_loader_mgr"
event_writer = "event_writer"


# Global settings consts
splunk_ta_aws = "Splunk_TA_aws"
proxy_type = "proxy_type"
proxy_hostname = "proxy_hostname"
proxy_port = "proxy_port"
proxy_username = "proxy_username"
proxy_password = "proxy_password"
log_level = "log_level"
log_stanza = "logging"
global_settings = "global_settings"
log_file = "log_file"

name = "name"
datainput = "datainput"

# global tuple used to check file extensions against for delimited file parsing
csv_file_suffixes = (".csv", ".psv", ".tsv")

# AWS related
key_id = "key_id"
secret_key = "secret_key"
account = "account"
iam_role = "iam_role"
account_id = "account_id"
region = "region"
regions = "regions"
is_secure = "is_secure"
validate_certs = "validate_certs"

aws_account = "aws_account"
aws_iam_role = "aws_iam_role"
aws_region = "aws_region"
aws_region_category = "aws_region_category"

polling_interval = "polling_interval"

kinesis = "kinesis"
cloudwatch = "cloudwatch"
config = "config"
inspector = "inspector"
inspector_v2 = "inspector2"
aws_service = "aws_service"

use_hec = "use_hec"
use_raw_hec = "use_raw_hec"
use_kv_store = "use_kv_store"
use_multiprocess = "use_multiprocess"
retry_max_attempts = "retry_max_attempts"
DEFAULT_ACCOUNT_ID = "000000000000"
RETRY_MODE = "adaptive"
DEFAULT_RETRY_MAX_ATTEMPTS = 5
LoadBalancerNames = "LoadBalancerNames"
ResourceArns = "ResourceArns"
LoadBalancerName = "LoadBalancerName"
ResourceArn = "ResourceArn"


class RegionCategory:
    """Class for region category."""

    DEFAULT = 0
    COMMERCIAL = 1
    USGOV = 2
    CHINA = 4
    VALID = [COMMERCIAL, USGOV, CHINA]


CATEGORY_HOST_NAME_MAP = {
    RegionCategory.COMMERCIAL: "s3.amazonaws.com",
    RegionCategory.USGOV: "s3-us-gov-west-1.amazonaws.com",
    RegionCategory.CHINA: "s3.cn-north-1.amazonaws.com.cn",
}

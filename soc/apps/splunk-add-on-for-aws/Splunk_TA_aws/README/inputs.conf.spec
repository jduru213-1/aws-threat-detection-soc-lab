##
## SPDX-FileCopyrightText: 2021 Splunk, Inc. <sales@splunk.com>
## SPDX-License-Identifier: LicenseRef-Splunk-8-2021
##
##
[aws_cloudtrail://<name>]
aws_account = AWS account used to connect to AWS
aws_region = AWS region of log notification SQS queue
sqs_queue = log notification SQS queue
exclude_describe_events = boolean indicating whether to exclude read-only events from indexing. defaults to true
remove_files_when_done = boolean indicating whether to remove s3 files after reading defaults to false
blacklist = override regex for the "exclude_describe_events" setting. default regex applied is ^(?:Describe|List|Get)
excluded_events_index = name of index to put excluded events into. default is empty, which discards the events
private_endpoint_enabled = To enable/disable use of private endpoint
sqs_private_endpoint_url = Private endpoint url to connect with sqs service
sts_private_endpoint_url = Private endpoint url to connect with sts service
s3_private_endpoint_url = Private endpoint url to connect with s3 service
python.version = python3


[aws_cloudtrail_lake://<name>]
aws_account = AWS account used to connect to AWS
aws_iam_role = AWS IAM role that to be assumed
aws_region = AWS region of event data store
private_endpoint_enabled = To enable/disable use of private endpoint
cloudtrail_private_endpoint_url = Private endpoint url to connect with cloudtrail service
sts_private_endpoint_url = Private endpoint url to connect with sts service
input_mode = Mode of input. continuously_monitor OR index_once
event_data_store = Name of the cloudtrail lake event data store.
start_date_time = Start time of the data collection. Default is 7 days ago
end_date_time = Required when index_once mode is selected
query_window_size = How many minute's worth of data to query each interval.
delay_throttle = CloudTrail typically delivers events within an average of about 5 minutes of an API call. This time is not guaranteed.


python.version = python3


[aws_cloudwatch://<name>]
aws_account = AWS account used to connect to AWS
aws_iam_role = AWS IAM role that to be assumed
aws_region = AWS region of CloudWatch metrics
metric_namespace = CloudWatch metric namespace
metric_names = CloudWatch metric names
metric_dimensions = CloudWatch metric dimensions
statistics = CloudWatch metric statistics being requested
period = CloudWatch metric granularity, in second
use_metric_format = boolean indicating whether to transform data to metric format
metric_expiration = How long the discovered metrics would be cached for, in seconds
query_window_size = How far back to retrieve data points for, in number of data points
polling_interval = Deprecated, Do Not Use
private_endpoint_enabled = To enable/disable use of private endpoint
sts_private_endpoint_url = Private endpoint url to connect with sts service
s3_private_endpoint_url = Private endpoint url to connect with s3 service
autoscaling_private_endpoint_url = Private endpoint url to connect with autoscaling service
ec2_private_endpoint_url = Private endpoint url to connect with ec2 service
elb_private_endpoint_url = Private endpoint url to connect with elb service
monitoring_private_endpoint_url = Private endpoint url to connect with Monitoring service
lambda_private_endpoint_url = Private endpoint url to connect with lambda service
python.version = python3


[aws_s3://<name>]
is_secure = whether use secure connection to AWS
host_name = the host name of the S3 service
aws_account = AWS account used to connect to AWS
bucket_name = S3 bucket
polling_interval = Polling interval for statistics
key_name = S3 key prefix
recursion_depth = For folder keys, -1 == unconstrained
initial_scan_datetime = Splunk relative time
terminal_scan_datetime = Only S3 keys which have been modified before this datetime will be considered. Using datetime format: %Y-%m-%dT%H:%M:%S%z (for example, 2011-07-06T21:54:23-0700).
max_items = Max trackable items.
max_retries = Max number of retry attempts to stream incomplete items.
whitelist = Override regex for blacklist when using a folder key.
blacklist = Keys to ignore when using a folder key.
character_set = The encoding used in your S3 files. Default to 'auto' meaning that file encoding will be detected automatically amoung UTF-8, UTF8 without BOM, UTF-16BE, UTF-16LE, UTF32BE and UTF32LE. Notice that once one specified encoding is set, data input will only handle that encoding.
ct_blacklist = The blacklist to exclude cloudtrail events. Only valid when manually set sourcetype=aws:cloudtrail.
ct_excluded_events_index = name of index to put excluded events into. default is empty, which discards the events
aws_iam_role = AWS IAM role that to be assumed.
aws_s3_region = Region to connect with s3 service using regional endpoint
private_endpoint_enabled = To enable/disable use of private endpoint
s3_private_endpoint_url = Private endpoint url to connect with s3 service
sts_private_endpoint_url = Private endpoint url to connect with sts service
parse_csv_with_header = Enable parsing of CSV data with header
parse_csv_with_delimiter = Enable parsing of CSV data by chosen delimiter
python.version = python3


[aws_billing://<name>]
aws_account = AWS account used to connect to fetch the billing report
host_name = the host name of the S3 service
bucket_name = S3 bucket
report_file_match_reg = CSV report file in regex, it will override below report type options instead
monthly_report_type = report type for monthly report. options: None, Monthly report, Monthly cost allocation report
detail_report_type = report type for detail report. options: None, Detailed billing report, Detailed billing report with resources and tags
aws_iam_role = AWS IAM role that to be assumed.
temp_folder = Temp folder used for downloading detailed billing csv.zip files.
aws_s3_region = Region to connect with s3 service using regional endpoint

# below items are internally used only
recursion_depth = recursion depth when iterate files
initial_scan_datetime = start scan time
monthly_timestamp_select_column_list = fields of timestamp extracted from monthly report, seperated by '|'
detail_timestamp_select_column_list = fields of timestamp extracted from detail report, seperated by '|'
time_format_list = time format extraction from existing. e.g. "%Y-%m-%d %H:%M:%S" seperated by '|'
max_file_size_csv_in_bytes = max file size in csv file format, default: 50MB
max_file_size_csv_zip_in_bytes = max file size in csv zip format, default: 1GB
header_look_up_max_lines = maximum lines to look up header of billing report
header_magic_regex = regex of header to look up
monthly_real_timestamp_extraction = for monthly report, regex to extract real timestamp in the montlh report, must contains "(%TIME_FORMAT_REGEX%)", which will be replaced with one value defined in "monthly_real_timestamp_format_reg_list"
monthly_real_timestamp_format_reg_list = for monthly report, regex to match the format of real time string. seperated by '|'
python.version = python3


[aws_config://<name>]
aws_account = AWS account used to connect to AWS
aws_region = AWS region of log notification SQS queue
sqs_queue = Starling Notification SQS queue
enable_additional_notifications = deprecated
polling_interval = Polling interval for statistics
python.version = python3


[aws_description://<name>]
placeholder = placeholder. Please see aws_description_tasks.conf.spec for task spec.
python.version = python3


[aws_metadata://<name>]
placeholder = placeholder. Please see aws_metadata_tasks.conf.spec for task spec.
retry_max_attempts = An integer representing the maximum number of retry attempts that will be made on a single request
python.version = python3


[aws_cloudwatch_logs://<name>]
placeholder = placeholder. Please see aws_cloudwatch_logs_tasks.conf.spec for task spec.
private_endpoint_enabled = To enable/disable use of private endpoint
logs_private_endpoint_url = Private endpoint url to connect with logs service
sts_private_endpoint_url = Private endpoint url to connect with sts service
python.version = python3


[aws_config_rule://<name>]
placeholder = placeholder
python.version = python3


[aws_inspector://<name>]
placeholder = placeholder
python.version = python3


[aws_inspector_v2://<name>]
placeholder = placeholder
python.version = python3


[aws_kinesis://<name>]
placeholder = placeholder
private_endpoint_enabled = To enable/disable use of private endpoint
kinesis_private_endpoint_url = Private endpoint url to connect with kinesis service
sts_private_endpoint_url = Private endpoint url to connect with sts service
python.version = python3


[splunk_ta_aws_sqs://<name>]
placeholder = placeholder
python.version = python3


[splunk_ta_aws_logs://<name>]
log_type =
aws_account =
host_name =
bucket_name =
bucket_region =
log_file_prefix =
log_start_date =
log_name_format =
log_path_format =
aws_iam_role = AWS IAM role that to be assumed.
max_retries = @integer:[-1, 1000]. default is -1. -1 means retry until success.
max_fails = @integer: [0, 10000]. default is 10000. Stop discovering new keys if the number of failed files exceeded the max_fails.
max_number_of_process = @integer:[1, 64]. default is 2.
max_number_of_thread = @integer:[1, 64]. default is 4.
aws_s3_region = Region to connect with s3 service using regional endpoint
private_endpoint_enabled = To enable/disable use of private endpoint
s3_private_endpoint_url = Private endpoint url to connect with s3 service
sts_private_endpoint_url = Private endpoint url to connect with sts service
python.version = python3


[aws_sqs_based_s3://<name>]
aws_account = The AWS account or EC2 IAM role the input uses to access SQS messages and S3 keys.
aws_iam_role = AWS IAM role that to be assumed in the input.
using_dlq = This checkbox gives an option to remove the checking of DLQ for ingestion of specific data. It is recommended to have DLQ linked with SQS Queue.
sqs_queue_url = Name of SQS queue to which notifications of S3 file(s) creation are sent.
sqs_queue_region = Name of the AWS region in which the notification queue is located.
sqs_batch_size = @integer:[1, 10]. Max number of messages to pull from SQS in one batch. Default is 10.
s3_file_decoder = Name of a decoder which decodes files into events: CloudTrail, Config, S3 Access Logs, ELB Access Logs, CloudFront Access Logs, Amazon Security Lake, Transit Gateway Flow Logs and CustomLogs.
private_endpoint_enabled = To enable/disable use of private endpoint
sqs_private_endpoint_url = Private endpoint url to connect with sqs service
s3_private_endpoint_url = Private endpoint url to connect with s3 service
sts_private_endpoint_url = Private endpoint url to connect with sts service
use_raw_hec = scheme://netloc/token, for instance, https://192.168.1.1:8088/550E8400-E29B-41D4-A716-446655440000.
sqs_sns_validation = Enable SNS singature validation
parse_firehose_error_data = Enable ErrorData parsing(failed kinesis firehose stream data)
parse_csv_with_header = Enable parsing of CSV data with header
parse_csv_with_delimiter = Enable parsing of CSV data by chosen delimiter
sns_max_age = Deprecated param, Max age of SNS message
metric_index_flag = Flag to check whether to use metric index or not
python.version = python3


[aws_billing_cur://<name>]
aws_account = The AWS account or EC2 IAM role for data ingestion.
aws_iam_role =  AWS IAM role would be assumed.
bucket_name = The bucket which reports deliver to.
bucket_region = The location of the bucket.
report_names = The regex for selection reports.
report_prefix = The report prefix.
start_date = Monitoring reports later than the date.
temp_folder = An alternative temp folder path.
aws_s3_region = Region to connect with s3 service using regional endpoint
private_endpoint_enabled = To enable/disable use of private endpoint
s3_private_endpoint_url = Private endpoint url to connect with s3 service
sts_private_endpoint_url = Private endpoint url to connect with sts service
python.version = python3

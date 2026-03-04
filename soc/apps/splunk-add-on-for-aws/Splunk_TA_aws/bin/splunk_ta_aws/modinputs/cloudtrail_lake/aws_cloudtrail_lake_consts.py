#
# SPDX-FileCopyrightText: 2021 Splunk, Inc. <sales@splunk.com>
# SPDX-License-Identifier: LicenseRef-Splunk-8-2021
#
#
from datetime import datetime, timedelta, timezone

USER = "nobody"
INPUT_MODE = "input_mode"
EVENT_DATA_STORE = "event_data_store"
EVENT_DATA_STORE_ID = "event_data_store_id"
START_DATE_TIME = "start_date_time"
END_DATE_TIME = "end_date_time"
QUERY_WINDOW_SIZE = "query_window_size"
DELAY_THROTTLE = "delay_throttle"
NEXT_TOKEN = "next_token"
QUERY_ID = "query_id"
QUERY_STATEMENT = "SELECT eventJson FROM {} WHERE eventTime>='{}' AND eventTime<'{}'"
MAX_RESULTS = 1000
MAX_QUERY_RESULTS = 1000
MAX_RETRIES = 3
INITIAL_DELAY = 1
MAX_QUEUED_TIMEOUT = 3600
MAX_DELAY = 64
DEFAULT_INPUT_MODE = "continuously_monitor"
DEFAULT_START_DATE_TIME = datetime.now(timezone.utc) - timedelta(days=7)
DEFAULT_QUERY_WINDOW_SIZE = 15
DEFAULT_DELAY_THROTTLE = 0
MIN_TTL = timedelta(minutes=15)

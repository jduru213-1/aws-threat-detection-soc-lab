#
# SPDX-FileCopyrightText: 2021 Splunk, Inc. <sales@splunk.com>
# SPDX-License-Identifier: LicenseRef-Splunk-8-2021
#
#
"""
File for S3 key processor for Generic S3.
"""


import io
import json
import re

import splunk_ta_aws.common.ta_aws_consts as tac
import splunksdc.log as logging
import splunksdc.utils as utils

from . import aws_s3_checkpointer as s3ckpt
from . import aws_s3_common as s3common
from . import aws_s3_consts as asc
from . import s3_key_reader as skr


def increase_error_count(
    key_store, max_retries, key, logger, bucket_name, count=1
):  # pylint: disable=too-many-arguments
    """Increases error count."""
    key_store.increase_error_count(count=count)
    if key_store.error_count() >= max_retries:
        logger.error(
            "Data collection has failed more than %s times.",
            max_retries,
            key_name=key.name,
            bucket_name=bucket_name,
        )
        key_store.delete()


class S3KeyProcesser:
    """Class for S3 key processor"""

    def __init__(
        self, s3_conn, loader_service, key_object, config, logger
    ):  # pylint: disable=too-many-arguments
        self._loader_service = loader_service
        self._config = config
        self.s3_conn = s3_conn
        self._key = key_object
        self._key_store = s3ckpt.S3KeyCheckpointer(config, self._key)
        self._logger = logger
        self._reader = None
        self._event_writer = config["classic_event_writer"]

    def __call__(self):
        with logging.LogContext(
            datainput=self._config[asc.data_input],
            bucket_name=self._config[asc.bucket_name],
            job_uid=self._config[asc.job_uid],
            start_time=self._config[asc.start_time],
            key_name=self._key.name,
            last_modified=self._key.last_modified,
            phase="fetch_key",
        ):
            try:
                self._safe_call()
            except Exception:  # pylint: disable=broad-except
                self._logger.exception("Failed to handle key.")
                increase_error_count(
                    self._key_store,
                    self._config[asc.max_retries],
                    self._key,
                    self._logger,
                    self._config[asc.bucket_name],
                )

    def _safe_call(self):
        config = {
            "s3_conn": self.s3_conn,
            asc.bucket_name: self._config[asc.bucket_name],
            asc.key_object: self._key,
            asc.key: self._key.name,
            asc.max_retries: self._config[asc.max_retries],
        }
        self._reader = skr.create_s3_key_reader(config, self._logger)

        self._logger.debug("Start processing.")

        try:
            self._do_call()
        except Exception:  # pylint: disable=broad-except
            increase_error_count(
                self._key_store,
                self._config[asc.max_retries],
                self._key,
                self._logger,
                self._config[asc.bucket_name],
            )
            self._logger.exception("Exception happened when fetching object.")
            self._reader.close(fast=True)
        self._logger.debug("End of processing.")

    def _do_call(self):
        logger = self._logger
        bucket_name, key_name = self._config[asc.bucket_name], self._key.name
        self._key_store.set_state(asc.processing)
        source = "s3://{bucket_name}/{key_name}".format(  # pylint: disable=consider-using-f-string
            bucket_name=bucket_name, key_name=key_name
        )

        if self._key_store.etag() != self._key.etag:
            logger.warning(
                "Last round of data collection was not completed,"
                " etag changed this round, start from beginning."
            )
            self._key_store.set_offset(0, commit=False)
            self._key_store.set_eof(eof=False)
        elif self._key_store.eof():
            self.set_eof()
            return

        offset = self._key_store.offset()
        if not self._key_store.eof() and offset:
            logger.info("Seeking offset for object.", offset=offset)
            self._reader.seek(offset)

        self._do_index(source)

    def _get_decoder(self):
        encoding = self._config.get(asc.character_set)
        if not encoding or encoding == "auto":
            encoding = self._key_store.encoding()

        previous_chunk = b""
        for previous_chunk in self._reader:
            break

        decoder, encoding = s3common.get_decoder(encoding, previous_chunk)
        self._key_store.set_encoding(encoding)
        return decoder, previous_chunk

    def _encode_to_utf8(self, decoder, chunk):
        if not chunk:
            return None
        try:
            data = decoder.decode(chunk)
            return data
        except Exception:  # pylint: disable=broad-except
            self._logger.exception(
                "Failed to decode data.", encoding=self._config[asc.character_set]
            )
            return None

    def _do_index_csv(  # pylint: disable=R0913
        self,
        data,
        truncated_line,
        header,
        source,
        current_file,
        row_count,
        rows_error_count,
        parse_csv_with_delimiter,
    ):
        """Processes CSV files in chunks of data or all file content at once, and indexes each row

        @param: data
        @paramType: io.BytesIO

        @param: truncated_line
        @paramType: string

        @param: header
        @paramType: list

        @param: source
        @paramType: string

        @param: current_file
        @paramType: string

        @param: row_count
        @paramType: int

        @param: rows_error_count
        @paramType: int

        @param: parse_csv_with_delimiter
        @paramType: string
        """
        for csv_line in data:
            # If csv_stream is a truncated line, it is assigned to truncated_line to use later,
            # csv_stream is set to None, and both are returned.
            # This must be done before decoding to be UTF-8 safe
            csv_line, truncated_line = utils.handle_truncated_line(
                csv_line, truncated_line
            )
            # checks if csv_stream is None because, if so, it would be a partial line, and the process moves to
            # the next line
            if csv_line is None:
                continue

            try:
                csv_stream = csv_line.decode("utf-8")
            except Exception as ex:  # pylint: disable=W0703
                row_count += 1
                rows_error_count += 1
                self._logger.error(
                    "Decoding to utf-8 failed. Reason: {}. Data at failure is on row {}. Line is {}.".format(  # pylint: disable=consider-using-f-string
                        ex, row_count, csv_line
                    )
                )
                continue

            # handles mapping fields to values, parses using the given delimiter parse_csv_with_delimiter
            event, header = utils.parseCSVLine(
                csv_stream, header, parse_csv_with_delimiter
            )
            if event:
                try:
                    index_event = self._event_writer.create_event(
                        source=self.append_file_name(source, current_file),
                        sourcetype=self._config[tac.sourcetype],
                        index=self._config[tac.index],
                        data=json.dumps(event),
                    )
                    self._event_writer.write_events([index_event])
                    row_count += 1
                except Exception as ex:  # pylint: disable=W0703
                    row_count += 1
                    rows_error_count += 1
                    self._logger.error(
                        "Indexing failed. Delimited event on row {} is NOT indexed. Reason: {}".format(  # pylint: disable=consider-using-f-string
                            row_count, ex
                        )
                    )
                    continue
        return truncated_line, header, row_count, rows_error_count

    def append_file_name(self, source, current_file):
        """Takes the source and current_file name, and if the source is a .zip, .tar, .tar.bz2, .tar.gz, or .tgz,
        it appends the current_file name to the source. This allows data from files within the package to be
        indexed individually.

        @param: source
        @paramType: string

        @param: current_file
        @paramType: string
        """
        if (  # pylint: disable=R0916
            source.endswith(".zip")
            or source.endswith(".tar")
            or source.endswith(".tar.bz2")
            or source.endswith(".tar.gz")
            or source.endswith(".tgz")
            or source.endswith(".gz")
        ):
            return source + "/" + current_file
        return source

    def log_file_info(self, log_info, current_file, parse_csv_with_header):
        """Takes log_info and current_file, checks if log_info is 0, and then logs the info message about
        what the current_file type is. if parse_csv_with_header is true then the file is being processed as
        a delimited file. Returns log_info so this message is only logged once per file.

        @param: log_info
        @paramType: int

        @param: current_file
        @paramType: string

        @param: parse_csv_with_header
        @paramType: boolean
        """
        if log_info == 0:
            if parse_csv_with_header:
                self._logger.info(
                    "Processing {} as a delimited file...".format(  # pylint: disable=consider-using-f-string
                        current_file
                    )
                )
                log_info += 1
            else:
                self._logger.info(
                    "{} detected as a custom file. processing...".format(  # pylint: disable=consider-using-f-string
                        current_file
                    )
                )
                log_info += 1
        return log_info

    def log_csv_parsing_summary(self, current_file, row_count, rows_error_count):
        """Takes current_file, row_count, rows_error_count. Logs the info message about the Delimited file
        parsing summary. The message will contain the file name, number of rows indexed, and number of errors.

        @param: current_file
        @paramType: string

        @param: row_count
        @paramType: int

        @param: rows_error_count
        @paramType: int
        """
        self._logger.info(
            "Delimited File Parser: {} ingested {} rows successfully. There are {} errors.".format(  # pylint: disable=consider-using-f-string
                current_file, row_count - rows_error_count, rows_error_count
            )
        )

    def check_for_file_change(  # pylint: disable=R0913
        self,
        next_file,
        current_file,
        header,
        row_count,
        rows_error_count,
        log_info,
        parse_csv_with_header,
    ):
        """In a tar with multiple files, checks if the file has changed. If so, current_file is set to next_file,
        and the header, row_count, rows_error_count, and log_info are reset for the next file. If
        parse_csv_with_header is true then the delimited file parsing message is logged.

        @param: next_file
        @paramType: string

        @param: current_file
        @paramType: string

        @param: header
        @paramType: list

        @param: row_count
        @paramType: int

        @param: rows_error_count
        @paramType: int

        @param: log_info
        @paramType: int

        @param: parse_csv_with_header
        @paramType: boolean
        """
        next_file = self._reader.file_path
        if current_file != next_file:
            self._logger.debug(
                "The file being processed has changed.",
                current_file=current_file,
                next_file=next_file,
            )
            if parse_csv_with_header:
                self.log_csv_parsing_summary(current_file, row_count, rows_error_count)
            current_file = next_file
            header = None
            row_count = 0
            rows_error_count = 0
            log_info = 0
            return (
                next_file,
                current_file,
                header,
                row_count,
                rows_error_count,
                log_info,
            )
        return next_file, current_file, header, row_count, rows_error_count, log_info

    def _do_index(self, source):  # pylint: disable=R0912,R0914,R0915
        """Processes data, either as chunks for large files or as whole data for small files,
         and indexes events. Checks first if a file is CSV or not.

        @param: source
        @paramType: string
        """
        decoder, previous_chunk = self._get_decoder()
        chunk = previous_chunk

        total = 0
        count = 0

        truncated_line = None
        header = None
        row_count = 0
        rows_error_count = 0
        log_info = 0
        parse_csv_with_delimiter = self._config.get(asc.parse_csv_with_delimiter, ",")
        parse_csv_with_header = self._config.get(asc.parse_csv_with_header, "0") == "1"

        current_file = self._reader.file_path
        next_file = self._reader.file_path
        self._logger.debug(
            "The file being processed currently is:", current_file=current_file
        )

        for chunk in self._reader:
            if self._loader_service.stopped():
                break

            size = len(previous_chunk)
            total += size
            count += 1

            if parse_csv_with_header:
                # If the file extension is not in the tuple of csv_file_suffixes, log a warning once per file
                # but continue processing the file as a delimited file
                if not current_file.endswith(tac.csv_file_suffixes) and log_info == 0:
                    self._logger.warning(
                        "The file extension {} is not in a delimited file format.".format(
                            current_file
                        )
                    )
                log_info = self.log_file_info(
                    log_info, current_file, parse_csv_with_header
                )
                data = io.BytesIO(previous_chunk)
                if data is not None:
                    # csv parsing
                    try:
                        (
                            truncated_line,
                            header,
                            row_count,
                            rows_error_count,
                        ) = self._do_index_csv(
                            data,
                            truncated_line,
                            header,
                            source,
                            current_file,
                            row_count,
                            rows_error_count,
                            parse_csv_with_delimiter,
                        )
                    except Exception as ex:  # pylint: disable=W0703
                        self._logger.error(
                            "Delimited file parsing failed. Reason: {}".format(  # pylint: disable=consider-using-f-string
                                row_count, ex
                            )
                        )
                        break
            else:
                log_info = self.log_file_info(
                    log_info, current_file, parse_csv_with_header
                )
                data = self._encode_to_utf8(decoder, previous_chunk)
                if data is not None:
                    data = self._event_writer.create_event(
                        source=self.append_file_name(source, current_file),
                        sourcetype=self._config[tac.sourcetype],
                        index=self._config[tac.index],
                        data=data,
                        unbroken=True,
                    )
                    self._event_writer.write_events([data])

            # check if the file has changed
            (
                next_file,
                current_file,
                header,
                row_count,
                rows_error_count,
                log_info,
            ) = self.check_for_file_change(
                next_file,
                current_file,
                header,
                row_count,
                rows_error_count,
                log_info,
                parse_csv_with_header,
            )

            previous_chunk = chunk
            if count % 100 == 0:
                self._key_store.increase_offset(total)
                self._logger.info("Indexed S3 files.", action="index", size=total)
                total = 0

        self._key_store.increase_offset(total)
        self._logger.info("Indexed S3 files.", action="index", size=total)

        if not self._loader_service.stopped():
            size = len(chunk)

            if parse_csv_with_header:
                # If the file extension is not in the tuple of csv_file_suffixes, log a warning once per file
                # but continue processing the file as a delimited file
                if not current_file.endswith(tac.csv_file_suffixes) and log_info == 0:
                    self._logger.warning(
                        "The file extension {} is not in a delimited file format.".format(
                            current_file
                        )
                    )
                log_info = self.log_file_info(
                    log_info, current_file, parse_csv_with_header
                )
                data = io.BytesIO(chunk)
                if data is not None:
                    try:
                        (
                            truncated_line,
                            header,
                            row_count,
                            rows_error_count,
                        ) = self._do_index_csv(
                            data,
                            truncated_line,
                            header,
                            source,
                            current_file,
                            row_count,
                            rows_error_count,
                            parse_csv_with_delimiter,
                        )
                    except Exception as ex:  # pylint: disable=W0703
                        self._logger.error(
                            "Delimited file parsing failed. Reason: {}".format(  # pylint: disable=consider-using-f-string
                                row_count, ex
                            )
                        )
            else:
                log_info = self.log_file_info(
                    log_info, current_file, parse_csv_with_header
                )
                data = self._encode_to_utf8(decoder, chunk)

                if data is not None:
                    if not data.endswith("\n"):
                        data += "\n"

                    data = self._event_writer.create_event(
                        source=self.append_file_name(source, current_file),
                        sourcetype=self._config[tac.sourcetype],
                        index=self._config[tac.index],
                        data=data,
                        unbroken=True,
                        done=True,
                    )
                    self._event_writer.write_events([data])

            # check if the file has changed
            (
                next_file,
                current_file,
                header,
                row_count,
                rows_error_count,
                log_info,
            ) = self.check_for_file_change(
                next_file,
                current_file,
                header,
                row_count,
                rows_error_count,
                log_info,
                parse_csv_with_header,
            )

            self._key_store.increase_offset(size)
            # if parse_csv_with_header is true, log the delimited file parsing/indexing summary
            if parse_csv_with_header:
                self.log_csv_parsing_summary(current_file, row_count, rows_error_count)
            self._logger.info("Indexed S3 files.", action="index", size=size)
            self.set_eof()
            header = None

    def set_eof(self):
        """Sets EOF."""
        self._key_store.set_eof(eof=True)
        self._key_store.delete()
        self._reader.close(fast=False)


class S3KeyCloudTrailProcesser(S3KeyProcesser):
    """Class for S3 key cloudtrail processor"""

    def __init__(
        self, s3_conn, loader_service, s3_key_object, config, logger
    ):  # pylint: disable=too-many-arguments, useless-super-delegation
        super(  # pylint: disable=super-with-arguments
            S3KeyCloudTrailProcesser, self
        ).__init__(s3_conn, loader_service, s3_key_object, config, logger)

    def _do_index(self, source):
        logger = self._logger
        all_data = list(self._reader)
        size = sum((len(data) for data in all_data), 0)
        if not all_data:
            self.set_eof()
            return

        try:
            all_data = json.loads(b"".join(all_data))
        except ValueError:
            logger.error("Invalid key of CloudTrail file.")
            self.set_eof()
            return

        records = all_data.get("Records", [])
        blacklist = self._config[asc.ct_blacklist]
        if blacklist:
            blacklist = re.compile(blacklist)
        else:
            blacklist = None

        loader_service = self._loader_service

        events = []
        for record in records:
            if loader_service.stopped():
                break

            if blacklist is not None and blacklist.search(record["eventName"]):
                continue

            data = self._event_writer.create_event(
                source=source,
                sourcetype=self._config[tac.sourcetype],
                index=self._config[tac.index],
                data=json.dumps(record),
            )
            events.append(data)

        if events:
            logger.info(
                "Indexed cloudtrail records.",
                action="index",
                num_reocords=len(records),
                size=size,
            )
            self._event_writer.write_events(events)

        if not loader_service.stopped():
            self._key_store.increase_offset(len(all_data))
            self.set_eof()


sourcetype_to_indexer = {
    asc.aws_s3: S3KeyProcesser,
    asc.aws_elb_accesslogs: S3KeyProcesser,
    asc.aws_cloudfront_accesslogs: S3KeyProcesser,
    asc.aws_s3_accesslogs: S3KeyProcesser,
    asc.aws_cloudtrail: S3KeyCloudTrailProcesser,
}


def create_s3_key_processer(s3_conn, config, loader_service, s3_key_object, logger):
    """Returns S3 key processor."""
    Cls = sourcetype_to_indexer.get(  # pylint: disable=invalid-name
        config[tac.sourcetype], S3KeyProcesser
    )
    return Cls(s3_conn, loader_service, s3_key_object, config, logger)

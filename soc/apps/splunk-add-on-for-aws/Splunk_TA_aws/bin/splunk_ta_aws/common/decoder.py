#
# SPDX-FileCopyrightText: 2021 Splunk, Inc. <sales@splunk.com>
# SPDX-License-Identifier: LicenseRef-Splunk-8-2021
#
#
"""
File for decoding inputs logs.
"""


import codecs
import json
from io import BytesIO


# External libraries to ASL inputs

from collections import namedtuple
from splunksdc import logging
from splunksdc.archive import ArchiveFactory
import aws_parquet

logger = logging.get_module_logger()


Metadata = namedtuple("Metadata", ["source", "sourcetype"])


class Decoder:
    """Class for Decoder."""

    def __init__(self, **kwargs):  # pylint: disable=unused-argument
        self._af = ArchiveFactory.create_default_instance()

    def __call__(self, fileobj, source):
        raise NotImplementedError()

    def _open(self, fileobj, filename):
        return self._af.open(fileobj, filename)

    @staticmethod
    def _product_multiple_lines(sequence):
        lines = list(sequence)
        lines.append("")
        return "\n".join(lines)


class CloudTrailLogsDecoder(Decoder):
    """Class for Cloudtrail logs decoder."""

    def __call__(self, fileobj, source):
        for member, uri in self._open(fileobj, source):
            document = json.load(member)
            if self._is_digest(document):
                logger.info("Ignore CloudTail digest file.", source=source)
                continue
            records = document["Records"]
            records = (json.dumps(item) for item in records)
            records = self._product_multiple_lines(records)
            yield records, Metadata(uri, "aws:cloudtrail")

    @staticmethod
    def _is_digest(document):
        return "Records" not in document


class ELBAccessLogsDecoder(Decoder):
    """Class for ELB access logs decoder."""

    def __call__(self, fileobj, source):
        for member, uri in self._open(fileobj, source):
            yield UTFStreamDecoder.create(member), Metadata(uri, "aws:elb:accesslogs")


class CloudFrontAccessLogsDecoder(Decoder):
    """Class for Cloudfront access logs decoder."""

    def __call__(self, fileobj, source):
        for member, uri in self._open(fileobj, source):
            yield UTFStreamDecoder.create(member), Metadata(
                uri, "aws:cloudfront:accesslogs"
            )


class S3AccessLogsDecoder(Decoder):
    """Class for S3 access logs decoder."""

    def __call__(self, fileobj, source):
        for member, uri in self._open(fileobj, source):
            yield UTFStreamDecoder.create(member), Metadata(uri, "aws:s3:accesslogs")


class ConfigDecoder(Decoder):
    """Class for config decoder."""

    def __call__(self, fileobj, source):
        for member, _ in self._open(fileobj, source):
            document = json.load(member)
            records = document["configurationItems"]
            records = (json.dumps(item) for item in records)
            records = self._product_multiple_lines(records)
            yield records, Metadata(source, "aws:config")


class VPCFlowLogsDecoder(Decoder):
    """Class for VPC flow logs decoder."""

    def __init__(self, **kwargs):
        super(VPCFlowLogsDecoder, self).__init__()
        self._sourcetype = kwargs.get("sourcetype", "aws:cloudwatchlogs:vpcflow")

    def __call__(self, fileobj, source):
        for member, uri in self._open(fileobj, source):
            document = member.read()
            records = document.decode("utf-8")
            records = records.split("\n", 1)[1]
            yield records, Metadata(uri, self._sourcetype)


class DelimitedFilesDecoder(Decoder):
    """Class for Delimited file decoder."""

    def __init__(self, **kwargs):
        super(  # pylint: disable=super-with-arguments
            DelimitedFilesDecoder, self
        ).__init__()
        self._sourcetype = kwargs.get("sourcetype", "aws:s3:csv")

    def __call__(self, fileobj, source):
        for member, uri in self._open(fileobj, source):
            yield UTFStreamDecoder.create(member), Metadata(uri, self._sourcetype)


class CustomLogsDecoder(Decoder):
    """Class for Custom logs decoder."""

    def __init__(self, **kwargs):
        super(  # pylint: disable=super-with-arguments
            CustomLogsDecoder, self
        ).__init__()
        self._sourcetype = kwargs.get("sourcetype", "")

    def __call__(self, fileobj, source):
        for member, uri in self._open(fileobj, source):
            yield UTFStreamDecoder.create(member), Metadata(uri, self._sourcetype)


class TransitGatewayDecoder(Decoder):
    def __init__(self, **kwargs):
        super(TransitGatewayDecoder, self).__init__()
        self._sourcetype = kwargs.get("sourcetype", "aws:transitgateway:flowlogs")
        self._plaintext_decoder = VPCFlowLogsDecoder(sourcetype=self._sourcetype)

    def __call__(self, fileobj, source):
        return self._plaintext_decoder(fileobj, source)


class ASLDecoder(Decoder):
    """Class for ASL Parquet File decoder."""

    def __init__(self, **kwargs):
        super(ASLDecoder, self).__init__()  # pylint: disable=super-with-arguments
        self._sourcetype = kwargs.get("sourcetype", "aws:asl")

    def __call__(self, fileobj, source):

        filename = fileobj.name
        # file must be close so that windows can read from the file directly
        fileobj.close()

        payload = []

        for line in aws_parquet.stream_parquet(filename):
            payload.append(line.strip())

            if len(payload) > 5000:
                yield self._product_multiple_lines(payload), Metadata(
                    source, self._sourcetype
                )
                payload = []

        yield self._product_multiple_lines(payload), Metadata(source, self._sourcetype)


class UTFStreamDecoder:
    """Class for UTF Stream decoder."""

    # keep longer signature ahead
    _BOM_SIGNATURE = [
        (codecs.BOM_UTF32_LE, "utf-32-le"),
        (codecs.BOM_UTF32_BE, "utf-32-be"),
        (codecs.BOM_UTF8, "utf-8-sig"),
        (codecs.BOM_UTF16_LE, "utf-16-le"),
        (codecs.BOM_UTF16_BE, "utf-16-be"),
    ]

    @classmethod
    def _create_decoder(cls, head):
        encoding = "utf-8"
        for signature, name in cls._BOM_SIGNATURE:
            if head.startswith(signature):
                encoding = name
                break
        factory = codecs.getincrementaldecoder(encoding)
        decoder = factory(errors="replace")
        return decoder

    @classmethod
    def create(cls, fileobj):
        """Creates file object."""
        if isinstance(fileobj, bytes):
            fileobj = BytesIO(fileobj)
        head = fileobj.read(4096)
        decoder = cls._create_decoder(head)
        obj = cls(decoder, fileobj)
        obj._decode(head)
        return obj

    def __init__(self, decoder, fileobj):
        self._fileobj = fileobj
        self._decoder = decoder
        self._pending = ""
        self._exhausted = False
        self._chunk_size = 4 * 1024 * 1024

    def _next_chunk(self):
        return self._fileobj.read(self._chunk_size)

    def _decode(self, data=b""):
        final = False if data else True  # pylint: disable=simplifiable-if-expression
        self._pending += self._decoder.decode(data, final=final)

    def read(self, size):
        """Reads chunk."""
        while len(self._pending) < size and not self._exhausted:
            chunk = self._next_chunk()
            if not chunk:
                self._decode()
                self._exhausted = True
                break
            self._decode(chunk)

        chunk = self._pending[:size]
        self._pending = self._pending[size:]
        return chunk


class DecoderFactory:
    """Class for decoder factory."""

    @classmethod
    def create_default_instance(cls):
        """Creates default instance."""
        factory = cls()
        factory.register("CustomLogs", CustomLogsDecoder)
        factory.register("DelimitedFilesDecoder", DelimitedFilesDecoder)
        factory.register("CloudTrail", CloudTrailLogsDecoder)
        factory.register("ELBAccessLogs", ELBAccessLogsDecoder)
        factory.register("CloudFrontAccessLogs", CloudFrontAccessLogsDecoder)
        factory.register("S3AccessLogs", S3AccessLogsDecoder)
        factory.register("Config", ConfigDecoder)
        factory.register("VPCFlowLogs", VPCFlowLogsDecoder)
        factory.register("AmazonSecurityLake", ASLDecoder)
        factory.register("TransitGatewayFlowLogs", TransitGatewayDecoder)

        return factory

    def __init__(self):
        self._registry = {}

    def create(self, name, **kwargs):
        """Creates teh decoder type"""
        name = name.lower()
        decoder_type = self._registry.get(name)
        return decoder_type(**kwargs)

    def register(self, name, decode_type):
        """Registers the decode type."""
        name = name.lower()
        self._registry[name] = decode_type

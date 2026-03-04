#
# SPDX-FileCopyrightText: 2021 Splunk, Inc. <sales@splunk.com>
# SPDX-License-Identifier: LicenseRef-Splunk-8-2021
#
#
"""
Filer for AWS S3 key reader.
"""


import gzip
import math
import tarfile
import zipfile
from io import BytesIO

from . import aws_s3_common as s3common
from . import aws_s3_consts as asc

# Note always use `for data in reader` to consume data


def read_all(reader):
    """Returns data chunks."""
    chunks = []
    for chunk in reader:
        chunks.append(chunk)
    return b"".join(chunks)


class S3KeyReader:  # pylint: disable=too-many-instance-attributes
    """Class for S3 key reader."""

    bufsize = 8192

    def __init__(self, config, logger):
        """
        :config: dict
        {
           key_object: xxx (Boto S3 Key object):
           key: yyy (string key name),
           key_id: xxx (string, AWS credentials),
           secret_key: yyy (string, AWS credentials),
           bucket_name: xxx,
           offset: xxx,
        }
        """

        self._config = config
        self._logger = logger
        self._read_pos = 0
        self._whence = 0
        self.s3_conn = self._config["s3_conn"]
        self._total_size = self._config[asc.key_object].size
        self._reached_eof = False
        self._iter = None
        self.file_path = config.get("key")

    def seekable(self):
        """Returns seekable value."""
        return True

    def seek(self, offset, whence=0):
        """
        Mimic the file.seek in Python
        """

        assert self._config[asc.key_object] is not None

        if whence == 1 and offset == 0:
            return

        pos = self._read_pos
        if whence == 0:
            pos = offset
        elif whence == 2:
            assert pos >= 0
            if offset == 0:
                pos = self._total_size
            elif offset < 0:
                pos = self._total_size + offset
        else:
            assert whence == 1
            pos = pos + offset
            assert pos >= 0

        if pos == self._total_size:
            byte_range = "bytes={}".format(  # pylint: disable=consider-using-f-string
                pos
            )
        else:
            byte_range = "bytes={}-".format(  # pylint: disable=consider-using-f-string
                pos
            )

        self._config[asc.key_object].body.close()

        # As seeking is not allowed in Boto3, needs to restream for given byte range
        # https://github.com/boto/boto3/issues/564
        self._get_key_object(byte_range=byte_range)

        self._whence = whence
        self._read_pos = pos

    def tell(self):
        """
        providing this function for zip reader
        """

        return self._read_pos

    def reached_eof(self):
        """Returns reached EOF."""
        return self._reached_eof

    def __iter__(self):
        if self._iter is None:
            self._iter = next(self)
        return self._iter

    def read(self, size=0):
        """
        :size: read size bytes from s3 key if size > 0,
        otherwise read all bytes from key. Providing this function for
        zip/tar reader.
        """

        assert self._config[asc.key_object] is not None

        if size == 0:
            size = self.bufsize

        if self._reached_eof:
            return b""

        data = self._config[asc.key_object].body.read(size)
        if data:
            self._read_pos += len(data)
        else:
            self._reached_eof = True

        return data

    def __next__(self):
        assert self._config[asc.key_object] is not None

        key = self._config[asc.key_object]
        bufsize = self.bufsize
        while 1:
            data = key.body.read(bufsize)
            if not data:
                self._reached_eof = True
                break
            self._read_pos += len(data)
            yield data

    next = __next__

    def key_object(self):
        """Returns key object"""
        return self._config[asc.key_object]

    def _get_key_object(self, byte_range=None):
        key_obj = s3common.get_key(
            self.s3_conn,
            self._config[asc.bucket_name],
            self._config[asc.key],
            byte_range,
        )
        self._config[asc.key_object] = key_obj
        if self._config[asc.key_object] is None:
            msg = "Failed to get S3 object."
            self._logger.error(msg, key=self._config[asc.key])
            raise Exception(msg)

    def read_all(self):
        """Returns all content."""
        return read_all(self)

    def close(self, fast=False):  # pylint: disable=unused-argument
        """Closes body."""
        self._config[asc.key_object].body.close()

    def size(self):
        """Returns size."""
        return self._total_size


class S3KeyPackageReader:
    """Class for S3 key Package reader."""

    def __init__(self, config, logger):
        s3reader = S3KeyReader(config, logger)
        self._key_object = s3reader.key_object()
        self._raw_size = s3reader.size()
        if self._raw_size <= 8192:
            logger.debug("Use perf enhanced s3 reader")
            data = s3reader.read_all()
            s3reader.close()
            s3reader = BytesIO(data)

        self._s3reader = s3reader
        self._read_pos = 0
        self._seek_left = ""
        self._iter = None

    def __iter__(self):
        if self._iter is None:
            self._iter = next(self)
        return self._iter

    def size(self):
        """Returns raw size."""
        return self._raw_size

    def seek(self, offset, whence=0):  # pylint: disable=unused-argument
        """
        only support seek from beginning
        """

        self._seek_left = self._discard(offset)
        self._read_pos = offset

    def tell(self):
        """Returns read pos."""
        return self._read_pos

    def _discard(self, size):
        for data in self:
            if size < len(data):
                return data[size:]

            size -= len(data)
            if size <= 0:
                break

        return ""

    def key_object(self):
        """Returns key object."""
        return self._key_object

    def read_all(self):
        """Returns all content."""
        return read_all(self)

    def close(self, fast=False):
        """Closes S3 key reader."""
        if isinstance(self._s3reader, S3KeyReader):
            return self._s3reader.close(fast=fast)
        else:
            return self._s3reader.close()

    def __next__(self):
        raise NotImplementedError("Derived class should implement")

    next = __next__


class S3KeyTarReader(S3KeyPackageReader):
    """Class for S3 key Tar reader."""

    def __init__(self, config, logger):
        super(S3KeyTarReader, self).__init__(  # pylint: disable=super-with-arguments
            config, logger
        )
        self._package_reader = tarfile.open(  # pylint: disable=consider-using-with
            None, "r|*", self._s3reader
        )

    def __next__(self):
        tar_reader = self._package_reader
        for member in tar_reader:
            if not member:
                continue

            if not member.isfile():
                continue

            counts = 0

            extracted = tar_reader.extractfile(member)
            self.file_path = member.name  # pylint: disable=W0201

            # using the size of the member file within tar, divide by the chunk size (S3KeyReader.bufsize)
            # to find how many chunks the file data will need to be processed in. Any remaining bytes will be
            # used to create a custom chunk, to seperate data between files in a multi-file tar
            counts = math.floor(member.size / S3KeyReader.bufsize)
            remainder = member.size % S3KeyReader.bufsize

            while 1:
                if self._seek_left:
                    data, self._seek_left = self._seek_left, ""
                    self._read_pos += len(self._seek_left)
                    yield data

                counts -= 1
                if counts == 0:
                    data = extracted.read(remainder)
                else:
                    data = extracted.read(S3KeyReader.bufsize)

                if data:
                    self._read_pos += len(data)
                    yield data
                else:
                    break

    next = __next__


class S3KeyGzipReader(S3KeyPackageReader):
    """Class for S3 key gzip reader."""

    def __init__(self, config, logger):
        super(S3KeyGzipReader, self).__init__(  # pylint: disable=super-with-arguments
            config, logger
        )
        self._package_reader = gzip.GzipFile(fileobj=self._s3reader)
        self.file_path = config.get("key").replace(".gz", "")

    def __next__(self):
        gzip_reader = self._package_reader
        while 1:
            if self._seek_left:
                data, self._seek_left = self._seek_left, ""
                self._read_pos += len(self._seek_left)
                yield data

            data = gzip_reader.read(S3KeyReader.bufsize)
            if not data:
                break

            self._read_pos += len(data)
            yield data

    next = __next__


class S3KeyZipReader(S3KeyPackageReader):
    """Class for S3 key zip reader."""

    def __init__(self, config, logger):
        super(S3KeyZipReader, self).__init__(config, logger)
        zipfile.ZipExtFile.MIN_READ_SIZE = 8192
        self._package_reader = zipfile.ZipFile(self._s3reader)

    def __next__(self):
        zip_reader = self._package_reader
        for member in zip_reader.infolist():
            # Skipping empty files and folder paths, as zip_reader treats folders as members too.
            if not member or member.file_size == 0 or member.filename.endswith("/"):
                continue

            self.file_path = member.filename
            with zip_reader.open(self.file_path) as zip_file:
                while 1:
                    if self._seek_left:
                        self._read_pos += len(self._seek_left)
                        yield self._seek_left
                        self._seek_left = ""

                    data = zip_file.read(S3KeyReader.bufsize)
                    if not data:
                        break

                    self._read_pos += len(data)
                    yield data

    next = __next__


def create_s3_key_reader(config, logger):
    """
    :config: dict
    {
       key_object: xxx (Boto S3 Key object):
       key: yyy (string key name),
       key_id: xxx (string, AWS credentials),
       secret_key: yyy (string, AWS credentials),
       bucket_name: xxx,
    }
    Create a correct S3 key reader accoring to the postfix of the key name
    """

    if config.get(asc.key_object) is not None:
        key_name = config[asc.key_object].name
    else:
        assert config[asc.key]
        key_name = config[asc.key]

    if isinstance(key_name, bytes):
        key_name = key_name.decode("utf-8")

    if (
        key_name.endswith(".tar")
        or key_name.endswith(".tar.bz2")
        or key_name.endswith(".tar.gz")
        or key_name.endswith(".tgz")
    ):
        return S3KeyTarReader(config, logger)
    elif key_name.endswith(".zip"):
        return S3KeyZipReader(config, logger)
    elif key_name.endswith(".gz"):
        return S3KeyGzipReader(config, logger)
    return S3KeyReader(config, logger)

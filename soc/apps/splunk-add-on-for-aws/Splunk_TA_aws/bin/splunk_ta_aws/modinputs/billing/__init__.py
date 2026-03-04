#
# SPDX-FileCopyrightText: 2021 Splunk, Inc. <sales@splunk.com>
# SPDX-License-Identifier: LicenseRef-Splunk-8-2021
#
#
"""
Init file for billing module.
"""


import os

from splunksdc import environ


# Notice that this function is copied and modified from incremental_s3
def delete_ckpt(name):
    """Deletes billing checkpoint."""
    root = environ.get_checkpoint_folder("aws_billing_cur")
    path = os.path.join(root, name)

    # try remove files for billing cur
    path += ".ckpt"
    if os.path.isfile(path):
        os.remove(path)

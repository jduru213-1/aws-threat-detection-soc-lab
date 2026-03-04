#
# SPDX-FileCopyrightText: 2021 Splunk, Inc. <sales@splunk.com>
# SPDX-License-Identifier: LicenseRef-Splunk-8-2021
#
#

import aws_bootstrap_env  # noqa: F401 # pylint: disable=unused-import

from splunktalib.rest_manager import base, multimodel, normaliser, validator


class AWSSettingHandler(multimodel.MultiModelRestHandler):
    """
    For previous 5 products: S3, CloudTrail, CloudWatch, Config, Billing.
    """

    stanzaName = ""

    def get(self, name):
        """Gets model."""
        if name == "logging":
            name = self.stanzaName
        return multimodel.MultiModelRestHandler.get(self, name)

    def create(self, name, **params):
        """Creates model."""
        if name == "logging":
            name = self.stanzaName
        return multimodel.MultiModelRestHandler.create(self, name, **params)

    def delete(self, name):
        """Deletes model."""
        if name == "logging":
            name = self.stanzaName
        return multimodel.MultiModelRestHandler.delete(self, name)

    def update(self, name, **params):
        """Updates model."""
        if name == "logging":
            name = self.stanzaName
        return multimodel.MultiModelRestHandler.update(self, name, **params)

    def setModel(self, objectID):
        """Sets the model."""
        if objectID == self.stanzaName:
            objectID = "logging"
        return multimodel.MultiModelRestHandler.setModel(self, objectID)


class AWSLogging(base.BaseModel):
    requiredArgs = {"level"}
    defaultVals = {"level": "INFO"}
    normalisers = {"level": normaliser.StringUpper()}
    validators = {"level": validator.Enum(("DEBUG", "INFO", "ERROR"))}

    outputExtraFields = ("eai:acl", "acl", "eai:appName", "eai:userName")


class AWSSettings(multimodel.MultiModel):
    endpoint = "configs/conf-log_info"
    modelMap = {"logging": AWSLogging}

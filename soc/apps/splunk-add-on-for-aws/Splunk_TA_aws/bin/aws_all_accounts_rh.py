#
# SPDX-FileCopyrightText: 2021 Splunk, Inc. <sales@splunk.com>
# SPDX-License-Identifier: LicenseRef-Splunk-8-2021
#
#
import aws_bootstrap_env  # noqa: F401 # pylint: disable=unused-import
import splunk.admin as admin

import splunk.clilib.cli_common as scc
from splunktalib.conf_manager.conf_manager import ConfManager
from splunk_ta_aws.common.aws_accesskeys import AwsAccessKeyManager

from splunktalib.rest_manager import util

from splunktaucclib.rest_handler.error import RestError

import splunk_ta_aws.common.ta_aws_consts as tac

import splunk_ta_aws.common.account_util as account_util

KEY_NAMESPACE = util.getBaseAppName()
KEY_OWNER = "-"

AWS_PROXY_PREFIX = "_aws_"

POSSIBLE_KEYS = ("secret_key", "key_id")
OPTIONAL_KEYS = ("category",)
CONF_FOR_ACCOUNT_EXT_FIELDS = "aws_account_ext"


class AccountRestHandler(admin.MConfigHandler):
    """
    Manage AWS Accounts in Splunk_TA_aws add-on.
    """

    def setup(self):
        """Setup method for all accounts."""
        if self.requestedAction in (admin.ACTION_CREATE, admin.ACTION_EDIT):
            for arg in POSSIBLE_KEYS:
                self.supportedArgs.addReqArg(arg)
            for arg in OPTIONAL_KEYS:
                self.supportedArgs.addOptArg(arg)
        return

    def _getConfManager(self):
        sessionKey = self.getSessionKey()
        server_uri = scc.getMgmtUri()
        return ConfManager(server_uri, sessionKey, "nobody", KEY_NAMESPACE)

    def _getAccountConfig(self, key, exts):
        result = {
            "name": key.name,
            "key_id": key.key_id,
            "secret_key": key.secret_key,
            "category": key.category,
            "iam": key.iam,
            "token": key.token,
            "account_id": key.account_id,
        }
        temp = exts.get(key.name)
        if temp:
            for key in temp:
                if key in OPTIONAL_KEYS:
                    result[key] = temp[key]
            result["category"] = int(result["category"])
            if result["category"] not in tac.RegionCategory.VALID:
                result["category"] = tac.RegionCategory.DEFAULT
        elif result["iam"]:
            # create account for EC2 role in aws_account_ext.conf
            cm = self._getConfManager()
            account_ext = {
                "category": result["category"],
                "iam": 1,
            }
            cm.create_stanza(CONF_FOR_ACCOUNT_EXT_FIELDS, key.name, account_ext)

            # append this account into summary index
            if result["account_id"] and result["name"]:
                account_util.append_account_to_summary(
                    name=result["name"],
                    account_id=result["account_id"],
                    category=result["category"],
                    session_key=self.getSessionKey(),
                )

        return result

    def handleList(self, confInfo):  # pylint: disable=invalid-name
        """Called when user invokes the "list" action."""
        try:
            if self.callerArgs.id is None:
                accs = self.all()
                for name, ent in accs.items():
                    self.makeConfItem(name, ent, confInfo)
            else:
                self.makeConfItem(
                    self.callerArgs.id, self.get(self.callerArgs.id), confInfo
                )
        except Exception as exc:
            raise RestError(400, exc)  # pylint: disable=raise-missing-from

    def all(self):
        """Returns all account information"""
        km = AwsAccessKeyManager(KEY_NAMESPACE, KEY_OWNER, self.getSessionKey())
        keys = km.all_accesskeys()
        all_accounts = {}
        all_accounts_exts = None
        for key in keys:
            if all_accounts_exts is None:
                cm = self._getConfManager()
                all_accounts_exts = cm.all_stanzas_as_dicts(CONF_FOR_ACCOUNT_EXT_FIELDS)
            if str(key.name).lower().startswith(AWS_PROXY_PREFIX):
                continue
            acc_conf = self._getAccountConfig(key, all_accounts_exts)
            if acc_conf:
                all_accounts[key.name] = acc_conf
        return all_accounts

    def get(self, name):
        """Gets account information."""
        name = name.strip()
        km = AwsAccessKeyManager(KEY_NAMESPACE, KEY_OWNER, self.getSessionKey())
        key = km.get_accesskey(name)
        if key is None:
            raise Exception(
                'No AWS account named "%s" exists.' % (name)
            )  # pylint: disable=consider-using-f-string
        cm = self._getConfManager()
        exts = cm.all_stanzas_as_dicts(CONF_FOR_ACCOUNT_EXT_FIELDS, do_reload=False)
        return self._getAccountConfig(key, exts)

    def makeConfItem(self, name, entity, confInfo):
        """Makes conf item for accounts."""
        confItem = confInfo[name]
        for key, val in entity.items():
            confItem[key] = val
        confInfo[name]["eai:appName"] = KEY_NAMESPACE
        confInfo[name]["eai:userName"] = "nobody"
        confItem.setMetadata(
            admin.EAI_ENTRY_ACL,
            {"app": KEY_NAMESPACE, "owner": "nobody"},
        )


if __name__ == "__main__":
    admin.init(AccountRestHandler, admin.CONTEXT_APP_AND_USER)

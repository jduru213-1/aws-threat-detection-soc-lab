#
# SPDX-FileCopyrightText: 2021 Splunk, Inc. <sales@splunk.com>
# SPDX-License-Identifier: LicenseRef-Splunk-8-2021
#
#


import logging
import re

import aws_bootstrap_env  # noqa: F401 # pylint: disable=unused-import
import splunk.admin as admin
import splunk.clilib.cli_common as scc
import splunk_ta_aws.common.account_util as account_util
import splunk_ta_aws.common.ta_aws_consts as tac
from aws_common_validator import PRIVATE_ENDPOINT_PATTERN
from botocore.exceptions import ClientError
from splunk_ta_aws.common.aws_accesskeys import AwsAccessKeyManager
from splunktalib.conf_manager.conf_manager import ConfManager
from splunktalib.rest_manager import error_ctl, util
from splunktaucclib.rest_handler.error import RestError

KEY_NAMESPACE = util.getBaseAppName()
KEY_OWNER = "-"

AWS_PROXY_PREFIX = "_aws_"

POSSIBLE_KEYS = ("secret_key", "key_id", "category", "sts_region")
OPTIONAL_KEYS = ("private_endpoint_enabled", "sts_private_endpoint_url")
CONF_FOR_ACCOUNT_EXT_FIELDS = "aws_account_ext"
STS_PRIVATE_ENDPOINT_PATTERN = PRIVATE_ENDPOINT_PATTERN.replace(
    "<service_name>", "sts"
).replace("<prefix>", "")


class AccountRestHandler(admin.MConfigHandler):
    """
    Manage AWS Accounts in Splunk_TA_aws add-on.
    """

    def setup(self):
        """Setup method for pricate account RH."""
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
            "sts_region": "us-east-1",
            "private_endpoint_enabled": "0",
            "sts_private_endpoint_url": "",
        }
        temp = exts.get(key.name)
        if temp:
            if "sts_region" not in temp.keys():
                result["skip_flag"] = 1  # Skip Normal Account
            for key in temp:
                if key in OPTIONAL_KEYS:
                    result[key] = temp[key]
                if key in ["category", "sts_region"]:
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

    def handleCreate(
        self, confInfo
    ):  # pylint: disable=invalid-name # pylint: disable=unused-argument
        """Called when user invokes the "create" action."""
        try:
            private_endpoint_enabled = int(
                self.callerArgs.data["private_endpoint_enabled"][0]
            )
            sts_private_endpoint_url = self.callerArgs.data.get(
                "sts_private_endpoint_url", [""]
            )[0]
            sts_private_endpoint_url = (
                ""
                if not sts_private_endpoint_url or not sts_private_endpoint_url.strip()
                else sts_private_endpoint_url
            )
            if private_endpoint_enabled:
                if not sts_private_endpoint_url:
                    raise Exception("Field Private Endpoint URL (STS) is required")
                else:
                    if not re.match(
                        STS_PRIVATE_ENDPOINT_PATTERN, sts_private_endpoint_url
                    ):
                        raise Exception("Provided private endpoint URL is invalid")

            self.callerArgs.id = self.callerArgs.id.strip()
            if self.callerArgs.id.lower() in ("default",):
                raise RestError(
                    400,
                    'Name "%s" for AWS account is not allowed.'
                    % self.callerArgs.id,  # pylint: disable=consider-using-f-string
                )
            accs = self.all()
            keys = {key.lower() for key in accs}
            if self.callerArgs.id.lower() in keys:
                raise Exception(
                    'An AWS account named "%s" already exists. Note: it is not case-sensitive.'  # pylint: disable=consider-using-f-string
                    % self.callerArgs.id
                )

            args = self.validate(self.callerArgs.data)
            km = AwsAccessKeyManager(KEY_NAMESPACE, KEY_OWNER, self.getSessionKey())
            km.set_accesskey(
                key_id=args["key_id"][0],
                secret_key=args["secret_key"][0],
                name=self.callerArgs.id,
            )

            cm = self._getConfManager()
            cate = args["category"][0]
            reg = args["sts_region"][0]
            use_cust_ep = args["private_endpoint_enabled"][0]
            cust_ep = sts_private_endpoint_url
            cm.create_stanza(
                CONF_FOR_ACCOUNT_EXT_FIELDS,
                self.callerArgs.id,
                {
                    "category": cate,
                    "sts_region": reg,
                    "private_endpoint_enabled": use_cust_ep,
                    "sts_private_endpoint_url": cust_ep,
                },
            )

            new_account = self.get(self.callerArgs.id)
            new_account["region_name"] = new_account["sts_region"]
            if private_endpoint_enabled:
                new_account["endpoint_url"] = cust_ep
            account_id = account_util.get_account_id(new_account, self.getSessionKey())

            account_util.append_account_to_summary(
                name=new_account["name"],
                account_id=account_id,
                category=new_account["category"],
                session_key=self.getSessionKey(),
            )

        except Exception as exc:
            raise RestError(400, exc)  # pylint: disable=raise-missing-from

    def handleRemove(
        self, confInfo
    ):  # pylint: disable=invalid-name # pylint: disable=unused-argument
        """Called when user invokes the "remove" action."""
        try:
            km = AwsAccessKeyManager(KEY_NAMESPACE, KEY_OWNER, self.getSessionKey())
            km.delete_accesskey(self.callerArgs.id)

            cm = self._getConfManager()
            if cm.stanza_exist(CONF_FOR_ACCOUNT_EXT_FIELDS, self.callerArgs.id):
                cm.delete_stanza(CONF_FOR_ACCOUNT_EXT_FIELDS, self.callerArgs.id)
        except Exception as exc:
            raise RestError(400, exc)  # pylint: disable=raise-missing-from

    def handleEdit(
        self, confInfo
    ):  # pylint: disable=invalid-name # pylint: disable=unused-argument
        """Called when user invokes the "edit" action."""
        try:
            private_endpoint_enabled = int(
                self.callerArgs.data["private_endpoint_enabled"][0]
            )
            sts_private_endpoint_url = self.callerArgs.data.get(
                "sts_private_endpoint_url", [""]
            )[0]
            sts_private_endpoint_url = (
                ""
                if not sts_private_endpoint_url or not sts_private_endpoint_url.strip()
                else sts_private_endpoint_url
            )
            if private_endpoint_enabled:
                if not sts_private_endpoint_url:
                    raise Exception("Field Private Endpoint URL (STS) is required")
                else:
                    if not re.match(
                        STS_PRIVATE_ENDPOINT_PATTERN, sts_private_endpoint_url
                    ):
                        raise Exception("Provided private endpoint URL is invalid")

            args = self.validate(self.callerArgs.data)
            account_name = self.callerArgs.id.strip()
            key_id = args["key_id"][0]
            secret_key = args["secret_key"][0]
            category = args["category"][0]
            region = args["sts_region"][0]
            session_key = self.getSessionKey()

            # check whether the updated one belongs to another account ID
            old_account_id = None

            try:
                old_account = self.get(account_name)
                old_account["region_name"] = region
                if private_endpoint_enabled:
                    old_account["endpoint_url"] = sts_private_endpoint_url
                old_account_id = account_util.get_account_id(old_account, session_key)
            except ClientError:
                pass
            endpoint_url = (
                sts_private_endpoint_url if private_endpoint_enabled else None
            )
            new_account_id = account_util.get_account_id(
                {
                    "key_id": key_id,
                    "secret_key": secret_key,
                    "category": category,
                    "region_name": region,
                    "endpoint_url": endpoint_url,
                },
                session_key,
            )

            if old_account_id is not None and old_account_id != new_account_id:
                raise Exception(
                    "Failed in updating AWS account. You can not update the account with a different root account ID."
                )

            km = AwsAccessKeyManager(KEY_NAMESPACE, KEY_OWNER, session_key)
            km.set_accesskey(key_id=key_id, secret_key=secret_key, name=account_name)

            cm = self._getConfManager()

            if cm.stanza_exist(CONF_FOR_ACCOUNT_EXT_FIELDS, account_name):
                cm.update_stanza(
                    CONF_FOR_ACCOUNT_EXT_FIELDS,
                    account_name,
                    {
                        "category": category,
                        "sts_region": region,
                        "private_endpoint_enabled": private_endpoint_enabled,
                        "sts_private_endpoint_url": sts_private_endpoint_url,
                    },
                )
            else:
                cm.create_stanza(
                    CONF_FOR_ACCOUNT_EXT_FIELDS,
                    account_name,
                    {
                        "category": category,
                        "sts_region": region,
                        "private_endpoint_enabled": private_endpoint_enabled,
                        "sts_private_endpoint_url": sts_private_endpoint_url,
                    },
                )

            # The old account is invalid. It means the secret key and key ID is invalid for the old one.
            # The new account needs to be appended into the summary index.
            if old_account_id is None:
                account_util.append_account_to_summary(
                    name=account_name,
                    account_id=new_account_id,
                    category=category,
                    session_key=self.getSessionKey(),
                )

        except Exception as exc:
            raise RestError(400, exc)  # pylint: disable=raise-missing-from

    def handleList(self, confInfo):  # pylint: disable=invalid-name
        """Called when user invokes the "list" action."""
        try:
            if self.callerArgs.id is None:
                accs = self.all()
                for name, ent in accs.items():
                    if "skip_flag" not in ent:
                        self.makeConfItem(name, ent, confInfo)
            else:
                self.makeConfItem(
                    self.callerArgs.id, self.get(self.callerArgs.id), confInfo
                )
        except Exception as exc:
            raise RestError(400, exc)  # pylint: disable=raise-missing-from

    def validate(self, args):
        """Validates account information."""
        try:
            args["key_id"][0] = args["key_id"][0].strip()
            if len(args["key_id"][0]) <= 0:
                raise Exception("")
        except Exception:
            error_ctl.RestHandlerError.ctl(1100, msgx="key_id", logLevel=logging.INFO)

        try:
            args["secret_key"][0] = args["secret_key"][0].strip()
            if len(args["secret_key"][0]) <= 0:
                raise Exception("")
        except Exception:
            error_ctl.RestHandlerError.ctl(
                1100, msgx="secret_key", logLevel=logging.INFO
            )

        try:
            cate = args["category"][0] = int(args["category"][0])
            if cate not in tac.RegionCategory.VALID:
                raise Exception("")
        except Exception:
            error_ctl.RestHandlerError.ctl(1100, msgx="category", logLevel=logging.INFO)

        sts_endpoint_url = None
        if int(args["private_endpoint_enabled"][0]):
            sts_endpoint_url = args["sts_private_endpoint_url"][0]

        # validate keys, category
        if not account_util.validate_keys(
            self.getSessionKey(),
            key_id=args["key_id"][0],
            secret_key=args["secret_key"][0],
            category=args["category"][0],
            region_name=args["sts_region"][0],
            endpoint_url=sts_endpoint_url,
        ):
            raise Exception(
                "The account key ID, secret key or category is invalid. Please check."
            )

        return args

    def all(self):
        """Gets all accounts."""
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
            all_accounts[key.name] = self._getAccountConfig(key, all_accounts_exts)
        return all_accounts

    def get(self, name):
        """Gets account config."""
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
        """Makes conf item for account."""
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

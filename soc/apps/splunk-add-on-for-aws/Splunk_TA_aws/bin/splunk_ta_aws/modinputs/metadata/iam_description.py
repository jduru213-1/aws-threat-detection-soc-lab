#
# SPDX-FileCopyrightText: 2021 Splunk, Inc. <sales@splunk.com>
# SPDX-License-Identifier: LicenseRef-Splunk-8-2021
#
#
"""
File for IAM description for metadata input.
"""


import datetime

import boto3
import splunk_ta_aws.common.ta_aws_consts as tac
import splunksdc.log as logging
from botocore.exceptions import ClientError

from . import description as desc
from . import aws_description_helper_functions as helper

logger = logging.get_module_logger()

CREDENTIAL_THRESHOLD = datetime.timedelta(minutes=20)

skipped_error_code_list = ["NoSuchEntity", "InvalidAction"]
PAGE_SIZE_FOR_IAM_DESCRIPTION = 1000


@desc.generate_credentials
@desc.decorate
def iam_users(config):
    iam_client = helper.get_conn(config, "iam")

    # Get authorization details of User
    paginator = iam_client.get_paginator("get_account_authorization_details")
    users_iterator = paginator.paginate(
        Filter=["User"],
        PaginationConfig={
            "PageSize": PAGE_SIZE_FOR_IAM_DESCRIPTION,
        },
    )

    # get account password policy (the same among users)
    password_policy = None

    # http://docs.aws.amazon.com/cli/latest/reference/iam/get-account-password-policy.html
    # account may not have enable password policy, and throws out a "NoSuchEntity" Error
    try:
        password_policy = iam_client.get_account_password_policy()
    except ClientError as client_error:
        if (
            "Code" not in client_error.response["Error"]
            or client_error.response["Error"]["Code"] not in skipped_error_code_list
        ):
            logger.error(
                '"get_account_password_policy" operation returns invalid '  # pylint: disable=consider-using-f-string
                "result for account %s: %s" % (config[tac.account_id], client_error)
            )

    # Get the User's detail
    for page in users_iterator:
        iam_users = page.get("UserDetailList", [])

        if iam_users is None and len(iam_users) <= 0:
            continue

        for iam_user in iam_users:
            # add account password policy
            if password_policy is not None:
                iam_user.update(password_policy)

            try:
                # Get last password used
                user_detail = iam_client.get_user(UserName=iam_user["UserName"])
                password_last_used = user_detail.get("User").get(
                    "PasswordLastUsed", None
                )
                if password_last_used:
                    iam_user["PasswordLastUsed"] = password_last_used
            except iam_client.exceptions.NoSuchEntityException:
                # The user does not have a password or login profile
                logger.error(
                    "The user {0} does not have a password or not signed in with password".format(
                        iam_user["UserName"]
                    )
                )
            except Exception as ex:
                logger.error(
                    "Error while fetching the password last used by user: {0}".format(
                        iam_user["UserName"]
                    )
                )

            # get access keys
            ak_paginator = iam_client.get_paginator("list_access_keys")
            access_key_list = []

            for ak_page in ak_paginator.paginate(
                UserName=iam_user["UserName"],
                PaginationConfig={"PageSize": PAGE_SIZE_FOR_IAM_DESCRIPTION},
            ):
                access_keys = ak_page["AccessKeyMetadata"]
                if access_keys is not None and len(access_keys) > 0:
                    for access_key in access_keys:
                        # get ak last used
                        # will throw out an error with code "InvalidAction" if does not support (CN region)
                        try:
                            ak_last_used = iam_client.get_access_key_last_used(
                                AccessKeyId=access_key["AccessKeyId"]
                            )
                            access_key.update(ak_last_used)
                        except ClientError as client_error:
                            if (
                                "Code" not in client_error.response["Error"]
                                or client_error.response["Error"]["Code"]
                                not in skipped_error_code_list
                            ):
                                logger.error(
                                    '"get_access_key_last_used" operation returns invalid '  # pylint: disable=consider-using-f-string
                                    "result for access key %s: %s"
                                    % (access_key["AccessKeyId"], client_error)
                                )

                        # remove metadata of response
                        access_key.pop("ResponseMetadata", None)

                        access_key_list.append(access_key)

            iam_user["AccessKeys"] = access_key_list

            user_policy_list = []

            # Get the User's Policy List
            list_user_policies = iam_user.get("UserPolicyList", [])
            for policy in list_user_policies:
                user_policy_list.append(policy.get("PolicyName", None))

            # Get the list of attached policies of the User
            list_attached_user_policies = iam_user.get("AttachedManagedPolicies", [])
            for policy in list_attached_user_policies:
                user_policy_list.append(policy)

            iam_user["UserPolicies"] = user_policy_list

            keys_to_remove = ["AttachedManagedPolicies", "GroupList", "UserPolicyList"]
            for key in keys_to_remove:
                iam_user.pop(key, None)

            yield iam_user
        desc.refresh_credentials(config, CREDENTIAL_THRESHOLD, iam_client)


@desc.generate_credentials
@desc.decorate
def iam_list_policy(config):
    """Fetches policy details"""
    iam_client = helper.get_conn(config, "iam")
    paginator = iam_client.get_paginator("list_policies")

    for page in paginator.paginate(
        PaginationConfig={"PageSize": PAGE_SIZE_FOR_IAM_DESCRIPTION}
    ):
        iam_policies = page["Policies"]

        if iam_policies is not None and len(iam_policies) > 0:
            for iam_policy in iam_policies:
                policy_version = iam_client.get_policy_version(
                    PolicyArn=iam_policy["Arn"],
                    VersionId=iam_policy["DefaultVersionId"],
                )
                policy_version.pop("ResponseMetadata", None)
                iam_policy["Policy"] = policy_version
                yield iam_policy
        desc.refresh_credentials(config, CREDENTIAL_THRESHOLD, iam_client)


@desc.generate_credentials
@desc.decorate
def iam_list_policy_local_and_only_attached(config):
    """Fetches policy details"""
    iam_client = helper.get_conn(config, "iam")
    paginator = iam_client.get_paginator("get_account_authorization_details")

    for page in paginator.paginate(
        Filter=["LocalManagedPolicy", "AWSManagedPolicy"],
        PaginationConfig={"PageSize": PAGE_SIZE_FOR_IAM_DESCRIPTION},
    ):
        iam_policies = page["Policies"]
        if iam_policies is not None and len(iam_policies) > 0:
            for iam_policy in iam_policies:
                iam_policy["Policy"] = {}
                policy_versions = iam_policy.pop("PolicyVersionList", None)
                if policy_versions is not None and len(policy_versions) > 0:
                    for pv in policy_versions:
                        if (
                            pv["VersionId"] == iam_policy["DefaultVersionId"]
                            and pv["IsDefaultVersion"]
                        ):
                            iam_policy["Policy"]["PolicyVersion"] = pv
                            break

                yield iam_policy
        desc.refresh_credentials(config, CREDENTIAL_THRESHOLD, iam_client)


@desc.generate_credentials
@desc.decorate
def iam_list_role_policies(config):
    """Fetches role policies details"""
    iam_roles = helper.metadata_list_helper(
        config,
        "iam",
        "list_roles",
        "Roles",
        {"PaginationConfig": {"PageSize": PAGE_SIZE_FOR_IAM_DESCRIPTION}},
    )
    for role in iam_roles:
        list_of_policies = []
        policies = helper.metadata_list_helper(
            config,
            "iam",
            "list_role_policies",
            "PolicyNames",
            {
                "RoleName": role["RoleName"],
                "PaginationConfig": {"PageSize": PAGE_SIZE_FOR_IAM_DESCRIPTION},
            },
        )
        for policy in policies:
            if policy is not None:
                list_of_policies.append(policy)
        role["PolicyNames"] = list_of_policies
        yield role


@desc.generate_credentials
@desc.decorate
def iam_list_mfa_devices(config):
    """Fetches mfa devices details"""
    iam_users = helper.metadata_list_helper(
        config,
        "iam",
        "list_users",
        "Users",
        {"PaginationConfig": {"PageSize": PAGE_SIZE_FOR_IAM_DESCRIPTION}},
    )
    for user in iam_users:
        list_of_mfa_devices = []
        mfa_devices = helper.metadata_list_helper(
            config,
            "iam",
            "list_mfa_devices",
            "MFADevices",
            {
                "UserName": user["UserName"],
                "PaginationConfig": {"PageSize": PAGE_SIZE_FOR_IAM_DESCRIPTION},
            },
        )
        for mfa_device in mfa_devices:
            if mfa_device is not None:
                list_of_mfa_devices.append(mfa_device)
        user["MFADevices"] = list_of_mfa_devices
        yield user


@desc.generate_credentials
@desc.decorate
def iam_server_certificates(config):
    """Fetches server certificates"""
    item = helper.metadata_list_helper(
        config,
        "iam",
        "list_server_certificates",
        "ServerCertificateMetadataList",
        {"PaginationConfig": {"PageSize": PAGE_SIZE_FOR_IAM_DESCRIPTION}},
    )
    return item


@desc.generate_credentials
@desc.decorate
def iam_list_signing_certificates(config):
    """Fetches signing certificates details"""
    # list users
    iam_users = helper.metadata_list_helper(
        config,
        "iam",
        "list_users",
        "Users",
        {"PaginationConfig": {"PageSize": PAGE_SIZE_FOR_IAM_DESCRIPTION}},
    )
    for user in iam_users:
        list_of_signing_certs = []
        # list signing certificates
        signing_certificates = helper.metadata_list_helper(
            config,
            "iam",
            "list_signing_certificates",
            "Certificates",
            {
                "UserName": user["UserName"],
                "PaginationConfig": {"PageSize": PAGE_SIZE_FOR_IAM_DESCRIPTION},
            },
        )
        for signing_certificate in signing_certificates:
            if signing_certificate is not None:
                signing_certificate.pop("CertificateBody", None)
                signing_certificate.pop("UserName", None)
                list_of_signing_certs.append(signing_certificate)
        if len(list_of_signing_certs) > 0:
            event = {
                "Arn": user["Arn"],
                "UserId": user["UserId"],
                "UserName": user["UserName"],
                "Certificates": list_of_signing_certs,
            }
            yield event


@desc.generate_credentials
@desc.decorate
def iam_list_ssh_public_keys(config):
    """Fetches SSH public keys associcated with the IAM user"""
    # SSH public key access
    iam_users = helper.metadata_list_helper(
        config,
        "iam",
        "list_users",
        "Users",
        {"PaginationConfig": {"PageSize": PAGE_SIZE_FOR_IAM_DESCRIPTION}},
    )
    for user in iam_users:
        list_of_ssh_keys = []
        ssh_keys = helper.metadata_list_helper(
            config,
            "iam",
            "list_ssh_public_keys",
            "SSHPublicKeys",
            {
                "UserName": user["UserName"],
                "PaginationConfig": {"PageSize": PAGE_SIZE_FOR_IAM_DESCRIPTION},
            },
        )
        for ssh_key in ssh_keys:
            if ssh_key is not None:
                list_of_ssh_keys.append(ssh_key)
        user["SSHPublicKeys"] = list_of_ssh_keys
        yield user

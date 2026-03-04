#
# SPDX-FileCopyrightText: 2021 Splunk, Inc. <sales@splunk.com>
# SPDX-License-Identifier: LicenseRef-Splunk-8-2021
#
#
"""
loads crypto lib and validates sns signatures
"""
import base64
import requests
import re
import threading

from typing import Callable
from splunksdc import log as logging


try:
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import padding
    from cryptography.exceptions import InvalidSignature
except Exception as ex:
    # logging will be handled in the load_cryptography
    pass

DEFAULT_CERTIFICATE_URL_REGEX = r"^https://sns\.[-a-z0-9]+\.amazonaws\.com(?:\.cn)?/"

logger = logging.get_module_logger()
thread_lock = threading.Lock()
validate_aws_sns_message = None


class ValidationException(Exception):
    """Custom exception for proper messages"""

    pass


class SNSMessageSignatureValidator:
    def __init__(
        self, cert_url_regex=DEFAULT_CERTIFICATE_URL_REGEX, signature_version="1"
    ):
        """Initialise the object

        Args:
            cert_url_regex (str, optional): SNS endpoint URL format. Defaults to DEFAULT_CERTIFICATE_URL_REGEX.
            signature_version (str, optional): Signature version. Defaults to "1".
        """
        self._cert_url_regex = cert_url_regex
        self._signature_version = signature_version

    def _validate_signature_version(self, message: dict) -> None:
        """Validates the signature version

        Args:
            message (dict): Dict containing the message details

        Raises:
            ValidationException: Raises exception if not a valid signature version
        """
        if message.get("SignatureVersion") != self._signature_version:
            raise ValidationException(
                f"Invalid signature version {message.get('SignatureVersion')}. Unable to verify signature."
            )

    def _validate_cert_url(self, message: dict) -> None:
        """Validates the certificate URL SNS endpoint

        Args:
            message (dict): Dict containing the message details

        Raises:
            ValidationException: Raises the exception if not a valid cert URL
        """
        cert_url = message.get("SigningCertURL")
        if not cert_url:
            raise ValidationException("Could not find SigningCertURL field in message.")
        if not re.search(self._cert_url_regex, cert_url):
            raise ValidationException(
                f"Invalid certificate URL. {cert_url} does not match the format {self._cert_url_regex}"
            )

    def _get_signing_content(self, message: dict) -> str:
        """Returns the signing content formatted from the message

        Args:
            message (dict): Dict containing the message details

        Raises:
            ValidationException: Raises exception if unknown message type

        Returns:
            str: Signing content formatted from the message details as per the type
        """
        keys = []
        message_type = message.get("Type")
        if message_type == "Notification":
            if "Subject" in message and message["Subject"] is not None:
                keys = (
                    "Message",
                    "MessageId",
                    "Subject",
                    "Timestamp",
                    "TopicArn",
                    "Type",
                )
            else:
                keys = (
                    "Message",
                    "MessageId",
                    "Timestamp",
                    "TopicArn",
                    "Type",
                )

        if message_type in ("SubscriptionConfirmation", "UnsubscribeConfirmation"):
            keys = (
                "Message",
                "MessageId",
                "SubscribeURL",
                "Timestamp",
                "Token",
                "TopicArn",
                "Type",
            )

        if not keys:
            raise ValidationException(f"Unknown message type {message_type}")

        pairs = [f"{key}\n{message.get(key)}" for key in keys]
        return "\n".join(pairs) + "\n"

    def _get_signing_cert_url(self, message: dict) -> str:
        """Returns the signing cert URL from the message

        Args:
            message (dict): Dict containing the message details

        Returns:
            str: Return cert URL if available in the message else None
        """
        if "SigningCertURL" in message:
            return message.get("SigningCertURL")
        elif "SigningCertUrl" in message:
            return message.get("SigningCertUrl")

        return None

    def validate(self, message: dict, get_certificate: Callable[[str], str]) -> None:
        """Validate the message signature

        Args:
            message (dict): Dict containing the message details
            get_certificate (Callable[[str], str]): A callable that takes a str URL as arguments and returns a str certificate.

        Raises:
            ValidationException: Raises an exception if invalid signature
        """
        self._validate_signature_version(message)
        self._validate_cert_url(message)
        cert_url = self._get_signing_cert_url(message)
        certificate = get_certificate(cert_url)
        cert = x509.load_pem_x509_certificate(certificate)

        signing_content = self._get_signing_content(message)
        encoded_signing_content = signing_content.encode()

        base64_signature = message.get("Signature")
        decoded_signature = base64.b64decode(base64_signature)

        try:
            # Verify the signature with the public key
            cert.public_key().verify(
                decoded_signature,
                encoded_signing_content,
                padding=padding.PKCS1v15(),
                algorithm=hashes.SHA1(),
            )
        except InvalidSignature:
            raise ValidationException("Invalid signature")
        except Exception as e:
            raise ValidationException(
                f"An error occurred during signature verification: {e}"
            )


cache_certificates = {}


def set_certificate_cache(url, certificate):
    """Adds certificate to cache_certificates

    Args:
        url (str): certificate URL
        certificate (str): certificate
    """
    cache_certificates[url] = certificate


def _set_proxy():
    """Sets proxies in the boto3 if configured

    Returns:
        dict: Proxy dict containing the proxy URLs
    """
    # HTTP_PROXY and HTTPS_PROXY are global variables. Hence, they should be imported on each function call.
    from .boto3_proxy_patch import HTTP_PROXY, HTTPS_PROXY

    if HTTP_PROXY or HTTPS_PROXY:
        proxies = {"http": HTTP_PROXY, "https": HTTPS_PROXY}
        return proxies


def get_certificate(url: str) -> str:
    """Check in the cache for the certificate. If not available then fetch the certificate from URL and caches
    Args:
        url (str): Certificate url from the message

    Raises:
        ValidationException: Raises failed to fetch the certificate exception

    Returns:
        str: Return the certificate from the cache
    """
    try:
        if url not in cache_certificates:
            cert = requests.get(url, proxies=_set_proxy()).content
            set_certificate_cache(url, cert)
            logger.debug(f"Fetched SNS Certificate", url={url})
    except Exception:
        raise ValidationException("Failed to fetch cert file.")

    return cache_certificates[url]


def load_cryptography():
    """
    Finds and loads cryptography.
    If fails it will set validate_aws_sns_message to False
    if success validate_aws_sns_message will be the SNSMessageSignatureValidator
    """
    global validate_aws_sns_message
    if validate_aws_sns_message is None:
        try:
            logger.debug("Loading cryptography")
            from cryptography import x509

            validate_aws_sns_message = SNSMessageSignatureValidator()
            logger.info("Loaded cryptography")
        except Exception as ex:
            logger.warning(f"Could not load cryptography {ex}")
            validate_aws_sns_message = False


def sqs_validate(message: dict, message_id: str) -> None:
    """For validating SNS->SQS message signatures.

    Args:
        message (dict): Dict containing the message details

    Raises:
        ValidationException: Throws exception on invalid signature
    """
    global validate_aws_sns_message
    if validate_aws_sns_message is None:
        with thread_lock:
            if validate_aws_sns_message is None:
                load_cryptography()
    if validate_aws_sns_message:
        validate_aws_sns_message.validate(message, get_certificate)
        logger.debug(f"Valid SNS Signature. message_id={message_id}")
    else:
        logger.warning(
            f"Could not load cryptography hence ignoring SNS validation. message_id={message_id}"
        )

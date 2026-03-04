#
# SPDX-FileCopyrightText: 2021 Splunk, Inc. <sales@splunk.com>
# SPDX-License-Identifier: LicenseRef-Splunk-8-2021
#
#
"""
File for init module for cloudwatch discovery.
"""


import boto3
from splunksdc import log as logging

from ..discovery import ebs, ec2, elb, elbv2, function, s3, sns, sqs
from .generic import DiscoverGenericMetrics

logger = logging.get_module_logger()


class DiscoveryPolicyFactory:
    """Class for Discovery policy factory."""

    def __init__(self):
        self._registries = {
            "AWS/EC2": ec2.create_policy_registry(),
            "AWS/EBS": ebs.create_policy_registry(),
            "AWS/ELB": elb.create_policy_registry(),
            "AWS/ApplicationELB": elbv2.create_policy_registry(),
            "AWS/NetworkELB": elbv2.create_policy_registry(),
            "AWS/SQS": sqs.create_policy_registry(),
            "AWS/SNS": sns.create_policy_registry(),
            "AWS/S3": s3.create_policy_registry(),
            "AWS/Lambda": function.create_policy_registry(),
        }

    def __call__(self, namespace, dimensions):
        policy = self._find(namespace, dimensions)
        cls = policy.__class__.__name__
        logger.debug(
            "Discovery policy created.",
            namespace=namespace,
            dimensions=dimensions,
            cls=cls,
        )
        return policy

    def _find(self, namespace, dimensions):
        registry = self._registries.get(namespace)
        if not registry:
            return DiscoverGenericMetrics(namespace)
        policy = registry.get(*dimensions)
        if not policy:
            return DiscoverGenericMetrics(namespace)
        return policy(namespace)


class Cache:
    """Class for cache."""

    def __init__(self):
        self._data = []

    def get(self):
        """Returns data."""
        return self._data

    def _append(self, elements):
        self._data.extend(elements)

    def _scan(self, pages, key):
        for page in pages:
            elements = page.get(key, [])
            self._append(elements)


class CloudWatchMetricsCache(Cache):
    """Class for cloudwatch metrics cache."""

    def __init__(self, namespace):
        super(  # pylint: disable=super-with-arguments
            CloudWatchMetricsCache, self
        ).__init__()
        self._namespace = namespace

    def load(
        self, credentials, region, session, endpoint_urls={}
    ):  # pylint: disable=dangerous-default-value
        """Loads cloudwatch metrics."""
        logger.debug("Start listing metrics.", namespace=self._namespace)
        client = credentials.client(
            "cloudwatch", region, session, endpoint_urls.get("monitoring_endpoint_url")
        )
        params = {"Namespace": self._namespace}
        paginator = client.get_paginator("list_metrics")
        pages = paginator.paginate(**params)
        self._scan(pages, "Metrics")


class EC2ReservationsCache(Cache):
    """Class for EC2 reservations cache."""

    def load(
        self, credentials, region, session, endpoint_urls={}
    ):  # pylint: disable=dangerous-default-value
        """Loads EC2 instances."""
        logger.debug("Start describing EC2 instances.")
        client = credentials.client(
            "ec2", region, session, endpoint_urls.get("ec2_endpoint_url")
        )
        paginator = client.get_paginator("describe_instances")
        pages = paginator.paginate()
        self._scan(pages, "Reservations")


class AutoScalingGroupsCache(Cache):
    """Class for auto scaling groups cache."""

    def load(
        self, credentials, region, session, endpoint_urls={}
    ):  # pylint: disable=dangerous-default-value
        """Loads auto scaling groups."""
        logger.debug("Start describing AutoScalingGroups.")
        client = credentials.client(
            "autoscaling",
            region,
            session,
            endpoint_urls.get("autoscaling_endpoint_url"),
        )
        paginator = client.get_paginator("describe_auto_scaling_groups")
        pages = paginator.paginate()
        self._scan(pages, "AutoScalingGroups")


class LaunchConfigurationsCache(Cache):
    """Class for launch configurations cache."""

    def load(
        self, credentials, region, session, endpoint_urls={}
    ):  # pylint: disable=dangerous-default-value
        """Loads Launchconfigurations."""
        logger.debug("Start describing LaunchConfigurations.")
        client = credentials.client(
            "autoscaling",
            region,
            session,
            endpoint_urls.get("autoscaling_endpoint_url"),
        )
        paginator = client.get_paginator("describe_launch_configurations")
        pages = paginator.paginate()
        self._scan(pages, "LaunchConfigurations")


class EBSVolumesCache(Cache):
    """Class for EBS volumes cache."""

    def load(
        self, credentials, region, session, endpoint_urls={}
    ):  # pylint: disable=dangerous-default-value
        """Loads EBS volumes."""
        logger.debug("Start describing EBS volumes.")
        client = credentials.client(
            "ec2", region, session, endpoint_urls.get("ec2_endpoint_url")
        )
        paginator = client.get_paginator("describe_volumes")
        pages = paginator.paginate()
        self._scan(pages, "Volumes")


class SQSQueuesCache(Cache):
    """Class for SQS queues cache."""

    def load(
        self, credentials, region, session, endpoint_urls={}
    ):  # pylint: disable=dangerous-default-value
        """Loads SQS queues."""
        logger.debug("Start listing SQS queues.")
        client = credentials.client(
            "sqs", region, session, endpoint_urls.get("sqs_endpoint_url")
        )
        # The number of queue is up to 1000 due to API limitation
        response = client.list_queues()
        elements = response.get("QueueUrls", [])
        self._append(elements)


class SNSTopicsCache(Cache):
    """Class for SNS topics cache."""

    def load(
        self, credentials, region, session, endpoint_urls={}
    ):  # pylint: disable=dangerous-default-value
        """Loads SNS topics."""
        logger.debug("Start listing SNS topics.")
        client = credentials.client(
            "sns", region, session, endpoint_urls.get("sns_endpoint_url")
        )
        paginator = client.get_paginator("list_topics")
        pages = paginator.paginate()
        self._scan(pages, "Topics")


class LambdaFunctionsCache(Cache):
    """Class for lambda functions cache."""

    def load(
        self, credentials, region, session, endpoint_urls={}
    ):  # pylint: disable=dangerous-default-value
        """Loads Lambda functions."""
        logger.debug("Start listing Lambda functions.")
        client = credentials.client(
            "lambda", region, session, endpoint_urls.get("lambda_endpoint_url")
        )
        paginator = client.get_paginator("list_functions")
        pages = paginator.paginate()
        self._scan(pages, "Functions")


class ELBInstancesCache(Cache):
    """Class for ELB instances cache."""

    def load(
        self, credentials, region, session, endpoint_urls={}
    ):  # pylint: disable=dangerous-default-value
        """Loads ELB instances."""
        logger.debug("Start listing ELB instances.")
        client = credentials.client(
            "elb", region, session, endpoint_urls.get("elb_endpoint_url")
        )
        paginator = client.get_paginator("describe_load_balancers")
        pages = paginator.paginate()
        self._scan(pages, "LoadBalancerDescriptions")


class ELBV2TargetGroupsCache(Cache):
    """Class for ELB v2 target groups cache."""

    def load(
        self, credentials, region, session, endpoint_urls={}
    ):  # pylint: disable=dangerous-default-value
        """Loads ELBv2 target groups."""
        logger.debug("Start describing ELBv2 TargetGroups.")
        client = credentials.client(
            "elbv2", region, session, endpoint_urls.get("elb_endpoint_url")
        )
        paginator = client.get_paginator("describe_target_groups")
        pages = paginator.paginate()
        self._scan(pages, "TargetGroups")


class ELBV2InstancesCache(Cache):
    """Class for ELB v2 instances cache."""

    def load(
        self, credentials, region, session, endpoint_urls={}
    ):  # pylint: disable=dangerous-default-value
        """Loads ELBv2 instances."""
        logger.debug("Start describing ELBv2 instances.")
        client = credentials.client(
            "elbv2", region, session, endpoint_urls.get("elb_endpoint_url")
        )
        paginator = client.get_paginator("describe_load_balancers")
        pages = paginator.paginate()
        self._scan(pages, "LoadBalancers")


class S3BucketsCache(Cache):
    """Class for S3 buckets cache."""

    def load(
        self, credentials, region, session, endpoint_urls={}
    ):  # pylint: disable=dangerous-default-value
        """Loads S3 buckets."""
        logger.debug("Start listing S3 buckets.")
        client = credentials.client(
            "s3", region, session, endpoint_urls.get("s3_endpoint_url")
        )
        response = client.list_buckets()
        for item in response.get("Buckets", []):
            bucket_name = item["Name"]
            self._data.append(bucket_name)

    # def _load_filters(self, name, client):
    #     params = {'Bucket': name}
    #     while True:
    #         response = client.list_bucket_metrics_configurations(**params)
    #         elements = response.get('MetricsConfigurationList', [])
    #         lst = self._filters.setdefault(name, list())
    #         lst.extend([item['Id'] for item in elements])
    #         truncated = response.get('IsTruncated')
    #         nct = response.get('NextContinuationToken')
    #         if not truncated or not nct:
    #             break
    #         params['ContinuationToken'] = nct


class AWSEnvironment:
    """Class for AWS environment."""

    def __init__(
        self, credentials, region, endpoint_urls={}
    ):  # pylint: disable=dangerous-default-value
        self._caches = {}
        self._credentials = credentials
        self._region = region
        self._session = boto3.Session()
        self._endpoint_urls = endpoint_urls

    def _acquire(self, cls, *args):
        key = cls.__name__ + "".join(args)
        if key not in self._caches:
            cache = cls(*args)
            cache.load(
                self._credentials, self._region, self._session, self._endpoint_urls
            )
            self._caches[key] = cache
        return self._caches[key].get()

    def get_cloudwatch_metrics(self, namespace):
        """Returns cloudwatch metrics."""
        return self._acquire(CloudWatchMetricsCache, namespace)

    def get_ec2_reservations(self):
        """Returns EC2 reservations."""
        return self._acquire(EC2ReservationsCache)

    def get_auto_scaling_groups(self):
        """Returns Auto scaling groups."""
        return self._acquire(AutoScalingGroupsCache)

    def get_launch_configurations(self):
        """Returns launch configurations."""
        return self._acquire(LaunchConfigurationsCache)

    def get_ebs_volumes(self):
        """Returns EBS volumes."""
        return self._acquire(EBSVolumesCache)

    def get_elb_instances(self):
        """Returns ELB instances."""
        return self._acquire(ELBInstancesCache)

    def get_elbv2_instances(self):
        """Returns ELB v2 instances."""
        return self._acquire(ELBV2InstancesCache)

    def get_elbv2_target_groups(self):
        """Returns ELB v2 targets."""
        return self._acquire(ELBV2TargetGroupsCache)

    def get_s3_buckets(self):
        """Returns S3 buckets.."""
        return self._acquire(S3BucketsCache)

    def get_sqs_queues(self):
        """Returns SQS queues.."""
        return self._acquire(SQSQueuesCache)

    def get_sns_topics(self):
        """Returns SNS topics."""
        return self._acquire(SNSTopicsCache)

    def get_lambda_functions(self):
        """Returns lambda function."""
        return self._acquire(LambdaFunctionsCache)

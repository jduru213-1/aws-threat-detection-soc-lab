# Guides

The full lab walkthrough is in **[step-by-step.md](step-by-step.md)** (prerequisites through teardown, with checks and troubleshooting in each part). For a shorter quick start, use the [repo README](../README.md).

| Section | What you do there |
|--------|-------------------|
| [Before you start](step-by-step.md#before-you-start) | Install tools, IAM expectations, checklist |
| [Step 1 — Start Splunk](step-by-step.md#step-1--start-splunk) | Run Splunk in Docker and sign in |
| [Step 2 — Create Splunk indexes](step-by-step.md#step-2--create-splunk-indexes) | Create `aws_cloudtrail`, `aws_config`, `aws_vpcflow` |
| [Step 3 — Install the Splunk Add-on for AWS](step-by-step.md#step-3--install-the-splunk-add-on-for-aws) | Install the add-on from Splunkbase |
| [Step 4 — Build the AWS infrastructure](step-by-step.md#step-4--build-the-aws-infrastructure) | Run `build.sh` / Terraform (SQS, keys, logging) |
| [Step 5 — Connect Splunk to AWS](step-by-step.md#step-5--connect-splunk-to-aws) | Add-on AWS account and SQS-based S3 inputs |
| [Step 6 — Run attack simulations (Stratus)](step-by-step.md#step-6--run-attack-simulations-stratus) | Configure Stratus and detonate techniques |
| [Step 7 — Write detections and build dashboards](step-by-step.md#step-7--write-detections-and-build-dashboards) | SPL examples, dashboards, `detections/` folder |
| [Teardown](step-by-step.md#teardown) | Run `destroy.sh`, empty buckets, destroy resources |

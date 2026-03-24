# Infra

This folder creates and tears down the AWS side of the lab.

## Recommended way

- Build: `./build.sh`
- Destroy: `./destroy.sh`

These scripts are the easiest path because they include prompts, checks, and safer defaults.

## What gets created

- S3 buckets for telemetry
- CloudTrail, AWS Config, and VPC Flow Logs integrations
- IAM user for Splunk ingestion
- IAM user for Stratus simulation
- Optional SQS resources for S3-to-Splunk ingestion

## Raw Terraform (manual option)

If you prefer to run Terraform commands directly:

```bash
cd infra

# Use a saved AWS profile (recommended)
export AWS_PROFILE=soc-lab-admin
export AWS_REGION=us-east-1

# Confirm credentials are valid
aws sts get-caller-identity

# Build
terraform init
terraform plan -out=tfplan
terraform apply tfplan

# Teardown later
terraform destroy
```

Use raw Terraform only if you want full manual control.

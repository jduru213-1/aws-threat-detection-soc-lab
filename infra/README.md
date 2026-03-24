# Infra (AWS)

**Up:** `./build.sh` - guided build flow with credential/tooling safeguards.  
**Down:** `./destroy.sh` - empties buckets then destroys (supports `--keep-iam-users`).

**Created:** S3 buckets, CloudTrail, AWS Config, VPC Flow Logs, Splunk IAM user, Stratus IAM user, and optional SQS ingestion resources.

## Raw Terraform Quickstart

Use this if you want direct Terraform commands instead of wrapper scripts.

```bash
cd infra

# Choose credential method A: saved AWS profile
export AWS_PROFILE=soc-lab-admin
export AWS_REGION=us-east-1

# OR credential method B: direct access keys
# export AWS_ACCESS_KEY_ID=YOUR_ACCESS_KEY_ID
# export AWS_SECRET_ACCESS_KEY=YOUR_SECRET_ACCESS_KEY
# export AWS_REGION=us-east-1

# Verify your shell can authenticate to AWS
aws sts get-caller-identity

# Initialize providers and backend metadata
terraform init

# Preview planned infrastructure changes and save plan to file
terraform plan -out=tfplan

# Apply exactly what was planned in tfplan
terraform apply tfplan

# Show output values (bucket names, IAM outputs, etc.)
terraform output

# Later: destroy all Terraform-managed infrastructure
terraform destroy
```

If you prefer guard rails and prompts, use `./build.sh` and `./destroy.sh`.

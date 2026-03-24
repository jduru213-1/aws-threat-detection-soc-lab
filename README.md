# AWS Threat Detection SOC Lab

Imagine a cloud SOC lab where building the infrastructure is part of the skill but you never have to rebuild it from scratch. This project gives you a repeatable environment where you stand everything up once, understand how it all fits together, and from there focus on what keeps building threat detection and security monitoring skills in the cloud. 

> Terraform codifies the infrastructure so you build it once and spin it up or down whenever you need it.

I originally built this to learn and sharing it in case it may be useful to others. Feel free to check out the medium blog that walks through the full implementation step by step as some pieces may require manual configuration in Splunk and AWS that cannot be automated.

---

## 🗺️ How it works

![Architecture: AWS telemetry to S3 to SQS to Splunk](https://github.com/user-attachments/assets/c65afbe7-7817-4510-8017-30ffeb521446)

1. AWS telemetry sources deliver log objects to S3.
2. S3 publishes `ObjectCreated` notifications to SQS queues.
3. The Splunk Add-on for AWS polls SQS, fetches the referenced S3 objects, and indexes them.
4. Stratus Red Team detonates attack techniques that show up in CloudTrail within minutes.

Each source has its own bucket, queue, and Splunk index so failures stay isolated.

---

## ⚙️ What gets built

| Component | What it does |
|---|---|
| CloudTrail | Records every AWS API call — who, what, when, from where |
| AWS Config | Tracks resource configuration changes over time |
| VPC Flow Logs | Captures accepted/rejected network traffic on the default VPC |
| S3 and SQS | Stores logs and notifies Splunk when new objects arrive |
| Splunk (Docker) | Local search and detection platform (SIEM) |
| IAM users | One for Splunk ingestion (read-only), one for Stratus adversary simulations |

---

## 🚀 Quick start

A full step-by-step walkthrough is in [`guides/step-by-step.md`](guides/step-by-step.md) and the Medium blog.

**Prerequisites:** 
- Docker Desktop
- Python 3.10+
- AWS account
- `aws configure` set up,
- Bash terminal.

### 1. Start Splunk
```bash
cd soc && docker compose up -d
# Open https://localhost:8000
```
### 2. Create indexes
```
pip install splunk-sdk
python ./scripts/setup_splunk.py --no-verify-tls
```
### 3. Build AWS infrastructure
```
cd infra && ./build.sh
# Save the bucket names, SQS queue URLs, and IAM credentials from the output
```
### 4. Install Splunk Add-on for AWS from Splunkbase, then configure:
```
#    Configuration → AWS Account  →  paste soc-lab-splunk-addon keys
#    Inputs → SQS-based S3        →  create inputs for each queue + index
```
### 5. Verify data
```
#    index=aws_cloudtrail earliest=-1h
```

---

## 🎯 Running simulations

```bash
cd attacks
source ./configure-stratus.sh

stratus list --platform aws
stratus detonate <technique-id> --cleanup
```

Re-run `source ./configure-stratus.sh` any time you open a new terminal — it sets the AWS profile and region for the current session only.

---

## 🔍 Detection examples

```spl
# Failed console logins
index=aws_cloudtrail eventName=ConsoleLogin errorMessage=*

# IAM user created
index=aws_cloudtrail eventName=CreateUser

# Security group opened
index=aws_cloudtrail eventName=AuthorizeSecurityGroupIngress

# Access key created
index=aws_cloudtrail eventName=CreateAccessKey
```

---

## 🧹 Teardown

```bash
cd infra && ./destroy.sh
```

Use your build credentials, not the Stratus profile. The script empties S3 buckets before destroying — S3 won't delete non-empty buckets. You'll be asked whether to keep the IAM users if you plan to rebuild later.

---

## 📁 Repo layout

```
infra/        Terraform + build.sh + destroy.sh
soc/          Splunk Docker Compose
scripts/      setup_splunk.py, knowledge_check.py
attacks/      configure-stratus.sh
guides/       step-by-step.md
detections/   add your own detections here
```

---

*Created by Justin Duru — collect AWS signals, build detections in Splunk, validate with Stratus.*

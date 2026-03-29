#  AWS Threat Detection SOC Lab

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Terraform](https://img.shields.io/badge/terraform-%3E%3D1.0-844FBA?logo=terraform&logoColor=white)](infra/versions.tf)

Imagine a cloud SOC lab where building the infrastructure is part of the skill, but you never have to rebuild it from scratch. This project gives you a repeatable environment where you stand everything up once, understand how it all fits together, and from there focus on what keeps building threat detection and security monitoring skills in the cloud.

> Terraform codifies the infrastructure, so you build it once and spin it up or down as needed.

I originally built this lab to strengthen my understanding of cloud-based threats and security monitoring while preparing for the AWS Solutions Architect certification, and I’m sharing it to help others on a similar journey.

> Feel free to check out the Medium blog, which walks through the full implementation step by step, as some components will require manual configuration in Splunk and AWS and cannot be fully automated.

---

### 🗺️ Architecture Overview

![Architecture: AWS telemetry to S3 to SQS to Splunk](https://github.com/user-attachments/assets/c65afbe7-7817-4510-8017-30ffeb521446)

1. AWS telemetry sources deliver log objects to S3.
2. S3 publishes `ObjectCreated` notifications to SQS queues.
3. The Splunk Add-on for AWS polls SQS, fetches the referenced S3 objects, and indexes them.
4. Stratus Red Team detonates attack techniques that show up in CloudTrail within minutes.

> Each source has its own bucket, queue, and Splunk index, so failures stay isolated.

---

### ⚙️ What This Lab Builds

| Component | What it does |
|---|---|
| CloudTrail | Records every AWS API call — who, what, when, from where |
| AWS Config | Tracks resource configuration changes over time |
| VPC Flow Logs | Captures accepted/rejected network traffic on the default VPC |
| S3 and SQS | Stores logs and notifies Splunk when new objects arrive |
| Splunk | Containerized local search and detection platform (SIEM) |
| IAM users | One for Splunk ingestion (read-only), one for Stratus adversary simulations |

> Cost note: AWS Config is often the largest ongoing charge. Run `./destroy.sh` when the lab is idle to avoid unexpected costs.

---

### 🚀 Quick start
For a detailed walkthrough with troubleshooting tips, see [`guides/step-by-step.md`](guides/step-by-step.md).

**Prerequisites**

- Docker Desktop
- Python 3.10+
- Bash (Git Bash on Windows)
- AWS Account (AdministratorAccess)

### 1. Start Splunk

```bash
cd soc && docker compose up -d
# Open https://localhost:8000  |  user: admin  |  pass: ChangeMe123!
```

### 2. Create indexes

```bash
pip install splunk-sdk
python ./scripts/setup_splunk.py
```

### 3. Install the Splunk Add-on for AWS

- Download from [Splunkbase](https://splunkbase.splunk.com/app/1876/).
- In Splunk: **Apps → Manage Apps → Install app from file**.
- Upload the `.tgz` and restart Splunk when prompted.

### 4. Build AWS infrastructure

```bash
cd infra && ./build.sh
# Save the SQS queue URLs and IAM credentials from the output
```

### 5. Configure ingestion

- **Configuration → AWS Account** — paste the `soc-lab-splunk-addon` keys from step 4
- **Inputs → SQS-based S3** — create one input per queue, mapped to its index:

| Queue | Index |
|-------|--------|
| CloudTrail SQS URL | `aws_cloudtrail` |
| Config SQS URL | `aws_config` |
| VPC Flow SQS URL | `aws_vpcflow` |

### 6. Verify data

```spl
index=aws_cloudtrail earliest=-1h
```

> Repeat for `aws_config` and `aws_vpcflow`. Allow a few minutes for the first delivery.

---

### 🎯 Running Threat Simulations

```bash
cd attacks
source ./configure-stratus.sh
```
```
stratus list --platform aws
stratus detonate <technique-id> --cleanup
```

> Every time you open a new terminal to run Stratus, run `source ./configure-stratus.sh` first. That loads the Stratus AWS profile into your current shell, and it does not persist when you start another session. Use this profile only for Stratus.

---

### 🔍 Detection Examples

```spl
# Failed console logins
index=aws_cloudtrail eventName=ConsoleLogin errorMessage=*
```
```
# IAM user created
index=aws_cloudtrail eventName=CreateUser
```
```
# Security group opened
index=aws_cloudtrail eventName=AuthorizeSecurityGroupIngress
```
```
# Access key created
index=aws_cloudtrail eventName=CreateAccessKey
```

> Add SPL or saved-search examples under [`detections/`](detections/). Pull requests welcome.

---

### 🧹 Teardown

```bash
cd infra && ./destroy.sh
```

> The script empties S3 first, then prompts whether to keep the Splunk/Stratus IAM users for faster rebuilds.

---

### 📁 Repo layout

```
infra/        Terraform, build.sh, destroy.sh
soc/          Splunk Docker Compose
scripts/      setup_splunk.py, knowledge_check.py
attacks/      configure-stratus.sh
guides/       step-by-step.md
detections/   SPL and saved-search snippets (PRs welcome)
```

---

*Created by Justin Duru — collect AWS signals, build detections in Splunk, validate with Stratus.*

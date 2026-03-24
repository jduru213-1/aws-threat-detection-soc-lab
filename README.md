# 🛡️ AWS Threat Detection SOC Lab
This project is a practical AWS threat detection lab built for hands-on SOC learning. The infrastructure is automated with Terraform, so you can spend your time on what matters most: adversary simulation, investigation practice, and detection improvement in Splunk.

> Terraform handles the infrastructure heavy lifting so you can focus on cloud detections, not setup friction.

## Quick Project Snapshot
| Area | Details |
|------|---------|
| Cloud telemetry | CloudTrail, AWS Config, VPC Flow Logs |
| Ingestion | S3 sends ObjectCreated notifications to SQS, and Splunk polls SQS to pull referenced S3 log objects |
| Validation | Simulate cloud threats with Stratus Red Team to understand attacker behavior and test detections |
| Outcome | Build cloud lab infrastructure once, then focus on attacks, investigations, and detection improvements without repeating setup |

This lab mirrors a real SOC workflow: collect cloud telemetry, ingest it into Splunk, simulate attacker behavior, and validate detection logic with real events.

---

## Architecture
This diagram shows the end-to-end workflow: AWS telemetry is collected, stored, and ingested into Splunk for detection validation.

![Architecture: AWS to S3 (optional SQS) to Splunk Docker](https://github.com/user-attachments/assets/c65afbe7-7817-4510-8017-30ffeb521446)

1. AWS telemetry sources (CloudTrail, AWS Config, and VPC Flow Logs) deliver log objects to Amazon S3.
2. Amazon S3 publishes `ObjectCreated` notifications to Amazon SQS queues provisioned by Terraform.
3. The Splunk Add-on for AWS polls SQS, processes each message, and retrieves the referenced S3 objects.
4. Parsed events are indexed in Splunk under the `aws_*` indexes.

---

## Table of contents
- [Quick Project Snapshot](#quick-project-snapshot)
- [Architecture](#architecture)
- [What this project delivers](#what-this-project-delivers)
- [Components](#components)
- [Prerequisites](#prerequisites)
- [Quick start](#quick-start-end-to-end)
- [Verify data in Splunk](#verify-data-in-splunk)
- [Cleanup](#cleanup)
- [Repo layout](#repo-layout)

---

## What this project delivers
- A repeatable AWS telemetry lab built with Terraform.
- A clean ingestion path from S3 and SQS into Splunk indexes.
- Controlled Stratus simulations to test detections against real events.
- A practical SOC workflow you can rebuild, run, and showcase.

## Components
| Component | What it does | Where |
|----------|--------------|------|
| Splunk (Docker) | Local Splunk Enterprise for searching and dashboards | `soc/` |
| Index Setup | Creates `aws_cloudtrail`, `aws_config`, `aws_vpcflow` | `scripts/setup_splunk.py` |
| Splunk Add-on for AWS | Ingests log objects from S3 (or SQS-based ingestion) | Splunk UI |
| AWS logging Infra | CloudTrail, Config, VPC Flow Logs -> S3 | `infra/` |
| Stratus Red Team | Generates “known-bad” activity to validate detections | `attacks/` |

## Prerequisites
- Docker Desktop
- Python 3.10+
- Bash-compatible terminal
- An AWS account with permissions to create lab resources
- `aws configure` set up on your machine

## Quick start (end-to-end)
Follow the more detailed walkthrough in [`guides/step-by-step.md`](guides/step-by-step.md). This is the fast version.

### 1) Start Splunk (Docker)
```bash
cd soc
docker compose up -d
```
Open `https://localhost:8000`

### 2) Create Splunk indexes
```bash
pip install splunk-sdk
python ./scripts/setup_splunk.py
```

### 3) Install the Splunk Add-on for AWS
Install the Splunk Add-on for AWS from [Splunkbase](https://splunkbase.splunk.com/app/1876/) and restart Splunk.

### 4) Build AWS resources (Terraform)
```bash
cd infra
./build.sh
```
Save the bucket names and the Splunk IAM key + secret printed by the script.

### 5) Configure ingestion in Splunk Add-on (SQS-based S3)
In the Splunk Add-on for AWS:
- Go to **Configuration -> AWS Account** and paste the Splunk IAM access key and secret from Step 4.
- Go to **Inputs** and create three **SQS-based S3** inputs:
  - CloudTrail queue -> index `aws_cloudtrail`
  - Config queue -> index `aws_config`
  - VPC Flow Logs queue -> index `aws_vpcflow`

Terraform prints the SQS queue URLs and ARNs after `./build.sh` (see `infra/outputs_sqs.tf`).

### 6) Run Stratus Red Team
```bash
cd attacks
source ./configure-stratus.sh
stratus list --platform aws
```
Then run a technique:
```bash
stratus detonate <technique-id> --cleanup
```

For exercise ideas and dashboard steps, see [`guides/step-by-step.md`](guides/step-by-step.md) section 7.

## Verify data in Splunk
Start with: `index=aws_cloudtrail earliest=-1h`

And repeat for:
- `index=aws_config earliest=-1h`
- `index=aws_vpcflow earliest=-1h`

If Splunk is empty, widen the time window (for example `earliest=-2h`) and wait a few minutes for AWS delivery and Splunk ingestion.


## Cleanup
Use build credentials (not Stratus):
```bash
cd infra
./destroy.sh
```

## Repo layout
| Path | What |
|------|------|
| `infra/` | `build.sh`, `destroy.sh`, Terraform |
| `soc/` | Splunk Docker + configuration |
| `scripts/` | Python helpers (Splunk index setup) |
| `guides/` | Step-by-step walkthrough |
| `attacks/` | Stratus Red Team instructions |

---

*Created by Justin Duru*  
*Collect AWS signals. Build detections in Splunk. Validate with Stratus.*

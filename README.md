# 🛡️ AWS Threat Detection SOC Lab
This project is a practical AWS threat detection lab built for hands-on SOC learning. The infrastructure is automated with Terraform, so you can spend your time on what matters most: adversary simulation, investigation practice, and detection improvement in Splunk.

> Terraform handles the infrastructure heavy lifting so you can focus on cloud detections, not setup friction.

## Why this project matters
Cloud SOC work is strongest when detections are tested against realistic behavior, not just theory. This lab gives you a repeatable way to generate AWS telemetry, ingest it into Splunk, and validate detection logic with controlled attack simulation.

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

1. CloudTrail / AWS Config / VPC Flow Logs write objects to S3
2. S3 sends ObjectCreated notifications to SQS queues (provisioned by Terraform)
3. Splunk Add-on polls SQS, reads messages, fetches referenced S3 objects
4. Events are written to Splunk indexes (`aws_*`)

---

## Table of contents
- [Why this project matters](#why-this-project-matters)
- [Quick Project Snapshot](#quick-project-snapshot)
- [Architecture](#architecture)
- [Overview](#overview)
- [Portfolio outcomes](#portfolio-outcomes)
- [Skills demonstrated](#skills-demonstrated)
- [Components](#components)
- [Prerequisites](#prerequisites)
- [Quick start](#quick-start-end-to-end)
- [Verify data in Splunk](#verify-data-in-splunk)
- [Cleanup](#cleanup)
- [Repo layout](#repo-layout)

---

## Overview
This repo is structured as a full SOC practice loop:
1. Build cloud telemetry infrastructure with Terraform.
2. Ingest logs into Splunk and normalize into dedicated indexes.
3. Simulate attacker behavior with Stratus Red Team.
4. Validate detections and investigations against real generated events.

## Portfolio outcomes
- Built a repeatable AWS telemetry pipeline for SOC practice.
- Implemented SQS-based ingestion from S3 into Splunk.
- Validated detections with controlled Stratus Red Team simulations.
- Documented a workflow that is easy to rebuild and demonstrate.

## Skills demonstrated
- Cloud detection engineering with real AWS telemetry.
- SIEM data onboarding and index strategy in Splunk.
- Threat simulation and validation using Stratus Red Team.
- Infrastructure as Code using Terraform and reproducible scripts.

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
In the Splunk Add-on:
- Configuration -> AWS Account: paste the Splunk IAM key and secret from Step 4.
- Inputs -> create three SQS-based S3 inputs:
  - CloudTrail queue (from Terraform outputs) → index `aws_cloudtrail`
  - Config queue (from Terraform outputs) → index `aws_config`
  - VPC Flow Logs queue (from Terraform outputs) → index `aws_vpcflow`
Note: Terraform prints SQS queue URLs/ARNs after `build.sh` (see also `infra/outputs_sqs.tf`).

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

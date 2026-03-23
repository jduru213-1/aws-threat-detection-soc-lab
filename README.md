# 🛡️ AWS Threat Detection SOC Lab
Imagine spinning up a cloud SOC lab where the infrastructure is already in place, so you can focus on what matters most such as adversary simulation, detection engineering, and real investigation practice. I built this Terraform-based project as a repeatable, cost-conscious AWS threat detection environment so others can learn (including me) by doing and focus on practical security outcomes.

> Terraform handles the infrastructure heavy lifting so you can focus on cloud detections, not setup friction.

## Quick Project Snapshot
| Area | Details |
|------|---------|
| Cloud telemetry | CloudTrail, AWS Config, VPC Flow Logs |
| Ingestion | S3 sends ObjectCreated notifications to SQS, and Splunk polls SQS to fetch referenced S3 log objects |
| Validation | Simulate cloud threats with Stratus Red Team to understand attacker behavior and test detections |
| Outcome | Build cloud lab infrastructure once, then focus on attacks, investigations, and detection improvements without repeating setup |

This lab simulates how a cloud SOC ingests AWS telemetry, maps attacker behavior to logs, builds practical detections in Splunk, and validates detection coverage with adversary emulation.

---

## Architecture
This diagram shows the end-to-end workflow: AWS telemetry is collected, stored, and ingested into Splunk to validate detections.

![Architecture: AWS to S3 (optional SQS) to Splunk Docker](https://github.com/user-attachments/assets/c65afbe7-7817-4510-8017-30ffeb521446)

1. CloudTrail / AWS Config / VPC Flow Logs write objects to S3
2. S3 sends ObjectCreated notifications to SQS queues (provisioned by Terraform)
3. Splunk Add-on polls SQS, reads messages, fetches referenced S3 objects
4. Events are written to Splunk indexes (`aws_*`)

---

## Table of contents
- [ Quick project snapshot](#quick-project-snapshot)
- [ Why this matters](#why-this-matters)
- [ Architecture](#architecture)
- [ Quick start](#quick-start-end-to-end)
- [ Components](#components-repo-map)
- [ Overview](#overview)
- [ Portfolio outcomes](#portfolio-outcomes)
- [ Evidence checklist](#evidence-checklist)
- [Prerequisites](#prerequisites)
- [Verify data in Splunk](#verify-data-in-splunk)
- [ Cleanup](#cleanup)
- [ Repo layout](#repo-layout)

---

## Overview
This repo is structured as a full SOC practice loop:
1. Build cloud telemetry infrastructure with Terraform.
2. Ingest logs into Splunk and normalize into dedicated indexes.
3. Simulate attacker behavior with Stratus Red Team.
4. Validate detections and investigations against real generated events.

## Portfolio outcomes
| Outcome | What was delivered |
|------|------|
| Detection-ready data pipeline | CloudTrail, AWS Config, and VPC Flow Logs routed to S3 and ingested into Splunk |
| Validated attack telemetry | Stratus techniques used to generate known-bad cloud activity for testing |
| Practical detections | Starter detections for failed logins, IAM user creation, and security group changes |
| Repeatable workflow | One-command build and teardown scripts for fast lab reset and iteration |
| Analyst workflow practice | Search, triage, and dashboard building based on realistic AWS event data |

## Evidence checklist
Use this list to quickly verify project outcomes:
- Splunk indexes exist: `aws_cloudtrail`, `aws_config`, `aws_vpcflow`
- SQS-based inputs are configured and receiving events
- Stratus detonation runs and corresponding events appear in Splunk
- Starter detections return expected matches in CloudTrail-backed data

## Components (repo map)
| Component | What it does | Where |
|----------|--------------|------|
| Splunk (Docker) | Local Splunk Enterprise for searching + dashboards | `soc/` |
| Index setup | Creates `aws_cloudtrail`, `aws_config`, `aws_vpcflow` | `scripts/setup_splunk.py` |
| Splunk Add-on for AWS | Ingests log objects from S3 (or SQS-based ingestion) | Splunk UI |
| AWS logging infra | CloudTrail + Config + VPC Flow Logs → S3 (+ optional SQS wiring) | `infra/` |
| Stratus Red Team | Generates “known-bad” activity to validate detections | `attacks/` |

## Prerequisites
- Docker Desktop
- Python 3.10+
- PowerShell (Windows) / a terminal to run scripts
- An AWS account + permissions to create the lab resources
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
```powershell
cd infra
.\build.ps1
```
Save the bucket names and the Splunk IAM key + secret printed by the script.

### 5) Configure ingestion in Splunk Add-on (SQS-based S3)
In the Splunk Add-on:
- Configuration → AWS Account: paste the Splunk IAM key + secret from Step 4
- Inputs → create three SQS-based S3 inputs:
  - CloudTrail queue (from Terraform outputs) → index `aws_cloudtrail`
  - Config queue (from Terraform outputs) → index `aws_config`
  - VPC Flow Logs queue (from Terraform outputs) → index `aws_vpcflow`
Note: Terraform prints SQS queue URLs/ARNs after `build.ps1` (see also `infra/outputs_sqs.tf`).

### 6) Run Stratus Red Team
```powershell
cd attacks
.\configure-stratus.ps1
stratus list --platform aws
```
Then run a technique:
```powershell
stratus detonate <technique-id> --cleanup
```

For exercise ideas and dashboard steps, see [`guides/step-by-step.md`](guides/step-by-step.md) section 7.

## Verify data in Splunk
Start with:
`index=aws_cloudtrail earliest=-1h`
And repeat for:
- `index=aws_config earliest=-1h`
- `index=aws_vpcflow earliest=-1h`

If Splunk is empty, widen the time window (for example `earliest=-2h`) and wait a few minutes for AWS delivery + Splunk ingestion.


## Cleanup
Use build credentials (not Stratus):
```powershell
cd infra
.\destroy.ps1
```

## Repo layout
| Path | What |
|------|------|
| `infra/` | `build.ps1`, `destroy.ps1`, Terraform |
| `soc/` | Splunk Docker + configuration |
| `scripts/` | Python helpers (Splunk index setup) |
| `guides/` | Step-by-step walkthrough |
| `attacks/` | Stratus Red Team instructions |

---

*Created by Justin Duru*  
*Collect AWS signals. Build detections in Splunk. Validate with Stratus.*

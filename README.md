# 🛡️ AWS Threat Detection SOC Lab
This project is a Terraform-based SOC lab for learning AWS threat detection and securtiy monitoring. It stands up core AWS telemetry, delivers it to S3 (optionally via SQS), and ingests it into Splunk running locally in Docker so you can practice investigations and build detections with real logs. It also includes Stratus Red Team to generate controlled “known-bad” activity for validation.

---

## Archeitecture
This flow shows how AWS telemetry is collected, stored, and ingested into Splunk so detections can be tested.
![Architecture: AWS to S3 (optional SQS) to Splunk Docker](https://github.com/user-attachments/assets/c8b22a6b-affa-441a-88df-82d818fa1a4e)

---

## Overview
This repo is a repeatable environment for setting up AWS logging and ingesting it into Splunk. The goal is simple: generate realistic AWS telemetry, run “known-bad” activity, and practice building detections based on what analysts actually see.

## What You Get (high level)
1. AWS telemetry
   - CloudTrail (management/API event trail) → S3
   - AWS Config (config change history) → S3
   - VPC Flow Logs (network telemetry) → S3
2. Ingestion into Splunk
   - Splunk runs locally via Docker (`soc/`)
   - `scripts/setup_splunk.py` creates indexes: `aws_cloudtrail`, `aws_config`, `aws_vpcflow`
   - Splunk Add-on for AWS ingests logs from S3 (and optionally from SQS)
3. Validation via red team activity
   - Stratus Red Team generates controlled “known-bad” AWS actions
   - Those actions land in CloudTrail and then in Splunk

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

## Quick Start (end-to-end)
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

### 4) Build AWS Resources (Terraform)
```powershell
cd infra
.\build.ps1
```
Save the bucket names and the Splunk IAM key + secret printed by the script.

### 5) Configure ingestion in Splunk Add-on
In the Splunk Add-on:
- Configuration → AWS Account: paste the Splunk IAM key + secret from Step 4
- Inputs → create three S3 inputs (main/recommended path):
  - CloudTrail bucket → index `aws_cloudtrail`
  - Config bucket → index `aws_config`
  - VPC Flow Logs bucket → index `aws_vpcflow`

Tip: start with plain S3 inputs. If you see SQS/Add-on errors, use the repo’s troubleshooting guidance below.

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

## How Ingestion Works (data flow)
At a high level, your pipeline is:

1. CloudTrail / AWS Config / VPC Flow Logs → S3
2. **Splunk Add-on → Splunk indexes (`aws_*`)**

Two ingestion modes exist:

- S3-only (recommended to start)
  - Splunk Add-on polls S3 and ingests new objects.
- SQS-based (optional)
  - Terraform can wire S3 ObjectCreated notifications → SQS queues
  - The Splunk Add-on can then poll SQS and fetch the referenced S3 objects.

Terraform supports SQS-based ingestion via `enable_sqs_s3_inputs` (default is `true`), but it only helps if you configure the Splunk Add-on inputs accordingly.

## Verify Data in Splunk
Start with:
`index=aws_cloudtrail earliest=-1h`
And repeat for:
- `index=aws_config earliest=-1h`
- `index=aws_vpcflow earliest=-1h`

If Splunk is empty, widen the time window (for example `earliest=-2h`) and wait a few minutes for AWS delivery + Splunk ingestion.

## Detection practice (starter searches)
These are good “first detections” tied to the telemetry your lab generates:

- Failed console login: `index=aws_cloudtrail eventName=ConsoleLogin errorMessage=*`
- IAM user created: `index=aws_cloudtrail eventName=CreateUser`
- Security group changes: `index=aws_cloudtrail eventName=AuthorizeSecurityGroupIngress OR RevokeSecurityGroupIngress`

For exercise ideas and dashboard steps, see [`guides/step-by-step.md`](guides/step-by-step.md) section 7.

## Troubleshooting
Common issues and fixes:

- Missing Splunk SDK (`splunklib.client` import error):
  - `pip install splunk-sdk`
- SQS / add-on errors:
  - Use plain S3 inputs first (no SQS). Keep ingestion simple until data is flowing.
- Destroy fails (for example `AccessDenied`):
  - Run `infra/destroy.ps1` using the same credentials you used for `build.ps1` (not your Stratus profile).

## Cleanup
Use build credentials (not Stratus):
```powershell
cd infra
.\destroy.ps1
```

## Notes on security
- Don’t commit `.env*` files or access keys.
- Treat the Splunk add-on IAM user (`soc-lab-splunk-addon`) as ingestion-only.
- Treat the Stratus IAM user (`soc-lab-stratus`) as attack-simulation-only.

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

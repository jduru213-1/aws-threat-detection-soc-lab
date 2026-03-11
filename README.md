# 🛡️ AWS Threat Detection SOC Lab

This project is a Terraform-and-script-driven lab for standing up **AWS logging** (CloudTrail, Config, VPC Flow Logs) into **S3** and ingesting that data into **Splunk** running locally in Docker. It gives you a repeatable, Infrastructure-as-Code path to practice threat detection and search without hand-wiring every bucket and input.

Once resources are deployed, use the [Splunk Add-on for AWS](https://splunkbase.splunk.com/app/1876/) to connect Splunk to the buckets; detailed flow and troubleshooting live in [guides/](guides/).

---

## ✨ Overview

The lab lets you:

- Run **Splunk Enterprise** locally via Docker with indexes prepped for AWS data.
- **Create AWS resources in one step** (`build.ps1`): three S3 buckets, CloudTrail, Config, VPC Flow Logs, and a least-privilege IAM user for Splunk.
- **Tear everything down** (`destroy.ps1`) so you don’t leave buckets or trails running.
- Practice **search and detection** over `aws_cloudtrail`, `aws_config`, and `aws_vpcflow` once data flows.
<img width="1330" height="778" alt="image" src="https://github.com/user-attachments/assets/c8b22a6b-affa-441a-88df-82d818fa1a4e" />


---

## 🧩 Components Overview

### 1. 🐳 Splunk (Docker)

Splunk runs in a container defined under `soc/`. First start can take a few minutes. Web UI and credentials are set in `soc/` (default admin password overridable via `soc/.env`).

### 2. 📚 Indexes

A small Python script (`scripts/setup_splunk.py`) creates the indexes the add-on expects: `aws_cloudtrail`, `aws_config`, `aws_vpcflow`. Run it after Splunk is up and reachable.

### 3. 📦 Splunk Add-on for AWS

Install from [Splunkbase](https://splunkbase.splunk.com/app/1876/) (or keep the `.tgz` under [soc/add-on/](soc/add-on/README.md)). Configure **AWS Account** and **S3 inputs** per bucket—use **plain S3** inputs only for this lab; the IAM user has S3 read, not SQS.

### 4. ☁️ AWS infrastructure (`infra/`)

Terraform provisions:

- **S3 buckets** for CloudTrail, Config, and VPC Flow Logs.
- **CloudTrail** trail writing to its bucket.
- **AWS Config** recorder and delivery channel to the Config bucket.
- **VPC Flow Logs** to the VPC Flow bucket.
- **IAM user** `soc-lab-splunk-addon` with read-only access to those buckets only.

`build.ps1` wraps `terraform init/plan/apply` and can install AWS CLI/Terraform if missing. `destroy.ps1` empties buckets then destroys.

---

## 🏗️ What gets created (AWS)

| Resource | Purpose |
|----------|---------|
| 3× S3 buckets | CloudTrail, Config, VPC Flow log storage; Splunk reads via add-on. |
| CloudTrail | API activity in the account. |
| AWS Config | Configuration change history. |
| VPC Flow Logs | Network flow metadata. |
| IAM user `soc-lab-splunk-addon` | Splunk uses this to list/get objects in the three buckets only. |

Build output prints bucket names and access keys—use those only in the add-on, not in code.

---

## ✅ Requirements

- **Docker Desktop** — Splunk container.
- **Python 3.10+** and `splunk-sdk` — index setup script.
- **AWS account** with permission to create the resources above.
- **PowerShell** — `infra/build.ps1` and `infra/destroy.ps1`.
- **AWS CLI configured** — run `aws configure` once so `build.ps1` doesn’t keep prompting.

---

## 🚀 Deployment Instructions

1. **Clone the repository** (or open this folder) and start Splunk:

   ```bash
   cd soc
   docker compose up -d
   ```

2. **Open Splunk** at `https://localhost:8000` and log in (see `soc/.env` or defaults in compose).

3. **Create indexes**:

   ```bash
   pip install splunk-sdk
   python ./scripts/setup_splunk.py
   ```

4. **Install the Splunk Add-on for AWS** via **Apps → Manage Apps → Install app from file**, then restart Splunk.

5. **Deploy AWS resources**:

   ```powershell
   cd infra
   .\build.ps1
   ```

   Confirm with `yes` when prompted. If execution policy blocks the script:

   ```powershell
   powershell -ExecutionPolicy Bypass -File .\build.ps1
   ```

6. **Configure the add-on** with the printed bucket names and `soc-lab-splunk-addon` keys—**Configuration → AWS Account** and **Inputs** (one S3 input per bucket).

End-to-end walkthrough: [guides/step-by-step.md](guides/step-by-step.md).

---

## 🔎 Searching once data is flowing

```
index=aws_cloudtrail earliest=-1h
index=aws_config earliest=-1h
index=aws_vpcflow earliest=-1h
```

---

## 🧹 Cleanup

To destroy AWS resources and avoid ongoing cost:

```powershell
cd infra
.\destroy.ps1
```

Confirm with `yes`. Splunk can keep running locally; only AWS is torn down. Advanced: Terraform directly—see [infra/README.md](infra/README.md).

---

## 🔐 Notes on security

- **Credentials**: Don’t commit access keys; use the IAM user only in the Splunk add-on UI.
- **SSH / network**: This lab is for learning; tighten security groups and access if you extend it toward production patterns.
- **SQS**: If the add-on UI shows SQS `AccessDenied`, use plain S3 inputs—the lab user is S3-only by design (see [guides/step-by-step.md § Step 5](guides/step-by-step.md#plain-s3-vs-sqs)).

---

## 🤝 Contributing

Improvements and fixes welcome via issues or pull requests.

---

## 🗂️ Project layout

| Path | Purpose |
|------|---------|
| `infra/` | Terraform; `build.ps1` / `destroy.ps1` |
| `soc/` | Docker Splunk, add-on `.tgz` folder |
| `scripts/` | Index creation |
| `guides/` | Step-by-step (Steps 1–7) |

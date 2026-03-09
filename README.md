# AWS Threat Detection SOC Lab

**Welcome to the AWS Threat Detection SOC Lab.**

This project gives you a hands-on environment to learn AWS threat detection with Splunk: run Splunk locally in Docker, stand up AWS logging (CloudTrail, Config, VPC Flow Logs) with one script, and practice detection. **Build** brings the environment up; **destroy** tears it down. No need to manage Terraform by hand unless you want to—the scripts handle it.

I built this as a way to combine threat detection, security monitoring, and cloud in one place. It’s a fun lab—use it to learn cloud security basics, test your detections, and practice building new ones.

---

## 📋 What you need

| Requirement | Purpose |
|-------------|---------|
| Docker Desktop (running) | Splunk in a container |
| Python 3.10+ | Splunk index setup script |
| AWS account | Lab AWS resources |
| PowerShell (Windows) | `build.ps1` / `destroy.ps1` |

---

## 🚀 Quick start

Do these in order.

**1. Start Splunk**

```bash
cd soc
docker compose up -d
```

Open https://localhost:8000 (login: `admin` / `ChangeMe123!`). Allow 2–5 min on first start.

**2. Create indexes** (from `soc`)

```bash
pip install splunk-sdk
python ./scripts/setup_splunk.py
```

Use your Splunk password when asked. Confirm indexes `aws_cloudtrail`, `aws_config`, `aws_vpcflow` in **Settings → Indexes**.

**3. Install Splunk Add-on for AWS** — In Splunk: **Apps → Manage Apps → Install app from file** (use the `.tgz` from [soc/add-on/README.md](soc/add-on/README.md)) → restart when prompted.

**4. Create AWS environment**

```powershell
cd infra
.\build.ps1
```

Enter AWS credentials, type **yes** to apply. Copy the **bucket names** and **Splunk user credentials** from the output for the Add-on. See [infra/README.md](infra/README.md) for details.

---

## 🛑 Shutting down

```powershell
cd infra
.\destroy.ps1
```

Enter credentials if prompted, type **yes** to confirm. The script empties S3 and removes all resources.

---

## 📦 After setup

- **Add-on:** Add your AWS account (key/secret from build output) and S3 inputs for each bucket so data flows into the indexes.
- **Practice:** Use `detections/` and `attacks/` once data is flowing.

---

## 📁 Project layout

| Path | Purpose |
|------|---------|
| `infra/` | AWS resources (Terraform). Use `build.ps1` / `destroy.ps1` or run Terraform directly. |
| `soc/` | Splunk (Docker), add-on drop folder, index setup. |
| `scripts/` | Splunk setup (e.g. index creation). |

---

## 🔧 Advanced

Run Terraform yourself from `infra/`: `terraform plan` / `apply` / `destroy`. See [infra/README.md](infra/README.md) for options (region, project name).

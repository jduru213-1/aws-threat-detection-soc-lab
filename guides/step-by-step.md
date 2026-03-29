# Step-by-step setup guide

This guide walks you through the full lab setup from scratch. Follow the steps in order — each one builds on the last.

For a shorter overview, see the repo [README](../README.md). For extra depth, see the project’s Medium blog.

---

## Before you start

Make sure you have everything below before running any commands.

### Tools to install

| Tool | Why |
|------|-----|
| [**Docker Desktop**](https://www.docker.com/products/docker-desktop/) | Runs Splunk locally on your machine |
| [**Python 3.10+**](https://www.python.org/downloads/) | Runs the index setup script |
| **Bash** ([**Git for Windows**](https://git-scm.com/download/win) includes Git Bash) | `build.sh` / `destroy.sh` are bash scripts (Git Bash works on Windows) |

### AWS account

Use a **personal or sandbox** AWS account, not production.

You do not need to run `aws configure` before Step 4, and you do not need to install the **AWS CLI** or **Terraform** yourself first. **`build.sh`** checks for both (and can help install them), then picks up credentials from the environment, `.env.soc-lab-admin`, the `soc-lab-admin` profile, or prompts you and saves keys there. After that it runs **`terraform`** to provision the stack.

If you install either tool yourself, use the [AWS CLI install guide](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html) and [Terraform install guide](https://developer.hashicorp.com/terraform/install).

### IAM permissions

**Read this before Step 4.**

- The identity whose keys you use with **`build.sh`** must be allowed to create IAM users, S3 buckets, SQS queues, CloudTrail, AWS Config, VPC Flow Logs, and related resources.
- A **restricted IAM user** will fail mid-apply with **`AccessDenied`**.
- For this lab, **`AdministratorAccess`** in a **non-production account** is typical.

### Quick checklist

- [ ] Docker Desktop is running
- [ ] Python 3.10+ is installed
- [ ] [IAM permissions](#iam-permissions) above reviewed before Step 4

---

## Step 1 — Start Splunk

Splunk is your local SIEM. It runs in Docker and is where you search logs and build detections.

```bash
cd soc
docker compose up -d
```

Open **https://localhost:8000** in your browser. Sign in with:

- **Username:** `admin`
- **Password:** `ChangeMe123!`

You can change the password by creating a **`soc/.env`** file next to `docker-compose.yml` before starting.

**Success:** The Splunk search page loads and you can sign in.

**Troubleshooting:** If the page does not load, confirm Docker Desktop is running and the container started (`docker ps`). Port **8000** must not be in use by another application.

---

## Step 2 — Create Splunk indexes

Indexes are where Splunk stores data. This lab uses **three** indexes — one per AWS log source — so searches and detections stay isolated.

```bash
pip install splunk-sdk
python ./scripts/setup_splunk.py
```

The script prompts for your Splunk password.

**Success:** In Splunk, go to **Settings → Indexes** and confirm these indexes exist:

| Index | Log source |
|-------|------------|
| `aws_cloudtrail` | AWS API activity |
| `aws_config` | Resource configuration changes |
| `aws_vpcflow` | Network traffic |

**Troubleshooting:** **`Connection refused`** — Splunk is not fully up yet; wait ~30 seconds and retry. **Import error** — run `pip install splunk-sdk` first.

---

## Step 3 — Install the Splunk Add-on for AWS

The add-on lets Splunk ingest from AWS. Install it now; you **configure** it in **Step 5** after AWS infrastructure exists.

1. Download the add-on from **[Splunkbase](https://splunkbase.splunk.com/app/1876/)** (free Splunk account may be required).
2. In Splunk: **Apps → Manage Apps → Install app from file**.
3. Upload the `.tgz` you downloaded.
4. Restart Splunk when prompted.

**Success:** After restart, the add-on appears under **Apps → Manage Apps**.

---

## Step 4 — Build the AWS infrastructure

This step uses Terraform (via **`build.sh`**) to create resources in AWS: S3 buckets, SQS queues, CloudTrail, AWS Config, VPC Flow Logs, and the IAM users Splunk and Stratus need.

**Note:**

- `build.sh` ensures the **AWS CLI** and **Terraform** are available and can help install either if they are missing.
- It resolves AWS credentials from the environment, **`.env.soc-lab-admin`** at the repo root, the **`soc-lab-admin`** profile, or an interactive prompt that saves keys to that profile.
- Use access keys for an identity that can apply this stack (see **Prerequisites** in the [repo README](../README.md)).
- If you install either tool yourself, see [**Before you start** → **AWS account**](#aws-account) for manual install links.

```bash
cd infra
./build.sh
```

Type **`yes`** when prompted to approve the Terraform apply. The build can take several minutes.

When it finishes, **save the output** — you need it in Step 5:

- The three **SQS queue URLs** (CloudTrail, Config, VPC Flow)
- The **`soc-lab-splunk-addon`** access key ID and secret key

You can retrieve values again with **`terraform output`** from the **`infra/`** directory.

**Success:** Terraform reports **Apply complete!** with no errors.

**Troubleshooting**

| Issue | What to do |
|-------|------------|
| `Permission denied` on the script | `chmod +x ./build.sh`, then retry |
| `AccessDenied` from AWS | IAM user lacks permissions — see [IAM permissions](#iam-permissions) under **Before you start** |
| Credential / auth errors | See the Step 4 note on credentials; check `.env.soc-lab-admin`, the `soc-lab-admin` profile, or run `./build.sh` again and enter keys when prompted |

---

## Step 5 — Connect Splunk to AWS

Wire Splunk to the queues Terraform created. When a new object lands in S3, SQS notifies Splunk; the add-on fetches and indexes it.

**Add AWS credentials to the add-on**

1. Open the **Splunk Add-on for AWS**.
2. **Configuration → AWS Account**.
3. **Add** the **`soc-lab-splunk-addon`** access key and secret from Step 4.

**Create three inputs (one per log source)**

**Inputs → Create New Input → SQS-based S3**:

| Input name (example) | Queue URL | Index |
|----------------------|-----------|--------|
| e.g. `cloudtrail-input` | CloudTrail SQS URL from Step 4 | `aws_cloudtrail` |
| e.g. `config-input` | Config SQS URL from Step 4 | `aws_config` |
| e.g. `vpcflow-input` | VPC Flow SQS URL from Step 4 | `aws_vpcflow` |

**Success:** After a few minutes, run:

```spl
index=aws_cloudtrail earliest=-30m
```

Repeat for `aws_config` and `aws_vpcflow`. First delivery can take a minute — retry if empty.

**Troubleshooting:** If nothing arrives after ~5 minutes, confirm queue URLs match **`terraform output`**, and that keys under **Configuration → AWS Account** are correct.

---

## Step 6 — Run attack simulations (Stratus)

Stratus Red Team generates realistic, safe AWS activity. Events show in CloudTrail within minutes and flow into Splunk.

```bash
cd attacks
source ./configure-stratus.sh
```

This sets the Stratus AWS profile for **this shell** — run it again in each new terminal.

```bash
stratus list --platform aws
stratus detonate <technique-id> --cleanup
```

**Success:** After detonation, search Splunk — for example an IAM technique may show:

```spl
index=aws_cloudtrail eventName=CreateUser
```

**Important**

- Use the **Stratus** profile only for simulations.
- Switch back to your **build/admin** credentials before **`./destroy.sh`**.

---

## Step 7 — Write detections and build dashboards

Use ingested data to practice searches that would catch real attacker behaviour.

**Starter searches**

```spl
# Failed console login attempts
index=aws_cloudtrail eventName=ConsoleLogin errorMessage=*

# New IAM user created
index=aws_cloudtrail eventName=CreateUser

# Security group opened to the internet
index=aws_cloudtrail eventName=AuthorizeSecurityGroupIngress

# Access key created (possible credential staging)
index=aws_cloudtrail eventName=CreateAccessKey
```

**Dashboards**

- Open **Dashboards → Create New Dashboard**.
- Add panels from saved searches (for example event counts over time, failed logins, IAM changes).

Share SPL you want to keep in [`detections/`](../detections/README.md).

---

## Teardown

**When you are done:** AWS charges accrue while the stack runs — tear down when you are finished for the day.

Use your **build** credentials — **not** the Stratus profile.

```bash
cd infra
./destroy.sh
```

- Confirm with **`yes`** when prompted.
- The script empties **S3 buckets** first (required before deletion), then destroys resources.
- You may be asked whether to **keep** the Splunk and Stratus IAM users. Answering **yes** is convenient if you will rebuild soon (avoids rotating keys).

**Success:** Terraform reports **Destroy complete!**; Cost Explorer should trend toward **near zero** for this stack.

- Run **`./destroy.sh --help`** to see **`--keep-iam-users`** and **`--delete-iam-users`**.
- Use those flags when you want to skip the interactive IAM prompts.

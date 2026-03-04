## AWS Threat Detection SOC Lab

### Overview

This repo contains a small, cost-safe AWS + Splunk lab for learning cloud threat detection. Follow the quick-start flow below to bring Splunk online, prep it for AWS logs, and keep moving toward the Terraform + ingestion phases.

### Why This Lab Exists

The goal is to give students and new analysts a realistic, hands-on way to explore AWS threat detection without large bills. You get to practice building detections, simulating attacks, and keeping costs predictable while learning how SOC teams operate in the cloud.

---

## Quick Start

### Step 1. Prerequisites

- Docker Desktop (running)
- Python 3.10+ (`python --version`)
- `pip` installed

Install the Splunk Python SDK:

```bash
pip install splunk-sdk
```

### Step 2. Start Splunk in Docker

From the `soc` folder:

```bash
cd soc
docker compose up -d
```

Notes:

- First startup can take 2-5 minutes.
- Check status: `docker compose ps`
- You should see `soc-splunk` with STATUS `Up`.

Open Splunk Web: https://localhost:8000

- Click through the certificate warning (Advanced -> Continue).
- Default login (unless changed in `.env`):
  - Username: `admin`
  - Password: `ChangeMe123!`

### Step 3. Create AWS Indexes (Python script)

The script `soc/scripts/setup_splunk.py` creates these indexes in Splunk:

- `aws_cloudtrail`
- `aws_config`
- `aws_guardduty`
- `aws_vpcflow`

Run it from `soc`:

```bash
cd soc
python ./scripts/setup_splunk.py
```

- Enter the Splunk admin password when prompted.
- Verify in Splunk: go to Settings -> Indexes and confirm the four indexes exist.

### Step 4. Install Splunk Add-on for AWS (manual step)

Download the add-on:

- Visit https://splunkbase.splunk.com/app/1876/
- Download the Splunk Add-on for AWS (`.spl` or `.tgz`).

Install in Splunk:

- In Splunk Web: Settings -> Manage Apps -> Install app from file.
- Select the downloaded file and upload.
- Restart Splunk when prompted.

Confirm:

- After restart, go to Settings -> Manage Apps.
- You should see Splunk Add-on for AWS listed.

---

## Next Steps

- Use Terraform under `infra/` to build the minimal AWS environment.
- Configure log ingestion so CloudTrail, Config, and VPC Flow logs land in the indexes above.
- Iterate on detections (`detections/`) and attack simulations (`attacks/`) once data is flowing.

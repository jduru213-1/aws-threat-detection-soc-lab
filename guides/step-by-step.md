# Step-by-step

Skip steps you’ve already done. For more depth, see the project’s Medium blog.

---

## Requirements

Docker Desktop · Python 3.10+ · AWS account · Bash shell · `aws configure` (so build doesn’t keep prompting)

---

## 1. Docker Splunk

```bash
cd soc
docker compose up -d
```

Open https://localhost:8000 — login `admin`, password in `soc/.env` or compose default. Start/stop via Docker Desktop.

---

## 2. Indexes

```bash
pip install splunk-sdk
python ./scripts/setup_splunk.py
```

Confirm **Settings → Indexes**: `aws_cloudtrail`, `aws_config`, `aws_vpcflow`.

---

## 3. AWS add-on

1. Download [Splunk Add-on for AWS](https://splunkbase.splunk.com/app/1876/)
2. Splunk → **Apps → Manage Apps → Install app from file** → upload → restart

Inputs come in Step 5.

---

## 4. Build AWS

```bash
cd infra
./build.sh
```

Confirm with `yes`. **Save from output:** bucket names, `soc-lab-splunk-addon` access key + secret.

- Credentials: `aws configure` to stop repeated prompts.
- If command fails with permission denied: `chmod +x ./build.sh` then rerun.

---

## 5. Data ingestion (SQS-based S3)

1. Add-on **Configuration → AWS Account** — paste Splunk IAM keys from Step 4.
2. **Inputs → Create New Input** — choose **SQS-based S3** and create three inputs:

| Type | Queue (from Terraform outputs) | Index |
|------|--------------------------------|--------|
| CloudTrail | cloudtrail SQS queue | `aws_cloudtrail` |
| Config | config SQS queue | `aws_config` |
| VPC Flow Logs | vpcflow SQS queue | `aws_vpcflow` |

Queues are printed by `build.sh` (and defined in `infra/outputs_sqs.tf`). The Splunk add-on IAM user already has SQS permissions via Terraform.

Verify: `index=aws_cloudtrail earliest=-30m` (and `aws_config`, `aws_vpcflow`). Wait and retry if empty.

---

## 6. Red team (Stratus)

Use [attacks/README.md](attacks/README.md): `cd attacks` -> `source ./configure-stratus.sh` -> `stratus list --platform aws` and `stratus detonate <id> --cleanup`. Events show in CloudTrail -> Splunk.

---

## 7. Detections / dashboard

Example Splunk searches:

- Failed console login: `index=aws_cloudtrail eventName=ConsoleLogin errorMessage=*`
- IAM user created: `index=aws_cloudtrail eventName=CreateUser`
- Security group change: `index=aws_cloudtrail eventName=AuthorizeSecurityGroupIngress OR RevokeSecurityGroupIngress`

**Dashboard:** Splunk → Dashboards → Create; add panels from saved searches (event counts, timeline, failed logins).

---

## Cleanup

```bash
cd infra
./destroy.sh
```

Use **build credentials** (not Stratus). Confirm with `yes`.

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Script blocked | `chmod +x ./build.sh && ./build.sh` |
| SQS / add-on errors | Use plain S3 inputs; clear Assume Role in AWS Account config |
| Destroy fails (AccessDenied) | Run destroy in a terminal where you haven’t set Stratus profile; use same creds as build |

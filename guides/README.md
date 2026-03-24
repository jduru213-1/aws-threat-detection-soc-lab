# Guides

Use these guides if you want a clear, click-by-click walkthrough.

| Step | Link | What you do |
|------|------|-------------|
| 1 | [Docker Splunk](step-by-step.md#1-docker-splunk) | Start Splunk locally |
| 2 | [Indexes](step-by-step.md#2-indexes) | Create Splunk indexes |
| 3 | [AWS add-on](step-by-step.md#3-aws-add-on) | Install Splunk Add-on for AWS |
| 4 | [Build AWS](step-by-step.md#4-build-aws) | Run `./build.sh` |
| 5 | [Ingestion](step-by-step.md#5-data-ingestion) | Configure SQS-based inputs |
| 6 | [Red team](step-by-step.md#6-red-team-stratus) | Run Stratus attack simulations |
| 7 | [Detections](step-by-step.md#7-detections--dashboard) | Review detections and dashboards |

When you're done, tear down with `cd infra && ./destroy.sh` (using build/admin credentials).

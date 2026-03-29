# Detections

Material for Splunk in this lab. Indexes: `aws_cloudtrail`, `aws_config`, `aws_vpcflow`.

- SPL you paste into Search, a short note about a saved search, or a brief write-up — use whatever makes it easy to reproduce or adapt.

## Contributing

- Filenames should make the topic obvious (e.g. `failed-console-login.spl`, `iam-create-user.md`).
- In each file: index, fields that matter (e.g. `eventName`), and what activity the search is meant to surface.
- Pull requests go to `main`. A large change can start with an issue.

Example SPL is in the [main README](../README.md) under Detection examples. For traffic you can search against, use [Stratus Red Team](https://stratus-red-team.cloud/attack-techniques/AWS/) in this lab’s AWS account.

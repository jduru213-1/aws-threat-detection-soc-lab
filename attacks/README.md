# Attacks (Stratus Red Team)

This folder helps you generate safe, controlled "known-bad" cloud activity for detection testing.

## Quick setup

1. Build the AWS lab resources:
   ```bash
   cd infra
   ./build.sh
   ```
2. Configure Stratus in your shell:
   ```bash
   cd attacks
   source ./configure-stratus.sh
   ```

## Run a simulation

```bash
stratus list --platform aws
stratus detonate <technique-id> --cleanup
```

These actions create telemetry that flows into CloudTrail and then into Splunk, where you can validate detections.

## Good starter scenarios

- Suspicious login behavior
- IAM privilege escalation actions
- Security group exposure changes
- Unexpected compute activity
- High-volume S3 access patterns

## Important notes

- If you open a new terminal, run `source ./configure-stratus.sh` again.
- For teardown, switch back to build/admin credentials before `./destroy.sh`.
- Use Stratus only in a sandbox/test account.

Reference: [Stratus usage guide](https://stratus-red-team.cloud/user-guide/usage/)
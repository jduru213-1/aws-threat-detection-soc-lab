#!/usr/bin/env bash
# =============================================================================
# build.sh — apply Terraform for the SOC lab AWS stack
# =============================================================================
# Runs from the directory that contains versions.tf (this script may live in
# repo root or under infra/; INFRA_DIR is resolved automatically).
#
# Flow: check CLI tools → load optional .env.soc-lab-admin → resolve AWS
# credentials (env, profile soc-lab-admin, or prompt) → terraform init →
# optionally import pre-existing IAM users/keys → plan → apply → print outputs
# → write .env.splunk and .env.stratus at repo root for Splunk / Stratus.
#
# Usage:
#   ./build.sh
#   ./build.sh --auto-approve    # apply without typing 'yes' at apply
#   ./build.sh --skip-apply      # stop after plan (run: terraform apply tfplan)
# =============================================================================
set -euo pipefail

AUTO_APPROVE=false
SKIP_APPLY=false
for arg in "$@"; do
  case "$arg" in
    --auto-approve) AUTO_APPROVE=true ;;
    --skip-apply) SKIP_APPLY=true ;;
    *)
      echo "Unknown argument: $arg"
      echo "Usage: ./build.sh [--auto-approve] [--skip-apply]"
      exit 1
      ;;
  esac
done

# Resolve infra directory: supports running as ./infra/build.sh or ./build.sh from repo root.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -f "$SCRIPT_DIR/versions.tf" ]]; then
  INFRA_DIR="$SCRIPT_DIR"
else
  INFRA_DIR="$SCRIPT_DIR/infra"
fi
cd "$INFRA_DIR"
echo "Working directory: $INFRA_DIR"

# -----------------------------------------------------------------------------
# Helpers: open docs in browser; ensure aws/terraform/python exist (winget on Windows optional)
# -----------------------------------------------------------------------------
open_link() {
  local url="$1"
  if command -v powershell.exe >/dev/null 2>&1; then
    powershell.exe -NoProfile -Command "Start-Process '$url'" >/dev/null 2>&1 || true
  elif command -v cmd.exe >/dev/null 2>&1; then
    cmd.exe /c start "$url" >/dev/null 2>&1 || true
  elif command -v xdg-open >/dev/null 2>&1; then
    xdg-open "$url" >/dev/null 2>&1 || true
  fi
}

ensure_cmd() {
  local cmd="$1"
  local app_name="$2"
  local doc_url="$3"
  local winget_id="${4:-}"
  if command -v "$cmd" >/dev/null 2>&1; then
    return 0
  fi

  echo "Missing required application: $app_name"
  echo "Download/Install guide: $doc_url"
  read -r -p "Would you like to open the download page now? (yes/no, default: yes): " open_ans
  open_ans="${open_ans,,}"
  if [[ -z "$open_ans" || "$open_ans" == "y" || "$open_ans" == "yes" ]]; then
    open_link "$doc_url"
  fi

  if [[ -n "$winget_id" && "$(command -v winget || true)" != "" ]]; then
    read -r -p "Would you like the script to install $app_name via winget now? (yes/no, default: no): " inst_ans
    inst_ans="${inst_ans,,}"
    if [[ "$inst_ans" == "y" || "$inst_ans" == "yes" ]]; then
      winget install "$winget_id" --accept-package-agreements --accept-source-agreements || true
    fi
  fi

  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "$app_name is still missing. Install it, restart terminal, then rerun this script."
    exit 1
  fi
}

ensure_cmd aws "AWS CLI" "https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html" "Amazon.AWSCLI"
ensure_cmd terraform "Terraform" "https://developer.hashicorp.com/terraform/install" "Hashicorp.Terraform"
ensure_cmd python "Python 3" "https://www.python.org/downloads/"

REPO_ROOT="$(cd "$INFRA_DIR/.." && pwd)"
ADMIN_ENV_FILE="$REPO_ROOT/.env.soc-lab-admin"

# Simple KEY=value loader (supports BOM and CRLF). Optional file for CI or repeated runs.
load_admin_env() {
  local env_file="$1"
  [[ -f "$env_file" ]] || return 0
  while IFS= read -r line || [[ -n "$line" ]]; do
    line="${line//$'\ufeff'/}"
    line="${line%$'\r'}"
    [[ -z "$line" || "$line" =~ ^[[:space:]]*# ]] && continue
    if [[ "$line" =~ ^[[:space:]]*([A-Za-z_][A-Za-z0-9_]*)=(.*)$ ]]; then
      local key="${BASH_REMATCH[1]}"
      local val="${BASH_REMATCH[2]}"
      export "$key=$val"
    fi
  done < "$env_file"
}

# Map SOC_LAB_ADMIN_* into standard AWS_* / TF_VAR_aws_region when present.
if [[ -f "$ADMIN_ENV_FILE" ]]; then
  load_admin_env "$ADMIN_ENV_FILE"
  [[ -n "${SOC_LAB_ADMIN_AWS_ACCESS_KEY_ID:-}" ]] && export AWS_ACCESS_KEY_ID="$SOC_LAB_ADMIN_AWS_ACCESS_KEY_ID"
  [[ -n "${SOC_LAB_ADMIN_AWS_SECRET_ACCESS_KEY:-}" ]] && export AWS_SECRET_ACCESS_KEY="$SOC_LAB_ADMIN_AWS_SECRET_ACCESS_KEY"
  [[ -n "${SOC_LAB_ADMIN_AWS_PROFILE:-}" ]] && export AWS_PROFILE="$SOC_LAB_ADMIN_AWS_PROFILE"
  [[ -n "${SOC_LAB_ADMIN_AWS_REGION:-}" ]] && export AWS_REGION="$SOC_LAB_ADMIN_AWS_REGION"
  [[ -n "${SOC_LAB_ADMIN_AWS_REGION:-}" ]] && export TF_VAR_aws_region="$SOC_LAB_ADMIN_AWS_REGION"
fi

LAB_PROFILE="${LAB_PROFILE:-soc-lab-admin}"

# If access keys are not in the environment, try default credential chain, then profile soc-lab-admin.
if [[ -z "${AWS_ACCESS_KEY_ID:-}" || -z "${AWS_SECRET_ACCESS_KEY:-}" ]]; then
  if ! aws sts get-caller-identity >/dev/null 2>&1; then
    if aws sts get-caller-identity --profile "$LAB_PROFILE" >/dev/null 2>&1; then
      export AWS_PROFILE="$LAB_PROFILE"
      echo "[AWS] Reusing saved profile: $LAB_PROFILE"
    fi
  fi
fi

# Last resort: prompt and persist under soc-lab-admin so destroy/build can reuse.
if [[ -z "${AWS_ACCESS_KEY_ID:-}" || -z "${AWS_SECRET_ACCESS_KEY:-}" ]]; then
  if ! aws sts get-caller-identity >/dev/null 2>&1; then
    echo "[AWS] No credentials found. Enter your AWS credentials."
    read -r -p "AWS Access Key ID: " AWS_ACCESS_KEY_ID
    read -r -s -p "AWS Secret Access Key: " AWS_SECRET_ACCESS_KEY
    echo
    export AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY
    read -r -p "AWS region (press Enter for us-east-1): " region_prompt
    if [[ -n "${region_prompt}" ]]; then
      export TF_VAR_aws_region="$region_prompt"
    fi
    aws configure set aws_access_key_id "$AWS_ACCESS_KEY_ID" --profile "$LAB_PROFILE"
    aws configure set aws_secret_access_key "$AWS_SECRET_ACCESS_KEY" --profile "$LAB_PROFILE"
    if [[ -n "${region_prompt}" ]]; then
      aws configure set region "$region_prompt" --profile "$LAB_PROFILE"
    else
      aws configure set region "us-east-1" --profile "$LAB_PROFILE"
    fi
    echo "[AWS] Saved credentials to profile: $LAB_PROFILE"
  fi
fi

terraform version
echo

# Always run init: keeps .terraform providers aligned with .terraform.lock.hcl and versions.tf.
# -upgrade=false avoids bumping provider versions on every run.
echo "[Build] terraform init (lock-file consistent)..."
terraform init -input=false -upgrade=false
echo

tf_state_has() {
  terraform state list 2>/dev/null | grep -Fxq "$1"
}

import_if_missing() {
  local addr="$1"
  local import_id="$2"
  [[ -z "$import_id" ]] && return 0
  if ! tf_state_has "$addr"; then
    echo "[Build] Importing existing resource into state: $addr"
    terraform import "$addr" "$import_id" >/dev/null || true
  fi
}

# -----------------------------------------------------------------------------
# Drift recovery: if IAM users already exist in AWS (e.g. partial apply) but are
# absent from state, import them so apply does not fail on "already exists".
# -----------------------------------------------------------------------------
PROJECT_NAME="soc-lab"
SPLUNK_USER="${PROJECT_NAME}-splunk-addon"
STRATUS_USER="${PROJECT_NAME}-stratus"

if aws iam get-user --user-name "$SPLUNK_USER" >/dev/null 2>&1; then
  import_if_missing "aws_iam_user.splunk[0]" "$SPLUNK_USER"
  import_if_missing "aws_iam_user_policy.splunk_cloudtrail[0]" "${SPLUNK_USER}:${PROJECT_NAME}-splunk-cloudtrail"
  import_if_missing "aws_iam_user_policy.splunk_config[0]" "${SPLUNK_USER}:${PROJECT_NAME}-splunk-config"
  import_if_missing "aws_iam_user_policy.splunk_vpcflow[0]" "${SPLUNK_USER}:${PROJECT_NAME}-splunk-vpcflow"
  import_if_missing "aws_iam_user_policy.splunk_sqs[0]" "${SPLUNK_USER}:${PROJECT_NAME}-splunk-sqs"
  SPLUNK_KEY_ID="$(aws iam list-access-keys --user-name "$SPLUNK_USER" --query 'AccessKeyMetadata[0].AccessKeyId' --output text 2>/dev/null || true)"
  [[ "$SPLUNK_KEY_ID" != "None" && -n "$SPLUNK_KEY_ID" ]] && import_if_missing "aws_iam_access_key.splunk[0]" "$SPLUNK_KEY_ID"
fi

if aws iam get-user --user-name "$STRATUS_USER" >/dev/null 2>&1; then
  import_if_missing "aws_iam_user.stratus[0]" "$STRATUS_USER"
  STRATUS_KEY_ID="$(aws iam list-access-keys --user-name "$STRATUS_USER" --query 'AccessKeyMetadata[0].AccessKeyId' --output text 2>/dev/null || true)"
  [[ "$STRATUS_KEY_ID" != "None" && -n "$STRATUS_KEY_ID" ]] && import_if_missing "aws_iam_access_key.stratus[0]" "$STRATUS_KEY_ID"
fi

echo
echo "[Build] terraform plan..."
terraform plan -out=tfplan
echo

if [[ "$SKIP_APPLY" == "true" ]]; then
  echo "[Build] SkipApply enabled. Run: terraform apply tfplan"
  exit 0
fi

if [[ "$AUTO_APPROVE" == "true" ]]; then
  echo "[Build] terraform apply (auto-approve)..."
  terraform apply -auto-approve tfplan
else
  echo "[Build] terraform apply..."
  terraform apply tfplan
fi

echo
echo "=== Build complete ==="
terraform output
echo

# -----------------------------------------------------------------------------
# Write git-ignored env files for local tooling (Splunk add-on keys, Stratus).
# Stratus file includes STRATUS_AWS_REGION so attacks/configure-stratus.sh does
# not need terraform output when the region is already known from apply.
# -----------------------------------------------------------------------------
TF_JSON="$(terraform output -json 2>/dev/null || true)"
if [[ -n "$TF_JSON" ]]; then
  python - "$REPO_ROOT" "$TF_JSON" <<'PY'
import json
import os
import sys

repo_root = sys.argv[1]
raw = sys.argv[2]
if not raw.strip():
    raise SystemExit(0)
out = json.loads(raw)

def write_env(path, lines):
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

splunk_key = ((out.get("splunk_iam_access_key_id") or {}).get("value"))
splunk_secret = ((out.get("splunk_iam_secret_key") or {}).get("value"))
if splunk_key and splunk_secret:
    write_env(
        os.path.join(repo_root, ".env.splunk"),
        [
            "# Splunk Add-on AWS credentials (local only, git-ignored)",
            f"SPLUNK_AWS_ACCESS_KEY_ID={splunk_key}",
            f"SPLUNK_AWS_SECRET_ACCESS_KEY={splunk_secret}",
        ],
    )

stratus_key = ((out.get("stratus_iam_access_key_id") or {}).get("value"))
stratus_secret = ((out.get("stratus_iam_secret_key") or {}).get("value"))
region = ((out.get("aws_region") or {}).get("value")) or ""
if stratus_key and stratus_secret:
    lines = [
        "# Stratus Red Team AWS credentials (local only, git-ignored)",
        f"STRATUS_AWS_ACCESS_KEY_ID={stratus_key}",
        f"STRATUS_AWS_SECRET_ACCESS_KEY={stratus_secret}",
    ]
    if region:
        lines.append(f"STRATUS_AWS_REGION={region}")
    write_env(os.path.join(repo_root, ".env.stratus"), lines)
PY
fi

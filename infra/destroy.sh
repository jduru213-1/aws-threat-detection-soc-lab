#!/usr/bin/env bash
# =============================================================================
# destroy.sh — tear down the SOC lab AWS stack
# =============================================================================
# Run with the same admin/build identity used for build (not the Stratus user).
# Order of operations:
#   1) Resolve AWS credentials (same pattern as build.sh).
#   2) Refuse if caller is the Stratus principal (wrong role for teardown).
#   3) Empty all lab S3 buckets (versioned deletes) so terraform can destroy them.
#   4) Optionally keep Splunk/Stratus IAM users by removing them from state only,
#      or delete access keys so Terraform can destroy the users.
#   5) terraform destroy
#
# Usage:
#   ./destroy.sh
#   ./destroy.sh --keep-iam-users | --delete-iam-users
#   ./destroy.sh --help
# =============================================================================
set -euo pipefail

KEEP_IAM_USERS=""
for arg in "$@"; do
  case "$arg" in
    --keep-iam-users) KEEP_IAM_USERS="yes" ;;
    --delete-iam-users) KEEP_IAM_USERS="no" ;;
    --help|-h)
      cat <<'EOF'
Usage: ./destroy.sh [--keep-iam-users | --delete-iam-users]

Options:
  --keep-iam-users    Keep Splunk/Stratus IAM users and their access keys.
  --delete-iam-users  Delete IAM access keys before terraform destroy.

If no option is provided, the script prompts interactively.
EOF
      exit 0
      ;;
    *)
      echo "Unknown argument: $arg"
      echo "Run ./destroy.sh --help"
      exit 1
      ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -f "$SCRIPT_DIR/versions.tf" ]]; then
  INFRA_DIR="$SCRIPT_DIR"
else
  INFRA_DIR="$SCRIPT_DIR/infra"
fi
cd "$INFRA_DIR"

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

if [[ -f "$ADMIN_ENV_FILE" ]]; then
  load_admin_env "$ADMIN_ENV_FILE"
  [[ -n "${SOC_LAB_ADMIN_AWS_ACCESS_KEY_ID:-}" ]] && export AWS_ACCESS_KEY_ID="$SOC_LAB_ADMIN_AWS_ACCESS_KEY_ID"
  [[ -n "${SOC_LAB_ADMIN_AWS_SECRET_ACCESS_KEY:-}" ]] && export AWS_SECRET_ACCESS_KEY="$SOC_LAB_ADMIN_AWS_SECRET_ACCESS_KEY"
  [[ -n "${SOC_LAB_ADMIN_AWS_PROFILE:-}" ]] && export AWS_PROFILE="$SOC_LAB_ADMIN_AWS_PROFILE"
  [[ -n "${SOC_LAB_ADMIN_AWS_REGION:-}" ]] && export AWS_REGION="$SOC_LAB_ADMIN_AWS_REGION"
fi

LAB_PROFILE="${LAB_PROFILE:-soc-lab-admin}"

if [[ -z "${AWS_ACCESS_KEY_ID:-}" || -z "${AWS_SECRET_ACCESS_KEY:-}" ]]; then
  if ! aws sts get-caller-identity >/dev/null 2>&1; then
    if aws sts get-caller-identity --profile "$LAB_PROFILE" >/dev/null 2>&1; then
      export AWS_PROFILE="$LAB_PROFILE"
      echo "[AWS] Reusing saved profile: $LAB_PROFILE"
    fi
  fi
fi

if [[ -z "${AWS_ACCESS_KEY_ID:-}" || -z "${AWS_SECRET_ACCESS_KEY:-}" ]]; then
  if ! aws sts get-caller-identity >/dev/null 2>&1; then
    echo "[AWS] No credentials found. Enter the same credentials used for build."
    read -r -p "AWS Access Key ID: " AWS_ACCESS_KEY_ID
    read -r -s -p "AWS Secret Access Key: " AWS_SECRET_ACCESS_KEY
    echo
    export AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY
    aws configure set aws_access_key_id "$AWS_ACCESS_KEY_ID" --profile "$LAB_PROFILE"
    aws configure set aws_secret_access_key "$AWS_SECRET_ACCESS_KEY" --profile "$LAB_PROFILE"
    if ! aws configure get region --profile "$LAB_PROFILE" >/dev/null 2>&1; then
      aws configure set region "us-east-1" --profile "$LAB_PROFILE"
    fi
    echo "[AWS] Saved credentials to profile: $LAB_PROFILE"
  fi
fi

# Stratus profile is for simulations; teardown must use admin/build credentials.
CALLER_ARN="$(aws sts get-caller-identity --query Arn --output text 2>/dev/null || true)"
if [[ "$CALLER_ARN" == *"soc-lab-stratus"* ]]; then
  echo "Destroy is running as soc-lab-stratus. Use your build/admin profile instead."
  exit 1
fi

# -----------------------------------------------------------------------------
# S3: empty buckets before destroy (AWS cannot delete non-empty buckets).
# Prefer terraform output names; merge with state scan for any bucket in state.
# -----------------------------------------------------------------------------
collect_buckets_from_outputs() {
  local names=()
  local val
  for key in cloudtrail_bucket_name config_bucket_name vpc_flow_logs_bucket_name; do
    val="$(terraform output -raw "$key" 2>/dev/null || true)"
    if [[ -n "$val" && "$val" != "null" ]]; then
      names+=("$val")
    fi
  done
  printf '%s\n' "${names[@]}"
}

collect_buckets_from_state() {
  terraform state pull 2>/dev/null | python - <<'PY'
import json, sys
raw = sys.stdin.read().strip()
if not raw:
    raise SystemExit(0)
try:
    data = json.loads(raw)
except Exception:
    raise SystemExit(0)
for r in data.get("resources", []):
    if r.get("type") != "aws_s3_bucket":
        continue
    for i in r.get("instances", []):
        bid = (((i or {}).get("attributes") or {}).get("id"))
        if isinstance(bid, str) and bid:
            print(bid)
PY
}

mapfile -t BUCKETS < <(
  {
    collect_buckets_from_outputs
    collect_buckets_from_state
  } | sort -u
)

# Delete all object versions and delete markers in batches (required for versioned buckets).
empty_bucket() {
  local bucket="$1"
  echo "  $bucket ..."
  while true; do
    local payload
    payload="$(aws s3api list-object-versions --bucket "$bucket" --output json 2>/dev/null || true)"
    [[ -z "$payload" ]] && break
    local delete_json
    delete_json="$(python - <<'PY' "$payload"
import json, sys
raw = sys.argv[1]
try:
    j = json.loads(raw)
except Exception:
    print("")
    raise SystemExit(0)
objs = []
for k in ("Versions", "DeleteMarkers"):
    for o in j.get(k, []) or []:
        key = o.get("Key")
        vid = o.get("VersionId")
        if key:
            item = {"Key": key}
            if vid is not None:
                item["VersionId"] = vid
            objs.append(item)
if objs:
    print(json.dumps({"Objects": objs}, separators=(",", ":")))
else:
    print("")
PY
)"
    [[ -z "$delete_json" ]] && break
    aws s3api delete-objects --bucket "$bucket" --delete "$delete_json" >/dev/null
  done
  aws s3 rm "s3://$bucket/" --recursive --quiet >/dev/null 2>&1 || true
}

if [[ "${#BUCKETS[@]}" -gt 0 ]]; then
  echo "Emptying S3 buckets:"
  for b in "${BUCKETS[@]}"; do
    empty_bucket "$b"
  done
else
  echo "No bucket outputs in state (already destroyed or not applied)."
fi

# -----------------------------------------------------------------------------
# IAM: keep users/keys for rebuilds (state rm only) or delete keys so destroy can remove users.
# -----------------------------------------------------------------------------
if [[ -z "$KEEP_IAM_USERS" ]]; then
  read -r -p "Keep IAM users and access keys for Splunk/Stratus? (yes/no, default: yes): " PRESERVE
  PRESERVE="${PRESERVE,,}"
  if [[ -z "$PRESERVE" ]]; then
    PRESERVE="yes"
  fi
else
  PRESERVE="$KEEP_IAM_USERS"
  echo "Keep IAM users and access keys for Splunk/Stratus: $PRESERVE"
fi

if [[ "$PRESERVE" == "y" || "$PRESERVE" == "yes" ]]; then
  echo "Keeping IAM users/keys. Removing IAM resources from Terraform state..."
  for addr in \
    "aws_iam_access_key.splunk[0]" \
    "aws_iam_user_policy.splunk_cloudtrail[0]" \
    "aws_iam_user_policy.splunk_config[0]" \
    "aws_iam_user_policy.splunk_vpcflow[0]" \
    "aws_iam_user_policy.splunk_sqs[0]" \
    "aws_iam_user.splunk[0]" \
    "aws_iam_access_key.stratus[0]" \
    "aws_iam_user_policy_attachment.stratus_power_user[0]" \
    "aws_iam_user_policy_attachment.stratus_iam_full[0]" \
    "aws_iam_user.stratus[0]" \
    "aws_iam_access_key.stratus" \
    "aws_iam_user.stratus"
  do
    terraform state rm "$addr" >/dev/null 2>&1 || true
  done
else
  for user in "soc-lab-splunk-addon" "soc-lab-stratus"; do
    mapfile -t key_ids < <(aws iam list-access-keys --user-name "$user" --query 'AccessKeyMetadata[].AccessKeyId' --output text 2>/dev/null | tr '\t' '\n' || true)
    if [[ "${#key_ids[@]}" -gt 0 ]]; then
      echo "Deleting IAM access keys for $user ..."
      for k in "${key_ids[@]}"; do
        [[ -n "$k" ]] && aws iam delete-access-key --user-name "$user" --access-key-id "$k" >/dev/null 2>&1 || true
      done
    fi
  done
fi

echo "Running terraform destroy..."
terraform destroy

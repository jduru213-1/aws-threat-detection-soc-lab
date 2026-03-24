#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
ENV_PATH="$REPO_ROOT/.env.stratus"
PROFILE="stratus-lab"
REGION="us-east-1"

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

# Ensure Go-installed binaries (including stratus) are discoverable in this shell.
if command -v go >/dev/null 2>&1; then
  export PATH="$(go env GOPATH)/bin:$PATH"
fi

ensure_cmd() {
  local cmd="$1"
  local app_name="$2"
  local doc_url="$3"
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
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "$app_name is still missing. Install it, restart terminal, then rerun this script."
    exit 1
  fi
}

install_stratus_with_go() {
  if command -v stratus >/dev/null 2>&1; then
    return 0
  fi

  echo "Stratus CLI is not installed."
  echo "Recommended install method: Go (go install ...)."
  echo "Guide: https://stratus-red-team.cloud/user-guide/getting-started/"

  if ! command -v go >/dev/null 2>&1; then
    ensure_cmd go "Go 1.23+ (Linux)" "https://go.dev/dl/"
  fi

  read -r -p "Would you like to install Stratus now with Go? (yes/no, default: yes): " go_ans
  go_ans="${go_ans,,}"
  if [[ -z "$go_ans" || "$go_ans" == "y" || "$go_ans" == "yes" ]]; then
    go install -v github.com/datadog/stratus-red-team/v2/cmd/stratus@latest
    export PATH="$(go env GOPATH)/bin:$PATH"
  fi

  if ! command -v stratus >/dev/null 2>&1; then
    echo "Stratus is still missing. Install manually from: https://stratus-red-team.cloud/user-guide/getting-started/"
    exit 1
  fi
}

ensure_cmd aws "AWS CLI" "https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html"
ensure_cmd awk "awk" "https://gitforwindows.org/"
ensure_cmd sed "sed" "https://gitforwindows.org/"
install_stratus_with_go

if [[ ! -f "$ENV_PATH" ]]; then
  echo "Missing .env.stratus at $ENV_PATH. Run infra/build.sh first."
  exit 1
fi

ACCESS_KEY_ID="$(grep -E '^(STRATUS_AWS_ACCESS_KEY_ID|AWS_ACCESS_KEY_ID)=' "$ENV_PATH" | tail -n1 | cut -d= -f2-)"
SECRET_ACCESS_KEY="$(grep -E '^(STRATUS_AWS_SECRET_ACCESS_KEY|AWS_SECRET_ACCESS_KEY)=' "$ENV_PATH" | tail -n1 | cut -d= -f2-)"

if [[ -z "$ACCESS_KEY_ID" || -z "$SECRET_ACCESS_KEY" ]]; then
  echo ".env.stratus must contain STRATUS_AWS_ACCESS_KEY_ID and STRATUS_AWS_SECRET_ACCESS_KEY."
  exit 1
fi

mkdir -p "$HOME/.aws"
CRED_PATH="$HOME/.aws/credentials"
touch "$CRED_PATH"

TMP_FILE="$(mktemp)"
awk -v profile="$PROFILE" '
BEGIN { in_section=0 }
/^\s*\[.*\]\s*$/ {
  in_section = ($0 ~ "^[[:space:]]*\\[" profile "\\][[:space:]]*$")
}
{
  if (!in_section) print $0
}
' "$CRED_PATH" > "$TMP_FILE"

{
  echo
  echo "[$PROFILE]"
  echo "aws_access_key_id = $ACCESS_KEY_ID"
  echo "aws_secret_access_key = $SECRET_ACCESS_KEY"
} >> "$TMP_FILE"

mv "$TMP_FILE" "$CRED_PATH"

export AWS_PROFILE="$PROFILE"
export AWS_REGION="$REGION"

echo "Profile '$PROFILE' updated in $CRED_PATH"
echo "Session: AWS_PROFILE=$PROFILE AWS_REGION=$REGION"
echo
echo "Run:"
echo "  stratus list --platform aws"
echo "  stratus detonate <technique-id> --cleanup"


#!/usr/bin/env bash

set -euo pipefail

usage() {
  cat <<'EOF'
Usage: ./scripts/setup-project-automation.sh [options]

Options:
  --repo <owner/name>        Target repository (defaults to current repo)
  --owner <user>             User login for a user-owned project (default: nicklasorte)
  --org <org>                Organization login for an org-owned project
  --project-number <number>  Project number (default: 2)
  --dry-run                  Show values that would be set without writing
  --verify                   Print current repository variables after setup
  -h, --help                 Show this help

Examples:
  ./scripts/setup-project-automation.sh
  ./scripts/setup-project-automation.sh --repo nicklasorte/spectrum-systems
  ./scripts/setup-project-automation.sh --owner nicklasorte --project-number 2
  ./scripts/setup-project-automation.sh --org my-org --project-number 2
  ./scripts/setup-project-automation.sh --dry-run
  ./scripts/setup-project-automation.sh --verify
EOF
}

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Error: required command '$1' not found. Please install it and retry." >&2
    exit 1
  fi
}

check_auth() {
  if ! gh auth status -t >/dev/null 2>&1; then
    echo "Error: gh is not authenticated. Run 'gh auth login' and try again." >&2
    exit 1
  fi
}

PROJECT_OWNER="nicklasorte"
PROJECT_NUMBER=2
OWNER_KIND="user"
DRY_RUN=false
VERIFY=false

if ! command -v gh >/dev/null 2>&1; then
  echo "Error: GitHub CLI (gh) is required." >&2
  exit 1
fi

DEFAULT_REPO=$(gh repo view --json nameWithOwner -q .nameWithOwner 2>/dev/null || echo "")
REPO="${DEFAULT_REPO}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo)
      REPO="${2:-}"
      shift 2
      ;;
    --owner)
      PROJECT_OWNER="${2:-}"
      OWNER_KIND="user"
      shift 2
      ;;
    --org)
      PROJECT_OWNER="${2:-}"
      OWNER_KIND="org"
      shift 2
      ;;
    --project-number)
      PROJECT_NUMBER="${2:-}"
      shift 2
      ;;
    --dry-run)
      DRY_RUN=true
      shift
      ;;
    --verify)
      VERIFY=true
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage
      exit 1
      ;;
  esac
done

if [[ -z "$REPO" ]]; then
  echo "Error: unable to determine repository. Use --repo to specify owner/name." >&2
  exit 1
fi

require_cmd gh
require_cmd jq
check_auth

if [[ -z "${PROJECT_OWNER}" ]]; then
  echo "Error: project owner is required via --owner or --org." >&2
  exit 1
fi

if [[ -z "${PROJECT_NUMBER}" ]]; then
  echo "Error: project number is required." >&2
  exit 1
fi

if [[ -z "${PROJECT_TOKEN_VALUE:-}" ]]; then
  echo "Error: PROJECT_TOKEN_VALUE environment variable is required to set PROJECT_TOKEN." >&2
  exit 1
fi

read -r -d '' USER_QUERY <<'EOF'
query($owner: String!, $number: Int!) {
  user(login: $owner) {
    projectV2(number: $number) {
      id
      title
      fields(first: 100) {
        nodes {
          ... on ProjectV2FieldCommon {
            id
            name
          }
          ... on ProjectV2SingleSelectField {
            id
            name
            options {
              id
              name
            }
          }
        }
      }
    }
  }
}
EOF

read -r -d '' ORG_QUERY <<'EOF'
query($owner: String!, $number: Int!) {
  organization(login: $owner) {
    projectV2(number: $number) {
      id
      title
      fields(first: 100) {
        nodes {
          ... on ProjectV2FieldCommon {
            id
            name
          }
          ... on ProjectV2SingleSelectField {
            id
            name
            options {
              id
              name
            }
          }
        }
      }
    }
  }
}
EOF

QUERY="$USER_QUERY"
PROJECT_SELECTOR=".data.user.projectV2"
if [[ "$OWNER_KIND" == "org" ]]; then
  QUERY="$ORG_QUERY"
  PROJECT_SELECTOR=".data.organization.projectV2"
fi

PROJECT_JSON=$(gh api graphql -f query="$QUERY" -F owner="$PROJECT_OWNER" -F number="$PROJECT_NUMBER")
PROJECT_NODE=$(echo "$PROJECT_JSON" | jq "$PROJECT_SELECTOR")

if [[ "$PROJECT_NODE" == "null" ]]; then
  echo "Error: project not found for owner '$PROJECT_OWNER' number '$PROJECT_NUMBER'." >&2
  exit 1
fi

PROJECT_ID=$(echo "$PROJECT_NODE" | jq -r '.id')
LIFECYCLE_FIELD_ID=$(echo "$PROJECT_NODE" | jq -r '.fields.nodes[] | select(.name == "Lifecycle Stage") | .id')
RAW_EVIDENCE_OPTION_ID=$(echo "$PROJECT_NODE" | jq -r '.fields.nodes[] | select(.name == "Lifecycle Stage") | .options[]? | select(.name == "Raw Evidence") | .id')
COMPLETE_OPTION_ID=$(echo "$PROJECT_NODE" | jq -r '.fields.nodes[] | select(.name == "Lifecycle Stage") | .options[]? | select(.name == "Complete") | .id')

if [[ -z "$PROJECT_ID" || "$PROJECT_ID" == "null" ]]; then
  echo "Error: ProjectV2 ID not found." >&2
  exit 1
fi

if [[ -z "$LIFECYCLE_FIELD_ID" || "$LIFECYCLE_FIELD_ID" == "null" ]]; then
  echo "Error: Lifecycle Stage field not found." >&2
  exit 1
fi

if [[ -z "$RAW_EVIDENCE_OPTION_ID" || "$RAW_EVIDENCE_OPTION_ID" == "null" ]]; then
  echo "Error: Raw Evidence option not found on Lifecycle Stage field." >&2
  exit 1
fi

if [[ -z "$COMPLETE_OPTION_ID" || "$COMPLETE_OPTION_ID" == "null" ]]; then
  echo "Error: Complete option not found on Lifecycle Stage field." >&2
  exit 1
fi

set_var() {
  local name="$1"
  local value="$2"
  if $DRY_RUN; then
    echo "[dry-run] Would set variable $name in $REPO to: $value"
  else
    gh variable set "$name" --repo "$REPO" --body "$value" >/dev/null
  fi
}

set_secret() {
  local name="$1"
  local value="$2"
  if $DRY_RUN; then
    echo "[dry-run] Would set secret $name in $REPO from PROJECT_TOKEN_VALUE"
  else
    gh secret set "$name" --repo "$REPO" --body "$value" >/dev/null
  fi
}

set_var "SSOS_PROJECT_ID" "$PROJECT_ID"
set_var "SSOS_LIFECYCLE_FIELD_ID" "$LIFECYCLE_FIELD_ID"
set_var "SSOS_RAW_EVIDENCE_OPTION_ID" "$RAW_EVIDENCE_OPTION_ID"
set_var "SSOS_COMPLETE_OPTION_ID" "$COMPLETE_OPTION_ID"
set_secret "PROJECT_TOKEN" "$PROJECT_TOKEN_VALUE"

echo "Repository: $REPO"
echo "Project owner: $PROJECT_OWNER ($OWNER_KIND)"
echo "Project number: $PROJECT_NUMBER"
echo "SSOS_PROJECT_ID: $PROJECT_ID"
echo "SSOS_LIFECYCLE_FIELD_ID: $LIFECYCLE_FIELD_ID"
echo "SSOS_RAW_EVIDENCE_OPTION_ID: $RAW_EVIDENCE_OPTION_ID"
echo "SSOS_COMPLETE_OPTION_ID: $COMPLETE_OPTION_ID"
echo "Secret PROJECT_TOKEN: sourced from PROJECT_TOKEN_VALUE"

if $VERIFY; then
  echo ""
  echo "Current repository variables:"
  gh variable get SSOS_PROJECT_ID --repo "$REPO" || true
  gh variable get SSOS_LIFECYCLE_FIELD_ID --repo "$REPO" || true
  gh variable get SSOS_RAW_EVIDENCE_OPTION_ID --repo "$REPO" || true
  gh variable get SSOS_COMPLETE_OPTION_ID --repo "$REPO" || true
fi

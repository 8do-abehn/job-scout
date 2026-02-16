#!/bin/bash
set -euo pipefail

# Create tracking labels for a job search repo
# Usage: ./scripts/setup-labels.sh owner/repo

if [[ -z "${1:-}" ]]; then
  echo "Usage: $0 owner/repo"
  echo "Example: $0 my-user/job-scout"
  exit 1
fi

REPO="$1"

create_label() {
  local name="$1"
  local color="$2"
  local description="${3:-}"

  if gh label create "$name" --repo "$REPO" --color "$color" --description "$description" 2>/dev/null; then
    echo "  Created: $name"
  else
    echo "  Exists:  $name"
  fi
}

echo "Setting up labels for $REPO..."

# Status labels
create_label "to-review"     "c5def5" "New job to review"
create_label "shortlisted"   "0e8a16" "Reviewed and interested"
create_label "applied"       "1d76db" "Application submitted"
create_label "interviewing"  "d93f0b" "Active interview process"
create_label "offer"         "0e8a16" "Received offer"
create_label "rejected"      "e4e669" "Closed opportunity"
create_label "passed"        "ededed" "Decided to skip"

# Source labels
create_label "indeed"        "ff6600" "Found on Indeed"
create_label "linkedin"      "0077b5" "Found on LinkedIn"
create_label "glassdoor"     "0caa41" "Found on Glassdoor"
create_label "zip_recruiter" "5e17eb" "Found on ZipRecruiter"
create_label "google"        "4285f4" "Found on Google Jobs"
create_label "usajobs"       "003366" "Found on USAJOBS"
create_label "manual"        "bfdadc" "Manually added (referral, direct, etc.)"

echo "Done! View labels: https://github.com/$REPO/labels"

#!/bin/bash
set -euo pipefail

# Job Search and GitHub Issue Creator
# Usage: ./search-and-track.sh "software engineer" [--remote] [--since 1w] [--limit 5] [--match-all]

API_URL="${JOB_API_URL:-http://localhost:8000/get-jobs}"
if [[ -z "${GITHUB_REPOSITORY:-}" ]]; then
  echo "Error: GITHUB_REPOSITORY must be set (e.g., export GITHUB_REPOSITORY=your-user/job-scout)"
  exit 1
fi
REPO="$GITHUB_REPOSITORY"
PROJECT_NUMBER="${GITHUB_PROJECT_NUMBER:-}"

# Defaults
KEYWORDS=""
IS_REMOTE="true"
SINCE="1w"
LIMIT="10"
MATCH_ALL="false"

# Parse args
while [[ $# -gt 0 ]]; do
  case $1 in
    --remote) IS_REMOTE="true"; shift ;;
    --no-remote) IS_REMOTE="false"; shift ;;
    --since) SINCE="$2"; shift 2 ;;
    --limit) LIMIT="$2"; shift 2 ;;
    --match-all) MATCH_ALL="true"; shift ;;
    *) KEYWORDS="$1"; shift ;;
  esac
done

if [[ -z "$KEYWORDS" ]]; then
  echo "Usage: $0 \"search keywords\" [--remote] [--since 1w] [--limit 10] [--match-all]"
  exit 1
fi

echo "Searching for: $KEYWORDS (remote=$IS_REMOTE, since=$SINCE, limit=$LIMIT, match_all=$MATCH_ALL)"

# Build JSON payload - split keywords into array for match-all mode
if [[ "$MATCH_ALL" == "true" ]]; then
  # Convert "word1 word2 word3" to ["word1", "word2", "word3"]
  KEYWORDS_JSON=$(echo "$KEYWORDS" | python3 -c "import sys,json; print(json.dumps(sys.stdin.read().strip().split()))")
else
  KEYWORDS_JSON="[\"$KEYWORDS\"]"
fi

PAYLOAD=$(cat <<EOF
{
  "sinceWhen": "$SINCE",
  "keywords": $KEYWORDS_JSON,
  "isRemote": $IS_REMOTE,
  "requireAllKeywords": $MATCH_ALL,
  "limit": $LIMIT
}
EOF
)

# Fetch jobs
RESPONSE=$(curl -s -X POST "$API_URL" -H "Content-Type: application/json" -d "$PAYLOAD")

# Check for errors
if echo "$RESPONSE" | python3 -c "import sys,json; sys.exit(0 if not json.load(sys.stdin).get('error') else 1)" 2>/dev/null; then
  echo "Found jobs, creating issues..."
else
  echo "Error fetching jobs"
  exit 1
fi

# Process each job
echo "$RESPONSE" | SEARCH_KEYWORDS="$KEYWORDS" SEARCH_REMOTE="$IS_REMOTE" REPO="$REPO" PROJECT_NUMBER="$PROJECT_NUMBER" python3 -c "
import sys
import json
import subprocess
import os

search_keywords = os.environ.get('SEARCH_KEYWORDS', '')
is_remote = os.environ.get('SEARCH_REMOTE', 'false')
repo = os.environ.get('REPO', '')
project_number = os.environ.get('PROJECT_NUMBER', '')

# Track issues created in this run to avoid duplicates (GitHub search index lag)
created_this_run = set()

data = json.load(sys.stdin)
jobs = data.get('jobs', [])

print(f'Found {len(jobs)} jobs')

for job in jobs:
    title = job.get('title', 'Unknown Title')
    company = job.get('company', 'Unknown Company')
    location = job.get('location') or 'Remote'
    url = job.get('job_url', '')
    site = job.get('site', 'unknown')
    desc_raw = job.get('description') or ''
    description = desc_raw[:1500] + '...' if len(desc_raw) > 1500 else desc_raw

    # Salary info
    salary = ''
    if job.get('min_amount') and job.get('max_amount'):
        salary = f\"\${int(job['min_amount']):,} - \${int(job['max_amount']):,}\"

    issue_title = f'{title} @ {company}'
    issue_body = f'''## {title}

**Company:** {company}
**Location:** {location}
**Salary:** {salary or 'Not listed'}
**Source:** {job.get('site', 'Unknown')}

### Links
- [Job Posting]({url})
- [Company Page]({job.get('company_url', '#')})

### Description
{description}

---
*Search: {search_keywords} | Remote: {is_remote}*
'''

    # Dedupe key: normalized title + company (case-insensitive)
    dedupe_key = f'{title.lower().strip()} @ {company.lower().strip()}'

    # Check if we already created this in the current run
    if dedupe_key in created_this_run:
        print(f'  SKIP: {issue_title} (duplicate in batch)')
        continue

    # Check if issue already exists in GitHub (include closed issues)
    check = subprocess.run(
        ['gh', 'issue', 'list', '--repo', repo, '--state', 'all', '--search', f'in:title \"{company}\"', '--json', 'title'],
        capture_output=True, text=True
    )
    existing = json.loads(check.stdout) if check.stdout else []

    if any(issue_title.lower() in i.get('title', '').lower() for i in existing):
        print(f'  SKIP: {issue_title} (already exists)')
        continue

    # Create issue with site label
    result = subprocess.run(
        ['gh', 'issue', 'create',
         '--repo', repo,
         '--title', issue_title,
         '--body', issue_body,
         '--label', 'to-review',
         '--label', site],
        capture_output=True, text=True
    )

    if result.returncode == 0:
        issue_url = result.stdout.strip()
        created_this_run.add(dedupe_key)
        print(f'  CREATED: {issue_title}')
        print(f'           {issue_url}')

        # Add to project (if configured)
        if project_number:
            owner = repo.split('/')[0]
            subprocess.run(
                ['gh', 'project', 'item-add', project_number, '--owner', owner, '--url', issue_url],
                capture_output=True
            )
    else:
        print(f'  ERROR: {issue_title}: {result.stderr}')
"

echo ""
echo "Done! View issues: https://github.com/$REPO/issues"
if [[ -n "$PROJECT_NUMBER" ]]; then
  OWNER="${REPO%%/*}"
  echo "View project: https://github.com/users/$OWNER/projects/$PROJECT_NUMBER"
fi

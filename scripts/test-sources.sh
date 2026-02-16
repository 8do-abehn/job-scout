#!/usr/bin/env bash
set -euo pipefail

# Test each US jobspy source individually
# Usage: ./scripts/test-sources.sh [backend_url]

BACKEND_URL="${1:-http://localhost:8000}"
SOURCES=("indeed" "linkedin" "glassdoor" "zip_recruiter" "google")

echo "Testing US jobspy sources against $BACKEND_URL"
echo "================================================"

PASSED=0
FAILED=0
RESULTS=()

for source in "${SOURCES[@]}"; do
    echo -n "Testing $source... "

    # Start backend with single source (using venv)
    JOBSPY_SITES="$source" JOBSPY_VERBOSE=0 backend/venv/bin/python backend/main.py &
    PID=$!

    # Wait for startup
    for i in {1..15}; do
        if curl -s "$BACKEND_URL/health" > /dev/null 2>&1; then
            break
        fi
        sleep 1
    done

    # Test the source
    RESPONSE=$(curl -s -X POST "$BACKEND_URL/get-jobs" \
        -H "Content-Type: application/json" \
        -d '{"sinceWhen": "7d", "keywords": ["software engineer"], "limit": 3}' 2>/dev/null || echo '{"error":true}')

    # Kill the backend
    kill $PID 2>/dev/null || true
    wait $PID 2>/dev/null || true
    sleep 1

    # Check results
    JOBS=$(echo "$RESPONSE" | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d.get('jobs',[])) if not d.get('error') else -1)" 2>/dev/null || echo "-1")

    if [[ "$JOBS" -ge 0 ]]; then
        if [[ "$JOBS" -gt 0 ]]; then
            echo "✓ PASS ($JOBS jobs)"
            RESULTS+=("$source: ✓ $JOBS jobs")
        else
            echo "⚠ PASS (0 jobs)"
            RESULTS+=("$source: ⚠ 0 jobs")
        fi
        ((PASSED++))
    else
        echo "✗ FAIL"
        RESULTS+=("$source: ✗ FAIL")
        ((FAILED++))
    fi
done

echo ""
echo "================================================"
echo "Summary: $PASSED passed, $FAILED failed"
echo ""
for result in "${RESULTS[@]}"; do
    echo "  $result"
done

exit $FAILED

# Feature: Enrich Job Descriptions

## Problem
JobSpy often returns empty or truncated job descriptions, especially from Glassdoor (Cloudflare protection) and LinkedIn (without full-fetch mode). This results in GitHub issues with incomplete information.

## Proposed Solution
Add Playwright-based description enrichment to fetch full job descriptions from the actual job posting pages.

## Implementation Options

### Option 1: Enrich during search (recommended)
- Add Playwright to backend dependencies
- After JobSpy returns results, visit each job URL
- Extract full description from rendered page
- Replace empty/truncated descriptions before returning

### Option 2: On-demand endpoint
- Add `POST /enrich-job` endpoint that takes a job URL
- Script calls it when description is empty
- Could also work for existing issues

## Technical Notes
- Playwright needed to bypass Cloudflare on Glassdoor
- Will make searches slower (add ~2-5 sec per job)
- Consider making it optional via env var: `JOBSPY_ENRICH_DESCRIPTIONS=true`
- Rate limiting may be needed to avoid blocks

## Files to modify
- `backend/main.py` - Add enrichment logic
- `backend/requirements.txt` - Add playwright
- `backend/Dockerfile` - Install playwright browsers

## Priority
Low - Current workaround is to enable `JOBSPY_LINKEDIN_FULL=true` for LinkedIn jobs.

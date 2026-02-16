# Job Scout

A self-hosted job search tool that scrapes LinkedIn, Indeed, Glassdoor, and ZipRecruiter, then tracks applications via GitHub Issues.

> **Fork Notice:** Originally forked from [0xDAEF0F/job-searchoor](https://github.com/0xDAEF0F/job-searchoor), with a self-hosted backend, scoring engine, and GitHub Issues tracking added.

## Real-World Results

During a real-world 6-month job search, the scraper surfaced ~23% of leads that resulted in applications during its active period, scanning 534 companies across 2 months of automated runs.

## Features

- Scrapes jobs from multiple sites (LinkedIn, Indeed, Glassdoor, ZipRecruiter, USAJOBS)
- Creates GitHub Issues for each job posting
- Tracks application status with labels (`to-review`, `applied`, `interviewing`, `rejected`, `offer`)
- Automated daily searches via GitHub Actions
- MCP server for Claude Desktop integration

## Quick Start

### Option 1: GitHub Actions (Easiest)

1. **Fork this repo** (keep it private for your job search)

2. **Set up labels** — run once after forking:
   ```bash
   ./scripts/setup-labels.sh YOUR_USERNAME/job-scout
   ```

3. **Configure search terms (optional)** - The workflow runs with sensible defaults. To customize, go to Settings → Secrets and variables → Actions → Variables:
   | Variable | Default | Description |
   |----------|---------|-------------|
   | `JOB_SEARCHES` | `software engineer,product manager,data analyst` | Comma-separated search terms |
   | `JOBSPY_SITES` | `indeed,linkedin,glassdoor,zip_recruiter,google` | Sites to scrape |

   > These are optional — if you don't set them, the defaults above are used. `GITHUB_REPOSITORY` is set automatically by GitHub Actions.

4. **Run manually** - Actions → Job Search → Run workflow

5. **View results** - Check the Issues tab for job postings

### Option 2: Local Setup

> **Platform note:** Developed and tested on macOS. Linux should work out of the box. Windows users should use WSL2 — the shell scripts require bash.

#### Prerequisites
- Python 3.10+ (`python3 --version`)
- Node.js 18+ or [Bun](https://bun.sh) (only needed for MCP server)
- [GitHub CLI](https://cli.github.com/) (`gh --version`) — used for issue creation
- `curl` (pre-installed on macOS/Linux)
- `git` (`git --version`)

#### 1. Clone and setup backend

```bash
git clone https://github.com/YOUR_USERNAME/job-scout.git
cd job-scout

# Backend setup
cd backend
python3 -m venv venv
source venv/bin/activate  # Windows (WSL2): source venv/bin/activate
pip install -r requirements.txt
python main.py
```

#### 2. Verify the backend is running

```bash
curl -s http://localhost:8000/health
# Should return: {"status":"ok","config_loaded":true}
```

#### 3. Set your repo and run a search (new terminal)

```bash
# Required — tells the script where to create GitHub issues
export GITHUB_REPOSITORY="YOUR_USERNAME/job-scout"

# Search and create GitHub issues
./scripts/search-and-track.sh "software engineer" --remote --limit 10

# Or test the API directly (no GITHUB_REPOSITORY needed)
curl -X POST http://localhost:8000/get-jobs \
  -H "Content-Type: application/json" \
  -d '{"sinceWhen":"1w","keywords":["software engineer"],"isRemote":true,"limit":5}'
```

### Option 3: Docker

```bash
docker compose up -d

# Verify backend is running
curl -s http://localhost:8000/health

# Set your repo and run a search
export GITHUB_REPOSITORY="YOUR_USERNAME/job-scout"
./scripts/search-and-track.sh "your search terms" --remote --limit 10
```

> Docker only runs the backend. You still need `gh` CLI installed locally for issue creation.

## Configuration

### Config File (Recommended)

Copy the example and customize:

```bash
cp config.yaml.example config.yaml
# Edit config.yaml with your preferences
```

The config file supports:
- **locations** - Search multiple areas (remote, cities)
- **searches** - Multiple search queries with priorities
- **exclude_keywords** - Filter out unwanted jobs
- **include_keywords** - Boost preferred jobs

See `config.yaml.example` for all options.

### Environment Variables

Environment variables override config file settings:

| Variable | Default | Description |
|----------|---------|-------------|
| `GITHUB_REPOSITORY` | *(required locally)* | Your `user/repo` for issue creation. Set automatically in GitHub Actions. |
| `GITHUB_PROJECT_NUMBER` | *(optional)* | GitHub Project number to auto-add new issues to a project board |
| `JOB_API_URL` | `http://localhost:8000/get-jobs` | Backend API URL (for MCP server or remote setups) |
| `CONFIG_PATH` | `config.yaml` | Path to config file |
| `JOBSPY_VERBOSE` | `1` | Logging: 0=errors, 1=warnings, 2=all |
| `JOBSPY_LINKEDIN_FULL` | `false` | Fetch full LinkedIn descriptions (slower) |
| `JOBSPY_SITES` | `indeed,linkedin,glassdoor,zip_recruiter,google` | Sites to scrape |
| `USAJOBS_API_KEY` | - | USAJOBS API key ([get one free](https://developer.usajobs.gov/apirequest/)) |
| `USAJOBS_EMAIL` | - | Email used to request API key |

### USAJOBS Integration

Search federal government IT jobs by setting your API credentials:

```bash
export USAJOBS_API_KEY="your-api-key"
export USAJOBS_EMAIL="your-email@example.com"
```

Or add to `config.yaml`:

```yaml
settings:
  usajobs_api_key: "your-api-key"
  usajobs_email: "your-email@example.com"
```

USAJOBS results are automatically included in searches when credentials are configured. Federal jobs get a +10 scoring boost (typically smaller organizations).

### Search Script Options

```bash
./scripts/search-and-track.sh "keywords" [options]

Options:
  --remote       Only remote jobs (default: true)
  --no-remote    Include non-remote jobs
  --since 1w     Time filter: 1d, 2d, 1w, 2w (default: 1w)
  --limit 10     Max results (default: 10)
  --match-all    Require ALL keywords in title/description (AND mode)
```

## Tracking Your Job Search

> **Keep your repo private.** Interview notes, salary info, personal assessments, and company research will live here. Treat it as your personal job search journal, not just a scraper output.

Issues are created with labels:
- **Source**: `linkedin`, `indeed`, `glassdoor`, `zip_recruiter`, `usajobs`
- **Status**: `to-review` → `shortlisted` → `applied` → `interviewing` → `offer` or `rejected`

### Best Practices

**Add interview notes directly in issue comments.** Each job issue becomes a thread — add prep notes before interviews, debrief notes after, and track follow-ups. This becomes your searchable source of truth that AI tools (Claude, ChatGPT, etc.) can reference to help you prepare.

**Manually create issues for jobs found on your own.** The scraper won't catch everything — direct applications, referrals, recruiter outreach, and jobs from niche boards should all get issues too. Keep everything in one place, not just scraper results. You can use AI to help create and manage these issues quickly.

**Use labels consistently.** Moving issues through `to-review` → `applied` → `interviewing` → `offer/rejected` gives you a clear pipeline view and lets you measure your conversion rates.

### Using Claude Code to Manage Issues

[Claude Code](https://docs.anthropic.com/en/docs/claude-code) can create and manage GitHub Issues directly from your terminal — useful for adding jobs you find outside the scraper (referrals, recruiter outreach, job boards the scraper doesn't cover).

```bash
# From your repo directory, ask Claude Code to create an issue
claude "Create a GitHub issue for a Senior Engineer role at Acme Corp.
  Remote, $150k-180k, found via recruiter email.
  Add the 'manual' and 'to-review' labels."

# Add interview notes to an existing issue
claude "Add a comment to issue #42 with my interview notes:
  First round was 30 min with the hiring manager, focused on
  team leadership and infrastructure migration experience.
  Next step is a technical panel on Thursday."

# Batch-create issues from a list
claude "Create GitHub issues for each of these jobs I found today:
  1. Platform Lead @ StartupCo - remote - found on Wellfound
  2. IT Director @ HealthOrg - Chicago - recruiter referral
  Use the 'manual' and 'to-review' labels for all of them."
```

This keeps all your job search data in one place — scraped jobs and manually found ones — so you have a single source of truth.

### GitHub Project Setup

#### 1. Create the Project

1. Go to your GitHub profile → **Projects** → **New project**
2. Select **Board** template
3. Name it (e.g., "Job Search Tracker")
4. Note the project number from the URL: `github.com/users/YOU/projects/1` → number is `1`

#### 2. Configure Columns

Delete default columns and create these:

| Column | Purpose |
|--------|---------|
| **To Review** | New jobs from searches |
| **Shortlisted** | Reviewed and interested, need to apply |
| **Applied** | Submitted applications |
| **Interviewing** | Active interview processes |
| **Offer** | Received offers |
| **Rejected** | Closed opportunities |
| **Passed** | Jobs you decided to skip |

#### 3. Add Custom Fields (Optional)

Click **+ New field** to add:
- **Company** (Text) - For filtering/grouping
- **Salary** (Text) - Compensation range
- **Applied Date** (Date) - Track timing
- **Next Step** (Text) - Follow-up reminders
- **Priority** (Single select: High/Medium/Low)

#### 4. Create Views

**Board View** (default)
- Group by Status column
- Drag issues between columns as you progress

**Table View**
- Click **+ New view** → **Table**
- Add columns: Title, Company, Salary, Applied Date, Labels
- Sort by Applied Date or Priority

**By Source View**
- Click **+ New view** → **Board**
- Group by: Labels (shows LinkedIn, Indeed, etc. as columns)

#### 5. Set Up Automation

Go to **...** → **Workflows** → Enable these:

| Workflow | Action |
|----------|--------|
| Item added | Set status to "To Review" |
| Item closed | Move to "Rejected" or "Passed" |
| Auto-archive | Archive items closed for 14 days |

#### 6. Connect to Searches

Set the environment variable to auto-add new jobs to your project:

```bash
# Local
export GITHUB_PROJECT_NUMBER=1

# GitHub Actions - add to repository variables
# Settings → Secrets and variables → Actions → Variables
# Name: GITHUB_PROJECT_NUMBER
# Value: 1
```

#### 7. Workflow Tips

1. **Daily review**: Check "To Review" column, research companies, move to "Applied" or "Passed"
2. **Track applications**: When you apply, move card and set "Applied Date"
3. **Follow up**: Use "Next Step" field for interview dates or follow-up reminders
4. **Filter by source**: Use the "By Source" view to see which job boards work best
5. **Archive regularly**: Close rejected/passed issues to keep board clean

## Claude Desktop Integration (MCP)

The MCP ([Model Context Protocol](https://modelcontextprotocol.io/)) server lets Claude Desktop search for jobs directly. Requires the backend running locally.

#### 1. Build the MCP server

[Bun](https://bun.sh) is a fast JavaScript runtime. Install it, then build:

```bash
# Install Bun (macOS/Linux)
curl -fsSL https://bun.sh/install | bash

# Build the MCP server
bun install && bun run build
```

#### 2. Configure Claude Desktop

Add to your Claude Desktop config file:

| Platform | Config path |
|----------|-------------|
| macOS | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| Linux | `~/.config/claude/claude_desktop_config.json` |
| Windows | `%APPDATA%\Claude\claude_desktop_config.json` |

```json
{
  "mcpServers": {
    "job-search": {
      "command": "node",
      "args": ["/absolute/path/to/job-scout/dist/index.js"],
      "env": {
        "JOB_API_URL": "http://localhost:8000/get-jobs"
      }
    }
  }
}
```

> Use the **absolute path** to `dist/index.js`. Restart Claude Desktop after saving.

## API Reference

### POST /get-jobs

Single location search.

```json
{
  "sinceWhen": "1d",
  "keywords": ["software", "engineer"],
  "excludeKeywords": ["senior"],
  "isRemote": true,
  "location": "New York, NY",
  "distance": 50,
  "requireAllKeywords": false,
  "limit": 10
}
```

| Field | Type | Description |
|-------|------|-------------|
| `sinceWhen` | string | Time filter: `1d`, `3d`, `1w`, `2w` |
| `keywords` | array | Search terms |
| `excludeKeywords` | array | Filter out jobs containing these |
| `isRemote` | bool | Remote jobs only |
| `location` | string | City/state (ignored if `isRemote` is true) |
| `distance` | int | Miles from location (default: 50) |
| `requireAllKeywords` | bool | Require ALL keywords (AND mode) |
| `limit` | int | Max results |

### POST /search-all

Search across all configured locations from `config.yaml`.

```json
{
  "sinceWhen": "3d",
  "keywords": ["infrastructure"],
  "limit": 50
}
```

Response includes `locations_searched` array and jobs tagged with `_location_name`.

### GET /config

Returns current configuration (sites, locations count, etc).

### GET /health

Returns `{"status": "ok", "config_loaded": true}`

## Troubleshooting

**"Error: GITHUB_REPOSITORY must be set"**
- Set it before running the search script: `export GITHUB_REPOSITORY="your-user/your-repo"`
- In GitHub Actions this is set automatically — you only need it for local/Docker use

**Backend won't start?**
- Check Python version: `python3 --version` (needs 3.10+)
- Make sure you're in the venv: `source backend/venv/bin/activate`
- Check port 8000 isn't in use: `curl -s http://localhost:8000/health`

**No LinkedIn results?**
- LinkedIn rate limits aggressively — it's the most unreliable source
- Try reducing `--limit` to 5 or wait 30 minutes between searches
- Indeed and Google Jobs usually work best and most consistently

**No results from any site?**
- Some sites block cloud IPs — running locally often works better than GitHub Actions for scraping
- Try `JOBSPY_VERBOSE=2 python main.py` to see detailed scraping logs
- Check if your search terms are too specific — try broader keywords first

**Duplicate issues?**
- The script checks for existing issues by title before creating
- Running the same search twice won't create duplicates

**GitHub Action failing?**
- Check Actions tab for logs
- Ensure `GITHUB_TOKEN` has Issues write permission (default for private repos)
- Rate limits: the workflow sleeps 5 seconds between searches to avoid hitting GitHub API limits

## Future Feature Ideas

Ideas for future enhancements. Contributions welcome!

### No API Required (Easier)

| Feature | Effort | Description |
|---------|--------|-------------|
| **Auto-close stale jobs** | Low | Check if job URL returns 404, auto-close issue |
| **Salary normalization** | Low | Parse "$150k-180k" vs "$150,000/yr" consistently |
| **Company Glassdoor lookup** | Medium | Auto-fetch ratings, add to issue body |
| **Resume match scoring** | Medium | Compare job description to resume keywords |
| **Duplicate company detection** | Low | Flag if you've applied to same company before |
| **Application tracking** | Low | Track applied → interview → offer flow with dates |
| **Email/Slack alerts** | Medium | Daily digest of high-match jobs |
| **Job description diff** | Low | Detect when a reposted job has changed |

### LinkedIn API (Requires Partner Access)

LinkedIn API access requires becoming a [LinkedIn Talent Solutions Partner](https://learn.microsoft.com/en-us/linkedin/talent/recruiter-system-connect) - not available to individual users.

| Feature | Effort | Description |
|---------|--------|-------------|
| **Connection check** | High | "You know 3 people at this company" |
| **InMail integration** | High | Auto-draft outreach messages |
| **Profile sync** | Medium | Keep resume/profile in sync |

### Scraping Workarounds (No API)

| Feature | Effort | Risk |
|---------|--------|------|
| **LinkedIn saved jobs import** | Medium | Export manually, parse CSV |
| **Browser extension** | High | Scrape while you browse (account risk) |

### Network Analysis (Warm Intros > Cold Apps)

> **Cold applications have <2% response rate.** Warm introductions are far more effective.
> — [Nate's Newsletter](https://natesnewsletter.substack.com/p/cold-applications-have-a-2-response)

Export your LinkedIn data (Settings → Data Privacy → Get a copy) and analyze:

| Analysis | Description |
|----------|-------------|
| **Warm path discovery** | Find 2nd-degree connections at target companies |
| **Dormant connections** | People you haven't contacted in 6+ months |
| **Reciprocity scores** | Who have you helped that might return the favor? |
| **Company coverage** | Which companies do you have the most connections at? |

Potential feature: Cross-reference job issues with your LinkedIn connections export to surface warm intro opportunities.

### Other Integrations

| Integration | Description |
|-------------|-------------|
| **Dice.com** | Tech-focused job board |
| **AngelList/Wellfound** | Startup jobs |
| **Lever/Greenhouse scraping** | Direct ATS job boards |
| **Glassdoor reviews API** | Auto-fetch company ratings |
| **Levels.fyi** | Salary data enrichment |

## Disclaimer

This tool is intended for **personal and educational use** — tracking your own job search, not bulk data collection or commercial scraping.

Job scraping may violate the terms of service of some job boards, including LinkedIn. The legality of web scraping varies by jurisdiction and depends on what data is collected and how it's used. Notably, while scraping publicly accessible data [does not violate the CFAA](https://en.wikipedia.org/wiki/HiQ_Labs_v._LinkedIn), it may still breach a site's terms of service.

The actual scraping is performed by [JobSpy](https://github.com/speedyapply/JobSpy), a third-party library. This project wraps JobSpy and creates private GitHub Issues for personal tracking — it does not store, redistribute, or publish scraped data.

**The authors are not responsible for how you use this tool.** Use it at your own risk, respect rate limits, and review the terms of service of any site you scrape.

## Credits

- Original MCP server by [0xDAEF0F](https://github.com/0xDAEF0F)
- Job scraping powered by [JobSpy](https://github.com/speedyapply/JobSpy) (MIT License)
- Federal jobs via [USAJOBS API](https://developer.usajobs.gov/)

## License

MIT License - See [LICENSE](LICENSE)

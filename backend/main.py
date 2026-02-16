#!/usr/bin/env python3
"""
Local job search backend using JobSpy.
Replaces the external ngrok endpoint with a self-hosted solution.

Configuration priority:
  1. config.yaml (or path in CONFIG_PATH env var)
  2. Environment variables
  3. Built-in defaults

Environment variables:
  CONFIG_PATH                - Path to config file (default: config.yaml)
  JOBSPY_VERBOSE=0|1|2       - Logging verbosity (default: 1)
  JOBSPY_LINKEDIN_FULL=true  - Fetch full LinkedIn descriptions (slower)
  JOBSPY_SITES=indeed,linkedin,glassdoor,zip_recruiter,google - Sites to scrape
"""

import os
from datetime import datetime
from pathlib import Path
from typing import Optional

import requests
import yaml
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from jobspy import scrape_jobs


# Default configuration
DEFAULTS = {
    "sites": ["indeed", "linkedin", "glassdoor", "zip_recruiter", "google"],
    "hours_old": 72,
    "results_wanted": 50,
    "country_indeed": "USA",
    "linkedin_fetch_description": False,
    "verbose": 1,
    "usajobs_enabled": False,
    "usajobs_api_key": None,
    "usajobs_email": None,
}


def load_config() -> dict:
    """Load configuration from YAML file, env vars, or defaults."""
    config = DEFAULTS.copy()

    # Try to load from config file
    config_path = Path(os.environ.get("CONFIG_PATH", "config.yaml"))
    if config_path.exists():
        try:
            with open(config_path) as f:
                file_config = yaml.safe_load(f) or {}
                settings = file_config.get("settings", {})

                if "sites" in settings:
                    config["sites"] = settings["sites"]
                if "hours_old" in settings:
                    config["hours_old"] = settings["hours_old"]
                if "results_wanted" in settings:
                    config["results_wanted"] = settings["results_wanted"]
                if "country_indeed" in settings:
                    config["country_indeed"] = settings["country_indeed"]
                if "linkedin_fetch_description" in settings:
                    config["linkedin_fetch_description"] = settings["linkedin_fetch_description"]

                # Store full config for searches, locations, filters
                config["searches"] = file_config.get("searches", [])
                config["locations"] = file_config.get("locations", [])
                config["exclude_keywords"] = file_config.get("exclude_keywords", [])
                config["include_keywords"] = file_config.get("include_keywords", [])

                # Scoring preferences
                scoring = file_config.get("scoring", {})
                if scoring:
                    config["scoring"] = scoring

                # USAJOBS settings
                if "usajobs_enabled" in settings:
                    config["usajobs_enabled"] = settings["usajobs_enabled"]
                if "usajobs_api_key" in settings:
                    config["usajobs_api_key"] = settings["usajobs_api_key"]
                if "usajobs_email" in settings:
                    config["usajobs_email"] = settings["usajobs_email"]

                print(f"Loaded config from {config_path}")
        except Exception as e:
            print(f"Warning: Failed to load {config_path}: {e}")

    # Environment variables override config file
    if os.environ.get("JOBSPY_VERBOSE"):
        config["verbose"] = int(os.environ.get("JOBSPY_VERBOSE", "1"))
    if os.environ.get("JOBSPY_LINKEDIN_FULL"):
        config["linkedin_fetch_description"] = os.environ.get("JOBSPY_LINKEDIN_FULL", "").lower() == "true"
    if os.environ.get("JOBSPY_SITES"):
        config["sites"] = os.environ.get("JOBSPY_SITES").split(",")

    # USAJOBS env vars (override config file)
    if os.environ.get("USAJOBS_API_KEY"):
        config["usajobs_api_key"] = os.environ.get("USAJOBS_API_KEY")
        config["usajobs_enabled"] = True  # Auto-enable if key is set
    if os.environ.get("USAJOBS_EMAIL"):
        config["usajobs_email"] = os.environ.get("USAJOBS_EMAIL")

    return config


# Load configuration at startup
CONFIG = load_config()

app = FastAPI(title="Job Scout Backend", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class JobRequest(BaseModel):
    sinceWhen: str = Field(..., pattern=r"^[0-9]+[dw]$")
    keywords: Optional[list[str]] = None
    excludeKeywords: Optional[list[str]] = None
    isRemote: Optional[bool] = None
    location: Optional[str] = None  # Specific location (e.g., "New York, NY")
    distance: Optional[int] = 50  # Distance in miles from location
    requireAllKeywords: bool = False  # AND mode: require ALL keywords in title/description
    limit: int = 10


class JobResponse(BaseModel):
    error: bool
    jobs: list[dict]
    locations_searched: Optional[list[str]] = None  # Which locations were searched


def parse_since_when(since_when: str) -> int:
    """Convert '1d' or '2w' format to hours."""
    value = int(since_when[:-1])
    unit = since_when[-1]
    if unit == "d":
        return value * 24
    elif unit == "w":
        return value * 24 * 7
    return 24


def scrape_single_location(
    search_term: str,
    hours_old: int,
    results_wanted: int,
    is_remote: bool = False,
    location: str | None = None,
    distance: int = 50,
) -> list[dict]:
    """Scrape jobs for a single location/remote setting."""
    params = {
        "site_name": CONFIG["sites"],
        "search_term": search_term,
        "country_indeed": CONFIG["country_indeed"],
        "results_wanted": results_wanted,
        "hours_old": hours_old,
        "linkedin_fetch_description": CONFIG["linkedin_fetch_description"],
        "verbose": CONFIG.get("verbose", 1),
    }

    if is_remote:
        params["is_remote"] = True
    elif location:
        params["location"] = location
        params["distance"] = distance
    else:
        params["location"] = "United States"

    jobs_df = scrape_jobs(**params)
    return jobs_df.to_dict(orient="records")


def scrape_usajobs(
    search_term: str,
    hours_old: int = 72,
    results_wanted: int = 50,
    is_remote: bool = False,
    location: str | None = None,
    distance: int = 50,
) -> list[dict]:
    """Scrape jobs from USAJOBS API.

    Returns jobs in the same format as JobSpy for compatibility.
    """
    api_key = CONFIG.get("usajobs_api_key")
    email = CONFIG.get("usajobs_email")

    if not api_key or not email:
        print("USAJOBS: Missing API key or email, skipping")
        return []

    # Convert hours to days for USAJOBS (max 60 days)
    days_posted = min(hours_old // 24, 60) or 1

    headers = {
        "Host": "data.usajobs.gov",
        "User-Agent": email,
        "Authorization-Key": api_key,
    }

    params = {
        "Keyword": search_term,
        "DatePosted": days_posted,
        "ResultsPerPage": min(results_wanted, 500),  # USAJOBS max is 500
        "JobCategoryCode": "2210",  # Information Technology Management
    }

    # Add location filtering
    # Note: RemoteIndicator=True is very restrictive for federal jobs
    # Instead, we fetch all and let the results show remote eligibility via _telework/_remote fields
    if location and not is_remote:
        params["LocationName"] = location
        if distance:
            params["Radius"] = distance

    try:
        response = requests.get(
            "https://data.usajobs.gov/api/search",
            headers=headers,
            params=params,
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()

        results = data.get("SearchResult", {}).get("SearchResultItems", [])
        jobs = []

        for item in results:
            job_data = item.get("MatchedObjectDescriptor", {})
            position = job_data.get("PositionLocation", [{}])[0] if job_data.get("PositionLocation") else {}

            # Extract salary info
            salary_info = job_data.get("PositionRemuneration", [{}])[0] if job_data.get("PositionRemuneration") else {}
            min_salary = salary_info.get("MinimumRange")
            max_salary = salary_info.get("MaximumRange")

            # Parse dates
            pub_date = job_data.get("PublicationStartDate", "")
            try:
                date_posted = datetime.strptime(pub_date, "%Y-%m-%d") if pub_date else None
            except ValueError:
                date_posted = None

            # Build job dict matching JobSpy format
            job = {
                "site": "usajobs",
                "title": job_data.get("PositionTitle", ""),
                "company": job_data.get("OrganizationName", ""),
                "location": position.get("LocationName", ""),
                "job_url": job_data.get("PositionURI", ""),
                "description": job_data.get("UserArea", {}).get("Details", {}).get("JobSummary", ""),
                "date_posted": date_posted,
                "min_amount": float(min_salary) if min_salary else None,
                "max_amount": float(max_salary) if max_salary else None,
                "interval": salary_info.get("RateIntervalCode", ""),
                "job_type": job_data.get("PositionSchedule", [{}])[0].get("Name", "") if job_data.get("PositionSchedule") else "",
                # USAJOBS-specific fields
                "_usajobs_id": job_data.get("PositionID", ""),
                "_department": job_data.get("DepartmentName", ""),
                "_grade": job_data.get("JobGrade", [{}])[0].get("Code", "") if job_data.get("JobGrade") else "",
                "_telework": job_data.get("TeleworkEligible", False),
                "_remote": job_data.get("RemoteIndicator", False),
            }
            jobs.append(job)

        print(f"USAJOBS: Found {len(jobs)} jobs for '{search_term}'")
        return jobs

    except requests.RequestException as e:
        print(f"USAJOBS API error: {e}")
        return []
    except Exception as e:
        print(f"USAJOBS parsing error: {e}")
        return []


def filter_jobs(jobs: list[dict], exclude_list: list[str]) -> list[dict]:
    """Filter out jobs containing excluded keywords in title only."""
    if not exclude_list:
        return jobs
    exclude_lower = [kw.lower() for kw in exclude_list]
    return [
        job for job in jobs
        if not any(
            exc in str(job.get("title", "")).lower()
            for exc in exclude_lower
        )
    ]


def score_jobs(jobs: list[dict], include_list: list[str]) -> list[dict]:
    """Score jobs based on role fit, industry, location, skills, and company size.

    Scoring preferences are loaded from config.yaml under the 'scoring:' key.
    Falls back to generic defaults if not configured.
    """
    scoring = CONFIG.get("scoring", {})

    # Role keywords - prefer people manager roles
    mgmt_titles = scoring.get("mgmt_titles", [
        "manager", "director", "head of", "vp ", "vice president",
    ])
    senior_ic_titles = scoring.get("senior_ic_titles", [
        "senior", "sr.", "sr ", "lead", "principal", "staff",
    ])

    # Preferred titles — add your target roles here via config
    preferred_titles = scoring.get("preferred_titles", [])

    # Titles that disqualify even if they have "manager" or infra terms
    bad_titles = scoring.get("bad_titles", [
        "developer", "software engineer", "product manager", "project manager",
        "data engineer", "machine learning", "ml ", "ai ", "analytics",
        "financial system", "business system", "hris", "erp", "salesforce",
        "mainframe", "z/os", "as/400", "cobol",
        "expense", "budget", "accounting", "credit", "risk analyst",
        "marketing", "sales engineer", "solutions architect", "pre-sales",
        "recruiting", "talent", "hr ", "human resource",
    ])

    # Target locations
    good_locations = scoring.get("good_locations", ["remote"])

    # Skills to boost
    good_skills = scoring.get("good_skills", [
        "terraform", "ansible", "kubernetes", "docker", "aws", "azure", "gcp",
    ])

    # Red flags
    red_flags = scoring.get("red_flags", [
        "contract to hire", "c2h",
    ])

    # Large companies to deprioritize
    large_companies = scoring.get("large_companies", [
        "amazon", "aws", "google", "microsoft", "meta", "facebook", "apple", "netflix",
        "nvidia", "oracle", "ibm", "cisco", "intel", "salesforce", "adobe",
        "accenture", "deloitte", "kpmg", "pwc", "cognizant", "infosys",
        "wipro", "tcs", "capgemini", "dxc", "hcl",
        "robert half", "randstad", "manpower", "kelly services", "adecco",
        "insight global", "teksystems", "apex systems",
    ])

    for job in jobs:
        title = str(job.get("title", "")).lower()
        description = str(job.get("description", "")).lower()
        location = str(job.get("location", "")).lower()
        company = str(job.get("company", "")).lower()
        text = f"{title} {description} {company}"
        score = 0

        # Role type scoring - prefer managers over IC
        is_manager = any(kw in title for kw in mgmt_titles)
        is_senior_ic = any(kw in title for kw in senior_ic_titles) and not is_manager

        if is_manager:
            score += 25  # Strong preference for people manager roles
        elif is_senior_ic:
            score += 10  # Senior/Lead IC is acceptable
        else:
            score -= 10  # Junior IC roles not preferred

        # Preferred title match (+15)
        if preferred_titles and any(kw in title for kw in preferred_titles):
            score += 15

        # Bad role types (-20)
        if any(kw in title for kw in bad_titles):
            score -= 20

        # Location match (+10)
        if any(loc in location for loc in good_locations):
            score += 10
        if "remote" in location or "remote" in title:
            score += 10

        # Skills boost (+5 each)
        for skill in good_skills:
            if skill in description:
                score += 5

        # Red flags (-10 each)
        for flag in red_flags:
            if flag in text:
                score -= 10

        # Company size heuristic - slight deprioritization for large companies
        # Reduced from -25 to -5 to avoid missing good role/location fits
        is_large_company = any(lc in company for lc in large_companies)
        if is_large_company:
            score -= 5
            job["_large_company"] = True

        # Boost government jobs (typically smaller orgs)
        site = str(job.get("site", "")).lower()
        if site == "usajobs":
            score += 10  # Government jobs are usually smaller orgs
            job["_govt_job"] = True

        job["_score"] = score
        job["_is_manager"] = is_manager
        job["_is_senior_ic"] = is_senior_ic

    # Sort by score descending
    return sorted(jobs, key=lambda x: x.get("_score", 0), reverse=True)


def validate_remote_jobs(jobs: list[dict], salary_threshold: int = 150000) -> list[dict]:
    """Filter out jobs with specific locations when searching remote.

    Keeps jobs if:
    - Location is empty, null, or generic (Remote, USA, United States)
    - Salary is above threshold (worth considering relocation)
    """
    # Generic locations that are OK for remote searches
    # Be careful with short strings that could match city names
    generic_locations = [
        "remote", "usa", "united states", "anywhere",
        "work from home", "wfh", "nationwide"
    ]

    # State abbreviations to detect specific locations
    state_abbrevs = [
        "al", "ak", "az", "ar", "ca", "co", "ct", "de", "fl", "ga",
        "hi", "id", "il", "in", "ia", "ks", "ky", "la", "me", "md",
        "ma", "mi", "mn", "ms", "mo", "mt", "ne", "nv", "nh", "nj",
        "nm", "ny", "nc", "nd", "oh", "ok", "or", "pa", "ri", "sc",
        "sd", "tn", "tx", "ut", "vt", "va", "wa", "wv", "wi", "wy", "dc"
    ]

    validated = []
    for job in jobs:
        location = str(job.get("location") or "").lower().strip()

        # Empty or null location - keep it
        if not location:
            job["_remote_validated"] = True
            validated.append(job)
            continue

        # Generic remote location - keep it
        if any(gen in location for gen in generic_locations):
            job["_remote_validated"] = True
            validated.append(job)
            continue

        # Check if salary is above threshold (worth considering)
        min_salary = job.get("min_amount") or 0
        max_salary = job.get("max_amount") or 0
        salary = max(min_salary, max_salary)
        if salary >= salary_threshold:
            job["_remote_validated"] = False
            job["_high_salary"] = True
            validated.append(job)
            continue

        # Has specific city/state - filter out
        # Check for state abbreviation pattern (e.g., "CA", "NY, US")
        has_state = any(f", {st}" in f", {location}" or location.endswith(f" {st}")
                       for st in state_abbrevs)

        if has_state or "," in location:
            # Specific location detected - skip
            continue

        # Ambiguous - keep it
        job["_remote_validated"] = True
        validated.append(job)

    return validated


def clean_job_data(jobs: list[dict]) -> list[dict]:
    """Clean up NaN values and datetimes for JSON serialization."""
    for job in jobs:
        for key, value in job.items():
            if isinstance(value, float) and value != value:  # NaN check
                job[key] = None
            elif isinstance(value, datetime):
                job[key] = value.isoformat()
    return jobs


def dedupe_jobs(jobs: list[dict]) -> list[dict]:
    """Deduplicate jobs by job_url, keeping first occurrence."""
    seen = set()
    unique = []
    for job in jobs:
        url = job.get("job_url")
        if url and url not in seen:
            seen.add(url)
            unique.append(job)
        elif not url:
            unique.append(job)  # Keep jobs without URLs
    return unique


@app.post("/get-jobs", response_model=JobResponse)
async def get_jobs(request: JobRequest):
    try:
        hours_old = parse_since_when(request.sinceWhen)
        search_term = " ".join(request.keywords) if request.keywords else "software engineer"

        jobs = scrape_single_location(
            search_term=search_term,
            hours_old=hours_old,
            results_wanted=request.limit,
            is_remote=request.isRemote or False,
            location=request.location,
            distance=request.distance or 50,
        )

        # Add USAJOBS results if enabled
        if CONFIG.get("usajobs_enabled") and CONFIG.get("usajobs_api_key"):
            try:
                usajobs = scrape_usajobs(
                    search_term=search_term,
                    hours_old=hours_old,
                    results_wanted=request.limit,
                    is_remote=request.isRemote or False,
                    location=request.location,
                    distance=request.distance or 50,
                )
                jobs.extend(usajobs)
            except Exception as e:
                print(f"Error searching USAJOBS: {e}")

        # Validate remote jobs - filter out non-remote when searching remote
        if request.isRemote:
            jobs = validate_remote_jobs(jobs)

        # Filter out excluded keywords (from request + config)
        exclude_list = list(request.excludeKeywords or []) + CONFIG.get("exclude_keywords", [])
        jobs = filter_jobs(jobs, exclude_list)

        # AND mode: require ALL keywords in title or description
        if request.requireAllKeywords and request.keywords:
            keywords_lower = [kw.lower() for kw in request.keywords]
            jobs = [
                job for job in jobs
                if all(
                    kw in str(job.get("title", "")).lower() or
                    kw in str(job.get("description", "")).lower()
                    for kw in keywords_lower
                )
            ]

        # Score and sort by include_keywords
        include_list = CONFIG.get("include_keywords", [])
        jobs = score_jobs(jobs, include_list)

        jobs = clean_job_data(jobs)
        return JobResponse(error=False, jobs=jobs[:request.limit])

    except Exception as e:
        print(f"Error scraping jobs: {e}")
        return JobResponse(error=True, jobs=[])


@app.post("/search-all", response_model=JobResponse)
async def search_all(request: JobRequest):
    """
    Run searches across all configured locations.
    Uses locations and searches from config.yaml.
    Falls back to single search if no config.
    """
    try:
        hours_old = parse_since_when(request.sinceWhen)
        search_term = " ".join(request.keywords) if request.keywords else "software engineer"

        locations = CONFIG.get("locations", [])
        if not locations:
            # No locations configured - use request params or defaults
            locations = [{"name": "default", "is_remote": request.isRemote or False}]
            if request.location:
                locations = [{"name": request.location, "location": request.location, "distance": request.distance or 50}]

        all_jobs = []
        locations_searched = []

        for loc in locations:
            loc_name = loc.get("name", "unknown")
            is_remote = loc.get("is_remote", False)
            location = loc.get("location")
            distance = loc.get("distance", 50)

            print(f"Searching: {search_term} in {loc_name}...")
            locations_searched.append(loc_name)

            try:
                jobs = scrape_single_location(
                    search_term=search_term,
                    hours_old=hours_old,
                    results_wanted=CONFIG.get("results_wanted", 50),
                    is_remote=is_remote,
                    location=location,
                    distance=distance,
                )

                # Validate remote jobs for this location
                if is_remote:
                    jobs = validate_remote_jobs(jobs)

                # Tag jobs with location source
                for job in jobs:
                    job["_location_name"] = loc_name

                all_jobs.extend(jobs)
            except Exception as e:
                print(f"Error searching {loc_name}: {e}")
                continue

        # Add USAJOBS results if enabled
        if CONFIG.get("usajobs_enabled") and CONFIG.get("usajobs_api_key"):
            for loc in locations:
                loc_name = loc.get("name", "unknown")
                is_remote = loc.get("is_remote", False)
                location = loc.get("location")
                distance = loc.get("distance", 50)

                try:
                    usajobs = scrape_usajobs(
                        search_term=search_term,
                        hours_old=hours_old,
                        results_wanted=CONFIG.get("results_wanted", 50),
                        is_remote=is_remote,
                        location=location,
                        distance=distance,
                    )
                    for job in usajobs:
                        job["_location_name"] = f"{loc_name}_usajobs"
                    all_jobs.extend(usajobs)
                except Exception as e:
                    print(f"Error searching USAJOBS for {loc_name}: {e}")

        # Deduplicate across locations
        all_jobs = dedupe_jobs(all_jobs)

        # Filter excluded keywords
        exclude_list = list(request.excludeKeywords or []) + CONFIG.get("exclude_keywords", [])
        all_jobs = filter_jobs(all_jobs, exclude_list)

        # AND mode filtering
        if request.requireAllKeywords and request.keywords:
            keywords_lower = [kw.lower() for kw in request.keywords]
            all_jobs = [
                job for job in all_jobs
                if all(
                    kw in str(job.get("title", "")).lower() or
                    kw in str(job.get("description", "")).lower()
                    for kw in keywords_lower
                )
            ]

        # Score and sort by include_keywords
        include_list = CONFIG.get("include_keywords", [])
        all_jobs = score_jobs(all_jobs, include_list)

        all_jobs = clean_job_data(all_jobs)

        return JobResponse(
            error=False,
            jobs=all_jobs[:request.limit],
            locations_searched=locations_searched,
        )

    except Exception as e:
        print(f"Error in search-all: {e}")
        return JobResponse(error=True, jobs=[])


@app.get("/health")
async def health():
    return {"status": "ok", "config_loaded": "searches" in CONFIG}


@app.get("/config")
async def get_config():
    """Return current configuration (excluding sensitive data)."""
    return {
        "sites": CONFIG["sites"],
        "hours_old": CONFIG["hours_old"],
        "results_wanted": CONFIG["results_wanted"],
        "country_indeed": CONFIG["country_indeed"],
        "linkedin_fetch_description": CONFIG["linkedin_fetch_description"],
        "searches_count": len(CONFIG.get("searches", [])),
        "locations_count": len(CONFIG.get("locations", [])),
        "exclude_keywords_count": len(CONFIG.get("exclude_keywords", [])),
        "include_keywords_count": len(CONFIG.get("include_keywords", [])),
        "usajobs_enabled": CONFIG.get("usajobs_enabled", False),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

```python
import math
import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


# =============================================================================
# INSTRUCTIONS
# =============================================================================
#
# 1. Export the "Own:Repos" sheet from the following Google Sheet in .xlsx
#    format:
#    https://docs.google.com/spreadsheets/d/1qpWfbPYLSaE_deaumWSEZfz91CshWd3v3B7xhOk5M4U/edit?gid=1990273504#gid=1990273504
#
# 2. Save the exported file as "repos.xlsx" and keep it in the same directory
#    as this script.
#
# 3. Run this script from the directory containing both this script and
#    "repos.xlsx".
#
# 4. The input Excel file must contain the following columns:
#    - repo url
#    - repo org
#    - owner.squad
#    - Repo Maintainer
#
# 5. Set the GITHUB_TOKEN environment variable if GitHub API authentication
#    is required, especially when scanning private repositories.
#
# The script generates an Excel report showing Django versions, Django
# constraints, Django imports/usages, and potential Django 5.2 upgrade risks.
#
# =============================================================================


# =============================================================================
# CONFIG
# =============================================================================

# 1) Load repos, orgs, owners, and maintainers from Excel input file
EXCEL_INPUT = "repos.xlsx"

df_input = pd.read_excel(EXCEL_INPUT)

repos = df_input["repo url"].fillna("").tolist()
repo_orgs = df_input["repo org"].fillna("").tolist()
repo_owners = df_input["owner.squad"].fillna("unknown").tolist()
repo_maintainers = df_input["Repo Maintainer"].fillna("").tolist()

assert (
    len(repos)
    == len(repo_orgs)
    == len(repo_owners)
    == len(repo_maintainers)
), (
    f"Column length mismatch: repos={len(repos)}, orgs={len(repo_orgs)}, "
    f"owners={len(repo_owners)}, maintainers={len(repo_maintainers)}"
)

print(f"Loaded {len(repos)} repos from '{EXCEL_INPUT}'")


# 2) Batching and cooldown
BATCH_SIZE = 10
COOLDOWN_SECONDS = 20


# 3) Output
OUTPUT_XLSX = "django_requirements_report_14.xlsx"


# 4) Network / GitHub
API_BASE = "https://api.github.com/repos"
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
DEFAULT_TIMEOUT = 15


# 5) Search API
#    Search calls are serialized through search_lock to avoid hitting
#    GitHub Search API rate limits when multiple threads are running.
SEARCH_API_SLEEP = 2.5


# =============================================================================
# Session with retries
# =============================================================================

def make_session() -> requests.Session:
    session = requests.Session()

    headers = {
        "Accept": "application/vnd.github.v3+json",
    }

    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"

    session.headers.update(headers)

    retry = Retry(
        total=5,
        connect=5,
        read=5,
        backoff_factor=0.8,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset(["GET"]),
        raise_on_status=False,
    )

    adapter = HTTPAdapter(
        max_retries=retry,
        pool_connections=20,
        pool_maxsize=50,
    )

    session.mount("https://", adapter)
    session.mount("http://", adapter)

    return session


SESSION = make_session()


# =============================================================================
# Locks and result storage
# =============================================================================

results_lock = threading.Lock()

# Serializes GitHub Search API calls across threads to avoid hitting
# the Search API rate limit when multiple workers run concurrently.
search_lock = threading.Lock()

results_rows = []


# =============================================================================
# Regex
# =============================================================================

DJANGO_VERSION_RE = re.compile(
    r"(?<![\w\-])django==\s*([\d\.]+)(?![\w\-])",
    re.IGNORECASE,
)

DJANGO_CONSTRAINT_RE = re.compile(
    r"(?<![\w\-])(django\s*[><=!~]+\s*[\d\.]+)(?![\w\-])",
    re.IGNORECASE,
)


# =============================================================================
# Helper to extract owner/repo from GitHub URL
# =============================================================================

def extract_repo_path(url_or_path: str) -> str:
    url_or_path = url_or_path.rstrip("/")

    if url_or_path.startswith(("http://", "https://")):
        parts = url_or_path.split("github.com/")

        if len(parts) > 1:
            return parts[1]

    return url_or_path


# =============================================================================
# Thread-safe result store and Excel writer
# =============================================================================

def write_excel_safely(
    filename: str,
    rows: list,
    retries: int = 5,
    sleep_s: float = 1.2,
):
    """
    Write the current results to Excel with retries.

    Retries are useful when the output file is temporarily in use,
    particularly on Windows.
    """
    last_exc = None

    columns = [
        "repo",
        "repo_org",
        "owner",
        "repo maintainer",
        "django_version",
        "constraint",
        "upgrade_to_5_2_risk",
        "has *.py files",
        "has import django files",
        "Has Django keyword",
    ]

    for attempt in range(1, retries + 1):
        try:
            df = pd.DataFrame(rows, columns=columns)

            with pd.ExcelWriter(
                filename,
                engine="openpyxl",
                mode="w",
            ) as writer:
                df.to_excel(writer, index=False)

            return

        except Exception as exc:
            last_exc = exc
            print(
                f"Excel write attempt {attempt}/{retries} failed: {exc}"
            )
            time.sleep(sleep_s)

    print(
        f"Could not write Excel after {retries} attempts. "
        f"Last error: {last_exc}"
    )


# =============================================================================
# Helper: GitHub GET wrappers
# =============================================================================

def get_json(url: str):
    response = SESSION.get(url, timeout=DEFAULT_TIMEOUT)
    response.raise_for_status()

    return response.json(), response


def get_text(url: str):
    response = SESSION.get(url, timeout=DEFAULT_TIMEOUT)
    response.raise_for_status()

    return response.text, response


def explain_403(resp, repo: str, note: str) -> str:
    try:
        api_msg = resp.json().get("message", "")
    except Exception:
        api_msg = resp.text

    sso_header = resp.headers.get("X-GitHub-SSO")
    rate_limit_remaining = resp.headers.get("X-RateLimit-Remaining")
    rate_limit_reset = resp.headers.get("X-RateLimit-Reset")

    print(f"403 Forbidden for {repo} ({note})")
    print(f"API message: {api_msg}")

    if sso_header:
        print(f"SSO header: {sso_header}")

    if rate_limit_remaining is not None:
        print(
            f"Rate limit remaining: {rate_limit_remaining}, "
            f"reset: {rate_limit_reset}"
        )

    if sso_header:
        return "Forbidden – org SSO authorization required"

    if (
        "rate limit" in (api_msg or "").lower()
        or rate_limit_remaining == "0"
    ):
        return "Forbidden – rate limited"

    if "Resource not accessible by integration" in (api_msg or ""):
        return "Forbidden – token/integration lacks repo access"

    return "Forbidden – private repo or insufficient scopes"


def is_repo_archived(repo: str) -> tuple:
    url = f"{API_BASE}/{repo}"

    try:
        data, _ = get_json(url)
        archived = data.get("archived", False)

        return archived, None

    except requests.exceptions.HTTPError as exc:
        code = (
            exc.response.status_code
            if exc.response is not None
            else "?"
        )

        return False, f"HTTP_{code}"

    except requests.exceptions.RequestException as exc:
        return False, f"NETWORK_ERR:{exc}"


# =============================================================================
# Check for .py files using Git Tree API
# =============================================================================

def check_py_files(repo: str) -> tuple:
    url = f"{API_BASE}/{repo}/git/trees/HEAD?recursive=1"

    try:
        data, _ = get_json(url)
        tree = data.get("tree", [])
        truncated = data.get("truncated", False)

        has_py = any(
            item.get("path", "").endswith(".py")
            for item in tree
        )

        if truncated and not has_py:
            print(
                f"[{repo}] Git tree was truncated. "
                "Cannot confirm no .py files exist."
            )
            return None, "Tree truncated – result may be incomplete"

        return has_py, None

    except requests.exceptions.HTTPError as exc:
        code = (
            exc.response.status_code
            if exc.response is not None
            else "?"
        )

        return None, f"HTTP_{code}"

    except requests.exceptions.RequestException as exc:
        return None, f"NETWORK_ERR:{exc}"


# =============================================================================
# GitHub Code Search API helper
# =============================================================================

def search_github_code(repo: str, query: str) -> tuple:
    with search_lock:
        url = "https://api.github.com/search/code"

        params = {
            "q": f"{query} repo:{repo}",
            "per_page": 1,
        }

        try:
            response = SESSION.get(
                url,
                params=params,
                timeout=DEFAULT_TIMEOUT,
            )

            remaining = int(
                response.headers.get("X-RateLimit-Remaining", 1)
            )

            if remaining == 0 or response.status_code in (403, 429):
                reset_ts = int(
                    response.headers.get(
                        "X-RateLimit-Reset",
                        time.time() + 60,
                    )
                )

                sleep_s = max(
                    reset_ts - int(time.time()),
                    15,
                )

                print(
                    f"Search API rate limited. Sleeping {sleep_s}s..."
                )

                time.sleep(sleep_s)

                response = SESSION.get(
                    url,
                    params=params,
                    timeout=DEFAULT_TIMEOUT,
                )

            response.raise_for_status()

            data = response.json()
            total = data.get("total_count", 0)

        except requests.exceptions.HTTPError as exc:
            code = (
                exc.response.status_code
                if exc.response is not None
                else "?"
            )

            time.sleep(SEARCH_API_SLEEP)

            return None, f"HTTP_{code}"

        except requests.exceptions.RequestException as exc:
            time.sleep(SEARCH_API_SLEEP)

            return None, f"NETWORK_ERR:{exc}"

        time.sleep(SEARCH_API_SLEEP)

        return total > 0, None


# =============================================================================
# Check Django imports in Python files
# =============================================================================

def check_has_django_imports(repo: str) -> tuple:
    found, error = search_github_code(
        repo,
        '"from django" in:file language:python',
    )

    if error:
        return None, error

    if found:
        return True, None

    found, error = search_github_code(
        repo,
        '"import django" in:file language:python',
    )

    if error:
        return None, error

    return found, None


# =============================================================================
# Check for any Django keyword in the repository
# =============================================================================

def check_has_django_keyword(repo: str) -> tuple:
    return search_github_code(
        repo,
        "django in:file",
    )


# =============================================================================
# Core scan functions
# =============================================================================

def get_requirements_files(repo: str):
    url = f"{API_BASE}/{repo}/contents/requirements"

    print(f"[{repo}] Checking requirements folder: {url}")

    try:
        data, _ = get_json(url)

        files = [
            (file["name"], file["download_url"])
            for file in data
            if file.get("name", "").endswith(".txt")
        ]

        print(
            f"[{repo}] requirements/ found "
            f"({len(files)} .txt files)"
        )

        return None, files

    except requests.exceptions.HTTPError as exc:
        code = (
            exc.response.status_code
            if exc.response is not None
            else "?"
        )

        if code == 404:
            print(f"[{repo}] requirements/ not found")
            return "NOT_FOUND", []

        if code == 403:
            reason = explain_403(
                exc.response,
                repo,
                "list requirements",
            )
            return f"HTTP_403:{reason}", []

        return f"HTTP_{code}:{exc}", []

    except requests.exceptions.RequestException as exc:
        print(f"[{repo}] Network error: {exc}")
        return f"NETWORK_ERR:{exc}", []


def fetch_file_text(repo: str, name: str, url: str):
    try:
        text, _ = get_text(url)
        return None, text

    except requests.exceptions.HTTPError as exc:
        code = (
            exc.response.status_code
            if exc.response is not None
            else "?"
        )

        return f"HTTP_{code}:{exc}", ""

    except requests.exceptions.RequestException as exc:
        return f"NETWORK_ERR:{exc}", ""


def strip_comments(text: str) -> str:
    clean_lines = [
        line.split("#")[0]
        for line in text.splitlines()
    ]

    return "\n".join(clean_lines)


def evaluate_upgrade_risk(
    django_version,
    constraints: set,
) -> str:
    risk = "Unknown – manual review"

    if django_version:
        try:
            parts = django_version.split(".")[:2]

            major_minor = (
                int(parts[0]),
                int(parts[1]) if len(parts) > 1 else 0,
            )

            if major_minor >= (5, 2):
                return "No – already 5.2+"

            return "Yes – upgrade needed (< 5.2)"

        except Exception:
            return "Unknown version format"

    if constraints:
        flat = "".join(
            constraint.replace(" ", "").lower()
            for constraint in constraints
        )

        if (
            "django<5.2" in flat
            or "django<=5.1" in flat
        ):
            return "Yes – constraint prevents 5.2"

        return "Possibly ok – check manually"

    return risk


# =============================================================================
# Main per-repo scan
# =============================================================================

def scan_single_repo(
    repo: str,
    org: str,
    owner: str,
    maintainer: str,
):
    """
    Scan a single repository and return a row tuple.
    """

    print("\n" + "-" * 78)
    print(f"Scanning: {repo} (Org: {org})")
    print("-" * 78)

    # =========================================================================
    # FAST FAIL: Check if we have API access to the repository
    # =========================================================================

    is_archived, archive_check_error = is_repo_archived(repo)

    if is_archived:
        print(f"[{repo}] Repository is archived – skipping.")
        return None

    if archive_check_error:
        print(
            f"[{repo}] Repo inaccessible "
            f"(Base check failed): {archive_check_error}"
        )

        return (
            repo,
            org,
            owner,
            maintainer,
            f"Error ({archive_check_error})",
            f"Error ({archive_check_error})",
            "Unknown – manual review",
            f"Error ({archive_check_error})",
            f"Error ({archive_check_error})",
            f"Error ({archive_check_error})",
        )

    # =========================================================================
    # CHECK 1: Has *.py files?
    # =========================================================================

    print(
        f"[{repo}] Checking for .py files via Git Tree API..."
    )

    has_py, py_error = check_py_files(repo)

    if py_error:
        has_py_display = f"Error ({py_error})"
        print(
            f"[{repo}] .py file check error: {py_error}"
        )
    else:
        has_py_display = str(has_py)
        print(
            f"[{repo}] Has .py files: {has_py}"
        )

    # =========================================================================
    # CHECK 2: Has Django imports in Python files?
    # =========================================================================

    print(
        f"[{repo}] Searching for Django imports "
        "(Search API)..."
    )

    has_django_imports, django_import_error = (
        check_has_django_imports(repo)
    )

    if django_import_error:
        has_django_imports_display = (
            f"Error ({django_import_error})"
        )

        print(
            f"[{repo}] Django import check error: "
            f"{django_import_error}"
        )
    else:
        has_django_imports_display = str(
            has_django_imports
        )

        print(
            f"[{repo}] Has Django imports: "
            f"{has_django_imports}"
        )

    # =========================================================================
    # CHECK 3: Has Django keyword anywhere in the repo?
    # =========================================================================

    print(
        f"[{repo}] Searching for 'django' keyword "
        "in any file (Search API)..."
    )

    has_django_keyword, django_keyword_error = (
        check_has_django_keyword(repo)
    )

    if django_keyword_error:
        has_django_keyword_display = (
            f"Error ({django_keyword_error})"
        )

        print(
            f"[{repo}] Django keyword check error: "
            f"{django_keyword_error}"
        )
    else:
        has_django_keyword_display = str(
            has_django_keyword
        )

        print(
            f"[{repo}] Has Django keyword: "
            f"{has_django_keyword}"
        )

    # =========================================================================
    # CHECK 4: requirements/ scan
    # =========================================================================

    status, files = get_requirements_files(repo)

    if status == "NOT_FOUND":
        print(
            f"[{repo}] Summary: No requirements folder."
        )

        return (
            repo,
            org,
            owner,
            maintainer,
            "Not Found",
            "Not Found",
            "Unknown – manual review",
            has_py_display,
            has_django_imports_display,
            has_django_keyword_display,
        )

    if status and status.startswith("HTTP_403"):
        print(
            f"[{repo}] Summary: 403 – {status}"
        )

        return (
            repo,
            org,
            owner,
            maintainer,
            "Forbidden",
            status,
            "Unknown – manual review",
            has_py_display,
            has_django_imports_display,
            has_django_keyword_display,
        )

    if status and (
        status.startswith("HTTP_")
        or status.startswith("NETWORK_ERR")
    ):
        print(
            f"[{repo}] Summary: Error – {status}"
        )

        return (
            repo,
            org,
            owner,
            maintainer,
            "Error",
            status,
            "Unknown – manual review",
            has_py_display,
            has_django_imports_display,
            has_django_keyword_display,
        )

    if not files:
        print(
            f"[{repo}] Summary: No requirement files found."
        )

        return (
            repo,
            org,
            owner,
            maintainer,
            "Not Found",
            "Not Found",
            "Unknown – manual review",
            has_py_display,
            has_django_imports_display,
            has_django_keyword_display,
        )

    django_version = None
    django_constraints = set()

    for name, url in files:
        print(f"[{repo}] Reading: {name}")

        file_status, text = fetch_file_text(
            repo,
            name,
            url,
        )

        if file_status:
            print(
                f"[{repo}] Skipping {name}: "
                f"{file_status}"
            )
            continue

        clean_text = strip_comments(text)

        pins = DJANGO_VERSION_RE.findall(clean_text)

        if pins:
            django_version = pins[-1]
            print(
                f"[{repo}] django== found: {pins}"
            )

        for constraint in DJANGO_CONSTRAINT_RE.findall(
            clean_text
        ):
            constraint = constraint.strip()

            if constraint.lower().startswith("django"):
                django_constraints.add(constraint)
                print(
                    f"[{repo}] constraint: {constraint}"
                )

    constraint_str = (
        ", ".join(sorted(django_constraints))
        if django_constraints
        else "None"
    )

    risk = evaluate_upgrade_risk(
        django_version,
        django_constraints,
    )

    print(f"[{repo}] Summary:")
    print(f"    Org                 : {org or 'N/A'}")
    print(
        f"    Django Version      : "
        f"{django_version or 'Not Found'}"
    )
    print(f"    Constraints         : {constraint_str}")
    print(f"    Upgrade to 5.2 Risk : {risk}")
    print(
        f"    Repo Maintainer     : "
        f"{maintainer or 'N/A'}"
    )
    print(
        f"    Has *.py files      : "
        f"{has_py_display}"
    )
    print(
        f"    Has Django imports  : "
        f"{has_django_imports_display}"
    )
    print(
        f"    Has Django keyword  : "
        f"{has_django_keyword_display}"
    )

    return (
        repo,
        org,
        owner,
        maintainer,
        django_version or "Not Found",
        constraint_str,
        risk,
        has_py_display,
        has_django_imports_display,
        has_django_keyword_display,
    )


# =============================================================================
# Batching runner
# =============================================================================

def chunked(seq, size):
    for index in range(0, len(seq), size):
        yield seq[index:index + size]


def process_batch(batch_items: list):
    print("\n" + "=" * 78)
    print(
        f"Starting batch of {len(batch_items)} repos"
    )
    print("=" * 78)

    with ThreadPoolExecutor(
        max_workers=min(BATCH_SIZE, len(batch_items))
    ) as executor:
        future_map = {
            executor.submit(
                scan_single_repo,
                repo,
                org,
                owner,
                maintainer,
            ): (
                repo,
                org,
                owner,
                maintainer,
            )
            for repo, org, owner, maintainer in batch_items
        }

        for future in as_completed(future_map):
            (
                repo,
                org,
                owner,
                maintainer,
            ) = future_map[future]

            try:
                row = future.result()

            except Exception as exc:
                print(
                    f"[{repo}] Worker crashed: {exc}"
                )

                row = (
                    repo,
                    org,
                    owner,
                    maintainer,
                    "Error",
                    f"WORKER_ERR:{exc}",
                    "Unknown – manual review",
                    "Unknown",
                    "Unknown",
                    "Unknown",
                )

            if row is None:
                continue

            with results_lock:
                results_rows.append(row)

                write_excel_safely(
                    OUTPUT_XLSX,
                    results_rows,
                )

    print("Batch complete.")


# =============================================================================
# Main
# =============================================================================

if __name__ == "__main__":
    # Filter out blank repository URLs from the input spreadsheet.
    processed = [
        (
            extract_repo_path(repo),
            org,
            owner,
            maintainer,
        )
        for repo, org, owner, maintainer in zip(
            repos,
            repo_orgs,
            repo_owners,
            repo_maintainers,
        )
        if str(repo).strip()
    ]

    total = len(processed)
    total_batches = math.ceil(total / BATCH_SIZE)

    print(
        f"Total repos: {total}, "
        f"batch size: {BATCH_SIZE}, "
        f"total batches: {total_batches}"
    )

    # Write an empty output file at the start.
    with results_lock:
        write_excel_safely(
            OUTPUT_XLSX,
            results_rows,
        )

    for index, batch in enumerate(
        chunked(processed, BATCH_SIZE),
        start=1,
    ):
        print(
            f"\nBatch {index}/{total_batches}"
        )

        process_batch(batch)

        if index < total_batches:
            print(
                f"Cooling down {COOLDOWN_SECONDS}s "
                "before next batch..."
            )
            time.sleep(COOLDOWN_SECONDS)

    print(
        f"\nAll done. Final Excel: {OUTPUT_XLSX}"
    )
```

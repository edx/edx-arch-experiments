"""
Audit Django versions and upgrade readiness across a list of GitHub repos.

Refer to the following Confluence page for the audit details and
documentation:
https://2u-internal.atlassian.net/wiki/spaces/AT/pages/4088659996/Django+5.2+spreadsheet+generation
"""

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


# Load repos, orgs, owners, and maintainers from Excel input file
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


TARGET_DJANGO_VERSION = "5.2"
BATCH_SIZE = 10
COOLDOWN_SECONDS = 20

REPORT_RUN_TIMESTAMP = time.strftime("%Y%m%d_%H%M%S")

TARGET_VERSION_SLUG = TARGET_DJANGO_VERSION.replace(".", "_")

OUTPUT_XLSX = (
    f"django_{TARGET_VERSION_SLUG}_upgrade_audit_"
    f"{REPORT_RUN_TIMESTAMP}.xlsx"
)

# Excel caps worksheet names at 31 characters, so keep this short.
OUTPUT_SHEET_NAME = f"Django {TARGET_DJANGO_VERSION} Audit"[:31]

# Network / GitHub
API_BASE = "https://api.github.com/repos"
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
DEFAULT_TIMEOUT = 15

# Serialize GitHub Search API calls to avoid rate limits.
SEARCH_API_SLEEP = 2.5


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

# Locks and result storage
results_lock = threading.Lock()

# Serialize GitHub Search API calls across threads to avoid rate limits.
search_lock = threading.Lock()

results_rows = []

DJANGO_VERSION_RE = re.compile(
    r"(?<![\w\-])django==\s*([\d\.]+)(?![\w\-])",
    re.IGNORECASE,
)

DJANGO_CONSTRAINT_RE = re.compile(
    r"(?<![\w\-])(django\s*[><=!~]+\s*[\d\.]+)(?![\w\-])",
    re.IGNORECASE,
)

# Splits a Django constraint into its operator and version for target evaluation.
CONSTRAINT_PARTS_RE = re.compile(
    r"^django\s*(===|==|>=|<=|!=|~=|<|>)\s*([\d\.\*xX]+)$",
    re.IGNORECASE,
)


def parse_version(version_text) -> tuple:
    """
    Parse a dotted release string into a comparable tuple of ints.

        "5.2"     -> (5, 2)
        "4.2.11"  -> (4, 2, 11)
        "4.2.*"   -> (4, 2)      wildcard component ends the tuple
        "5.0rc1"  -> (5, 0)      pre-release suffix is truncated

    Returns None when nothing usable can be parsed.
    """
    if not version_text:
        return None

    parts = []

    for chunk in str(version_text).strip().split("."):
        chunk = chunk.strip()

        if chunk in ("", "*", "x", "X"):
            break

        if chunk.isdigit():
            parts.append(int(chunk))
            continue

        leading_digits = re.match(r"\d+", chunk)

        if not leading_digits:
            return None

        parts.append(int(leading_digits.group()))
        break

    return tuple(parts) or None


def take_components(version: tuple, count: int) -> tuple:
    """Right-pad a version tuple with zeros, then take `count` components."""
    padded = version + (0,) * max(0, count - len(version))

    return padded[:count]


def compare_versions(left: tuple, right: tuple) -> int:
    """Return -1, 0 or 1 comparing two version tuples of any length."""
    width = max(len(left), len(right))

    left_padded = take_components(left, width)
    right_padded = take_components(right, width)

    if left_padded < right_padded:
        return -1

    if left_padded > right_padded:
        return 1

    return 0


def constraint_allows_target(constraint_text: str, target: tuple):
    """
    Evaluate one captured constraint against the target version.

    Returns:
        True  -> the constraint permits the target version
        False -> the constraint blocks the target version
        None  -> the constraint could not be parsed (needs manual review)
    """
    match = CONSTRAINT_PARTS_RE.match(constraint_text.strip())

    if not match:
        return None

    operator = match.group(1)
    version_text = match.group(2)

    version = parse_version(version_text)

    if version is None:
        return None

    is_wildcard = (
        "*" in version_text
        or version_text.lower().rstrip(".").endswith("x")
    )

    if operator in ("==", "==="):
        if is_wildcard:
            return take_components(target, len(version)) == version

        return compare_versions(target, version) == 0

    if operator == "!=":
        if is_wildcard:
            return take_components(target, len(version)) != version

        return compare_versions(target, version) != 0

    if operator == "<":
        return compare_versions(target, version) < 0

    if operator == "<=":
        return compare_versions(target, version) <= 0

    if operator == ">":
        return compare_versions(target, version) > 0

    if operator == ">=":
        return compare_versions(target, version) >= 0

    if operator == "~=":
        # Compatible release:
        #   ~=X.Y   means  >= X.Y   and  == X.*
        #   ~=X.Y.Z means  >= X.Y.Z and  == X.Y.*
        if len(version) < 2:
            return None

        if compare_versions(target, version) < 0:
            return False

        prefix = version[:-1]

        return take_components(target, len(prefix)) == prefix

    return None


TARGET_VERSION_TUPLE = parse_version(TARGET_DJANGO_VERSION)

assert TARGET_VERSION_TUPLE is not None, (
    f"TARGET_DJANGO_VERSION={TARGET_DJANGO_VERSION!r} is not a valid "
    'dotted release number (expected something like "5.2")'
)


# Helper to extract owner/repo from GitHub URL
def extract_repo_path(url_or_path: str) -> str:
    url_or_path = url_or_path.rstrip("/")

    if url_or_path.startswith(("http://", "https://")):
        parts = url_or_path.split("github.com/")

        if len(parts) > 1:
            return parts[1]

    return url_or_path


# Thread-safe result store and Excel writer
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
        f"upgrade_to_{TARGET_VERSION_SLUG}_risk",
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
                df.to_excel(
                    writer,
                    index=False,
                    sheet_name=OUTPUT_SHEET_NAME,
                )

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


# Helper: GitHub GET wrappers
def get_json(url: str):
    response = SESSION.get(url, timeout=DEFAULT_TIMEOUT)
    response.raise_for_status()

    return response.json(), response


def get_text(url: str):
    response = SESSION.get(url, timeout=DEFAULT_TIMEOUT)
    response.raise_for_status()

    return response.text, response


# Handles GitHub App authentication errors when repository access is restricted.
INTEGRATION_403_MESSAGE = "resource not accessible by integration"


def explain_403(resp, repo: str, note: str) -> str:
    """
    Classify a 403 response into an actionable reason.

    The checks are ordered most-specific first, and each branch prints its own
    diagnostic immediately before returning, so no condition is evaluated or
    logged twice.
    """
    try:
        api_msg = resp.json().get("message", "")
    except Exception:
        api_msg = resp.text

    api_msg = api_msg or ""
    api_msg_lower = api_msg.lower()

    sso_header = resp.headers.get("X-GitHub-SSO")
    rate_limit_remaining = resp.headers.get("X-RateLimit-Remaining")
    rate_limit_reset = resp.headers.get("X-RateLimit-Reset")

    print(f"403 Forbidden for {repo} ({note})")
    print(f"API message: {api_msg or '(no message)'}")

    if sso_header:
        print(f"SSO header: {sso_header}")
        return "Forbidden – org SSO authorization required"

    if rate_limit_remaining == "0" or "rate limit" in api_msg_lower:
        print(
            f"Rate limit remaining: {rate_limit_remaining}, "
            f"reset: {rate_limit_reset}"
        )
        return "Forbidden – rate limited"

    if INTEGRATION_403_MESSAGE in api_msg_lower:
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


# Check for .py files using Git Tree API
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


# GitHub Code Search API helper
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


# Check Django imports in Python files
def check_has_django_imports(repo: str) -> tuple:
    # Both spellings count as a Django import, so short-circuit on the first
    # hit. Add further spellings to this tuple rather than to the body.
    for query in ('"from django"', '"import django"'):
        found, error = search_github_code(
            repo,
            f"{query} in:file language:python",
        )

        if error:
            return None, error

        if found:
            return True, None

    return False, None


# Check for any Django keyword in the repository
def check_has_django_keyword(repo: str) -> tuple:
    return search_github_code(
        repo,
        "django in:file",
    )


# Shared runner for per-repository checks and result formatting.
def run_repo_check(repo: str, label: str, check_fn) -> str:
    print(f"[{repo}] {label}: checking...")

    value, error = check_fn(repo)

    display = f"Error ({error})" if error else str(value)

    print(f"[{repo}] {label}: {display}")

    return display


# Core scan functions
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
    """
    Decide whether a repo can move to TARGET_DJANGO_VERSION; changing the target
    version is sufficient to retarget the audit for a future Django release.
    """
    target_label = TARGET_DJANGO_VERSION

    if django_version:
        version = parse_version(django_version)

        if version is None:
            return "Unknown version format"

        if compare_versions(version, TARGET_VERSION_TUPLE) >= 0:
            return f"No – already {target_label}+"

        return f"Yes – upgrade needed (< {target_label})"

    if constraints:
        verdicts = {
            constraint: constraint_allows_target(
                constraint,
                TARGET_VERSION_TUPLE,
            )
            for constraint in constraints
        }

        blocking = sorted(
            constraint
            for constraint, allowed in verdicts.items()
            if allowed is False
        )

        if blocking:
            return (
                f"Yes – constraint prevents {target_label} "
                f"({', '.join(blocking)})"
            )

        unparsed = sorted(
            constraint
            for constraint, allowed in verdicts.items()
            if allowed is None
        )

        if unparsed:
            return (
                f"Unknown – unparsed constraint "
                f"({', '.join(unparsed)}) – manual review"
            )

        return f"Possibly ok – constraints allow {target_label}"

    return "Unknown – manual review"


# Main per-repo scan
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

    # FAST FAIL: Check if we have API access to the repository
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

    # CHECKS 1-3: .py files, Django imports, Django keyword
    has_py_display = run_repo_check(
        repo,
        "Has *.py files",
        check_py_files,
    )

    has_django_imports_display = run_repo_check(
        repo,
        "Has Django imports",
        check_has_django_imports,
    )

    has_django_keyword_display = run_repo_check(
        repo,
        "Has Django keyword",
        check_has_django_keyword,
    )

    # CHECK 4: requirements/ scan
    status, files = get_requirements_files(repo)

    # get_requirements_files returns None as the status on success, so
    # normalize it here and the startswith() checks below stay readable.
    status = status or ""

    # Shared row fragments for the early returns below.
    base_result = (
        repo,
        org,
        owner,
        maintainer,
    )

    manual_review = (
        "Unknown – manual review",
        has_py_display,
        has_django_imports_display,
        has_django_keyword_display,
    )

    # Check error statuses before empty-file handling to preserve the actual error.
    if status.startswith("HTTP_403"):
        print(f"[{repo}] Summary: 403 – {status}")

        return (*base_result, "Forbidden", status, *manual_review)

    if status.startswith("HTTP_") or status.startswith("NETWORK_ERR"):
        print(f"[{repo}] Summary: Error – {status}")

        return (*base_result, "Error", status, *manual_review)

    if status == "NOT_FOUND" or not files:
        message = (
            "No requirements folder."
            if status == "NOT_FOUND"
            else "No requirement files found."
        )

        print(f"[{repo}] Summary: {message}")

        return (*base_result, "Not Found", "Not Found", *manual_review)

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
    print(
        f"    Upgrade Risk        : {risk} "
        f"(target Django {TARGET_DJANGO_VERSION})"
    )
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
        *base_result,
        django_version or "Not Found",
        constraint_str,
        risk,
        has_py_display,
        has_django_imports_display,
        has_django_keyword_display,
    )


# Batching runner
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
        f"Auditing upgrade readiness for Django "
        f"{TARGET_DJANGO_VERSION}"
    )
    print(
        f"Total repos: {total}, "
        f"batch size: {BATCH_SIZE}, "
        f"total batches: {total_batches}"
    )
    print(f"Report will be written to: {OUTPUT_XLSX}")

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

"""
Script to get the annotations from all checks in a repo in a given date range.

Run with --help (or see docstring of `run`) for more details.
"""

import json
import os
import time
from datetime import datetime
from os import path

import click
import requests


def _ensure_dir(base, *more):
    """
    Join these path segments, create as dir if not already, and return the path.
    """
    subdir = path.join(base, *more)
    os.makedirs(subdir, exist_ok=True)
    return subdir


class ActionsDownloader:

    def __init__(self, *, output_dir, token):
        self.output_dir = output_dir
        self.api_headers = {
            'Accept': 'application/vnd.github+json',
            'Authorization': f"Bearer {token}",
            'X-GitHub-Api-Version': '2022-11-28',
        }

        # Unix epoch timestamp in seconds when GitHub will allow us to
        # resume making requests (or None if not rate-limited)
        self.github_sleep_until_s = None

        # The actual contents doesn't really matter, but empty files might
        # be confusing and maybe the fetch date will be useful.
        self.download_marker_data = {
            'fetch_run_timestamp': datetime.utcnow().isoformat(),
        }
        self.workflow_fetch_params = {
            # We don't want the response to include all the PRs that include this commit.
            # It can be large for active repos and it doesn't help us.
            'exclude_pull_requests': 'true',
        }

    def _github_get(self, url, *, params=None):
        """
        GET the url with GitHub auth token and return a `requests` response.

        Performs both proactive backoff based on response header hints and
        reactive backoff based on error responses responses.

        Docs:
        - https://docs.github.com/en/rest/using-the-rest-api/best-practices-for-using-the-rest-api?apiVersion=2022-11-28
        - https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api?apiVersion=2022-11-28
        """
        backoff_s = None  # exponential backoff in seconds, or None if not in effect
        while True:
            # If GitHub has told us how long to wait, use that instead of the
            # current exponential backoff value.
            if self.github_sleep_until_s is not None:
                # Add slop to prevent tight loop on expiry
                sleep_s = self.github_sleep_until_s + 5.0 - time.time()
            else:
                sleep_s = backoff_s

            if sleep_s and sleep_s > 0:
                time.sleep(sleep_s)

            response = requests.get(url, params=params, headers=self.api_headers, timeout=20.0)

            # Update rate-limiting data for next call
            if out_of_requests := (response.headers.get('x-ratelimit-remaining') == '0'):
                self.github_sleep_until_s = int(response.headers.get('x-ratelimit-reset'))
                print(
                    "Reached rate limit. "
                    f"Will wait {int(self.github_sleep_until_s - time.time())} seconds "
                    "before next request."
                )
            else:
                self.github_sleep_until_s = None
                backoff_s = None

            if response.status_code == 200:
                # We're good to go!
                return response
            elif out_of_requests:
                # We got an error and have been informed we're out of requests.
                # (Should be a 429 or 403 according to GitHub's docs.) We'll try
                # again.
                continue
            elif response.status_code == 429:
                # It's possible that GitHub might give us a 429 without the
                # expected rate-limiting headers.
                print("Rate-limited without timing hint; performing exponential backoff.")
                backoff_s = 2 * backoff_s if backoff_s else 4
                continue
            else:
                # Generic error case
                response.raise_for_status()

    def _write_json(self, data, *path_parts):
        """
        Write data as pretty-printed JSON to the given path (joining as needed).
        """
        with open(path.join(*path_parts), 'w') as f:
            json.dump(data, f, sort_keys=True, indent=2)

    def _log_attempt(self, attempt, workflow_dir):
        """
        Log this attempt and all of its checks and annotations.
        """
        attempt_dir = _ensure_dir(workflow_dir, f"attempt_{attempt['run_attempt']}")

        attempt_file = path.join(attempt_dir, f"attempt.json")
        if path.isfile(attempt_file):
            print("Attempt already fully downloaded; skipping.")
            return

        # Get the checks associated with this workflow run -- this
        # includes output title, summary, and text.
        for check_run in self._github_get(attempt['check_suite_url'] + '/check-runs').json()['check_runs']:
            self._write_json(check_run, attempt_dir, f"check_run_{check_run['id']}.json")

            annotations = self._github_get(check_run['output']['annotations_url']).json()
            self._write_json(annotations, attempt_dir, f"annotations_{check_run['id']}.json")

        # Do this last, indicating that the attempt was completely
        # downloaded. This allows us to skip it next time.
        self._write_json(attempt, attempt_file)

    def _list_all_attempts(self, run):
        """
        Yield all attempts of the given workflow run, including that one.
        """
        yield run
        while next_url := run.get('previous_attempt_url'):
            resp = self._github_get(next_url, params=self.workflow_fetch_params)
            run = resp.json()
            yield run

    def _download_workflow_run(self, run, repo_dir):
        print(f"Downloading workflow run id={run['id']}")

        workflow_dir = _ensure_dir(repo_dir, f"run_{run['id']}",)

        download_marker = path.join(workflow_dir, f"download-marker.json")
        if path.isfile(download_marker):
            print("Workflow already fully downloaded; skipping.")
            return

        # We're getting the *most recent attempt* of a run. Spool
        # out the whole list of attempts and write them out.
        for attempt in self._list_all_attempts(run):
            self._log_attempt(attempt, workflow_dir)

        # Once all attempts have been logged, write out a marker file
        # that indicates this workflow has been completely downloaded
        # and can be skipped in the future.
        self._write_json(self.download_marker_data, download_marker)

    def _list_completed_runs(self, owner, repo, start_date, end_date):
        """
        Yield all completed workflow runs.
        """
        # https://docs.github.com/en/rest/actions/workflow-runs?apiVersion=2022-11-28#list-workflow-runs-for-a-repository
        runs_url = f"https://api.github.com/repos/{owner}/{repo}/actions/runs"
        while runs_url is not None:
            params = {
                **self.workflow_fetch_params,
                # Filter on status=completed to get all workflows that have finished
                # running. The API docs allow you to use a status *or* a conclusion
                # here, but doesn't explain their relationship. The check run API docs
                # seem to cover basically the same values, though:
                # https://docs.github.com/en/rest/guides/using-the-rest-api-to-interact-with-checks?apiVersion=2022-11-28#about-check-runs
                'status': 'completed',
                # https://docs.github.com/en/search-github/getting-started-with-searching-on-github/understanding-the-search-syntax#query-for-dates
                'created': f'{start_date}..{end_date}',
                'per_page': 100,
            }
            print(f"Requesting {runs_url} with {params=!r}")
            resp = self._github_get(runs_url, params=params)
            yield from resp.json()['workflow_runs']
            runs_url = resp.links.get('next', {}).get('url')

    def download(self, owner, repo, start_date, end_date):
        repo_dir = _ensure_dir(self.output_dir, owner, repo)

        for workflow_run in self._list_completed_runs(owner, repo, start_date, end_date):
            self._download_workflow_run(workflow_run, repo_dir)


@click.command()
@click.option(
    '--token', envvar='GITHUB_TOKEN',
    required=True,
    help="A GitHub access token that has access to the repository.",
)
@click.option(
    '--output-dir', type=click.Path(file_okay=False, dir_okay=True, writable=True),
    required=True,
    help="A directory (or path where one can be created) where the output will be written.",
)
@click.option(
    '--owner', type=str, required=True,
    help="Owning user or organization of the repo, e.g. openedx.",
)
@click.option(
    '--repo', type=str, required=True,
    help="Repo shortname, e.g. edx-platform.",
)
@click.option(
    '--start-date', type=click.DateTime(formats=["%Y-%m-%d"]), required=True,
    help="Only fetch workflow runs starting from this date.",
)
@click.option(
    '--end-date', type=click.DateTime(formats=["%Y-%m-%d"]), required=True,
    help="Only fetch workflow runs up through this date.",
)
def run(*, token, output_dir, owner, repo, start_date, end_date):
    """
    Fetch information about workflows and check outcomes for a repository
    within some date range, writing the output to a directory.

    This script will fetch:

    \b
    - Workflow runs, including prior attempts
    - Check runs associated with the attempts
    - Annotations produced by the checks

    The output directory will contain subdirectories of the form
    `{OWNER}/{REPO}/run_#/attempt_#/` for each attempt of a workflow run.
    (run_# is numbered by workflow run ID, and attempt_# by attempt index.)
    The run_# directory will also contain a `download-marker.json` which
    indicates that all information about the workflow run was successfully
    downloaded. (If missing, this indicates a partial download.)

    Each attempt directory will contain:

    \b
    - attempt.json: Information about the workflow run. The documents for each
      attempt of a workflow run will be largely the same.
    - check_run_#.json: One of the checks associated with the attempt, numbered
      by check-run ID.
    - annotations_#.json: Annotations associated with the check run of that ID.
    """
    dl = ActionsDownloader(output_dir=output_dir, token=token)
    dl.download(
        owner, repo,
        # We just want the Y-m-d part
        start_date.date().isoformat(), end_date.date().isoformat(),
    )


if __name__ == '__main__':
    run()

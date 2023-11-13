"""
Script to get the annotations from all failed checks in edx-platform after a given date

Gets all the commits to master after the date, then for each commit gets each check suite, then for each failed check
suite gets each run. Collects the annotations for all the failed runs. The annotations will sometimes contain useful
error messages, sometimes just the exit code. Getting the full logs requires admin permissions to edx-platform so it's
not included in this script.
Example output row:
commit_date,run_started_at,run_completed_at,commit_hash,name,message
2023-07-26T20:59:01Z,2023-07-27T06:56:23Z,2023-07-27T07:01:58Z,06e738e64a3485ecec037a9b8a36cf4ae145ea8a,
upgrade-one-python-dependency-workflow,Process completed with exit code 2.


This script takes a pretty long time to run (15m for 2 months) and there is a risk if you look too far back you will hit
your API limit.
"""

from csv import DictWriter
from datetime import datetime

import click
import requests


@click.command()
@click.option('--token', envvar='GITHUB_TOKEN')
@click.option('--start_date', type=click.DateTime(formats=["%Y-%m-%d"]), help="Date of earliest commit")
@click.option('--filename', help="Where to write the data")
def get_errors_from_date(token, start_date, filename):
    """
    Creates a csv documenting the annotations from all failed runs for commits to edx-platform after the given date

    Parameters:
        token (string): The GitHub API token. Retrieved from the env GITHUB_TOKEN variable
        start_date (date): The earliest date to look for
        filename (string): Where to write the csv

    """
    headers = {'Authorization': f"Bearer {token}"}
    all_commits_after_date = get_commits_after_date(start_date, headers=headers)
    all_check_suites = []
    all_rows = []
    for commit in all_commits_after_date:
        # gather all the check suite data from each commit into a single list
        add_commit_check_suites(commit, all_check_suites, headers)
    for check_suite in all_check_suites:
        # only record annotations for failed runs
        if check_suite['conclusion'] == 'failure':
            check_runs = requests.get(check_suite['check_runs_url'], headers=headers).json()
            for run in check_runs['check_runs']:
                if run['conclusion'] == 'failure' and run['output']['annotations_count'] > 0:
                    annotations = requests.get(run['output']['annotations_url'], headers=headers).json()
                    for annotation in annotations:
                        all_rows.append({
                            'commit_hash': run['head_sha'],
                            'name': run['name'],
                            'message': annotation['message'],
                            'run_started_at': run['started_at'],
                            'run_completed_at': run['completed_at'],
                            'commit_date': check_suite['commit_date']
                        })

    with open(filename, 'w') as f:
        writes = DictWriter(f, fieldnames=['commit_date', 'run_started_at', 'run_completed_at', 'commit_hash', 'name',
                                           'message'])
        writes.writeheader()
        writes.writerows(all_rows)


def get_commits_after_date(cut_off_date, headers):
    """
    Get API data for all commits to edx-platform/master after the given date

    Parameters:
        cut_off_date (date): Earliest date to look
        headers (dict): Authentication headers for GH requests

    Returns:
        A list of all the API responses for each commit after the date
    """
    base_url = "https://api.github.com/repos/openedx/edx-platform/commits?sha=master&per_page=100"
    # will keep track of whether we've hit our start_date. the API automatically returns commits ordered
    # by date, descending
    found_last = False
    all_commits_after_date = []
    page = 1
    while not found_last:
        page_url = f"{base_url}&page={page}"
        print(f"Fetching page {page_url}")
        response = requests.get(page_url, headers=headers)
        if response.status_code >= 400:
            print(response)
            break
        response_json = response.json()
        if len(response_json) == 0:
            break
        for single_commit in response_json:
            # if present, take off the "Z" at the end of the date to make it proper ISO format
            commit_date = datetime.fromisoformat(single_commit['commit']['committer']['date'].replace("Z", ""))
            if commit_date < cut_off_date:
                found_last = True
                break
            all_commits_after_date.append(single_commit)
        page += 1
    return all_commits_after_date


def add_commit_check_suites(current_commit, current_suites, headers):
    """
    Add API information from all check suites performed for a given commit to the given list

    Parameters:
        current_commit (str): the SHA of the commit to check
        current_suites (list): list to be extended
        headers (dict): Authentication headers for connecting to GitHub
    """
    sha = current_commit['sha']
    check_url = f"https://api.github.com/repos/openedx/edx-platform/commits/{sha}/check-suites?per_page=100"
    page = 1
    while True:
        # Keep going until we get an empty check_suites list or an error. An empty list means we've hit the last page.
        paginated_url = f"{check_url}&page={page}"
        print(f"Fetching page {paginated_url}")
        response = requests.get(paginated_url, headers=headers).json()
        if 'check_suites' not in response.keys():
            print(response)
            break
        check_suites = response['check_suites']
        if len(check_suites) == 0:
            break
        # silly line to pass the date of the commit along to eventually write in the spreadsheet
        current_suites.extend([{**s, 'commit_date': current_commit['commit']['committer']['date']}
                               for s in check_suites])
        page += 1


if __name__ == '__main__':
    get_errors_from_date()

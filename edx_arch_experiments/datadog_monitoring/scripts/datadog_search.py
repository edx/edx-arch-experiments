"""
This script takes a regex to search through the Datadog monitors
and dashboards.`

For help::

    python edx_arch_experiments/datadog_monitoring/scripts/datadog_search.py --help

"""
import datetime
import re
import types

import click

try:
    import datadog_api_client
    from datadog_api_client import ApiClient, Configuration
    from datadog_api_client.v1.api.dashboards_api import DashboardsApi
    from datadog_api_client.v1.api.monitors_api import MonitorsApi
except ModuleNotFoundError:
    datadog_api_client = None


@click.command()
@click.option(
    '--regex',
    required=True,
    help="The regex to use to search in monitors and dashboards.",
)
def main(regex):
    """
    Search Datadog monitors and dashboards using regex.

    Example usage:

        python datadog_search.py --regex tnl

    Note: The search ignores case since most features are case insensitive.

    \b
    Pre-requisites:
    1. Install the client library:
        pip install datadog-api-client
    2. Set the following environment variables (in a safe way):
        export DD_API_KEY=XXXXX
        export DD_APP_KEY=XXXXX
    See https://docs.datadoghq.com/api/latest/?code-lang=python for more details.

    \b
    If you get a Forbidden error, you either didn't supply a proper DD_API_KEY and
    DD_APP_KEY, or your DD_APP_KEY is missing these required scopes:
    - dashboards_read
    - monitors_read

    For developing with the datadog-api-client, see:
    https://github.com/DataDog/datadog-api-client-python

    """
    # Note: The \b's in the docstring above are for formatting help
    # text in the click library output.

    if datadog_api_client is None:
        print('Missing required datadog client library. Please run:')
        print('\n    pip install datadog-api-client')
        exit(1)

    compiled_regex = re.compile(regex)
    configuration = Configuration()
    api_client = ApiClient(configuration)

    search_monitors(compiled_regex, api_client)
    print('\n')
    search_dashboards(compiled_regex, api_client)
    print(flush=True)


def search_monitors(regex, api_client):
    """
    Searches Datadog monitors using the regex argument.

    Arguments:
        regex (re.Pattern): compiled regex used to find matches.
        api_client (ApiClient): a Datadog client for making API requests.
    """
    api_instance = MonitorsApi(api_client)

    print(f"Searching for regex {regex.pattern} in all monitors:")
    total_match_count = 0
    monitor_match_count = 0
    for monitor in api_instance.list_monitors_with_pagination():
        matches = find_matches(regex, monitor, 'monitor')
        total_match_count += len(matches)
        if matches:
            monitor_match_count += 1
            print('\n')
            print(f'- {monitor.id} "{monitor.name}" {monitor.tags}')
            for match in matches:
                print(f'  - match_path: {match[1]}')
                print(f'    - match: {match[0]}')
            match_found = True
        else:
            print('.', end='', flush=True)  # shows search progress

    if total_match_count:
        print(f"\n\nFound {total_match_count} matches in "
              f"{monitor_match_count} monitors.")
    else:
        print("\n\nNo monitors matched.")


def search_dashboards(regex, api_client):
    """
    Searches Datadog dashboards using the regex argument.

    Arguments:
        regex (re.Pattern): compiled regex used to find matches.
        api_client (ApiClient): a Datadog client for making API requests.
    """
    api_instance = DashboardsApi(api_client)

    print(f"Searching for regex {regex.pattern} in all dashboards:")
    errors = []
    total_match_count = 0
    dashboard_match_count = 0
    for dashboard in api_instance.list_dashboards_with_pagination():
        try:
            dashboard_details = api_instance.get_dashboard(dashboard.id)
        except Exception as e:
            errors.append((dashboard.id, e))
            continue

        matches = find_matches(regex, dashboard_details, 'dashboard_details')
        total_match_count += len(matches)
        if matches:
            dashboard_match_count += 1
            if hasattr(dashboard_details, 'tags'):
                tags = f' {dashboard_details.tags}'
            else:
                tags = ''
            print('\n')
            print(f'- {dashboard.id} "{dashboard.title}"{tags}')
            for match in matches:
                print(f'  - match_path: {match[1]}')
                print(f'    - match: {match[0]}')
            match_found = True
        else:
            print('.', end='', flush=True)  # shows search progress

    if errors:
        print('\n')
        for error in errors:
            print(f'Skipping {error[0]} due to error: {error[1]}')

    if total_match_count:
        print(f"\n\nFound {total_match_count} matches in "
              f"{dashboard_match_count} dashboards.")
    else:
        print("\n\nNo dashboards matched.")


def find_matches(regex, obj, obj_path):
    """
    Recursive function to find matches in DD API results.

    Returns:
        List of tuples, where first entry is the matched
        string and the second is the obj_path. Returns an
        empty list if no matches are found.

    Usage:
        matches = find_matches(regex, obj, 'top-level-obj')

    Arguments:
        regex (re.Pattern): compiled regex used to compare against.
        obj: an object (not necessarily top-level) from a DD api result
        obj_path: a human readable code path to reach obj from
            the top-level object.
    """
    use_attributes = False
    if hasattr(obj, 'to_dict') or isinstance(obj, dict):
        if hasattr(obj, 'to_dict'):
            # API objects that we treat like a dict, except when building the path,
            # where we use attributes instead of dict keys.
            use_attributes = True
            dict_obj = obj.to_dict()
        else:
            dict_obj = obj
        dict_matches = []
        for key in dict_obj:
            if use_attributes:
                new_obj_path = f"{obj_path}.{key}"
            else:
                new_obj_path = f"{obj_path}['{key}']"
            new_obj = dict_obj[key]
            dict_matches.extend(find_matches(regex, new_obj, new_obj_path))
        return dict_matches
    elif isinstance(obj, list):
        list_matches = []
        for index, item in enumerate(obj):
            list_matches.extend(find_matches(regex, item, f"{obj_path}[{index}]"))
        return list_matches
    elif isinstance(obj, str):
        if regex.search(obj, re.IGNORECASE):
            return [(obj, obj_path)]
        return []
    elif isinstance(obj, (int, float, datetime.datetime, types.NoneType)):
        return []
    assert False, f'Unhandled type: {type(obj)}. Add handling code.'


if __name__ == "__main__":
    main()  # pylint: disable=no-value-for-parameter

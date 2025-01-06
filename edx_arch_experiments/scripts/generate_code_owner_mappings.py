"""
This script generates code owner mappings for monitoring LMS.

Sample usage::

    python generate_code_owner_mappings.py
      --repo-csv "edX _ OCM Tech Ownership Assignment - Own_ Repos.csv"
      --app-csv "edX _ OCM Tech Ownership Assignment - Own_ edx-platform Apps.csv"
      --dep-csv "edX _ OCM Tech Ownership Assignment - Reference_ edx-platform Libs.csv"
      --override-csv "edX _ OCM Tech Ownership Assignment - Own_ Ownership overrides.csv"

Or for more details::

    python generate_code_owner_mappings.py --help


"""
import csv
import os
import re

import click

# Maps edx-platform installed Django apps to the edx repo that contains
# the app code. Please add in alphabetical order.
#
# The URLs here must match the URLs in the "Own: Repos" sheet:
# https://docs.google.com/spreadsheets/d/1qpWfbPYLSaE_deaumWSEZfz91CshWd3v3B7xhOk5M4U/view#gid=1990273504
# These applications are the ones which contain views we want to monitor
EDX_REPO_APPS = {
    'bulk_grades': 'https://github.com/openedx/edx-bulk-grades',
    'coaching': 'https://github.com/edx/platform-plugin-coaching',
    'completion': 'https://github.com/openedx/completion',
    'config_models': 'https://github.com/openedx/django-config-models',
    'consent': 'https://github.com/openedx/edx-enterprise',
    'csrf': 'https://github.com/openedx/edx-drf-extensions',
    'edx_arch_experiments': 'https://github.com/edx/edx-arch-experiments',
    'edx_name_affirmation': 'https://github.com/edx/edx-name-affirmation',
    'edx_proctoring': 'https://github.com/openedx/edx-proctoring',
    'edx_recommendations': 'https://github.com/edx/edx-recommendations',
    'edxval': 'https://github.com/openedx/edx-val',
    'enterprise': 'https://github.com/openedx/edx-enterprise',
    'enterprise_learner_portal': 'https://github.com/openedx/edx-enterprise',
    'eventtracking': 'https://github.com/openedx/event-tracking',
    'federated_content_connector': 'https://github.com/edx/federated-content-connector',
    'help_tokens': 'https://github.com/openedx/help-tokens',
    'integrated_channels': 'https://github.com/openedx/edx-enterprise',
    'learner_pathway_progress': 'https://github.com/edx/learner-pathway-progress',
    'learning_assistant': 'https://github.com/edx/learning-assistant',
    'lti_consumer': 'https://github.com/openedx/xblock-lti-consumer',
    'notices': 'https://github.com/edx/platform-plugin-notices',
    'openassessment': 'https://github.com/openedx/edx-ora2',
    'ora2': 'https://github.com/openedx/edx-ora2',
    'organizations': 'https://github.com/openedx/edx-organizations',
    'persona_integration': 'https://github.com/edx/persona-integration',
    'search': 'https://github.com/openedx/edx-search',
    'super_csv': 'https://github.com/openedx/super-csv',
    'translatable_xblocks': 'https://github.com/edx/translatable-xblocks',
    'wiki': 'https://github.com/openedx/django-wiki',
}

# Maps edx-platform installed Django apps to the third-party repo that contains
# the app code. Please add in alphabetical order.
#
# The URLs here must match the URLs in the "Reference: edx-platform Libs" sheet:
# https://docs.google.com/spreadsheets/d/1qpWfbPYLSaE_deaumWSEZfz91CshWd3v3B7xhOk5M4U/view#gid=506252353
# These applications are the ones which contain views we want to monitor
THIRD_PARTY_APPS = {
    'corsheaders': 'https://github.com/adamchainz/django-cors-headers',
    'django': 'https://github.com/django/django',
    'django_object_actions': 'https://github.com/crccheck/django-object-actions',
    'drf_yasg': 'https://github.com/axnsan12/drf-yasg',
    'edx_sga': 'https://github.com/mitodl/edx-sga',
    'lx_pathway_plugin': 'https://github.com/open-craft/lx-pathway-plugin',
    'oauth2_provider': 'https://github.com/jazzband/django-oauth-toolkit',
    'rest_framework': 'https://github.com/encode/django-rest-framework',
    'simple_history': 'https://github.com/treyhunner/django-simple-history',
    'social_django': 'https://github.com/python-social-auth/social-app-django',
}


@click.command()
@click.option(
    '--repo-csv',
    help="File name of .csv file with repo ownership details.",
    required=True
)
@click.option(
    '--app-csv',
    help="File name of .csv file with edx-platform app ownership details.",
    required=True
)
@click.option(
    '--dep-csv',
    help="File name of .csv file with edx-platform 3rd-party dependency ownership details.",
    required=True
)
@click.option(
    '--override-csv',
    help="File name of .csv file with ownership override details. Entries here will override entries in app-csv and"
         " dep-csv",
    required=False
)
def main(repo_csv, app_csv, dep_csv, override_csv=None):
    """
    Reads CSVs of ownership data and outputs config.yml setting to system.out.

    Expected Repo CSV format:

        \b
        repo url,owner.squad
        https://github.com/openedx/edx-bulk-grades,team-red
        ...

    Expected App CSV format:

        \b
        Path,owner.squad
        ./openedx/core/djangoapps/user_authn,team-blue
        ...

    Expected 3rd-party Dependency CSV format:

        \b
        repo url,owner.squad
        https://github.com/django/django,team-red
        ...

    Expected Override CSV format:

        \b
        app_name,owner.squad
        integrated_channels,team-blue
        ...

    Final output only includes paths which might contain views.

    """
    # Maps owner names to a list of dotted module paths.
    # For example: { 'team-red': [ 'openedx.core.djangoapps.api_admin', 'openedx.core.djangoapps.auth_exchange' ] }
    owner_to_paths_map = {}
    _map_repo_apps('edx-repo', repo_csv, override_csv, EDX_REPO_APPS, owner_to_paths_map)
    _map_repo_apps('3rd-party', dep_csv, override_csv, THIRD_PARTY_APPS, owner_to_paths_map)
    _map_edx_platform_apps(app_csv, owner_to_paths_map)

    # NB: An automated script looks for this comment when updating config files,
    # so please update regenerate_code_owners_config.py in jenkins-job-dsl-internal
    # if you change the comment format here.
    print(f'# Do not hand edit CODE_OWNER_TO_PATH_MAPPINGS. Generated by {os.path.basename(__file__)}')
    print('CODE_OWNER_TO_PATH_MAPPINGS:')
    for owner, path_list in sorted(owner_to_paths_map.items()):
        print(f"  {owner}:")
        path_list.sort()
        for path in path_list:
            print(f"  - {path}")


def _map_repo_apps(csv_type, repo_csv, override_csv, app_to_repo_map, owner_to_paths_map):
    """
    Reads CSV of repo ownership and uses app_to_repo_map to update owner_to_paths_map

    Only the paths in app_to_repo_map will be added to owner_to_paths_map. All repositories not corresponding to an
    app in app_to_repo_map will be ignored.

    Arguments:
        csv_type (string): Either 'edx-repo' or '3rd-party' for error message
        repo_csv (string): File name for the edx-repo or 3rd-party repo csv
        override_csv (string): File name for the override csv (which may be None)
        app_to_repo_map (dict): Dict mapping Django apps to repo urls
        owner_to_paths_map (dict): Holds results mapping owner to paths

    """
    with open(repo_csv) as file:
        csv_data = file.read()
    reader = csv.DictReader(csv_data.splitlines())

    overrides = {}
    if override_csv:
        with open(override_csv) as override_file:
            override_data = override_file.read()
        override_reader = csv.DictReader(override_data.splitlines())
        for row in override_reader:
            owner = _get_code_owner(row)
            overrides[row['app']] = owner

    csv_repo_to_owner_map = {}
    for row in reader:
        owner = _get_code_owner(row)
        csv_repo_to_owner_map[row.get('repo url')] = owner

    for app, repo_url in app_to_repo_map.items():
        # look for any overrides in the override map before looking in the spreadsheet
        owner = overrides.get(app, None)
        if not owner:
            owner = csv_repo_to_owner_map.get(repo_url, None)
        if owner:
            if owner not in owner_to_paths_map:
                owner_to_paths_map[owner] = []
            owner_to_paths_map[owner].append(app)
        else:
            raise Exception(
                f'ERROR: Repo {repo_url} was not found in {csv_type} csv. Needed for app {app}. '
                'Please reconcile the hardcoded lookup tables in this script with the ownership '
                'sheet.'
            )


def _map_edx_platform_apps(app_csv, owner_to_paths_map):
    """
    Reads CSV of edx-platform app ownership and updates mappings
    """
    with open(app_csv) as file:
        csv_data = file.read()
    reader = csv.DictReader(csv_data.splitlines())
    for row in reader:
        path = row.get('Path')
        owner = _get_code_owner(row)

        # add paths that may have views
        may_have_views = re.match(r'.*djangoapps', path) or re.match(r'[./]*openedx\/features', path)
        # remove cms (studio) paths and tests
        may_have_views = may_have_views and not re.match(r'.*(\/tests\b|cms\/).*', path)

        if may_have_views:
            path = path.replace('./', '')  # remove ./ from beginning of path
            path = path.replace('/', '.')  # convert path to dotted module name

            # skip catch-alls to ensure everything is properly mapped
            if path in ('common.djangoapps', 'lms.djangoapps', 'openedx.core.djangoapps', 'openedx.features'):
                continue

            if owner not in owner_to_paths_map:
                owner_to_paths_map[owner] = []
            owner_to_paths_map[owner].append(path)


def _get_code_owner(row):
    """
    From a csv row, returns the squad as code_owner.

    Arguments:
        row: A csv row that should have 'owner.squad'.

    Returns:
        The code_owner for the row, which comes from the squad name.

    """
    squad = row.get('owner.squad')
    assert squad, 'Csv row is missing required owner.squad: %s' % row

    # use lower case names only
    squad = squad.lower()
    return squad


if __name__ == "__main__":
    main()  # pylint: disable=no-value-for-parameter

Monitoring by Code Owner
************************

Status
======

Accepted

Context
=======

It is difficult for different teams to have team-based on-calls rotations, alerting and monitoring for various parts of the edx-platform (specifically LMS).

* The original decision to add code_owner custom span tags (custom attributes) was documented in `edx-platform in 0001-monitoring-by-code-owner`_.
* The decision to move the code for reuse across IDAs was documented in `edx-django-utils in 0001-monitoring-by-code-owner.rst`_.
* The decision for how to implement code owner details for celery tasks was documented in `0003-code-owner-for-celery-tasks_, and was limited by New Relic's instrumentation.
* The decision to break up the ``code_owner`` custom span tag (custom attribute) into ``code_owner_squad`` and ``code_owner_theme`` tags was documented in `0004-code-owner-theme-and-squad`_.

Some changes or clarifications since this time:

* It turns out that this functionality is only really useful for the edx-platform LMS. Our other services (IDAs) are small enough to keep to a single owner, or to solve monitoring issues in other ways.
* It is likely that the ``code_owner`` code is only really needed by 2U.
* 2U wants to drop owner themes from its code_owner custom span tag.
* 2U has switched to Datadog, which has slightly different capabilities from New Relic.

  * Note that Datadog has custom span tags, where New Relic has custom attributes to refer to its tagging capabilities.

.. _edx-platform in 0001-monitoring-by-code-owner: https://github.com/openedx/edx-platform/blob/f29e418264f374099930a5b1f5b8345c569892e9/lms/djangoapps/monitoring/docs/decisions/0001-monitoring-by-code-owner.rst
.. _edx-django-utils in 0001-monitoring-by-code-owner.rst: https://github.com/openedx/edx-django-utils/blob/a1a1ec95d7c1d4767deb578748153c99c9562a04/edx_django_utils/monitoring/docs/decisions/0001-monitoring-by-code-owner.rst
.. _0003-code-owner-for-celery-tasks: https://github.com/openedx/edx-django-utils/blob/a1a1ec95d7c1d4767deb578748153c99c9562a04/edx_django_utils/monitoring/docs/decisions/0003-code-owner-for-celery-tasks.rst
.. _0004-code-owner-theme-and-squad: https://github.com/openedx/edx-django-utils/blob/a1a1ec95d7c1d4767deb578748153c99c9562a04/edx_django_utils/monitoring/docs/decisions/0004-code-owner-theme-and-squad.rst

Decision
========

2U has moved its code owner monitoring implementation to the datadog_monitoring plugin.

* The owner theme name has been dropped from the ``code_owner`` custom span tag value in this new implementation.
* The ``code_owner_theme`` span tag has been dropped altogether from this new implementation.
* The now deprecated ``code_owner_squad`` span tag, which is redundant with the updated ``code_owner`` tag, will continue to be supported for backward compatibility.
* A Datadog span processor was used to add the code owner span tags for celery tasks, so there is no longer a need for a special decorator on each celery task.
* A new capability added to edx-django-utils to add `monitoring signals for plugins`_ is used to monitor Django requests.

Also, a new search script was implemented in this repository: `search_datadog.rst`_.

.. _monitoring signals for plugins: https://github.com/openedx/edx-django-utils/pull/467
.. _search_datadog.rst: https://github.com/edx/edx-arch-experiments/blob/main/edx_arch_experiments/datadog_monitoring/scripts/datadog_search.py

Consequences
============

- In addition to having greater flexibility to update these custom tags as-needed for 2U, we can also DEPR the code owner functionality in the Open edX codebase, where it is not likely to be needed.
- Spreadsheet changes will no longer be required when a squad moves from one part of the organization to another (e.g. changes themes).
- However, without including themes, it may take additional time to learn about a squad's place in the organization when seen in the code_owner span tag. For example, it will not be as immediately clear when dealing with an enterprise squad, unless you are familiar with all of the squad names.

Using Code_Owner Custom Span Tags
=================================

.. contents::
   :local:
   :depth: 2

What are the code owner custom span tags?
------------------------------------------

The code owner custom span tags can be used to create custom dashboards and alerts for monitoring the things that you own. It was originally introduced for the LMS, as is described in this `ADR on monitoring by code owner`_. However, it was first moved to edx-django-utils to be used in any IDA. It was later moved to this 2U-specific plugin because it is for 2U.

The code owner custom attributes consist of:

* code_owner_2: The owner name. When themes and squads are used, this will be the theme and squad names joined by a hyphen.
* code_owner_2_theme: The theme name of the owner.
* code_owner_2_squad: The squad name of the owner. Use this to avoid issues when theme name changes.

Note: The ``_2`` of the code_owner_2 naming is for initial rollout to compare with edx-django-utils span tags. Ultimately, we will use adjusted names, which may include dropping the theme.

If you want to learn more about custom span tags in general, see `Enhanced Monitoring and Custom Attributes`_.

.. _ADR on monitoring by code owner: https://github.com/openedx/edx-platform/blob/master/lms/djangoapps/monitoring/docs/decisions/0001-monitoring-by-code-owner.rst
.. _Enhanced Monitoring and Custom Attributes: https://edx.readthedocs.io/projects/edx-django-utils/en/latest/monitoring/how_tos/using_custom_attributes.html

Setting up the Middleware
-------------------------

You simply need to add ``edx_arch_experiments/datadog_monitoring/code_owner/middleware.CodeOwnerMonitoringMiddleware`` to get code owner span tags on Django requests.

Handling celery tasks
---------------------

For celery tasks, this plugin will automatically detect and add code owner span tags to any span with ``operation_name:celery.run``.

Configuring your app settings
-----------------------------

Once the Middleware is made available, simply set the Django Settings ``CODE_OWNER_MAPPINGS`` and ``CODE_OWNER_THEMES`` appropriately.

The following example shows how you can include an optional config for a catch-all using ``'*'``. Although you might expect this example to use Python, it is intentionally illustrated in YAML because the catch-all requires special care in YAML.

::

    # YAML format of example CODE_OWNER_MAPPINGS
    CODE_OWNER_MAPPINGS:
      theme-x-team-red:
        - xblock_django
        - openedx.core.djangoapps.xblock
      theme-x-team-blue:
      - '*'  # IMPORTANT: you must surround * with quotes in yml

    # YAML format of example CODE_OWNER_THEMES
    CODE_OWNER_THEMES:
      theme-x:
      - theme-x-team-red
      - theme-x-team-blue

How to find and fix code_owner mappings
---------------------------------------

If you are missing the ``code_owner_2`` custom attributes on a particular Transaction or Error, or if ``code_owner`` is matching the catch-all, but you want to add a more specific mapping, you can use the other supporting tags like ``code_owner_2_module`` and ``code_owner_2_path_error`` to determine what the appropriate mappings should be.

Updating Datadog monitoring
---------------------------

To update monitoring in the event of a squad or theme name change, see `Update Monitoring for Squad or Theme Changes`_.

.. _Update Monitoring for Squad or Theme Changes:

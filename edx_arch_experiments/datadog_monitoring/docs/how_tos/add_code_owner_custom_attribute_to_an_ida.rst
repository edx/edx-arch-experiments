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

What gets code_owner span tags
------------------------------

Simply by installing the datadog_monitoring plugin, code owner span tags will automatically be added for:

* ``operation_name:django.request``: tags are added by using edx-django-utils monitoring signals, which are sent by its MonitoringSupportMiddleware.
* ``operation_name:celery.run``: tags are added using celery's ``worker_process_init`` signal, and then adding a custom Datadog span processor to add the span tags as appropriate.

Configuring your app settings
-----------------------------

Once the Middleware is made available, simply set the Django Settings ``CODE_OWNER_MAPPINGS`` and ``CODE_OWNER_THEMES`` appropriately.

::

    # YAML format of example CODE_OWNER_MAPPINGS
    CODE_OWNER_MAPPINGS:
      theme-x-team-red:
        - xblock_django
        - openedx.core.djangoapps.xblock
      theme-x-team-blue:
        - lms

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

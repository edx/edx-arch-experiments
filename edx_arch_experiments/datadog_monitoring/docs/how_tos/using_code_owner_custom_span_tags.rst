Using Code_Owner Custom Span Tags
=================================

.. contents::
   :local:
   :depth: 2

What are the code owner custom span tags?
-----------------------------------------

The code owner custom span tags (formerly known as the code owner custom attributes) can be used to create custom dashboards and monitors for the things that you own.

To read more on the decision to use these custom span tags, read `ADR on monitoring by code owner`_.

The code owner span tags are as follows:

* code_owner: The squad name of the owner.
* code_owner_squad: Deprecated. Redundant with code_owner for backward compatibility.
* code_owner_module: Module used for determining code_owner. Useful for debugging missing code owner details.
* code_owner_path_error: Possible error determining code_owner. Useful for debugging missing code owner details.

If you want to learn more about custom span tags in general, see `Enhanced Monitoring and Custom Attributes`_.

.. _ADR on monitoring by code owner: https://github.com/edx/edx-arch-experiments/blob/main/edx_arch_experiments/datadog_monitoring/docs/decisions/0001-monitoring-by-code-owner.rst
.. _Enhanced Monitoring and Custom Attributes: https://edx.readthedocs.io/projects/edx-django-utils/en/latest/monitoring/how_tos/using_custom_attributes.html

How code owner span tags are added
----------------------------------

Simply by installing the datadog_monitoring plugin, code owner span tags will automatically be added for:

* ``operation_name:django.request``: tags are added by using edx-django-utils monitoring signals, which are sent by its MonitoringSupportMiddleware.
* ``operation_name:celery.run``: tags are added using celery's ``worker_process_init`` signal, and then adding a custom Datadog span processor to add the span tags as appropriate.

Configuring your app settings
-----------------------------

Once the datadog_monitoring plugin is installed, set the Django Settings ``CODE_OWNER_TO_PATH_MAPPINGS`` appropriately.

::

    # YAML format of example CODE_OWNER_TO_PATH_MAPPINGS
    CODE_OWNER_TO_PATH_MAPPINGS:
      team-red:
        - xblock_django
        - openedx.core.djangoapps.xblock
      team-blue:
        - lms

Updating Datadog monitoring
---------------------------

To update monitoring in the event of a squad name change, see `Update Monitoring for Squad Changes`_.

.. _Update Monitoring for Squad Changes: https://github.com/edx/edx-arch-experiments/blob/main/edx_arch_experiments/datadog_monitoring/docs/how_tos/update_monitoring_for_squad_changes.rst

Update Monitoring for Squad or Theme Changes
============================================

.. contents::
   :local:
   :depth: 2

Understanding code owner custom attributes
------------------------------------------

If you first need some background on the ``code_owner_2_squad`` and ``code_owner_2_theme`` custom attributes, see `Using Code_Owner Custom Span Tags`_.

.. _Using Code_Owner Custom Span Tags: https://github.com/edx/edx-arch-experiments/blob/main/edx_arch_experiments/datadog_monitoring/docs/how_tos/add_code_owner_custom_attribute_to_an_ida.rst

Expand and contract name changes
--------------------------------

Datadog monitors or dashboards may use the ``code_owner_2_squad`` or ``code_owner_2_theme`` (or ``code_owner_2``) custom span tags.

To change a squad or theme name, you should *expand* before the change, and *contract* after the change.

Example expand phase::

    code_owner_2_squad:('old-squad-name', 'new-squad-name')
    code_owner_2_theme:('old-theme-name', 'new-theme-name')

Example contract phase::

    code_owner_2_squad:'new-squad-name'
    code_owner_2_theme:'new-theme-name'

To find relevant usage of these span tags, see `Searching Datadog monitors and dashboards`_.

Searching Datadog monitors and dashboards
-----------------------------------------

TODO: This section needs to be updated as part of https://github.com/edx/edx-arch-experiments/issues/786, once the script has been migrated for use with Datadog.

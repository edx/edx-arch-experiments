Update Monitoring for Squad Changes
===================================

.. contents::
   :local:
   :depth: 2

Understanding code owner custom span tags
-----------------------------------------

If you first need some background on the ``code_owner`` custom span tag, see `Using Code_Owner Custom Span Tags`_.

.. _Using Code_Owner Custom Span Tags: https://github.com/edx/edx-arch-experiments/blob/main/edx_arch_experiments/datadog_monitoring/docs/how_tos/using_code_owner_custom_span_tags.rst

Expand and contract name changes
--------------------------------

Datadog monitors or dashboards may use the ``code_owner`` (or deprecated ``code_owner_squad``) custom span tags.

To change a squad name, you should *expand* before the change, and *contract* after the change.

Example expand phase::

    code_owner:('old-squad-name', 'new-squad-name')

Example contract phase::

    code_owner:'new-squad-name'

To find relevant usage of these span tags, see `Searching Datadog monitors and dashboards`_.

Searching Datadog monitors and dashboards
-----------------------------------------

See :doc:`search_datadog` for general information about the ``datadog_search.py`` script.

This script can be especially useful for helping with the expand/contract phase when changing squad names. For example, you could use the following::

    ./datadog_search.py --regex old-squad-name
    ./datadog_search.py --regex new-squad-name

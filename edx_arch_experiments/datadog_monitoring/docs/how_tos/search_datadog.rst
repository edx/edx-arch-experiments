Searching Datadog
=================
The search script `datadog_search.py`_ can be used to search Datadog monitors and dashboards. Run the script with ``--help`` for more details.

Known limitations
-----------------

The script only searches Datadog monitors and dashboards. It does not search these Datadog areas:

* APM generated metrics: https://app.datadoghq.com/apm/traces/generate-metrics
* APM retention filters: https://app.datadoghq.com/apm/traces/retention-filters

.. _datadog_search.py: https://github.com/edx/edx-arch-experiments/blob/main/edx_arch_experiments/datadog_monitoring/scripts/datadog_search.py

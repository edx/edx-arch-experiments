Searching Datadog
=================
The search script `datadog_search.py`_ can be used to search Datadog monitors and dashboards. Run the script with ``--help`` for more details.

Known limitations
-----------------

The script only searches Datadog monitors and dashboards. It is not a complete search across all Datadog products or configuration.

Examples of Datadog areas that are not searched include:

* APM Generated Metrics: https://app.datadoghq.com/apm/traces/generate-metrics
* APM Retention Filters: https://app.datadoghq.com/apm/traces/retention-filters
* SLOs: https://docs.datadoghq.com/api/latest/service-level-objectives/
* Notebooks: https://docs.datadoghq.com/api/latest/notebooks/
* Synthetic Tests: https://docs.datadoghq.com/api/latest/synthetics/
* Metric Tag Configurations: https://docs.datadoghq.com/api/latest/metrics/

.. _datadog_search.py: https://github.com/edx/edx-arch-experiments/blob/main/edx_arch_experiments/datadog_monitoring/scripts/datadog_search.py

Change Log
----------

..
   All enhancements and patches to edx_arch_experiments will be documented
   in this file.  It adheres to the structure of https://keepachangelog.com/ ,
   but in reStructuredText instead of Markdown (for ease of incorporation into
   Sphinx documentation and the PyPI description).

   This project adheres to Semantic Versioning (https://semver.org/).

.. There should always be an "Unreleased" section for changes pending release.

Unreleased
~~~~~~~~~~

[5.1.0] - 2024-11-21
~~~~~~~~~~~~~~~~~~~~
Added
-----
* Added Datadog monitoring app which adds code owner monitoring. This is the first step in moving code owner code from edx-django-utils to this plugin.

  * Adds near duplicate of code owner middleware from edx-django-utils.
  * Adds code owner span tags for celery using Datadog span processing of celery.run spans.
  * Uses temporary span tags names using ``_2``, like ``code_owner_2``, for rollout and comparison with the original span tags.
  * Span tag code_owner_2_module includes the task name, where the original code_owner_module does not. In both cases, the code owner is computed the same, because it is based on a prefix match.

[5.0.0] - 2024-10-22
~~~~~~~~~~~~~~~~~~~~
Removed
-------
* Deleted Datadog diagnostics plugin app and middleware, which are no longer in use in edxapp.

[4.5.0] - 2024-09-19
~~~~~~~~~~~~~~~~~~~~
Added
-----
* Datadog diagnostics middleware can now attempt to close anomalous spans. Can be enabled via Waffle flag ``datadog.diagnostics.close_anomalous_spans`` (controlled separately from logging feature).

[4.4.0] - 2024-09-10
~~~~~~~~~~~~~~~~~~~~
Changed
-------
* Datadog diagnostics now logs ancestor spans when an anomaly is encountered, up to a limit of 10 (controlled by new Django setting ``DATADOG_DIAGNOSTICS_LOG_SPAN_DEPTH``). Spans are logged in full and on separate lines, so this logging is now much more verbose; consider only enabling this logging for short periods. Log format of first line has also changed slightly.

[4.3.0] - 2024-08-22
~~~~~~~~~~~~~~~~~~~~
Added
-----
* Added celery lifecycle logging for Datadog diagnostics, to be enabled using ``DATADOG_DIAGNOSTICS_CELERY_LOG_SIGNALS``.

[4.2.0] - 2024-08-13
~~~~~~~~~~~~~~~~~~~~
Fixed
-----
* Fixed loading of ``DATADOG_DIAGNOSTICS_ENABLE``, which was previously not loaded properly and therefore was always True. Also fixed loading of ``DATADOG_DIAGNOSTICS_MAX_SPANS``, which was presumably broken as well.

Removed
-------
* Removed early span-start logging. It never worked properly, possibly because workers are continually being destroyed and created, leading to high log volume.

[4.1.0] - 2024-08-09
~~~~~~~~~~~~~~~~~~~~
Changed
-------
* Datadog diagnostics will now log all span-starts for the first minute after server startup
* **WARNING**: Do not use this version; see 4.2.0 release notes.

[4.0.0] - 2024-08-05
~~~~~~~~~~~~~~~~~~~~
Changed
-------
* Dropped support for Python 3.8; only testing with 3.11 and above now.

Added
-----
* ``DatadogDiagnosticMiddleware`` can now detect and log anomalous traces, enabled by Waffle flag ``datadog.diagnostics.detect_anomalous_trace``

[3.6.0] - 2024-07-24
~~~~~~~~~~~~~~~~~~~~
Added
-----
* New middleware ``edx_arch_experiments.datadog_diagnostics.middleware.DatadogDiagnosticMiddleware`` for logging diagnostics on traces in Datadog.

[3.5.1] - 2024-07-15
~~~~~~~~~~~~~~~~~~~~
Changed
-------
* Added ``federated-content-connector`` to the generate_code_owners script.

[3.5.0] - 2024-07-11
~~~~~~~~~~~~~~~~~~~~
Added
-----
* Toggle ``DATADOG_DIAGNOSTICS_ENABLE`` for disabling that plugin quickly if needed. (Feature remains enabled by default.)

Fixed
-----
* Limit the number of spans collected via new setting ``DATADOG_DIAGNOSTICS_MAX_SPANS``, defaulting to 100. This may help avoid memory leaks.
* Make accidental class variables into member variables in ``datadog_diagnostics``

[3.4.0] - 2024-07-10
~~~~~~~~~~~~~~~~~~~~
Added
-----
* Added ``datadog_diagnostics`` plugin app

[3.3.2] - 2024-04-19
~~~~~~~~~~~~~~~~~~~~
Changed
-------
* Added ``translatable-xblocks`` to the generate_code_owners script.


[3.3.1] - 2024-02-26
~~~~~~~~~~~~~~~~~~~~
Added
_______
* Added support for ``Python 3.12``

[3.3.0] - 2024-01-23
~~~~~~~~~~~~~~~~~~~~
Changed
_______
* Updated ``ConfigWatcher`` to include the IDA's name in change messages if ``CONFIG_WATCHER_SERVICE_NAME`` is set
* Enabled ``ConfigWatcher`` as a plugin for CMS

[3.2.0] - 2024-01-11
~~~~~~~~~~~~~~~~~~~~
Added
_____
* Add ``codejail_service`` app for transition to containerized codejail

[3.1.1] - 2023-11-06
~~~~~~~~~~~~~~~~~~~~
Fixed
_____
* ConfigWatcher should now respond to model events properly now that it registers receivers with strong references. (Tested in sandbox.)

[3.1.0] - 2023-10-31
~~~~~~~~~~~~~~~~~~~~

Changed
_______

* Add log message for each model the ConfigWatcher is listening to
* Ensure that ConfigWatcher only attaches receivers once

[3.0.0] - 2023-10-30
~~~~~~~~~~~~~~~~~~~~

Changed
_______

* Renamed ``ConfigWatcherApp`` to ``ConfigWatcher`` to be less redundant. This is technically a breaking change but the app was not in use yet.
* Enabled ``ConfigWatcher`` as a plugin for LMS

[2.2.0] - 2023-10-27
~~~~~~~~~~~~~~~~~~~~

Added
_____

* Add ``edx_arch_experiments.config_watcher`` Django app for monitoring Waffle changes
* Add script to get github action errors
* Add script to republish failed events

[2.1.0] - 2023-10-10
~~~~~~~~~~~~~~~~~~~~

* Add ORA2 to our code owner mapping script.

[2.0.0] - 2023-06-01
~~~~~~~~~~~~~~~~~~~~

* Removes summary hook aside, now in the ai-aside repo

[1.2.0] - 2023-05-08
~~~~~~~~~~~~~~~~~~~~

* Update summary hook to trigger on videos
* Remove text selection data key from summary hook html

[1.1.4] - 2023-04-14
~~~~~~~~~~~~~~~~~~~~

* Add course and block ID to summary hook html

[1.1.3] - 2023-04-05
~~~~~~~~~~~~~~~~~~~~

Fixed
_____

* Removed ``default_app_config`` (deprecated in Django 3)

[1.1.2] - 2023-03-14
~~~~~~~~~~~~~~~~~~~~

* Add "staff only" summary hook flag

[1.1.1] - 2023-03-09
~~~~~~~~~~~~~~~~~~~~

* Revise summary hook HTML

[1.1.0] - 2023-03-08
~~~~~~~~~~~~~~~~~~~~

* Add summary hook xblock aside

[1.0.0] - 2022-10-06
~~~~~~~~~~~~~~~~~~~~

* **Breaking change**: Remove ``kafka_consumer`` package and plugin (migrated to ``edx-event-bus-kafka``)

[0.2.1] - 2022-06-14
~~~~~~~~~~~~~~~~~~~~

* Add new target to Makefile
* Update openedx-events

[0.2.0] - 2022-03-16
~~~~~~~~~~~~~~~~~~~~

* Update consumer to use bridge and signals

[0.1.1] - 2022-03-16
~~~~~~~~~~~~~~~~~~~~

* Fix GitHub actions

[0.1.0] - 2022-02-22
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Added
_____

* First release on PyPI.

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

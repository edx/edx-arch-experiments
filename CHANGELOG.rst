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

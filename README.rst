edx-arch-experiments
=============================

|pypi-badge| |ci-badge| |codecov-badge| |pyversions-badge|
|license-badge|

A plugin to include applications under development by the architecture team at edX

Overview
------------------------

This plugin is meant to house experimental and in-development applications from the architecture team at edX that are either not appropriate (i.e. edX/2U specific) or not yet ready for community consumption.


Development Workflow
--------------------

One Time Setup
~~~~~~~~~~~~~~
.. code-block::

  # Clone the repository
  git clone git@github.com:edx/edx-arch-experiments.git
  cd edx-arch-experiments

  # Set up a virtualenv using virtualenvwrapper with the same name as the repo and activate it
  mkvirtualenv -p python3.8 edx-arch-experiments

Local testing
~~~~~~~~~~~~~
To test your changes locally, you will need to install the package from your local branch into edx-platform. For example, if using devstack, copy or clone your branch into <devstack-parent>/src/edx-arch-experiments. Then, in an lms or cms shell, run ``pip install -e /edx/src/edx-arch-experiments``.  The plug-in configuration will automatically be picked up once installed, and changes will be hot reloaded.


Every time you develop something in this repo
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
.. code-block::

  # Activate the virtualenv
  workon edx-arch-experiments

  # Grab the latest code
  git checkout main
  git pull

  # Install/update the dev requirements
  make requirements

  # Run the tests and quality checks (to verify the status before you make any changes)
  make validate

  # Make a new branch for your changes
  git checkout -b <your_github_username>/<short_description>

  # Using your favorite editor, edit the code to make your change.
  vim …

  # Run your new tests
  pytest ./path/to/new/tests

  # Run all the tests and quality checks
  make validate

  # Commit all your changes
  git commit …
  git push

  # Open a PR and ask for review.

License
-------

The code in this repository is licensed under the AGPL 3.0 unless
otherwise noted.

Please see `LICENSE.txt <LICENSE.txt>`_ for details.

How To Contribute
-----------------

Contributions are very welcome.
Please read `How To Contribute <https://github.com/edx/edx-platform/blob/master/CONTRIBUTING.rst>`_ for details.
Even though they were written with ``edx-platform`` in mind, the guidelines
should be followed for all Open edX projects.

The pull request description template should be automatically applied if you are creating a pull request from GitHub. Otherwise you
can find it at `PULL_REQUEST_TEMPLATE.md <.github/PULL_REQUEST_TEMPLATE.md>`_.

The issue report template should be automatically applied if you are creating an issue on GitHub as well. Otherwise you
can find it at `ISSUE_TEMPLATE.md <.github/ISSUE_TEMPLATE.md>`_.

Reporting Security Issues
-------------------------

Please do not report security issues in public. Please email security@edx.org.

Getting Help
------------

If you're having trouble, we have discussion forums at https://discuss.openedx.org where you can connect with others in the community.

Our real-time conversations are on Slack. You can request a `Slack invitation`_, then join our `community Slack workspace`_.

For more information about these options, see the `Getting Help`_ page.

.. _Slack invitation: https://openedx-slack-invite.herokuapp.com/
.. _community Slack workspace: https://openedx.slack.com/
.. _Getting Help: https://openedx.org/getting-help

.. |pypi-badge| image:: https://img.shields.io/pypi/v/edx-arch-experiments.svg
    :target: https://pypi.python.org/pypi/edx-arch-experiments/
    :alt: PyPI

.. |ci-badge| image:: https://github.com/edx/edx-arch-experiments/workflows/Python%20CI/badge.svg?branch=main
    :target: https://github.com/edx/edx-arch-experiments/actions
    :alt: CI

.. |codecov-badge| image:: https://codecov.io/github/edx/edx-arch-experiments/coverage.svg?branch=main
    :target: https://codecov.io/github/edx/edx-arch-experiments?branch=main
    :alt: Codecov

.. |pyversions-badge| image:: https://img.shields.io/pypi/pyversions/edx-arch-experiments.svg
    :target: https://pypi.python.org/pypi/edx-arch-experiments/
    :alt: Supported Python versions

.. |license-badge| image:: https://img.shields.io/github/license/edx/edx-arch-experiments.svg
    :target: https://github.com/edx/edx-arch-experiments/blob/main/LICENSE.txt
    :alt: License

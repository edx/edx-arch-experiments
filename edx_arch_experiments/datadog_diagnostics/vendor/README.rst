Vendored files for Datadog debugging
####################################

**Notice**: This directory contains files that are not covered under
the repository license and have been copied from elsewhere for build
and deploy convenience.

Listing of files, their origin, and their purpose for inclusion:

* ``ddtrace-*.whl``: `ddtrace <https://github.com/DataDog/dd-trace-py>`__

  * ``ddtrace-2.14.0.dev106+g241ca66cf-cp311-cp311-manylinux_2_17_x86_64.manylinux2014_x86_64.whl`` is a CI build of `<https://github.com/DataDog/dd-trace-py/pull/10676>`__ (2024-09-23) for a possible root-cause fix for `<https://github.com/edx/edx-arch-experiments/issues/692>`__. It will be fetched from GitHub for edx-platform deploys at build time.

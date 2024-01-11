Codejail Service
################

When installed in the LMS as a plugin app, the ``codejail_service`` app allows the CMS to delegate codejail executions to the LMS across the network.

This is intended as a `temporary situation <https://github.com/openedx/edx-platform/issues/33538>`_ with the following goals:

- Unblock containerization of the CMS. Codejail cannot be readily containerized due to its reliance on AppArmor, but if codejail execution is outsourced, then we can containerize CMS first and will be in a better position to containerize the LMS afterwards.
- Exercise the remote-codejail pathway and have an opportunity to discover and implement needed improvements before fully building out a separate, dedicated codejail service.

Usage
*****

In LMS:

- Install ``edx-arch-experiments`` as a dependency
- Identify a service account that will be permitted to make calls to the codejail service and ensure it has the ``is_staff`` Django flag. In devstack, this would be ``cms_worker``.
- In Djano admin, under ``Django OAuth Toolkit > Applications``, find or create a Client Credentials application for that service user.

In CMS:

- Set ``ENABLE_CODEJAIL_REST_SERVICE`` to ``True``
- Set ``CODE_JAIL_REST_SERVICE_HOST`` to the URL origin of the LMS (e.g. ``http://edx.devstack.lms:18000`` in devstack)
- Keep ``CODE_JAIL_REST_SERVICE_REMOTE_EXEC`` at its default of ``xmodule.capa.safe_exec.remote_exec.send_safe_exec_request_v0``
- Adjust ``CODE_JAIL_REST_SERVICE_CONNECT_TIMEOUT`` and ``CODE_JAIL_REST_SERVICE_READ_TIMEOUT`` if needed
- Set ``CODE_JAIL_REST_SERVICE_OAUTH_URL`` to the LMS OAuth endpoint (e.g. ``http://edx.devstack.lms:18000`` in devstack)
- Set ``CODE_JAIL_REST_SERVICE_OAUTH_CLIENT_ID`` and ``CODE_JAIL_REST_SERVICE_OAUTH_CLIENT_SECRET`` to the client credentials app ID and secret that you identified in the LMS. (In devstack, these would be ``cms-backend-service-key`` and ``cms-backend-service-secret``.)

"""
Codejail service API.
"""

import json
import logging
from copy import deepcopy

from codejail.safe_exec import SafeExecException, safe_exec
from django.conf import settings
from edx_toggles.toggles import SettingToggle
from jsonschema.exceptions import best_match as json_error_best_match
from jsonschema.validators import Draft202012Validator
from rest_framework.decorators import api_view, parser_classes, permission_classes
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response

log = logging.getLogger(__name__)

# .. toggle_name: CODEJAIL_SERVICE_ENABLED
# .. toggle_implementation: SettingToggle
# .. toggle_default: True
# .. toggle_description: If True, codejail execution calls will be accepted over the network,
#   allowing this IDA to act as a codejail service for another IDA.
# .. toggle_use_cases: circuit_breaker
# .. toggle_creation_date: 2023-12-21
# .. toggle_tickets: https://github.com/openedx/edx-platform/issues/33538
CODEJAIL_SERVICE_ENABLED = SettingToggle('CODEJAIL_SERVICE_ENABLED', default=True, module_name=__name__)

# Schema for the JSON passed in the v0 API's 'payload' field.
payload_schema = {
    'type': 'object',
    'properties': {
        'code': {'type': 'string'},
        'globals_dict': {'type': 'object'},
        # Some of these are configured as union types because
        # edx-platform appears to currently default to None for some
        # of them (rather than omitting the keys.)
        'python_path': {
            'anyOf': [
                {
                    'type': 'array',
                    'items': {'type': 'string'},
                },
                {'type': 'null'},
            ],
        },
        'limit_overrides_context': {
            'anyOf': [
                {'type': 'string'},
                {'type': 'null'},
            ],
        },
        'slug': {
            'anyOf': [
                {'type': 'string'},
                {'type': 'null'},
            ],
        },
        'unsafely': {'type': 'boolean'},
    },
    'required': ['code', 'globals_dict'],
}
# Use this rather than jsonschema.validate, since that would check the schema
# every time it is called. Best to do it just once at startup.
Draft202012Validator.check_schema(payload_schema)
payload_validator = Draft202012Validator(payload_schema)


# A note on the authorization model used here:
#
# We really just need one service account to be able to call this, and
# then also allow is_staff to call it for convenience and debugging
# purposes.
#
# To do this "right", I'd probably have to create an empty abstract
# model, create a permission on it, create a group, add the permission
# to the group, and add the service account to the group. Then I could
# check the calling user's has_perm. If I wanted to use bridgekeeper
# (as we're trying to do more of) I might be able to give bridgekeeper
# a `@blanket_rule` that checks membership in the group, then use
# bridgekeeper here instead of checking permissions directly, but it's
# possible this wouldn't work because bridgekeeper might require there
# to be a model instance to pass in (and there wouldn't be one, since
# it's just an abstract model.)
#
# But... given that the service account will be is_staff, and I'll be
# opening this up to is_staff alongside the intended service account,
# and this is already a hacky intermediate solution... we can just use
# the `IsAdminUser` permission class and be done with it.


@api_view(['POST'])
@parser_classes([FormParser, MultiPartParser])
@permission_classes([IsAdminUser])
def code_exec_view_v0(request):
    """
    Executes code in a codejail sandbox for a remote caller.

    This implements the API used by edxapp's xmodule.capa.safe_exec.remote_exec.
    It accepts a POST of a form containing a `payload` value and zero or more
    extra files.

    The payload is JSON and contains the parameters to be sent to codejail's
    safe_exec (aside from `extra_files`). See payload_schema for type information.

    This API does not permit `unsafely=true`.

    If the response is a 200, the codejail execution completed. The response
    will be JSON containing either a single key `globals_dict` (containing
    the global scope values at the end of a run to completion) or `emsg` (the
    exception the submitted code raised).

    Other responses are errors, with a JSON body containing further details.
    """
    if not CODEJAIL_SERVICE_ENABLED.is_enabled():
        return Response({'error': "Codejail service not enabled"}, status=500)

    # There's a risk of getting into a loop if e.g. the CMS asks the
    # LMS to run codejail executions on its behalf, and the LMS is
    # *also* inadvertently configured to call the LMS (itself).
    # There's no good reason to have a chain of >2 services passing
    # codejail requests along, so only allow execution here if we
    # aren't going to pass it along to someone else.
    if getattr(settings, 'ENABLE_CODEJAIL_REST_SERVICE', False):
        log.error(
            "Refusing to run codejail request from over the network "
            "when we're going to pass it to another IDA anyway"
        )
        return Response({'error': "Codejail service is misconfigured. (Refusing to act as relay.)"}, status=500)

    params_json = request.data['payload']
    params = json.loads(params_json)

    if json_error := json_error_best_match(payload_validator.iter_errors(params)):
        return Response({'error': f"Payload JSON did not match schema: {json_error.message}"}, status=400)

    complete_code = params['code']  # includes standard prolog
    input_globals_dict = params['globals_dict']
    python_path = params.get('python_path') or []
    limit_overrides_context = params.get('limit_overrides_context')
    slug = params.get('slug')
    unsafely = params.get('unsafely')

    # Convert to a list of (string, bytestring) pairs. Any duplicated file names
    # are resolved as last-wins.
    extra_files = [(filename, file.read()) for filename, file in request.FILES.items()]

    # Far too dangerous to allow unsafe executions to come in over the
    # network, no matter who we think the caller is. The caller is the
    # one who has the context on safety.
    if unsafely:
        return Response({'error': "Refusing codejail execution with unsafely=true"}, status=400)

    output_globals_dict = deepcopy(input_globals_dict)  # Output dict will be mutated by safe_exec
    try:
        safe_exec(
            complete_code,
            output_globals_dict,
            python_path=python_path,
            extra_files=extra_files,
            limit_overrides_context=limit_overrides_context,
            slug=slug,
        )
    except SafeExecException as e:
        log.debug("CodejailService execution failed for {slug=} with: {e}")
        return Response({'emsg': str(e)})

    log.debug("CodejailService execution succeeded for {slug=}, with globals={output_globals_dict!r}")
    return Response({'globals_dict': output_globals_dict})

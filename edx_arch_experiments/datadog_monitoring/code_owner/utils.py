"""
Utilities for monitoring code_owner
"""
import logging

from django.conf import settings
from django.urls import resolve
from edx_django_utils.monitoring import set_custom_attribute

log = logging.getLogger(__name__)


def get_code_owner_from_module(module):
    """
    Attempts lookup of code_owner based on a code module,
    finding the most specific match. If no match, returns None.

    For example, if the module were 'openedx.features.discounts.views',
    this lookup would match on 'openedx.features.discounts' before
    'openedx.features', because the former is more specific.

    """
    if not module:
        return None

    code_owner_mappings = get_code_owner_mappings()
    if not code_owner_mappings:
        return None

    module_parts = module.split('.')
    # To make the most specific match, start with the max number of parts
    for number_of_parts in range(len(module_parts), 0, -1):
        partial_path = '.'.join(module_parts[0:number_of_parts])
        if partial_path in code_owner_mappings:
            code_owner = code_owner_mappings[partial_path]
            return code_owner
    return None


def is_code_owner_mappings_configured():
    """
    Returns True if code owner mappings were configured, and False otherwise.
    """
    return isinstance(get_code_owner_mappings(), dict)


# cached lookup table for code owner given a module path.
# do not access this directly, but instead use get_code_owner_mappings.
_PATH_TO_CODE_OWNER_MAPPINGS = None


def get_code_owner_mappings():
    """
    Returns the contents of the CODE_OWNER_TO_PATH_MAPPINGS Django Setting, processed
    for efficient lookup by path.

    Returns:
         (dict): dict mapping modules to code owners, or None if there are no
            configured mappings, or an empty dict if there is an error processing
            the setting.

    Example return value::

        {
            'xblock_django': 'team-red',
            'openedx.core.djangoapps.xblock': 'team-red',
            'badges': 'team-blue',
        }

    """
    global _PATH_TO_CODE_OWNER_MAPPINGS

    # Return cached processed mappings if already processed
    if _PATH_TO_CODE_OWNER_MAPPINGS is not None:
        return _PATH_TO_CODE_OWNER_MAPPINGS

    # Uses temporary variable to build mappings to avoid multi-threading issue with a partially
    # processed map.  Worst case, it is processed more than once at start-up.
    path_to_code_owner_mapping = {}

    # .. setting_name: CODE_OWNER_TO_PATH_MAPPINGS
    # .. setting_default: None
    # .. setting_description: Used for monitoring and reporting of ownership. Use a
    #      dict with keys of code owner name and value as a list of dotted path
    #      module names owned by the code owner.
    code_owner_mappings = getattr(settings, 'CODE_OWNER_TO_PATH_MAPPINGS', None)
    if code_owner_mappings is None:
        return None

    try:
        for code_owner in code_owner_mappings:
            path_list = code_owner_mappings[code_owner]
            for path in path_list:
                path_to_code_owner_mapping[path] = code_owner
    except TypeError as e:
        log.exception(
            'Error processing CODE_OWNER_TO_PATH_MAPPINGS. {}'.format(e)  # pylint: disable=logging-format-interpolation
        )
        raise e

    _PATH_TO_CODE_OWNER_MAPPINGS = path_to_code_owner_mapping
    return _PATH_TO_CODE_OWNER_MAPPINGS


def set_code_owner_span_tags_from_module(module):
    """
    Updates the code_owner and code_owner_module custom span tags.

    Usage::

        set_code_owner_span_tags_from_module(__name__)

    """
    # .. custom_attribute_name: code_owner_module
    # .. custom_attribute_description: The module used to determine the code_owner. This can
    #     be useful for debugging issues for missing code owner span tags.
    set_custom_attribute('code_owner_module', module)
    code_owner = get_code_owner_from_module(module)

    if code_owner:
        set_code_owner_custom_span_tags(code_owner)


def set_code_owner_custom_span_tags(code_owner):
    """
    Sets custom span tags for code_owner, and code_owner_squad
    """
    if not code_owner:  # pragma: no cover
        return

    # .. custom_attribute_name: code_owner
    # .. custom_attribute_description: The squad owner name for the tagged span.
    set_custom_attribute('code_owner', code_owner)
    # .. custom_attribute_name: code_owner_squad
    # .. custom_attribute_description: Deprecated code_owner_squad is now redundant
    #     to the code_owner span tag.
    set_custom_attribute('code_owner_squad', code_owner)

    # .. custom_attribute_name: code_owner_plugin
    # .. custom_attribute_description: This is a temporary span tag to roll out the
    #     the switch from edx-django-utils to this plugin. If this span tag is True,
    #     the plugin has added the above custom span tags (possibly in addition to
    #     edx-django-utils). If the code_owner_theme span tag is also seen, then
    #     edx-django-utils is also adding these span tags. If not, only the plugin is
    #     creating these tags.
    set_custom_attribute('code_owner_plugin', True)


def set_code_owner_span_tags_from_request(request):
    """
    Sets the code_owner custom span tag for the request.
    """
    module = _get_module_from_request(request)
    if module:
        set_code_owner_span_tags_from_module(module)


def _get_module_from_request(request):
    """
    Get the module from the request path or the current transaction.

    Side-effects:
        Sets code_owner_path_error custom span tag if applicable.

    Returns:
        str: module name or None if not found

    """
    if not is_code_owner_mappings_configured():
        return None

    module, path_error = _get_module_from_request_path(request)

    if path_error:
        # .. custom_attribute_name: code_owner_path_error
        # .. custom_attribute_description: Error details if the module can't be found. This can
        #     be useful for debugging issues for missing code owner span tags.
        set_custom_attribute('code_owner_path_error', path_error)

    return module


def _get_module_from_request_path(request):
    """
    Uses the request path to get the view_func module.

    Returns:
        (str, str): (module, error_message), where at least one of these should be None

    """
    try:
        view_func, _, _ = resolve(request.path)
        module = view_func.__module__
        return module, None
    except Exception as e:  # pragma: no cover, pylint: disable=broad-exception-caught
        return None, str(e)


def clear_cached_mappings():
    """
    Clears the cached code owner mappings. Useful for testing.
    """
    global _PATH_TO_CODE_OWNER_MAPPINGS
    _PATH_TO_CODE_OWNER_MAPPINGS = None

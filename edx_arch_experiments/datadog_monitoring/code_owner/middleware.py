"""
Middleware for code_owner_2 custom attribute
"""
import logging

from django.urls import resolve
from edx_django_utils.monitoring import set_custom_attribute

from .utils import get_code_owner_from_module, is_code_owner_mappings_configured, set_code_owner_custom_attributes

log = logging.getLogger(__name__)


class CodeOwnerMonitoringMiddleware:
    """
    Django middleware object to set custom attributes for the owner of each view.

    For instructions on usage, see:
    https://github.com/edx/edx-arch-experiments/blob/master/edx_arch_experiments/datadog_monitoring/docs/how_tos/add_code_owner_custom_attribute_to_an_ida.rst

    Custom attributes set:
    - code_owner_2: The owning team mapped to the current view.
    - code_owner_2_module: The module found from the request or current transaction.
    - code_owner_2_path_error: The error mapping by path, if code_owner_2 isn't found in other ways.

    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        self._set_code_owner_attribute(request)
        return response

    def process_exception(self, request, exception):    # pylint: disable=W0613
        self._set_code_owner_attribute(request)

    def _set_code_owner_attribute(self, request):
        """
        Sets the code_owner_2 custom attribute for the request.
        """
        code_owner = None
        module = self._get_module_from_request(request)
        if module:
            code_owner = get_code_owner_from_module(module)

        if code_owner:
            set_code_owner_custom_attributes(code_owner)

    def _get_module_from_request(self, request):
        """
        Get the module from the request path or the current transaction.

        Side-effects:
            Sets code_owner_2_module custom attribute, used to determine code_owner_2.
            If module was not found, may set code_owner_2_path_error custom attribute
                if applicable.

        Returns:
            str: module name or None if not found

        """
        if not is_code_owner_mappings_configured():
            return None

        module, path_error = self._get_module_from_request_path(request)
        if module:
            set_custom_attribute('code_owner_2_module', module)
            return module

        # monitor errors if module was not found
        if path_error:
            set_custom_attribute('code_owner_2_path_error', path_error)
        return None

    def _get_module_from_request_path(self, request):
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

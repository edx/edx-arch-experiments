"""
Datadog span processor for celery span code owners.
"""
from .utils import set_code_owner_attribute_from_module


class CeleryCodeOwnerSpanProcessor:
    """
    Datadog span processor that adds celery code owner span tags.
    """

    def on_span_start(self, span):
        """
        Adds code owner span tag for celery run spans at span creation.
        """
        if getattr(span, 'name', None) == 'celery.run':
            # We can use this for celery spans, because the resource name is more predictable
            # and available from the start. For django requests, we'll instead continue to use
            # django middleware for setting code owner.
            set_code_owner_attribute_from_module(span.resource)

    def on_span_finish(self, span):
        pass

    def shutdown(self, _timeout):
        pass

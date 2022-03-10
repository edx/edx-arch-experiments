"""
    Temporary copy of TrackingEvent from license-manager to represent license manager events.
    Eventually to be moved to openedx_events.
"""

import logging

logger = logging.getLogger(__name__)


# TODO (EventBus):
# Use TrackingEvent class from openedx_events and use Attr <-> Avro bridge to deserialize
class TrackingEvent:

    """
    Data class for license-manager subscription events
    """

    def __init__(self, *args, **kwargs):
        self.license_uuid = kwargs.get('license_uuid', None)
        self.license_activation_key = kwargs.get('license_activation_key', None)
        self.previous_license_uuid = kwargs.get('previous_license_uuid', None)
        self.assigned_date = kwargs.get('assigned_date', None)
        self.activation_date = kwargs.get('activation_date', None)
        self.assigned_lms_user_id = kwargs.get('assigned_lms_user_id', None)
        self.assigned_email = kwargs.get('assigned_email', None)
        self.expiration_processed = kwargs.get('expiration_processed', None)
        self.auto_applied = kwargs.get('auto_applied', None)
        self.enterprise_customer_uuid = kwargs.get('enterprise_customer_uuid', None)
        self.enterprise_customer_slug = kwargs.get('enterprise_customer_slug', None)
        self.enterprise_customer_name = kwargs.get('enterprise_customer_name', None)
        self.customer_agreement_uuid = kwargs.get('customer_agreement_uuid', None)

    # Some paths will set assigned_lms_user_id to '' if empty, so need to allow strings in the schema
    TRACKING_EVENT_AVRO_SCHEMA = """
        {
            "namespace": "license_manager.apps.subscriptions",
            "name": "TrackingEvent",
            "type": "record",
            "fields": [
                {"name": "license_uuid", "type": "string"},
                {"name": "license_activation_key", "type": "string"},
                {"name": "previous_license_uuid", "type": "string"},
                {"name": "assigned_date", "type": "string"},
                {"name": "assigned_lms_user_id", "type": ["int", "string", "null"], "default": "null"},
                {"name": "assigned_email", "type":"string"},
                {"name": "expiration_processed", "type": "boolean"},
                {"name": "auto_applied", "type": "boolean", "default": "false"},
                {"name": "enterprise_customer_uuid", "type": ["string", "null"], "default": "null"},
                {"name": "customer_agreement_uuid", "type": ["string", "null"], "default": "null"},
                {"name": "enterprise_customer_slug", "type": ["string", "null"], "default": "null"},
                {"name": "enterprise_customer_name", "type": ["string", "null"], "default": "null"}
            ]
        }

    """

    @staticmethod
    def from_dict(dict_instance, ctx=None):  # pylint: disable=unused-argument
        return TrackingEvent(**dict_instance)

    @staticmethod
    def to_dict(obj, ctx=None):  # pylint: disable=unused-argument
        # remove lms id and email from to_dict for event consumer to not print PII
        return {
            'enterprise_customer_uuid': obj.enterprise_customer_uuid,
            'customer_agreement_uuid': obj.customer_agreement_uuid,
            'enterprise_customer_slug': obj.enterprise_customer_slug,
            'enterprise_customer_name': obj.enterprise_customer_name,
            "license_uuid": obj.license_uuid,
            "license_activation_key": obj.license_activation_key,
            "previous_license_uuid": obj.previous_license_uuid,
            "assigned_date": obj.assigned_date,
            "activation_date": obj.activation_date,
            "expiration_processed": obj.expiration_processed,
            "auto_applied": (obj.auto_applied or False),
        }

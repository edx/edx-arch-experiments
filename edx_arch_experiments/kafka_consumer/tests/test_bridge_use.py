from datetime import datetime
from unittest.mock import Mock

from confluent_kafka.schema_registry import SchemaRegistryClient
from confluent_kafka.schema_registry.avro import AvroDeserializer, AvroSerializer
from django.test import TestCase
from opaque_keys.edx.keys import CourseKey
from openedx_events.bridge.avro_attrs_bridge import AvroAttrsBridgeKafkaWrapper
from openedx_events.learning.data import CourseData, CourseEnrollmentData, UserData, UserPersonalData
from openedx_events.learning.signals import COURSE_ENROLLMENT_CREATED


class BridgeTest(TestCase):

    def test_produce_and_consume_event_with_bridge(self):
        bridge = AvroAttrsBridgeKafkaWrapper(COURSE_ENROLLMENT_CREATED)
        mock_src = SchemaRegistryClient({'url': 'https://www.example.com'})
        mock_src.register_schema = Mock(return_value=3)

        serializer = AvroSerializer(schema_str=bridge.schema_str(),
                                    schema_registry_client=mock_src,
                                    to_dict=bridge.to_dict)

        serializer._subject_name_func = Mock()

        user_personal_data = UserPersonalData(username="username", email="email", name="name")
        user_data = UserData(id=1, is_active=True, pii=user_personal_data)
        course_id = "course-v1:edX+DemoX.1+2014"
        course_key = CourseKey.from_string(course_id)
        course_data = CourseData(
            course_key=course_key,
            display_name="display_name",
            start=datetime.now(),
            end=datetime.now(),
        )
        course_enrollment_data = CourseEnrollmentData(
            user=user_data,
            course=course_data,
            mode="mode",
            is_active=False,
            creation_date=datetime.now(),
            created_by=user_data,
        )

        event_data = { "enrollment": course_enrollment_data }

        as_bytes = serializer(event_data, None)

        mock_src.get_schema = Mock(return_value=serializer._schema)
        deserializer = AvroDeserializer(schema_str=bridge.schema_str(),
                                        schema_registry_client=mock_src,
                                        from_dict=bridge.from_dict)

        course_enrollment_data_deserialized = deserializer(as_bytes, None)

        assert event_data == course_enrollment_data_deserialized

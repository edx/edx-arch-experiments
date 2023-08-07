"""
Publish events from a csv

This is meant to help republish failed events. The CSV may be an export from Splunk, or it may be manually created, as
long as it has 'initial_topic', 'event_type', 'event_data_as_json', 'event_key_field', and 'event_metadata_as_json'
columns.

Example row:
initial_topic,event_type,event_data_as_json,event_key_field,event_metadata_as_json
test-topic,org.openedx.test.event,{"test_data": {"course_key": "ABCx"}},test_data.course_key,
    {"event_type": "org.openedx.test.event","id": "12345", "minorversion": 0, "source": "openedx/cms/web",
     "sourcehost": "ip-10-3-16-4", "time"": ""2023-08-10T17:55:22.088808+00:00", ""sourcelib"": [8, 5, 0]}


This is created as a script instead of a management command because it's meant to be used as a one-off and not to
require pip installing this package into anything else to run. However, since edx-event-bus-kafka does expect certain
settings, the script must be run in an environment with DJANGO_SETTINGS_MODULE.

To run:
tox -e scripts -- python edx_arch_experiments/scripts/republish_failed_events.py
 --filename /Users/rgraber/oneoffs/failed_events.csv
"""

import csv
import json
import sys

import click
from edx_event_bus_kafka.internal.producer import create_producer
from openedx_events.tooling import EventsMetadata, OpenEdxPublicSignal, load_all_signals


@click.command()
@click.option('--filename', type=click.Path(exists=True))
def read_and_send_events(filename):
    load_all_signals()
    producer = create_producer()
    try:
        log_columns = ['initial_topic', 'event_type', 'event_data_as_json', 'event_key_field', 'event_metadata_as_json']
        with open(filename) as log_file:
            reader = csv.DictReader(log_file)
            # Make sure csv contains all necessary columns for republishing
            if not all(column in reader.fieldnames for column in log_columns):
                print(f'Missing required columns {set(log_columns).difference(set(reader.fieldnames))}. Cannot'
                      f' republish events.')
                sys.exit(1)
            ids = set()
            for row in reader:
                # An empty field may end up in Splunk as the string "None". That is not a valid value for any of the
                # fields we care about, so just treat it the same as empty
                empties = [key for key, value in row.items() if key in log_columns and value in [None, '', 'None']]
                # If any row is missing data, stop processing the whole file to avoid sending events out of order
                if len(empties) > 0:
                    print(f'Missing required fields in row {reader.line_num}: {empties}. Will not continue publishing.')
                    sys.exit(1)

                # Strip single quotation marks off everything (Splunk adds them on all fields)
                topic = row['initial_topic'].replace("'", "")
                event_type = row['event_type'].replace("'", "")
                event_data = json.loads(row['event_data_as_json'].replace("'", ""))
                event_key_field = row['event_key_field'].replace("'", "")
                events_metadata_json = row['event_metadata_as_json'].replace("'", "")
                metadata = EventsMetadata.from_json(events_metadata_json)
                signal = OpenEdxPublicSignal.get_signal_by_type(event_type)
                if metadata.id in ids:
                    print(f"Skipping duplicate id {metadata.id}")
                    continue
                ids.add(metadata.id)

                producer.send(signal=signal, event_data=event_data, event_key_field=event_key_field, topic=topic,
                              event_metadata=metadata)
    finally:
        producer.prepare_for_shutdown()


if __name__ == '__main__':
    read_and_send_events()

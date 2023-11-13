"""
Publish events from a CSV to the Event Bus.

This is meant to help republish failed events. The CSV may be an export from Splunk, or it may be manually created, as
long as it has 'initial_topic', 'event_type', 'event_data_as_json', 'event_key_field', and 'event_metadata_as_json'
columns.

If the CSV is manually created, you will need to use the python __repr__ of all fields. For strings, including
json dumps, this means enclosing them in single quotes

Example row (second line split up for readability, in the csv it should be all one line)
initial_topic,event_type,event_data_as_json,event_key_field,event_metadata_as_json
'test-topic','org.openedx.test.event','{"user_data": {"id": 1, "is_active": True}}','user_data.id',
'{"event_type": "org.openedx.test.event", "id": "12345", "minorversion": 0, "source": "openedx/cms/web",
 "sourcehost": "ip-10-3-16-25", "time": "2023-08-10T17:15:38.549331+00:00", "sourcelib": [8, 5, 0]}'

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
from ast import literal_eval

import click
from openedx_events.event_bus import get_producer
from openedx_events.tooling import EventsMetadata, OpenEdxPublicSignal, load_all_signals


@click.command()
@click.option('--filename', type=click.Path(exists=True))
def read_and_send_events(filename):
    load_all_signals()
    producer = get_producer()
    try:
        log_columns = ['initial_topic', 'event_type', 'event_data_as_json', 'event_key_field', 'event_metadata_as_json']
        with open(filename) as log_file:
            reader = csv.DictReader(log_file)
            # Make sure csv contains all necessary columns for republishing
            missing_columns = set(log_columns).difference(set(reader.fieldnames))
            if len(missing_columns) > 0:
                print(f'Missing required columns {missing_columns}. Cannot republish events.')
                sys.exit(1)
            ids = set()
            for row in reader:
                # We log everything using __repr__, so strings get quotes around them and "None" gets
                # written literally. Use literal_eval to go from "None" to None and remove the extraneous quotes
                # from the logs
                empties = [key for key, value in row.items() if key in log_columns and literal_eval(value) is None]
                # If any row is missing data, stop processing the whole file to avoid sending events out of order
                if len(empties) > 0:
                    print(f'Missing required fields in row {reader.line_num}: {empties}. Will not continue publishing.')
                    sys.exit(1)

                topic = literal_eval(row['initial_topic'])
                event_type = literal_eval(row['event_type'])
                event_data = json.loads(literal_eval(row['event_data_as_json']))
                event_key_field = literal_eval(row['event_key_field'])
                metadata = EventsMetadata.from_json(literal_eval(row['event_metadata_as_json']))
                signal = OpenEdxPublicSignal.get_signal_by_type(event_type)
                if metadata.id in ids:
                    print(f"Skipping duplicate id {metadata.id}")
                    continue
                ids.add(metadata.id)

                producer.send(signal=signal, event_data=event_data, event_key_field=event_key_field, topic=topic,
                              event_metadata=metadata)
                print(f'Successfully published event to event bus. line={reader.line_num} {event_data=} {topic=}'
                      f' {event_key_field=} metadata={metadata.to_json()}')
    finally:
        producer.prepare_for_shutdown()


if __name__ == '__main__':
    read_and_send_events()

ConfigWatcher
#############

Plugin app that can report on changes to Django model instances via logging and optionally Slack messages. The goal is to help operators who are investigating an outage or other sudden change in behavior by allowing them to easily determine what has changed recently.

Currently specialized to observe Waffle flags, switches, and samples, but could be expanded to other models.

See ``.signals.receivers`` for available settings and ``/setup.py`` for IDA plugin configuration.

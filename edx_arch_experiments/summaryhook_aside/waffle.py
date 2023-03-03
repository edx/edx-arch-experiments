"""
Waffle flag controlling summary hook distribution.
Xblocks do not generally use waffle flags,
import at use time method taken from the LTI Xblock
"""

# Namespace
WAFFLE_NAMESPACE = 'summaryhook'

# .. toggle_name: summaryhook.enabled
# .. toggle_implementation: CourseWaffleFlag
# .. toggle_default: False
# .. toggle_description: Enables OpenAI driven summary xblock aside
# .. toggle_use_cases: temporary
# .. toggle_creation_date: 2023-03-06
# .. toggle_target_removal_date: 2023-12-06
# .. toggle_tickets: ACADEMIC-15709 (2U)
# .. toggle_warning: None.
SUMMARYHOOK_ENABLED = 'summaryhook_enabled'


def _get_summaryhook_enabled_waffle_flag():
    """
    Import and return Waffle flag for enabling the summary hook
    """
    # pylint: disable=import-error,import-outside-toplevel
    from openedx.core.djangoapps.waffle_utils import CourseWaffleFlag
    return CourseWaffleFlag(f'{WAFFLE_NAMESPACE}.{SUMMARYHOOK_ENABLED}', __name__)


def summary_enabled(course_key):
    """
    Return whether the summaryhook.summaryhook_enabled WaffleFlag is on.
    """
    return _get_summaryhook_enabled_waffle_flag().is_enabled(course_key)

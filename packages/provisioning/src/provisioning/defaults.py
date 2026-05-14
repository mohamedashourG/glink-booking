"""Standard policy applied to every provisioned client."""

EVENT_TYPE_TITLE = "30 Minute Meeting"
EVENT_TYPE_SLUG = "30min"
EVENT_TYPE_LENGTH_MINUTES = 30

BEFORE_BUFFER_MINUTES = 15
AFTER_BUFFER_MINUTES = 15
MINIMUM_NOTICE_MINUTES = 4 * 60  # 4 hours
ROLLING_WINDOW_DAYS = 60

SCHEDULE_NAME = "Working Hours"

# Booking questions added on top of the system `name` + `email` defaults.
EXTRA_BOOKING_QUESTIONS = [
    {"name": "company", "label": "Company", "type": "text", "required": False},
    {
        "name": "discussionTopic",
        "label": "What would you like to discuss?",
        "type": "textarea",
        "required": False,
    },
]

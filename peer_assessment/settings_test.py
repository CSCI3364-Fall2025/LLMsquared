# peer_assessment/settings_test.py
from .settings import *
TESTING = True

# Force SQLite for tests
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

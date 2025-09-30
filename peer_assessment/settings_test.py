# peer_assessment/settings_test.py
from .settings import *
TESTING = True
import os

# Force SQLite for tests
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}



# for email in scheduler
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"


os.environ.setdefault("OPENAI_API_KEY", "dummy")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

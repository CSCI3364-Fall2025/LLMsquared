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

# # Optional: speed up hashing in tests
# PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# conftest.py
import os
import pytest
from django.core.management import call_command

@pytest.fixture(scope="session", autouse=True)
def seed_dataset(django_db_setup, django_db_blocker):
    if os.environ.get("TEST_SKIP_SEED", "0") == "1":
        return

    level = int(os.environ.get("TEST_SEED_LEVEL", "1"))
    semester = os.environ.get("TEST_SEED_SEMESTER", "Fall")
    year = int(os.environ.get("TEST_SEED_YEAR", "2025"))

    with django_db_blocker.unblock():
        # Purge then seed once for the whole pytest session
        call_command(
            "seed_data",
            "--level", str(level),
            "--semester", semester,
            "--year", str(year),
            "--purge",
        )

        # need this since course was none when going through on of scheduler tests
        from my_app.models import Course
        print("Seeded courses (session fixture):", Course.objects.count())
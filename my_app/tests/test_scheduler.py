# test_scheduler.py
import os
import pytest
from datetime import timedelta
from django.utils import timezone
from django.core.management import call_command

from my_app.models import User, Course, CourseMember, Assessment

# Per-test dataset via seed command 
@pytest.fixture(autouse=True)
def seed_scheduler_dataset(django_db_blocker):
    semester = os.environ.get("TEST_SEMESTER", "Fall")
    year = os.environ.get("TEST_YEAR", "2025")

    with django_db_blocker.unblock():
        call_command(
            "seed_data",
            "--level", "1",
            "--semester", semester,
            "--year", year,
            "--purge",
        )
    yield

# Tests 
@pytest.mark.django_db
def test_send_12h_reminder_sends_to_all_course_members(monkeypatch):
    """
    Integration-style test: uses seeded data from seed_data command.
    Publishes an assessment due within the scheduler's window and verifies
    one email is sent to all enrolled students in that course.
    """
    import my_app.scheduler as sched

    fixed_now = timezone.now()
    monkeypatch.setattr(sched, "now", lambda: fixed_now)

    # Use the first seeded course
    course = Course.objects.first()
    assert course is not None, "Seeded data missing a Course"

    # Collect seeded course members' emails
    emails = list(
        CourseMember.objects.filter(course=course)
        .select_related("user")
        .values_list("user__email", flat=True)
    )
    assert emails, "Seeded course has no students"

    # Create an assessment due within the scheduler's 1-min window
    Assessment.objects.create(
        title="HW1",
        course=course,
        status="published",
        due_date=fixed_now + timedelta(seconds=30),
    )

    # Stub the email sender
    sent = []

    def fake_send_mail(subject, message, from_email, recipient_list, fail_silently):
        sent.append({"subject": subject, "to": list(recipient_list)})
        return len(recipient_list)

    monkeypatch.setattr(sched, "send_mail", fake_send_mail)

    # Run the job
    sched.send_12h_reminder()

    # One email to all members
    assert len(sent) == 1
    assert set(sent[0]["to"]) == set(emails)
    assert "[Assessmate] Reminder" in sent[0]["subject"]
    assert "HW1" in sent[0]["subject"]


@pytest.mark.django_db
def test_send_12h_reminder_skips_when_not_due_or_not_published(monkeypatch):
    """
    No emails if (A) due date is outside the window or (B) assessment is not published.
    Creates its own tiny objects alongside the seeded dataset.
    """
    import my_app.scheduler as sched

    fixed_now = timezone.now()
    monkeypatch.setattr(sched, "now", lambda: fixed_now)

    # Independent course/user so we don't depend on the large seed for this case
    teacher = User.objects.create(email="teacher2@example.com", name="Prof. Z", role="teacher")
    course = Course.objects.create(
        course_number="CS102",
        course_name="Data Structures",
        course_semester="Fall",
        course_year="2025",
        teacher=teacher,
    )
    student = User.objects.create(email="s3@example.com", name="S Three", role="student")
    CourseMember.objects.create(course=course, user=student)

    # Case A: published but due too far in the future (> 1 minute)
    Assessment.objects.create(
        title="HW-Future",
        course=course,
        status="published",
        due_date=fixed_now + timedelta(hours=2),
    )

    # Case B: within the window but not published
    Assessment.objects.create(
        title="HW-Draft",
        course=course,
        status="draft",
        due_date=fixed_now + timedelta(seconds=30),
    )

    sent = []
    monkeypatch.setattr(
        sched,
        "send_mail",
        lambda *a, **k: sent.append({"to": list(k.get("recipient_list") or a[3])}),
    )

    sched.send_12h_reminder()

    assert sent == []
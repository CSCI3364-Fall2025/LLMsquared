# my_app/tests/scheduler_test.py
import pytest
from datetime import timedelta
from django.utils import timezone

def _make_user(UserModel, username, email, password="x"):
    """
    Create a user instance for whatever model CourseMember.user points to,
    without assuming the manager exposes .create_user().
    """
    user = UserModel()
    if hasattr(user, "username"):
        user.username = username
    if hasattr(user, "email"):
        user.email = email
    # If the model supports password hashing, use it; otherwise ignore.
    if hasattr(user, "set_password"):
        user.set_password(password)
    elif hasattr(user, "password"):
        user.password = password  # not hashed; OK for tests that don't auth
    user.save()
    return user

@pytest.mark.django_db
def test_send_12h_reminder_sends_to_all_course_members(monkeypatch):
    import my_app.scheduler as sched
    fixed_now = timezone.now()
    monkeypatch.setattr(sched, "now", lambda: fixed_now)

    from my_app.models import Course, Assessment, CourseMember

    # Use the exact user model required by the FK
    UserModel = CourseMember._meta.get_field("user").remote_field.model

    course = Course.objects.create(course_number="CS101")
    u1 = _make_user(UserModel, "u1", "u1@example.com")
    u2 = _make_user(UserModel, "u2", "u2@example.com")
    CourseMember.objects.create(course=course, user=u1)
    CourseMember.objects.create(course=course, user=u2)

    # Due in the 1-minute window
    Assessment.objects.create(
        title="HW1",
        course=course,
        status="published",
        due_date=fixed_now + timedelta(seconds=30),
    )

    sent = []
    def fake_send_mail(subject, message, from_email, recipient_list, fail_silently):
        sent.append({"subject": subject, "message": message, "to": list(recipient_list)})
        return len(recipient_list)

    # Stub actual email sending
    monkeypatch.setattr(sched, "send_mail", fake_send_mail)

    # Act
    sched.send_12h_reminder()

    # Assert
    assert len(sent) == 1
    assert set(sent[0]["to"]) == {u1.email, u2.email}
    assert "[Assessmate] Reminder" in sent[0]["subject"]
    assert "HW1" in sent[0]["subject"]

@pytest.mark.django_db
def test_send_12h_reminder_skips_when_not_due_or_not_published(monkeypatch):
    import my_app.scheduler as sched
    fixed_now = timezone.now()
    monkeypatch.setattr(sched, "now", lambda: fixed_now)

    from my_app.models import Course, Assessment, CourseMember

    UserModel = CourseMember._meta.get_field("user").remote_field.model

    course = Course.objects.create(course_number="CS102")
    user = _make_user(UserModel, "u3", "u3@example.com")
    CourseMember.objects.create(course=course, user=user)

    # Too far in the future
    Assessment.objects.create(
        title="HW2",
        course=course,
        status="published",
        due_date=fixed_now + timedelta(hours=2),
    )

    # Not published (even if within window)
    Assessment.objects.create(
        title="HW3",
        course=course,
        status="draft",
        due_date=fixed_now + timedelta(seconds=30),
    )

    sent = []
    monkeypatch.setattr(
        sched, "send_mail",
        lambda *a, **k: sent.append({"to": list(k.get("recipient_list") or a[3])}),
    )

    sched.send_12h_reminder()
    assert sent == []


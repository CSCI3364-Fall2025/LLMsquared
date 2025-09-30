
import pytest
from datetime import timedelta
from django.utils import timezone
import my_app.scheduler as sched
from my_app.models import User, Course, CourseMember, Assessment

@pytest.mark.django_db
def test_send_12h_reminder_sends_to_all_course_members(monkeypatch):
    '''
    Unit test that tests  scheduler.py. A published assessment due within the window 
    triggers one mocked email to all enrolled students.
    '''
    import my_app.scheduler as sched
    fixed_now = timezone.now()
    monkeypatch.setattr(sched, "now", lambda: fixed_now)


    from my_app.models import User, Course, CourseMember, Assessment

    # Teacher
    teacher = User.objects.create(
        email="teacher@example.com", name="Prof. T", role="teacher"
    )

    # Course
    course = Course.objects.create(
        course_number="CS101",
        course_name="Intro to CS",
        course_semester="Fall",
        course_year="2025",
        teacher=teacher,
    )

    s1 = User.objects.create(email="s1@example.com", name="S One", role="student")
    s2 = User.objects.create(email="s2@example.com", name="S Two", role="student")
    CourseMember.objects.create(course=course, user=s1)
    CourseMember.objects.create(course=course, user=s2)

    # Assessment due within the 1-minute window (your function’s window)
    Assessment.objects.create(
        title="HW1",
        course=course,
        status="published",
        due_date=fixed_now + timedelta(seconds=30),
    )

    # Stub email sending
    sent = []
    def fake_send_mail(subject, message, from_email, recipient_list, fail_silently):
        sent.append(
            {"subject": subject, "message": message, "from": from_email, "to": list(recipient_list)}
        )
        return len(recipient_list)

    monkeypatch.setattr(sched, "send_mail", fake_send_mail)

    # call the actual job function
    sched.send_12h_reminder()

    # exactly one email, to all enrolled students
    assert len(sent) == 1
    assert set(sent[0]["to"]) == {"s1@example.com", "s2@example.com"}
    assert "[Assessmate] Reminder" in sent[0]["subject"]
    assert "HW1" in sent[0]["subject"]


@pytest.mark.django_db
def test_send_12h_reminder_skips_when_not_due_or_not_published(monkeypatch):
    '''
    Unit/behavioral test
    Ensures no emails are sent if due date is outside the window 
    or assessment is not published.
    '''
    import my_app.scheduler as sched
    fixed_now = timezone.now()
    monkeypatch.setattr(sched, "now", lambda: fixed_now)

    from my_app.models import User, Course, CourseMember, Assessment

    teacher = User.objects.create(
        email="teacher2@example.com", name="Prof. Z", role="teacher"
    )

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
        sched, "send_mail",
        lambda *a, **k: sent.append({"to": list(k.get("recipient_list") or a[3])}),
    )

    sched.send_12h_reminder()

    # No emails should be sent in either case
    assert sent == []

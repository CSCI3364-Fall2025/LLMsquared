# test_google_domain_login.py
import pytest
from django.urls import reverse
from django.contrib.auth import get_user_model

VIEWS_MODULE = "my_app.views"

# allow @bc.edu
ALLOWED_DOMAIN = "bc.edu"

ALLOWED_DOMAIN = "your-real-domain.com"

# Mock googles token verification
@pytest.fixture
def monkeypatch_google_verify(monkeypatch):
    def _set_payload(payload, raises=None):
        target = "google.oauth2.id_token.verify_oauth2_token"
        def fake_verify(*args, **kwargs):
            if raises:
                raise raises
            return payload
        monkeypatch.setattr(target, fake_verify, raising=True)
    return _set_payload

# checking for allowed domain
@pytest.mark.django_db
def test_google_login_allows_allowed_domain(client, settings, monkeypatch_google_verify):
    settings.ALLOWED_LOGIN_DOMAIN = ALLOWED_DOMAIN

    payload = {
        "email": f"user@{ALLOWED_DOMAIN}",
        "email_verified": True,
        "hd": ALLOWED_DOMAIN,
        "sub": "google-user-id-123",
        "name": "User",
    }
    monkeypatch_google_verify(payload)

    url = reverse("google_callback")
    resp = client.get(url, {"id_token": "FAKE", "state": "student"}, follow=True)

    # custom session keys that app uses
    session = client.session
    assert session.get("user_id"), "user_id not stored in session"
    assert session.get("user_email") == f"user@{ALLOWED_DOMAIN}"
    assert session.get("user_role") == "student"

    assert resp.status_code == 200

# checking to see if it blocks other domains
@pytest.mark.django_db
def test_google_login_blocks_other_domains(client, settings, monkeypatch_google_verify):
    settings.ALLOWED_LOGIN_DOMAIN = ALLOWED_DOMAIN

    payload = {
        "email": "intruder@other.com",
        "email_verified": True,
        "hd": "other.com",
        "sub": "google-user-id-999",
    }
    monkeypatch_google_verify(payload)

    url = reverse("google_callback")
    resp = client.get(url, {"id_token": "FAKE_ID_TOKEN"}, follow=True)

    assert not resp.wsgi_request.user.is_authenticated

# checking to see if google account is verified – i.e. if someone's account has a bc.edu domain but not verified Google acc
@pytest.mark.django_db
def test_google_login_blocks_unverified_email(client, settings, monkeypatch_google_verify):
    settings.ALLOWED_LOGIN_DOMAIN = ALLOWED_DOMAIN

    payload = {
        "email": f"user@{ALLOWED_DOMAIN}",
        "email_verified": False,
        "hd": ALLOWED_DOMAIN,
        "sub": "google-user-id-777",
    }
    monkeypatch_google_verify(payload)

    url = reverse("google_callback")
    resp = client.get(url, {"id_token": "FAKE_ID_TOKEN"}, follow=True)

    assert not resp.wsgi_request.user.is_authenticated
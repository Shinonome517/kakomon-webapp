from datetime import timedelta
from unittest.mock import patch

import pytest
from axes.models import AccessAttempt
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import Client
from django.utils import timezone

pytestmark = pytest.mark.django_db


def test_A01_creation_change_login():
    with patch(
        "accounts.management.commands.create_learner.getpass",
        return_value="Synthetic-temporary-7239",
    ):
        call_command("create_learner", username="SYNTHETIC-USER")
    user = get_user_model().objects.get(username="synthetic-user")
    assert user.email == "" and user.must_change_password
    client = Client()
    assert (
        client.post(
            "/login/", {"username": "SYNTHETIC-USER", "password": "Synthetic-temporary-7239"}
        ).status_code
        == 302
    )
    assert client.get("/").url == "/password/"
    assert client.get("/stats/").url == "/password/"
    assert client.get("/api/unknown/").status_code == 403
    response = client.post(
        "/password/",
        {
            "old_password": "Synthetic-temporary-7239",
            "new_password1": "Synthetic-changed-9642",
            "new_password2": "Synthetic-changed-9642",
        },
    )
    assert response.status_code == 302
    user.refresh_from_db()
    assert not user.must_change_password and not user.check_password("Synthetic-temporary-7239")
    assert user.check_password("Synthetic-changed-9642")
    assert client.get("/").status_code == 200


def test_A02_logout_disable_reset(user, signed):
    assert signed.get("/logout/").status_code == 405
    assert signed.post("/logout/").status_code == 302
    assert signed.get("/").status_code == 302
    signed.force_login(user)
    call_command("disable_learner", username=user.username)
    assert signed.get("/").status_code == 302
    user.is_active = True
    user.save()
    signed.force_login(user)
    with patch(
        "accounts.management.commands.reset_learner_password.getpass",
        return_value="Synthetic-reset-75391",
    ):
        call_command("reset_learner_password", username=user.username)
    assert signed.get("/").status_code == 302
    user.refresh_from_db()
    assert user.must_change_password


def test_A02_password_change_other_sessions_and_expiry(user, signed, settings):
    other = Client()
    other.force_login(user)
    old_key = signed.session.session_key
    signed.post(
        "/password/",
        {
            "old_password": "Synthetic-check-7391",
            "new_password1": "Synthetic-fresh-8976",
            "new_password2": "Synthetic-fresh-8976",
        },
    )
    assert signed.get("/").status_code == 200
    assert other.get("/").status_code == 302
    assert signed.session.session_key != old_key
    assert settings.SESSION_COOKIE_AGE == 14 * 24 * 3600
    from django.contrib.sessions.models import Session

    Session.objects.filter(session_key=signed.session.session_key).update(
        expire_date=timezone.now() - timedelta(seconds=1)
    )
    assert signed.get("/").status_code == 302


def test_A06_limit_expiry_and_other_source(user):
    client = Client(REMOTE_ADDR="192.0.2.1")
    for _ in range(5):
        response = client.post("/login/", {"username": user.username, "password": "wrong"})
    assert response.status_code == 429
    assert (
        client.post(
            "/login/", {"username": user.username, "password": "Synthetic-check-7391"}
        ).status_code
        == 429
    )
    assert (
        Client(REMOTE_ADDR="192.0.2.2")
        .post("/login/", {"username": user.username, "password": "Synthetic-check-7391"})
        .status_code
        == 302
    )
    AccessAttempt.objects.update(attempt_time=timezone.now() - timedelta(minutes=16))
    assert (
        client.post(
            "/login/", {"username": user.username, "password": "Synthetic-check-7391"}
        ).status_code
        == 302
    )


def test_A06_source_limit_different_names():
    client = Client(REMOTE_ADDR="192.0.2.3")
    for i in range(5):
        response = client.post("/login/", {"username": f"unknown-{i}", "password": "wrong"})
    assert response.status_code == 429
    response = Client(REMOTE_ADDR="192.0.2.4").post(
        "/login/", {"username": "unknown", "password": "wrong"}
    )
    assert "ユーザー名またはパスワードが違います" in response.content.decode()


def test_A01_password_validation():
    from django.core.management import CommandError

    with (
        patch("accounts.management.commands.create_learner.getpass", return_value="short"),
        pytest.raises(CommandError),
    ):
        call_command("create_learner", username="new-learner")
    assert not get_user_model().objects.filter(username="new-learner").exists()


def test_A01_same_password_cannot_bypass_required_change(user, signed):
    user.must_change_password = True
    user.save()
    response = signed.post(
        "/password/",
        {
            "old_password": "Synthetic-check-7391",
            "new_password1": "Synthetic-check-7391",
            "new_password2": "Synthetic-check-7391",
        },
    )
    assert response.status_code == 200
    assert "現在と異なる" in response.content.decode()
    user.refresh_from_db()
    assert user.must_change_password
    assert signed.get("/").url == "/password/"

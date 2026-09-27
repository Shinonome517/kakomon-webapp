import json
import os
import sqlite3
import subprocess
import sys
from unittest.mock import Mock, patch

import pytest
from django.conf import settings
from django.db import connection
from learning.services import start_session, submit_answer
from operations.backup import export_snapshot, restore_snapshot, validate

from scripts.ddns import api_call, select_address, update_record


def addresses(*entries):
    return [
        {
            "ifname": "eth-test",
            "addr_info": [
                {"family": "inet6", "scope": "global", "local": address, **flags}
                for address, flags in entries
            ],
        }
    ]


def test_A27_gua_selection():
    # Public addresses are synthetic test inputs; no network is contacted.
    usable = "2001:4860:1234::1"
    assert (
        select_address(
            addresses(
                (usable, {}),
                ("fd00::1", {}),
                ("fe80::1", {}),
                ("2001:4860:1234::2", {"temporary": True}),
            ),
            "eth-test",
        )
        == usable
    )
    for flag in ["temporary", "deprecated", "tentative", "dadfailed"]:
        with pytest.raises(ValueError):
            select_address(addresses((usable, {"flags": [flag]})), "eth-test")
    with pytest.raises(ValueError):
        select_address(addresses((usable, {}), ("2001:4860:1234::2", {})), "eth-test")
    with pytest.raises(ValueError):
        select_address(addresses((usable, {})), "missing")


def test_A27_patch_noop_and_failure():
    record = {
        "type": "AAAA",
        "name": "study.example.com",
        "content": "2001:db8::1",
        "proxied": True,
        "ttl": 1,
    }
    call = Mock(return_value={"success": True, "result": record})
    assert update_record(call, record["content"], record["name"]) is False
    call.assert_called_once_with("GET", None)
    desired = {**record, "content": "2001:db8::2"}
    call = Mock(side_effect=[{"result": record}, {"result": desired}])
    assert update_record(call, desired["content"], desired["name"])
    assert call.call_args.args == ("PATCH", desired)
    call = Mock(return_value={"result": {**record, "type": "A"}})
    with pytest.raises(ValueError):
        update_record(call, record["content"], record["name"])
    import urllib.error

    with (
        patch(
            "scripts.ddns.urllib.request.urlopen", side_effect=urllib.error.URLError("unavailable")
        ) as request,
        patch("scripts.ddns.time.sleep"),
    ):
        with pytest.raises(RuntimeError):
            api_call("https://example.com", "synthetic", "GET", None)
        assert request.call_count == 3


@pytest.mark.django_db(transaction=True)
def test_A26_live_export_restore(seeded, user, signed, tmp_path):
    item = start_session(user, {}, count=1).items.first()
    submit_answer(user, item.pk, "second")
    signed.get("/")
    source = export_snapshot(
        connection.settings_dict["NAME"], settings.MEDIA_ROOT, tmp_path / "export"
    )
    manifest = validate(source)
    assert len(manifest["files"]) == 4
    restored = restore_snapshot(source, tmp_path / "restored")
    with sqlite3.connect(restored / "db.sqlite3") as db:
        assert db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert db.execute("SELECT COUNT(*) FROM accounts_user").fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM questions_question").fetchone()[0] == 6
        assert (
            db.execute("SELECT COUNT(*) FROM learning_answerattempt WHERE is_correct=1").fetchone()[
                0
            ]
            == 1
        )
        assert db.execute("SELECT COUNT(*) FROM django_session").fetchone()[0] == 0
    env = {
        **os.environ,
        "APP_DB": str(restored / "db.sqlite3"),
        "APP_RUNTIME": str(restored),
        "PYTHONPATH": "app",
    }
    script = "import django; django.setup(); from accounts.models import User; from learning.services import statistics, question_set; import json; print(json.dumps(statistics(question_set(User.objects.first()))))"
    result = subprocess.run(
        [sys.executable, "-c", script], env=env, capture_output=True, text=True, check=True
    )
    assert json.loads(result.stdout) == {"total": 6, "answered": 1, "correct": 1, "rate": "100.0%"}
    for name in manifest["files"]:
        if name.startswith("media/"):
            assert (restored / name).read_bytes() == (source / name).read_bytes()
    with pytest.raises(ValueError):
        restore_snapshot(source, restored)
    (source / next(name for name in manifest["files"] if name.startswith("media/"))).write_bytes(
        b"corrupt"
    )
    with pytest.raises(ValueError):
        restore_snapshot(source, tmp_path / "corrupt")
    assert not (tmp_path / "corrupt").exists()


def test_A28_production_settings(tmp_path):
    base = {
        **os.environ,
        "APP_ENV": "production",
        "APP_RUNTIME": str(tmp_path),
        "PYTHONPATH": "app",
    }
    for key in ["DJANGO_SECRET_KEY", "DJANGO_ALLOWED_HOSTS", "DJANGO_CSRF_TRUSTED_ORIGINS"]:
        base.pop(key, None)
    command = [sys.executable, "app/manage.py", "check", "--deploy", "--fail-level", "WARNING"]
    result = subprocess.run(command, env=base, capture_output=True)
    assert result.returncode != 0
    good = {
        **base,
        "DJANGO_SECRET_KEY": "synthetic-test-secret-only-" * 4,
        "DJANGO_ALLOWED_HOSTS": "study.example.com",
        "DJANGO_CSRF_TRUSTED_ORIGINS": "https://study.example.com",
    }
    result = subprocess.run(command, env=good, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    script = """import django; django.setup()
from django.test import Client
from django.conf import settings
assert not settings.DEBUG
assert settings.SESSION_COOKIE_SECURE and settings.CSRF_COOKIE_SECURE
c=Client()
assert c.get('/health/',HTTP_HOST='bad.example').status_code == 400
assert c.get('/login/',HTTP_HOST='study.example.com').status_code == 301
assert c.get('/login/',HTTP_HOST='study.example.com',HTTP_X_FORWARDED_PROTO='https').status_code == 200
"""
    result = subprocess.run(
        [sys.executable, "-c", script], env=good, capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(
    "override",
    [
        {"APP_ENV": "prodution"},
        {
            "APP_ENV": "production",
            "DJANGO_SECRET_KEY": "REPLACE_WITH_A_RANDOM_SECRET_OF_AT_LEAST_50_CHARACTERS",
        },
    ],
)
def test_A28_environment_typo_and_placeholder_rejected(tmp_path, override):
    env = {
        **os.environ,
        "PYTHONPATH": "app",
        "APP_RUNTIME": str(tmp_path),
        "DJANGO_ALLOWED_HOSTS": "study.example.com",
        "DJANGO_CSRF_TRUSTED_ORIGINS": "https://study.example.com",
        **override,
    }
    result = subprocess.run(
        [sys.executable, "app/manage.py", "check"], env=env, capture_output=True
    )
    assert result.returncode != 0

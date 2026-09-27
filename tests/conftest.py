import shutil
from pathlib import Path

import pytest
from accounts.models import User
from django.test import Client
from questions.importer import import_bundle


@pytest.fixture
def bundle(tmp_path):
    target = tmp_path / "bundle"
    shutil.copytree(Path(__file__).parent / "fixtures/synthetic", target)
    return target


@pytest.fixture
def seeded(db, settings, tmp_path, bundle):
    settings.MEDIA_ROOT = tmp_path / "media"
    import_bundle(bundle)
    return bundle


@pytest.fixture
def user(db):
    return User.objects.create_user(
        username="learner-one", password="Synthetic-check-7391", must_change_password=False
    )


@pytest.fixture
def other(db):
    return User.objects.create_user(
        username="learner-two", password="Synthetic-check-7392", must_change_password=False
    )


@pytest.fixture
def signed(user):
    client = Client()
    client.force_login(user)
    return client

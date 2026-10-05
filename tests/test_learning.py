from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from django.db import close_old_connections, connection
from django.test import Client
from learning.models import AnswerAttempt, Bookmark, StudyItem
from learning.services import StudyError, question_set, start_session, statistics, submit_answer
from questions.models import Question

pytestmark = pytest.mark.django_db


def make_item(user, filters=None):
    return start_session(user, filters or {}, count=1).items.first()


def test_A03_A07_A19_protection_before_answer(seeded, user, signed):
    item = make_item(user)
    explanation = item.revision.assets.get(usage="explanation", local_asset_id="figure-3")
    url = f"/study/{item.pk}/"
    anonymous = Client()
    for path in [url, "/stats/", "/history/", f"/image/{item.pk}/{explanation.pk}/", "/"]:
        assert anonymous.get(path).status_code == 302
    assert anonymous.post(f"/api/answer/{item.pk}/").status_code == 401
    response = signed.get(url)
    assert response.status_code == 200
    text = response.content.decode()
    assert "correct_choice_id" not in text
    assert "解説専用テキスト" not in text
    assert f"/image/{item.pk}/{explanation.pk}/" not in text
    assert signed.get(f"/image/{item.pk}/{explanation.pk}/").status_code == 404
    stem = item.revision.assets.filter(usage="stem").first()
    image = signed.get(f"/image/{item.pk}/{stem.pk}/")
    assert image.status_code == 200
    assert image["Cache-Control"] == "private, no-store"
    assert signed.get("/media/" + stem.asset.storage_key).status_code == 404
    assert response["Cache-Control"] == "private, no-store"


def test_A04_ownership(seeded, user, other, signed):
    item = make_item(other)
    attempt = submit_answer(other, item.pk, "second")
    ref = item.revision.assets.first()
    for url in [f"/study/{item.pk}/", f"/history/{attempt.pk}/", f"/image/{item.pk}/{ref.pk}/"]:
        assert signed.get(url).status_code == 404
    assert (
        signed.post(f"/api/answer/{item.pk}/", {"choice": "first", "user_id": other.pk}).status_code
        == 404
    )
    assert signed.post(f"/bookmark/{item.pk}/", {"enabled": "1"}).status_code == 404
    assert Bookmark.objects.count() == 0
    assert str(item.pk) not in signed.get("/history/").content.decode()


def test_A05_csrf_and_choice_validation(seeded, user):
    item = make_item(user)
    client = Client(enforce_csrf_checks=True)
    client.force_login(user)
    url = f"/api/answer/{item.pk}/"
    assert client.post(url, {"choice": "second"}).status_code == 403
    client.get(f"/study/{item.pk}/")
    token = client.cookies["csrftoken"].value
    assert (
        client.post(
            url,
            {"choice": "second", "csrfmiddlewaretoken": token},
            HTTP_ORIGIN="https://evil.example",
        ).status_code
        == 403
    )
    assert client.post(url, {"choice": "foreign", "csrfmiddlewaretoken": token}).status_code == 400
    assert AnswerAttempt.objects.count() == 0
    assert client.post(url, {"choice": "second", "csrfmiddlewaretoken": token}).status_code == 302


def test_A08_A10_A11_A12_answer_retry(seeded, user, signed):
    item = make_item(user)
    url = f"/api/answer/{item.pk}/"
    first = signed.post(url, {"choice": "second"}, HTTP_ACCEPT="application/json")
    assert first.status_code == 200 and first.json()["saved"]
    assert "○ 正解" in first.json()["html"]
    assert "解説専用テキスト" in first.json()["html"]
    again = signed.post(url, {"choice": "second"}, HTTP_ACCEPT="application/json")
    assert again.json() == first.json()
    different = signed.post(url, {"choice": "first"}, HTTP_ACCEPT="application/json")
    assert different.status_code == 409 and different.json()["saved"]
    assert AnswerAttempt.objects.count() == 1
    for _ in range(2):
        assert "○ 正解" in signed.get(f"/study/{item.pk}/").content.decode()
    assert AnswerAttempt.objects.count() == 1
    ref = item.revision.assets.get(usage="explanation", local_asset_id="figure-3")
    assert signed.get(f"/image/{item.pk}/{ref.pk}/").status_code == 200
    second = make_item(user)
    assert second.pk != item.pk
    submit_answer(user, second.pk, "first")
    assert AnswerAttempt.objects.count() == 2


def test_A13_latest_statistics(seeded, user):
    a, b, *_ = list(Question.objects.all())

    def answer(q, choice):
        item = start_session(user, {}, count=0).items.get(revision=q.current_revision)
        return submit_answer(user, item.pk, choice)

    answer(a, "first")
    answer(a, "second")
    answer(b, "first")
    assert statistics(question_set(user)) == {
        "total": 6,
        "answered": 2,
        "correct": 1,
        "rate": "50.0%",
    }
    answer(b, "second")
    assert statistics(question_set(user))["rate"] == "100.0%"
    assert statistics(question_set(user))["answered"] == 2


def test_A14_empty(seeded, user, signed):
    assert statistics(question_set(user))["rate"] == "—（未回答）"
    assert statistics(question_set(user, {"subjects": ["missing"]}))["total"] == 0
    with pytest.raises(StudyError):
        start_session(user, {"subjects": ["missing"]})
    page = signed.get("/?target=bookmarked&ordering=ordered&count=10")
    assert "disabled" in page.content.decode()
    assert (
        signed.post("/", {"target": "bookmarked", "ordering": "ordered", "count": "10"}).status_code
        == 200
    )
    assert StudyItem.objects.count() == 0


def test_A15_A16_filters_and_queue(seeded, user, signed):
    session = start_session(user, {}, count=0)
    items = list(session.items.select_related("revision__question"))
    assert [i.revision.question.stable_id for i in items] == [
        f"synthetic-{i:02}" for i in range(1, 7)
    ]
    submit_answer(user, items[0].pk, "first")
    submit_answer(user, items[1].pk, "second")
    q = items[0].revision.question
    Bookmark.objects.create(user=user, question=q)
    filters = {"subjects": ["無線工学"], "papers": ["synthetic-1"], "topics": ["basic"]}
    assert list(question_set(user, {**filters, "target": "incorrect"})) == [q]
    assert list(question_set(user, {**filters, "target": "bookmarked"})) == [q]
    assert question_set(user, {**filters, "target": "unanswered"}).count() == 1
    assert question_set(user, {**filters, "topics": ["rules"]}).count() == 0
    random = start_session(user, {}, "random", 0)
    ids = list(random.items.values_list("revision_id", flat=True))
    assert len(ids) == len(set(ids)) == 6
    signed.get(f"/study/{random.items.first().pk}/")
    assert ids == list(random.items.values_list("revision_id", flat=True))
    # Explicit desired bookmark state is safe to resend.
    for _ in range(2):
        signed.post(f"/bookmark/{items[0].pk}/", {"enabled": "1"})
    assert Bookmark.objects.count() == 1


@pytest.mark.django_db(transaction=True)
def test_A09_A25_parallel_real_file(seeded, user):
    assert str(connection.settings_dict["NAME"]).endswith(".sqlite3")
    item = make_item(user)
    barrier = Barrier(2)

    def send():
        close_old_connections()
        barrier.wait()
        try:
            return submit_answer(user, item.pk, "second").pk
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: send(), range(2)))
    assert results[0] == results[1]
    assert AnswerAttempt.objects.filter(study_item=item).count() == 1
    assert statistics(question_set(user))["answered"] == 1


@pytest.mark.django_db(transaction=True)
def test_A25_lock_timeout_rolls_back(seeded, user):
    import sqlite3
    import time

    item = make_item(user)
    lock = sqlite3.connect(connection.settings_dict["NAME"])
    lock.execute("BEGIN IMMEDIATE")
    started = time.monotonic()
    try:
        with pytest.raises(StudyError) as error:
            submit_answer(user, item.pk, "second")
        assert error.value.status == 503
        assert time.monotonic() - started < 10
    finally:
        lock.rollback()
        lock.close()
    assert AnswerAttempt.objects.count() == 0
    submit_answer(user, item.pk, "second")
    assert AnswerAttempt.objects.count() == 1


@pytest.mark.django_db(transaction=True)
def test_A25_parallel_distinct_items_latest_server_id(seeded, user):
    items = [make_item(user), make_item(user)]
    barrier = Barrier(2)

    def send(pair):
        item, choice = pair
        close_old_connections()
        barrier.wait()
        try:
            return submit_answer(user, item.pk, choice).pk
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as pool:
        ids = list(pool.map(send, zip(items, ["first", "second"], strict=True)))
    latest = AnswerAttempt.objects.get(pk=max(ids))
    result = statistics(question_set(user))
    assert result["answered"] == 1
    assert result["correct"] == int(latest.is_correct)
    assert len(set(ids)) == 2

import pytest
from django.test import Client
from learning.forms import StudyForm
from learning.models import StudySession
from learning.services import start_session, submit_answer
from questions.models import Question, Topic

pytestmark = pytest.mark.django_db


def filter_data():
    return StudyForm(select_all=True).data.copy()


@pytest.mark.parametrize("path", ["/", "/stats/"])
def test_A15_initial_ranges_are_all_selected(seeded, signed, path):
    response = signed.get(path)
    assert response.status_code == 200
    form = response.context["form"]
    for name in ("subjects", "papers", "topics"):
        assert set(form[name].value()) == {value for value, _ in form.fields[name].choices}
    if path == "/stats/":
        assert "ordering" not in form.fields and "count" not in form.fields
        assert response.context["stats"]["total"] == 6
    else:
        assert response.context["count"] == 6


@pytest.mark.parametrize("name", ["subjects", "papers", "topics"])
@pytest.mark.parametrize("path", ["/", "/stats/"])
def test_A15_unchecking_range_is_invalid(seeded, signed, name, path):
    data = filter_data()
    del data[name]
    response = signed.get(path, data)
    assert name in response.context["form"].errors
    assert response.context["form"][name].value() == []
    text = response.content.decode()
    assert "1つ以上選んでください。" in text
    assert 'class="rate"' not in text
    if path == "/stats/":
        assert response.status_code == 400
        assert "<h1>学習の記録</h1>" in text
    else:
        assert "data-start disabled" in text
        signed.post(path, data)
        assert not StudySession.objects.exists()


@pytest.mark.parametrize("path", ["/", "/stats/"])
def test_A14_no_registered_questions_is_empty_state(signed, path):
    response = signed.get(path)
    assert response.status_code == 200
    assert not response.context["form"].errors
    text = response.content.decode()
    assert "学習できる問題がまだありません。" in text
    assert "1つ以上選んでください。" not in text


def test_A14_A15_preview_validation_and_zero_matches(seeded, signed):
    data = filter_data()
    data["target"] = "bookmarked"
    for kind in ("home", "stats"):
        response = signed.get(f"/api/filters/{kind}/", data)
        assert response.status_code == 200
        assert response.json()["valid"]
        assert "条件に合う問題がありません。" in response.json()["html"]
        assert response["Cache-Control"] == "private, no-store"
    del data["subjects"]
    response = signed.get("/api/filters/home/", data)
    assert response.status_code == 400
    assert not response.json()["valid"]
    assert response.json()["errors"]["subjects"] == ["科目を1つ以上選んでください。"]
    assert "対象 <strong>" not in response.json()["html"]
    assert signed.get("/api/filters/home/").status_code == 400


@pytest.mark.parametrize("kind", ["home", "stats"])
def test_A03_preview_requires_auth_and_password_change(seeded, user, signed, kind):
    path = f"/api/filters/{kind}/"
    assert Client().get(path).status_code == 401
    user.must_change_password = True
    user.save(update_fields=["must_change_password"])
    assert signed.get(path).status_code == 403


def test_A15_stats_uses_stable_topic_groups_and_sort_order(seeded, signed):
    questions = list(Question.objects.select_related("topic", "exam_paper"))
    subject = questions[0].exam_paper.subject
    members = [q for q in questions if q.exam_paper.subject == subject]
    assert len(members) >= 3
    topic_specs = [
        ("z-last", "同じ表示名", 20),
        ("b-first", "同じ表示名", 10),
        ("a-first", "あ", 10),
    ]
    for question, (code, label, order) in zip(members, topic_specs, strict=False):
        question.topic = Topic.objects.create(
            code=code, label=label, subject=subject, sort_order=order
        )
        question.save(update_fields=["topic"])
    response = signed.get("/stats/")
    group = next(g for g in response.context["topic_groups"] if g["subject"] == subject)
    assert [topic.code for topic, _ in group["topics"]] == ["a-first", "b-first", "z-last"]
    assert all(
        stats["answered"] == 0 and stats["rate"] == "—（未回答）" for _, stats in group["topics"]
    )
    text = response.content.decode()
    assert f'<details data-topic-subject="{subject}">' in text
    assert "<details open" not in text


def test_A13_A24_preview_updates_entire_aggregate(seeded, user, signed):
    items = list(start_session(user, {}, count=0).items.select_related("revision__question"))
    submit_answer(user, items[0].pk, "second")
    submit_answer(user, items[1].pk, "first")
    revised = items[1].revision.question
    revised.grading_version += 1
    revised.save(update_fields=["grading_version"])
    data = filter_data()
    data["subjects"] = [items[0].revision.question.exam_paper.subject]
    response = signed.get("/api/filters/stats/", data)
    assert response.status_code == 200
    html = response.json()["html"]
    assert "100.0%" in html
    assert "正解 1 / 回答済み 1 問" in html
    assert "学習進捗 1 / 対象 3 問" in html
    assert "改訂のため再学習：1 問" in html
    assert "data-topic-subject=" in html
    data["target"] = "unanswered"
    html = signed.get("/api/filters/stats/", data).json()["html"]
    assert "学習進捗 0 / 対象 2 問" in html
    assert "100.0%" not in html


def test_A15_no_js_get_and_post_and_count_cap(seeded, signed):
    data = filter_data()
    data["count"] = "0"
    response = signed.get("/", data)
    assert response.context["count"] == 6
    data["count"] = "10"
    assert signed.get("/api/filters/home/", data).json()["count"] == 6
    assert signed.post("/", data).status_code == 302
    assert StudySession.objects.get().items.count() == 6

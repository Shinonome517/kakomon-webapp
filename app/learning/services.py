import random
import time

from django.db import OperationalError, transaction
from django.db.models import Exists, OuterRef, Subquery
from django.http import Http404
from django.utils import timezone
from questions.models import Question

from .models import AnswerAttempt, Bookmark, StudyItem, StudySession


class StudyError(Exception):
    def __init__(self, message, status=400, answer=None):
        self.status, self.answer = status, answer
        super().__init__(message)


def question_set(user, filters=None):
    latest = AnswerAttempt.objects.filter(
        user=user, question=OuterRef("pk"), grading_version=OuterRef("grading_version")
    ).order_by("-id")
    qs = (
        Question.objects.filter(status="verified")
        .select_related("exam_paper", "topic", "current_revision")
        .annotate(
            latest_correct=Subquery(latest.values("is_correct")[:1]),
            bookmarked=Exists(Bookmark.objects.filter(user=user, question=OuterRef("pk"))),
            has_history=Exists(AnswerAttempt.objects.filter(user=user, question=OuterRef("pk"))),
        )
    )
    filters = filters or {}
    for key, field in [
        ("subjects", "exam_paper__subject"),
        ("papers", "exam_paper__code"),
        ("topics", "topic__code"),
    ]:
        if filters.get(key):
            qs = qs.filter(**{field + "__in": filters[key]})
    target = filters.get("target", "all")
    if target == "incorrect":
        qs = qs.filter(latest_correct=False)
    elif target == "unanswered":
        qs = qs.filter(latest_correct__isnull=True)
    elif target == "bookmarked":
        qs = qs.filter(bookmarked=True)
    return qs


def statistics(questions):
    questions = list(questions)
    answered = sum(q.latest_correct is not None for q in questions)
    correct = sum(q.latest_correct is True for q in questions)
    return {
        "total": len(questions),
        "answered": answered,
        "correct": correct,
        "rate": f"{100 * correct / answered:.1f}%" if answered else "—（未回答）",
    }


def start_session(user, filters, ordering="ordered", count=10):
    with transaction.atomic():
        questions = list(question_set(user, filters))
        if not questions:
            raise StudyError("条件に合う問題がありません。")
        if ordering == "random":
            random.SystemRandom().shuffle(questions)
        if count:
            questions = questions[:count]
        session = StudySession.objects.create(user=user, filters=filters, ordering=ordering)
        StudyItem.objects.bulk_create(
            [
                StudyItem(session=session, position=i + 1, revision=q.current_revision)
                for i, q in enumerate(questions)
            ]
        )
    return session


def owned_item(user, item_id):
    try:
        return StudyItem.objects.select_related("session", "revision__question__exam_paper").get(
            pk=item_id, session__user=user, revision__question__status="verified"
        )
    except (StudyItem.DoesNotExist, ValueError) as exc:
        raise Http404 from exc


def grade(revision, choice):
    if choice not in {c["choice_id"] for c in revision.choices}:
        raise StudyError("選択肢が不正です。")
    return choice == revision.correct_choice_id


def submit_answer(user, item_id, choice, *, is_unknown=False):
    for attempt in range(3):
        try:
            with transaction.atomic():
                item = owned_item(user, item_id)
                rev = item.revision
                if rev.grading_version != rev.question.grading_version:
                    raise StudyError(
                        "問題が改訂されました。出題設定から学習を始め直してください。", 409
                    )
                if is_unknown and choice:
                    raise StudyError("選択肢と「わからない」は同時に送信できません。")
                correct = False if is_unknown else grade(rev, choice)
                existing = AnswerAttempt.objects.filter(study_item=item).first()
                if existing:
                    if existing.selected_choice_id != choice or existing.is_unknown != is_unknown:
                        raise StudyError("この問題の回答は保存済みです。", 409, existing)
                    return existing
                answer = AnswerAttempt.objects.create(
                    user=user,
                    study_item=item,
                    question=rev.question,
                    revision=rev,
                    grading_version=rev.grading_version,
                    selected_choice_id=choice,
                    is_unknown=is_unknown,
                    is_correct=correct,
                )
                if not item.session.items.exclude(answer__isnull=False).exists():
                    StudySession.objects.filter(pk=item.session_id).update(
                        finished_at=timezone.now()
                    )
                return answer
        except OperationalError as exc:
            if "locked" not in str(exc).lower():
                raise
            if attempt == 2:
                raise StudyError(
                    "保存状況を確認できません。同じ回答を再送してください。", 503
                ) from exc
            time.sleep(0.05 * (attempt + 1))

from collections import defaultdict

from django.conf import settings
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.views.decorators.http import require_GET, require_POST
from questions.models import Question, RevisionAsset

from .forms import StudyForm
from .models import AnswerAttempt, Bookmark
from .services import StudyError, owned_item, question_set, start_session, statistics, submit_answer


def valid_form(request, *, for_stats=False):
    data = request.POST if request.method == "POST" else request.GET
    return StudyForm(data, for_stats=for_stats, select_all=request.method == "GET" and not data)


def filter_context(user, form, *, for_stats=False):
    context = {"form": form, "count": 0}
    if not form.is_valid():
        return context
    questions = question_set(user, form.cleaned_data)
    if not for_stats:
        context["count"] = questions.count()
        return context
    questions = list(questions)
    subjects, topics = defaultdict(list), defaultdict(list)
    for question in questions:
        subjects[question.exam_paper.subject].append(question)
        topics[question.topic_id].append(question)
    context.update(
        stats=statistics(questions),
        subjects=[(name, statistics(items)) for name, items in subjects.items()],
        topic_groups=[
            {
                "subject": name,
                "stats": statistics(items),
                "topics": [
                    (topic, statistics(topics[topic.pk]))
                    for topic in sorted(
                        {q.topic for q in items},
                        key=lambda topic: (topic.sort_order, topic.label, topic.pk),
                    )
                ],
            }
            for name, items in subjects.items()
        ],
        revised_count=sum(q.has_history and q.latest_correct is None for q in questions),
    )
    return context


def home(request):
    form = valid_form(request)
    context = filter_context(request.user, form)
    if request.method == "POST" and form.is_valid():
        try:
            session = start_session(
                request.user,
                form.cleaned_data,
                form.cleaned_data["ordering"],
                form.cleaned_data["count"],
            )
            return redirect("item", item_id=session.items.first().pk)
        except StudyError as exc:
            form.add_error(None, str(exc))
    return render(request, "home.html", context)


def item_context(item, user):
    answer = AnswerAttempt.objects.filter(study_item=item, user=user).first()
    return {
        "item": item,
        "revision": item.revision,
        "answer": answer,
        "next_item": item.session.items.filter(position__gt=item.position).first(),
        "previous_item": item.session.items.filter(position=item.position - 1).first(),
        "bookmarked": Bookmark.objects.filter(user=user, question=item.revision.question).exists(),
        "revised": item.revision.grading_version != item.revision.question.grading_version,
    }


@require_GET
def item(request, item_id):
    study_item = owned_item(request.user, item_id)
    return render(request, "item.html", item_context(study_item, request.user))


@require_POST
def answer(request, item_id):
    status, message = 200, ""
    try:
        if request.POST.get("unknown") not in (None, "1"):
            raise StudyError("回答の送信内容が不正です。")
        submit_answer(
            request.user,
            item_id,
            request.POST.get("choice", ""),
            is_unknown=request.POST.get("unknown") == "1",
        )
    except StudyError as exc:
        status, message = exc.status, str(exc)
    if request.headers.get("Accept") == "application/json":
        context = item_context(owned_item(request.user, item_id), request.user)
        return JsonResponse(
            {
                "error": message,
                "saved": context["answer"] is not None,
                "html": render_to_string("result.html", context, request=request)
                if context["answer"]
                else "",
            },
            status=status,
        )
    if status != 200:
        return render(
            request,
            "item.html",
            {**item_context(owned_item(request.user, item_id), request.user), "error": message},
            status=status,
        )
    return redirect("item", item_id=item_id)


@require_POST
def bookmark(request, item_id):
    study_item = owned_item(request.user, item_id)
    if request.POST.get("enabled") == "1":
        Bookmark.objects.get_or_create(user=request.user, question=study_item.revision.question)
    elif request.POST.get("enabled") == "0":
        Bookmark.objects.filter(user=request.user, question=study_item.revision.question).delete()
    else:
        return HttpResponse(status=400)
    return redirect("item", item_id=item_id)


@require_GET
def stats(request):
    form = valid_form(request, for_stats=True)
    context = filter_context(request.user, form, for_stats=True)
    return render(request, "stats.html", context, status=400 if form.errors else 200)


@require_GET
def filter_preview(request, kind):
    form = StudyForm(request.GET, for_stats=kind == "stats")
    context = filter_context(request.user, form, for_stats=kind == "stats")
    return JsonResponse(
        {
            "html": render_to_string(f"{kind}_preview.html", context, request=request),
            "valid": not bool(form.errors),
            "errors": form.errors,
            "count": context["count"],
        },
        status=400 if form.errors else 200,
    )


@require_GET
def history(request):
    answers = (
        AnswerAttempt.objects.filter(user=request.user)
        .select_related("question", "revision")
        .order_by("-id")[:100]
    )
    return render(request, "history.html", {"answers": answers})


@require_GET
def history_detail(request, answer_id):
    attempt = get_object_or_404(AnswerAttempt, pk=answer_id, user=request.user)
    # Withdrawn content is never rendered, even for past attempts.
    get_object_or_404(Question, pk=attempt.question_id, status="verified")
    return redirect("item", item_id=attempt.study_item_id)


@require_GET
def image(request, item_id, ref_id):
    study_item = owned_item(request.user, item_id)
    ref = get_object_or_404(
        RevisionAsset.objects.select_related("asset"), pk=ref_id, revision=study_item.revision
    )
    if study_item.revision.grading_version != study_item.revision.question.grading_version:
        raise Http404
    if (
        ref.usage == "explanation"
        and not AnswerAttempt.objects.filter(study_item=study_item, user=request.user).exists()
    ):
        raise Http404
    response = FileResponse(
        (settings.MEDIA_ROOT / ref.asset.storage_key).open("rb"), content_type=ref.asset.mime
    )
    response["Cache-Control"] = "private, no-store"
    return response

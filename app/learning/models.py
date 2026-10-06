import uuid

from django.conf import settings
from django.db import models


class StudySession(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    mode = models.CharField(max_length=20, default="practice")
    filters = models.JSONField(default=dict)
    ordering = models.CharField(max_length=20, default="ordered")
    created_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True)


class StudyItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(StudySession, on_delete=models.PROTECT, related_name="items")
    position = models.PositiveIntegerField()
    revision = models.ForeignKey("questions.QuestionRevision", on_delete=models.PROTECT)

    class Meta:
        ordering = ["position"]
        constraints = [
            models.UniqueConstraint(fields=["session", "position"], name="session_position")
        ]


class AnswerAttempt(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    study_item = models.OneToOneField(StudyItem, on_delete=models.PROTECT, related_name="answer")
    question = models.ForeignKey("questions.Question", on_delete=models.PROTECT)
    revision = models.ForeignKey("questions.QuestionRevision", on_delete=models.PROTECT)
    grading_version = models.PositiveIntegerField()
    selected_choice_id = models.CharField(max_length=80)
    is_unknown = models.BooleanField(default=False)
    is_correct = models.BooleanField()
    answered_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["user", "question", "grading_version", "id"])]


class Bookmark(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    question = models.ForeignKey("questions.Question", on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "question"], name="user_bookmark")]

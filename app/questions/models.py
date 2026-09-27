from django.db import models


class ExamPaper(models.Model):
    code = models.CharField(max_length=100, unique=True)
    qualification_code = models.CharField(max_length=40, default="rikutoku1")
    exam_year = models.PositiveIntegerField()
    session_code = models.CharField(max_length=60)
    session_label = models.CharField(max_length=100)
    subject = models.CharField(max_length=80)
    sort_key = models.CharField(max_length=40)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["qualification_code", "exam_year", "session_code", "subject"],
                name="paper_identity",
            )
        ]

    def __str__(self):
        return f"{self.exam_year} {self.session_label} / {self.subject}"


class Topic(models.Model):
    code = models.CharField(max_length=100, unique=True)
    subject = models.CharField(max_length=80)
    label = models.CharField(max_length=100)
    sort_order = models.IntegerField(default=0)


class Question(models.Model):
    stable_id = models.CharField(max_length=100, unique=True)
    exam_paper = models.ForeignKey(ExamPaper, on_delete=models.PROTECT)
    question_number = models.PositiveIntegerField()
    topic = models.ForeignKey(Topic, on_delete=models.PROTECT)
    status = models.CharField(
        max_length=12, choices=[(x, x) for x in ["draft", "verified", "withdrawn"]]
    )
    current_revision = models.ForeignKey(
        "QuestionRevision", null=True, on_delete=models.PROTECT, related_name="+"
    )
    grading_version = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["exam_paper__sort_key", "exam_paper__subject", "question_number", "id"]
        constraints = [
            models.UniqueConstraint(fields=["exam_paper", "question_number"], name="paper_number")
        ]


class QuestionRevision(models.Model):
    question = models.ForeignKey(Question, on_delete=models.PROTECT, related_name="revisions")
    revision_number = models.PositiveIntegerField()
    grading_version = models.PositiveIntegerField()
    question_type = models.CharField(max_length=30, default="single_choice")
    stem_blocks = models.JSONField()
    choices = models.JSONField()
    correct_choice_id = models.CharField(max_length=80)
    explanation_blocks = models.JSONField()
    metadata = models.JSONField(default=dict)
    checksum = models.CharField(max_length=64)
    grading_checksum = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["question", "revision_number"], name="question_revision"
            )
        ]


class Asset(models.Model):
    sha256 = models.CharField(max_length=64, unique=True)
    storage_key = models.CharField(max_length=80)
    mime = models.CharField(max_length=30)
    width = models.PositiveIntegerField()
    height = models.PositiveIntegerField()
    byte_size = models.PositiveIntegerField()


class RevisionAsset(models.Model):
    revision = models.ForeignKey(QuestionRevision, on_delete=models.PROTECT, related_name="assets")
    asset = models.ForeignKey(Asset, on_delete=models.PROTECT)
    local_asset_id = models.CharField(max_length=80)
    usage = models.CharField(max_length=12)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["revision", "local_asset_id", "usage"], name="revision_asset"
            )
        ]


class ImportBatch(models.Model):
    bundle_id = models.CharField(max_length=100)
    checksum = models.CharField(max_length=64, unique=True)
    result = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

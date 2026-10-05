from django import forms
from questions.models import ExamPaper, Topic


class StudyForm(forms.Form):
    subjects = forms.MultipleChoiceField(
        label="科目", required=False, widget=forms.CheckboxSelectMultiple
    )
    papers = forms.MultipleChoiceField(
        label="年度・実施回", required=False, widget=forms.CheckboxSelectMultiple
    )
    topics = forms.MultipleChoiceField(
        label="分野", required=False, widget=forms.CheckboxSelectMultiple
    )
    target = forms.ChoiceField(
        label="対象",
        choices=[
            ("all", "すべて"),
            ("incorrect", "最終不正解"),
            ("unanswered", "未回答"),
            ("bookmarked", "ブックマーク"),
        ],
        initial="all",
    )
    ordering = forms.ChoiceField(
        label="順序", choices=[("ordered", "元の問題順"), ("random", "ランダム")], initial="ordered"
    )
    count = forms.TypedChoiceField(
        label="件数",
        choices=[(10, "10問"), (20, "20問"), (50, "50問"), (0, "すべて")],
        coerce=int,
        initial=10,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        papers = (
            ExamPaper.objects.filter(question__status="verified")
            .distinct()
            .order_by("sort_key", "subject")
        )
        self.fields["subjects"].choices = [(s, s) for s in sorted({p.subject for p in papers})]
        self.fields["papers"].choices = [(p.code, str(p)) for p in papers]
        self.fields["topics"].choices = [
            (t.code, f"{t.subject} / {t.label}")
            for t in Topic.objects.filter(question__status="verified")
            .distinct()
            .order_by("sort_order", "code")
        ]

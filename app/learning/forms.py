from django import forms
from questions.models import ExamPaper, Topic


class StudyForm(forms.Form):
    subjects = forms.MultipleChoiceField(label="科目", widget=forms.CheckboxSelectMultiple)
    papers = forms.MultipleChoiceField(label="年度・実施回", widget=forms.CheckboxSelectMultiple)
    topics = forms.MultipleChoiceField(label="分野", widget=forms.CheckboxSelectMultiple)
    target = forms.ChoiceField(
        label="対象",
        choices=[
            ("all", "すべて"),
            ("incorrect", "最後に間違えた問題"),
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

    def __init__(self, data=None, *, for_stats=False, select_all=False, **kwargs):
        papers = list(
            ExamPaper.objects.filter(question__status="verified")
            .distinct()
            .order_by("sort_key", "subject")
        )
        choices = {
            "subjects": [(s, s) for s in sorted({p.subject for p in papers})],
            "papers": [(p.code, str(p)) for p in papers],
            "topics": [
                (t.code, f"{t.subject} / {t.label}")
                for t in Topic.objects.filter(question__status="verified")
                .distinct()
                .order_by("subject", "sort_order", "label", "pk")
            ],
        }
        if select_all:
            data = {
                **{name: [value for value, _ in options] for name, options in choices.items()},
                "target": "all",
                "ordering": "ordered",
                "count": "10",
            }
        super().__init__(data, **kwargs)
        self.has_questions = bool(papers)
        for name, options in choices.items():
            field = self.fields[name]
            field.choices = options
            field.required = bool(options)
            field.widget.attrs["aria-describedby"] = f"{self[name].auto_id}_error"
            field.error_messages["required"] = f"{field.label}を1つ以上選んでください。"
        if for_stats:
            del self.fields["ordering"]
            del self.fields["count"]

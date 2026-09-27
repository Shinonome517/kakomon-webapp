import json
from pathlib import Path

import pytest
from learning.models import AnswerAttempt, Bookmark
from learning.services import StudyError, question_set, start_session, statistics, submit_answer
from questions.importer import ImportFailure, import_bundle
from questions.models import Asset, ImportBatch, Question, QuestionRevision

pytestmark = pytest.mark.django_db


def change(bundle, edit):
    path = bundle / "manifest.json"
    data = json.loads(path.read_text())
    edit(data)
    path.write_text(json.dumps(data))


def test_A20_dry_run(bundle, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path / "nonexistent"
    result = import_bundle(bundle, dry_run=True)
    assert result["added"] == 6
    assert not settings.MEDIA_ROOT.exists()
    assert not Question.objects.exists() and not ImportBatch.objects.exists()


def test_A21_repeat_preserves_history(seeded, user):
    item = start_session(user, {}, count=1).items.first()
    submit_answer(user, item.pk, "first")
    Bookmark.objects.create(user=user, question=item.revision.question)
    result = import_bundle(seeded)
    assert result["unchanged"] == 6
    assert Question.objects.count() == QuestionRevision.objects.count() == 6
    assert Asset.objects.count() == 3
    assert ImportBatch.objects.count() == 1
    assert AnswerAttempt.objects.count() == Bookmark.objects.count() == 1


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d["questions"].append(d["questions"][0]),
        lambda d: d["questions"][0].update(question_type="multi_choice"),
        lambda d: d["questions"][0].update(correct_choice_id=["first", "second"]),
        lambda d: d["questions"][0].update(correct_choice_id="absent"),
        lambda d: d["questions"][0]["choices"].append(d["questions"][0]["choices"][0]),
        lambda d: d["questions"][0]["assets"][0].update(path="../outside.png"),
        lambda d: d["questions"][0]["assets"][0].update(path="/tmp/outside.png"),
        lambda d: d["questions"][0]["assets"][0].update(path="assets/missing.png"),
        lambda d: d["questions"][0]["stem_blocks"][0].update(text="<script>alert(1)</script>"),
        lambda d: d["questions"][0]["stem_blocks"][0].update(
            text="![image](https://example.com/a.png)"
        ),
        lambda d: d["questions"][0]["stem_blocks"][0].update(text="[click](javascript:alert(1))"),
        lambda d: d["questions"][0]["stem_blocks"].append(
            {"type": "image", "asset_id": "missing", "alt": "missing"}
        ),
    ],
)
def test_A18_A22_invalid_manifest(bundle, settings, tmp_path, mutate):
    settings.MEDIA_ROOT = tmp_path / "media"
    change(bundle, mutate)
    with pytest.raises(ImportFailure):
        import_bundle(bundle)
    assert not Question.objects.exists() and not Asset.objects.exists()
    assert not settings.MEDIA_ROOT.exists()


def test_A22_symlink_and_large_image(bundle, settings, tmp_path):
    from PIL import Image

    settings.MEDIA_ROOT = tmp_path / "media"
    path = bundle / "assets/figure-1.png"
    original = path.read_bytes()
    path.unlink()
    path.symlink_to(bundle / "assets/figure-2.png")
    with pytest.raises(ImportFailure):
        import_bundle(bundle)
    path.unlink()
    path.write_bytes(original)
    Image.new("1", (6000, 6000)).save(path)
    with pytest.raises(ImportFailure):
        import_bundle(bundle)
    path.write_bytes(b"<svg></svg>")
    with pytest.raises(ImportFailure):
        import_bundle(bundle)
    assert not Question.objects.exists()


def test_A18_invalid_math_becomes_draft(bundle, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path / "media"
    change(bundle, lambda d: d["questions"][0]["stem_blocks"][0].update(text=r"$\notacommand{x}$"))
    report = import_bundle(bundle)
    assert report["unpublished"] == 1
    assert Question.objects.get(stable_id="synthetic-01").status == "draft"


def test_A23_withdrawn_and_draft(seeded, user, signed):
    item = start_session(user, {}, count=1).items.first()
    submit_answer(user, item.pk, "second")
    ref = item.revision.assets.first()
    for status in ["withdrawn", "draft"]:
        change(seeded, lambda d: d["questions"][0].update(status=status))
        import_bundle(seeded)
        assert question_set(user).count() == 5
        assert statistics(question_set(user))["answered"] == 0
        assert signed.get(f"/study/{item.pk}/").status_code == 404
        assert signed.get(f"/image/{item.pk}/{ref.pk}/").status_code == 404
    assert AnswerAttempt.objects.count() == 1


def test_A24_revision_grading_and_bookmark(seeded, user):
    item = start_session(user, {}, count=1).items.first()
    submit_answer(user, item.pk, "second")
    Bookmark.objects.create(user=user, question=item.revision.question)
    change(
        seeded, lambda d: d["questions"][0]["explanation_blocks"][0].update(text="解説だけを訂正。")
    )
    import_bundle(seeded)
    q = Question.objects.get(pk=item.revision.question_id)
    assert q.grading_version == 1 and q.current_revision.revision_number == 2
    assert statistics(question_set(user))["rate"] == "100.0%"
    change(seeded, lambda d: d["questions"][0].update(correct_choice_id="first"))
    import_bundle(seeded)
    q.refresh_from_db()
    assert q.grading_version == 2
    assert statistics(question_set(user))["answered"] == 0
    with pytest.raises(StudyError) as error:
        submit_answer(user, item.pk, "second")
    assert error.value.status == 409
    assert AnswerAttempt.objects.count() == Bookmark.objects.count() == 1


def test_A24_grading_image_changes(seeded, user):
    from PIL import Image

    item = start_session(user, {}, count=1).items.first()
    submit_answer(user, item.pk, "second")
    Image.new("RGB", (100, 100), "black").save(seeded / "assets/figure-1.png")
    import_bundle(seeded)
    assert Question.objects.get(pk=item.revision.question_id).grading_version == 2


def test_A17_metadata_stripped(bundle, settings, tmp_path):
    from PIL import Image, PngImagePlugin

    settings.MEDIA_ROOT = tmp_path / "media"
    path = bundle / "assets/figure-1.png"
    with Image.open(path) as img:
        info = PngImagePlugin.PngInfo()
        info.add_text("secret", "must-be-removed")
        img.save(path, pnginfo=info)
    import_bundle(bundle)
    for file in Path(settings.MEDIA_ROOT).iterdir():
        with Image.open(file) as img:
            assert "secret" not in img.info


def test_A20_dry_run_detects_database_collisions(seeded):
    change(seeded, lambda d: d["questions"][0].update(stable_id="different-id"))
    for dry_run in [True, False]:
        with pytest.raises(ImportFailure):
            import_bundle(seeded, dry_run=dry_run)
    assert Question.objects.count() == 6


def test_A22_image_write_failure_can_retry(bundle, settings, tmp_path):
    from unittest.mock import patch

    settings.MEDIA_ROOT = tmp_path / "media"
    with (
        patch("questions.importer.os.fsync", side_effect=OSError("synthetic interruption")),
        pytest.raises(OSError),
    ):
        import_bundle(bundle)
    assert list(settings.MEDIA_ROOT.iterdir()) == []
    assert Question.objects.count() == 0
    assert import_bundle(bundle)["added"] == 6


def test_A20_existing_dry_run_preserves_all_state(seeded, user, settings):
    import hashlib

    item = start_session(user, {}, count=1).items.first()
    submit_answer(user, item.pk, "second")
    Bookmark.objects.create(user=user, question=item.revision.question)
    before = {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in settings.MEDIA_ROOT.iterdir()
    }
    change(seeded, lambda d: d["questions"][0].update(correct_choice_id="first"))
    report = import_bundle(seeded, dry_run=True)
    assert report["updated"] == 1
    assert QuestionRevision.objects.count() == 6
    assert ImportBatch.objects.count() == 1
    assert AnswerAttempt.objects.count() == Bookmark.objects.count() == 1
    assert statistics(question_set(user))["rate"] == "100.0%"
    assert before == {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in settings.MEDIA_ROOT.iterdir()
    }

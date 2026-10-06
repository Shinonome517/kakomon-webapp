import json
import shutil
from pathlib import Path

import pytest
from learning.services import start_session
from questions.importer import import_bundle

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("numbers_only", [None, False, True])
def test_choice_display_keeps_accessible_content_and_answer_ids(
    numbers_only, settings, tmp_path, signed, user
):
    bundle = tmp_path / "bundle"
    shutil.copytree(Path(__file__).parent / "fixtures/synthetic-choice-numbers", bundle)
    path = bundle / "manifest.json"
    data = json.loads(path.read_text())
    metadata = data["questions"][0]["metadata"]
    if numbers_only is None:
        metadata.pop("choice_numbers_only")
    else:
        metadata["choice_numbers_only"] = numbers_only
    path.write_text(json.dumps(data))
    settings.MEDIA_ROOT = tmp_path / "media"
    import_bundle(bundle)
    item = start_session(user, {}, count=1).items.first()
    response = signed.get(f"/study/{item.pk}/")
    assert response.status_code == 200
    html = response.content.decode()
    assert ('class="choice choice-numbers-only"' in html) is bool(numbers_only)
    assert ('<span class="sr-only">' in html) is bool(numbers_only)
    assert "Aは2、Bは3。" in html
    assert "Aは3、Bは2。" in html
    assert 'alt="合成の組合せ表。2番はAが3、Bが2。"' in html
    assert 'aria-hidden="true"' not in html
    assert 'name="choice" value="first"' in html
    assert 'name="choice" value="second"' in html
    assert "指定した組合せは1番です。" not in html
    result = signed.post(
        f"/api/answer/{item.pk}/", {"choice": "first"}, HTTP_ACCEPT="application/json"
    )
    assert result.status_code == 200
    item.refresh_from_db()
    assert item.answer.selected_choice_id == "first"
    assert item.answer.is_correct

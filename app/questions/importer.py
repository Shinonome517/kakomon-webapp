import hashlib
import io
import json
import os
import re
import subprocess
import tempfile
import warnings
from pathlib import Path

from django.conf import settings
from django.db import transaction
from jsonschema import Draft202012Validator
from PIL import Image

from .models import Asset, ExamPaper, ImportBatch, Question, QuestionRevision, RevisionAsset, Topic


class ImportFailure(ValueError):
    pass


def digest(data):
    return hashlib.sha256(data).hexdigest()


def canonical(data):
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def safe_path(root, relative):
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise ImportFailure("バンドル外のパスは使用できません")
    target = root
    for part in path.parts:
        target = target / part
        if target.is_symlink():
            raise ImportFailure("symlinkは使用できません")
    if not target.is_file() or not target.resolve().is_relative_to(root.resolve()):
        raise ImportFailure("ファイルが存在しないか、バンドル外です")
    return target


def read_image(path):
    if path.stat().st_size > 20 * 1024 * 1024:
        raise ImportFailure("画像は20MiB以下にしてください")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(path) as img:
                if (
                    img.format not in {"PNG", "JPEG", "WEBP"}
                    or img.width * img.height > 30_000_000
                    or getattr(img, "n_frames", 1) != 1
                ):
                    raise ImportFailure("画像形式・ピクセル数が不正です")
                img.load()
                clean = Image.new("RGBA" if "A" in img.getbands() else "RGB", img.size)
                clean.paste(img.convert(clean.mode))
                output = io.BytesIO()
                clean.save(output, format="PNG")
                data = output.getvalue()
                return data, img.width, img.height
    except (
        OSError,
        ValueError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ) as exc:
        raise ImportFailure("画像を安全に読み込めません") from exc


def unique(entries, key):
    values = [e[key] for e in entries]
    if len(values) != len(set(values)):
        raise ImportFailure(f"{key}が重複しています")
    return {e[key]: e for e in entries}


def prepare(bundle):
    root = Path(bundle)
    if root.is_symlink():
        raise ImportFailure("symlinkは使用できません")
    manifest = safe_path(root, "manifest.json")
    if manifest.stat().st_size > 20 * 1024 * 1024:
        raise ImportFailure("manifestが大きすぎます")

    def no_duplicate_keys(pairs):
        result = {}
        for k, v in pairs:
            if k in result:
                raise ImportFailure("JSONキーが重複しています")
            result[k] = v
        return result

    data = json.loads(manifest.read_text(), object_pairs_hook=no_duplicate_keys)
    schema = json.loads((settings.BASE_DIR / "schemas/question-bundle.schema.json").read_text())
    errors = list(Draft202012Validator(schema).iter_errors(data))
    if errors:
        raise ImportFailure(
            "JSON Schemaに一致しません: " + "/".join(map(str, errors[0].absolute_path))
        )
    papers, topics = unique(data["papers"], "code"), unique(data["topics"], "code")
    unique(data["questions"], "stable_id")
    positions = set()
    images = {}
    texts, text_questions = [], []
    for q in data["questions"]:
        if (
            q["exam_id"] not in papers
            or q["topic_id"] not in topics
            or papers[q["exam_id"]]["subject"] != topics[q["topic_id"]]["subject"]
        ):
            raise ImportFailure("試験・分野の参照が不正です")
        position = (q["exam_id"], q["number"])
        if position in positions:
            raise ImportFailure("問題番号が重複しています")
        positions.add(position)
        if q["correct_choice_id"] not in unique(q["choices"], "choice_id"):
            raise ImportFailure("唯一の正解IDが必要です")
        assets = unique(q["assets"], "asset_id")
        q["_assets"] = {}
        for aid, entry in assets.items():
            content, width, height = read_image(safe_path(root, entry["path"]))
            sha = digest(content)
            images[sha] = (content, width, height)
            q["_assets"][aid] = sha
        q["_usage"] = set()
        for usage, blocks in [
            ("stem", q["stem_blocks"]),
            ("explanation", q["explanation_blocks"]),
        ] + [("choice", c["blocks"]) for c in q["choices"]]:
            for block in blocks:
                if block["type"] == "image":
                    if block["asset_id"] not in assets:
                        raise ImportFailure("画像参照がありません")
                    q["_usage"].add((block["asset_id"], usage))
                else:
                    text = block["text"]
                    if re.search(
                        r"<\s*/?\s*[a-zA-Z!]|!\[|javascript\s*:|data\s*:|\\(?:href|url|includegraphics|html)\b",
                        text,
                        re.I,
                    ):
                        raise ImportFailure("生HTML・外部画像・危険なURLは使用できません")
                    texts.append(text)
                    text_questions.append(q)
        if q["status"] == "verified" and not q["metadata"]["reviewed"]:
            q["status"] = "draft"
    try:
        result = subprocess.run(
            ["node", str(settings.BASE_DIR / "scripts/validate_math.cjs")],
            input=json.dumps(texts),
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        )
        for q, invalid in zip(text_questions, json.loads(result.stdout), strict=True):
            if invalid:
                q["status"] = "draft"
    except (OSError, subprocess.SubprocessError) as exc:
        raise ImportFailure("数式検証にNode.jsとローカルKaTeXが必要です") from exc
    for q in data["questions"]:
        q["_checksum"] = digest(canonical({k: v for k, v in q.items() if k != "_usage"}))
        grading_assets = {
            aid: q["_assets"][aid] for aid, usage in q["_usage"] if usage != "explanation"
        }
        q["_grading"] = digest(
            canonical(
                [
                    q["question_type"],
                    q["stem_blocks"],
                    q["choices"],
                    q["correct_choice_id"],
                    grading_assets,
                ]
            )
        )
    return data, images


def import_bundle(bundle, dry_run=False):
    data, images = prepare(bundle)
    identities = set()
    for paper in data["papers"]:
        identity = {
            key: paper[key]
            for key in ["qualification_code", "exam_year", "session_code", "subject"]
        }
        value = tuple(identity.values())
        if (
            value in identities
            or ExamPaper.objects.filter(**identity).exclude(code=paper["code"]).exists()
        ):
            raise ImportFailure("試験の識別情報が重複しています")
        identities.add(value)
    for q in data["questions"]:
        if (
            Question.objects.filter(exam_paper__code=q["exam_id"], question_number=q["number"])
            .exclude(stable_id=q["stable_id"])
            .exists()
        ):
            raise ImportFailure("既存の問題番号と重複しています")
    report = {"added": 0, "updated": 0, "unchanged": 0, "unpublished": 0, "errors": 0}
    for q in data["questions"]:
        old = (
            Question.objects.filter(stable_id=q["stable_id"])
            .select_related("current_revision")
            .first()
        )
        report[
            "added"
            if old is None
            else "unchanged"
            if old.current_revision.checksum == q["_checksum"]
            else "updated"
        ] += 1
        report["unpublished"] += q["status"] != "verified"
    if dry_run:
        return report
    media = Path(settings.MEDIA_ROOT)
    media.mkdir(parents=True, exist_ok=True)
    for sha, (content, _, _) in images.items():
        target = media / (sha + ".png")
        if target.exists():
            if digest(target.read_bytes()) != sha:
                raise ImportFailure("既存画像のハッシュが一致しません")
        else:
            fd, temporary = tempfile.mkstemp(prefix=".import-", dir=media)
            try:
                with os.fdopen(fd, "wb") as handle:
                    handle.write(content)
                    handle.flush()
                    os.fsync(handle.fileno())
                # link is atomic and cannot overwrite a concurrently installed image.
                try:
                    os.link(temporary, target)
                except FileExistsError:
                    if digest(target.read_bytes()) != sha:
                        raise ImportFailure("既存画像のハッシュが一致しません") from None
            finally:
                Path(temporary).unlink(missing_ok=True)
    with transaction.atomic():
        papers = {
            p["code"]: ExamPaper.objects.update_or_create(
                code=p["code"], defaults={k: v for k, v in p.items() if k != "code"}
            )[0]
            for p in data["papers"]
        }
        topics = {
            t["code"]: Topic.objects.update_or_create(
                code=t["code"], defaults={k: v for k, v in t.items() if k != "code"}
            )[0]
            for t in data["topics"]
        }
        assets = {
            sha: Asset.objects.get_or_create(
                sha256=sha,
                defaults={
                    "storage_key": sha + ".png",
                    "mime": "image/png",
                    "width": w,
                    "height": h,
                    "byte_size": len(content),
                },
            )[0]
            for sha, (content, w, h) in images.items()
        }
        for q in data["questions"]:
            question, created = Question.objects.get_or_create(
                stable_id=q["stable_id"],
                defaults={
                    "exam_paper": papers[q["exam_id"]],
                    "question_number": q["number"],
                    "topic": topics[q["topic_id"]],
                    "status": q["status"],
                },
            )
            old = question.current_revision
            if old and old.checksum == q["_checksum"]:
                continue
            if old and old.grading_checksum != q["_grading"]:
                question.grading_version += 1
            revision = QuestionRevision.objects.create(
                question=question,
                revision_number=1 if created else old.revision_number + 1,
                grading_version=question.grading_version,
                question_type=q["question_type"],
                stem_blocks=q["stem_blocks"],
                choices=q["choices"],
                correct_choice_id=q["correct_choice_id"],
                explanation_blocks=q["explanation_blocks"],
                metadata=q["metadata"],
                checksum=q["_checksum"],
                grading_checksum=q["_grading"],
            )
            RevisionAsset.objects.bulk_create(
                [
                    RevisionAsset(
                        revision=revision,
                        asset=assets[q["_assets"][aid]],
                        local_asset_id=aid,
                        usage=usage,
                    )
                    for aid, usage in q["_usage"]
                ]
            )
            question.current_revision = revision
            question.exam_paper, question.topic = papers[q["exam_id"]], topics[q["topic_id"]]
            question.question_number, question.status = q["number"], q["status"]
            question.save()
        checksum = digest(
            canonical([q["_checksum"] for q in data["questions"]] + data["papers"] + data["topics"])
        )
        ImportBatch.objects.get_or_create(
            checksum=checksum, defaults={"bundle_id": data["bundle_id"], "result": report}
        )
    return report

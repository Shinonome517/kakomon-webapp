import hashlib
import json
import os
import shutil
import sqlite3
import tempfile
from pathlib import Path


def sha256(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def validate(directory):
    directory = Path(directory)
    manifest = json.loads((directory / "manifest.json").read_text())
    if manifest.get("format") != 1:
        raise ValueError("Unknown backup format")
    for name, expected in manifest["files"].items():
        file = directory / name
        if (
            Path(name).is_absolute()
            or ".." in Path(name).parts
            or file.is_symlink()
            or not file.resolve().is_relative_to(directory.resolve())
        ):
            raise ValueError("Unsafe backup path")
        if sha256(file) != expected:
            raise ValueError("Backup hash mismatch")
    if "db.sqlite3" not in manifest["files"]:
        raise ValueError("Database missing")
    with sqlite3.connect(f"file:{directory / 'db.sqlite3'}?mode=ro", uri=True) as db:
        if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("Database integrity failure")
        for key, sha in db.execute("SELECT storage_key, sha256 FROM questions_asset"):
            if manifest["files"].get("media/" + key) != sha:
                raise ValueError("Referenced image missing")
    return manifest


def export_snapshot(db_path, media_path, destination):
    destination = Path(destination)
    if destination.exists():
        raise ValueError("Destination must not exist")
    destination.parent.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix=".export-", dir=destination.parent))
    try:
        with (
            sqlite3.connect(f"file:{Path(db_path).resolve()}?mode=ro", uri=True) as source,
            sqlite3.connect(work / "db.sqlite3") as target,
        ):
            source.backup(target)
            if target.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ValueError("Database integrity failure")
            assets = target.execute("SELECT storage_key, sha256 FROM questions_asset").fetchall()
        (work / "media").mkdir()
        files = {"db.sqlite3": sha256(work / "db.sqlite3")}
        for key, expected in assets:
            if Path(key).name != key:
                raise ValueError("Unsafe storage key")
            source = Path(media_path) / key
            if source.is_symlink() or sha256(source) != expected:
                raise ValueError("Source image hash mismatch")
            shutil.copyfile(source, work / "media" / key)
            files["media/" + key] = expected
        (work / "manifest.json").write_text(
            json.dumps({"format": 1, "app_version": "0.1.0", "files": files}, indent=2) + "\n"
        )
        validate(work)
        os.rename(work, destination)
    finally:
        if work.exists():
            shutil.rmtree(work)
    return destination


def restore_snapshot(source, destination):
    source, destination = Path(source), Path(destination)
    manifest = validate(source)
    if destination.exists():
        raise ValueError("Restore destination must not exist; never overwrite a live database")
    destination.parent.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix=".restore-", dir=destination.parent))
    try:
        for name in manifest["files"]:
            target = work / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source / name, target)
        shutil.copyfile(source / "manifest.json", work / "manifest.json")
        validate(work)
        with sqlite3.connect(work / "db.sqlite3") as db:
            db.execute("DELETE FROM django_session")
        # The restored DB intentionally differs because all sessions were invalidated.
        (work / "manifest.json").unlink()
        os.rename(work, destination)
    finally:
        if work.exists():
            shutil.rmtree(work)
    return destination

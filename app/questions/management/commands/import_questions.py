import json

from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError

from questions.importer import ImportFailure, import_bundle


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("bundle")
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        try:
            result = import_bundle(options["bundle"], options["dry_run"])
        except (ImportFailure, OSError, ValueError, IntegrityError) as exc:
            raise CommandError(
                f"取り込み拒否（部分公開なし）: {type(exc).__name__}: {exc}"
            ) from exc
        self.stdout.write(json.dumps(result, ensure_ascii=False))

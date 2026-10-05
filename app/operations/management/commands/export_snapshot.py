from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from operations.backup import export_snapshot


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("destination")

    def handle(self, *args, **options):
        try:
            export_snapshot(
                settings.DATABASES["default"]["NAME"], settings.MEDIA_ROOT, options["destination"]
            )
        except (OSError, ValueError) as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write("整合性・画像ハッシュ検証済みのスナップショットを作成しました。")

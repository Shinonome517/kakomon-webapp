from django.core.management.base import BaseCommand, CommandError

from operations.backup import restore_snapshot


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("source")
        parser.add_argument("destination")

    def handle(self, *args, **options):
        try:
            restore_snapshot(options["source"], options["destination"])
        except (OSError, ValueError) as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write("隔離ディレクトリへ復元しました。既存セッションは無効です。")

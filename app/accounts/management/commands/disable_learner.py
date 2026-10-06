from django.core.management.base import BaseCommand, CommandError

from accounts.models import User


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("--username", required=True)

    def handle(self, *args, **options):
        if not User.objects.filter(username=User.normalize_username(options["username"])).update(
            is_active=False
        ):
            raise CommandError("利用者アカウントが見つかりません。")
        self.stdout.write("利用者アカウントを無効にしました。")

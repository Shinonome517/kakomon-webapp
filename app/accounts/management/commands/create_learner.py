from getpass import getpass

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from accounts.models import User


class Command(BaseCommand):
    help = "利用者を発行（パスワードは非表示の対話入力）"

    def add_arguments(self, parser):
        parser.add_argument("--username", required=True)

    def handle(self, *args, **options):
        user = User(username=User.normalize_username(options["username"]))
        try:
            user.full_clean(exclude=["password"])
            password = getpass("仮パスワード: ")
            if password != getpass("再入力: "):
                raise CommandError("パスワードが一致しません")
            validate_password(password, user)
            user.set_password(password)
            user.save()
        except ValidationError as exc:
            raise CommandError(" / ".join(exc.messages)) from exc
        self.stdout.write("利用者を発行しました。初回変更が必要です。")

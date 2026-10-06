from getpass import getpass

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from accounts.models import User


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("--username", required=True)

    def handle(self, *args, **options):
        try:
            user = User.objects.get(username=User.normalize_username(options["username"]))
            password = getpass("新しい仮パスワード: ")
            if password != getpass("再入力: "):
                raise CommandError("パスワードが一致しません。")
            validate_password(password, user)
            user.set_password(password)
            user.must_change_password = True
            user.save()
        except (User.DoesNotExist, ValidationError) as exc:
            raise CommandError("ユーザー名またはパスワードを確認してください。") from exc
        self.stdout.write("仮パスワードを再設定しました。既存セッションは失効します。")

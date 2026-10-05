from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator
from django.db import models


class User(AbstractUser):
    username = models.CharField(
        max_length=32,
        unique=True,
        validators=[
            RegexValidator(
                r"\A[a-z0-9_.-]{3,32}\Z", "ユーザー名は英小文字・数字・_ . - の3〜32文字です。"
            )
        ],
    )
    display_name = models.CharField(max_length=80, blank=True)
    must_change_password = models.BooleanField(default=True)
    REQUIRED_FIELDS = []

    @classmethod
    def normalize_username(cls, username):
        return super().normalize_username(username).strip().lower()

    def save(self, *args, **kwargs):
        self.username = self.normalize_username(self.username)
        self._meta.get_field("username").run_validators(self.username)
        super().save(*args, **kwargs)

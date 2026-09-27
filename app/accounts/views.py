from django import forms
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm
from django.contrib.auth.views import LoginView, PasswordChangeView
from django.urls import reverse_lazy

from .models import User


class LoginForm(AuthenticationForm):
    error_messages = {
        "invalid_login": "ユーザー名またはパスワードが違います。",
        "inactive": "ユーザー名またはパスワードが違います。",
    }

    def clean_username(self):
        return User.normalize_username(self.cleaned_data["username"])


class Login(LoginView):
    template_name = "login.html"
    authentication_form = LoginForm


class FreshPasswordForm(PasswordChangeForm):
    def clean_new_password1(self):
        password = self.cleaned_data["new_password1"]
        if self.user.check_password(password):
            raise forms.ValidationError("現在と異なるパスワードを設定してください。")
        return password


class Password(PasswordChangeView):
    template_name = "password.html"
    form_class = FreshPasswordForm
    success_url = reverse_lazy("home")

    def form_valid(self, form):
        response = super().form_valid(form)
        self.request.user.must_change_password = False
        self.request.user.save(update_fields=["must_change_password"])
        return response

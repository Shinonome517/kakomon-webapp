from django.http import JsonResponse
from django.shortcuts import redirect


class AccessMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        public = request.path in {"/login/", "/health/"} or request.path.startswith("/static/")
        api = request.path.startswith("/api/")
        if not public and not request.user.is_authenticated:
            response = (
                JsonResponse({"error": "ログインしてください。"}, status=401)
                if api
                else redirect("login")
            )
        elif (
            not public
            and request.user.must_change_password
            and request.path not in {"/password/", "/logout/"}
        ):
            response = (
                JsonResponse({"error": "パスワードを変更してください。"}, status=403)
                if api
                else redirect("password")
            )
        else:
            response = self.get_response(request)
        if not request.path.startswith("/static/"):
            response["Cache-Control"] = "private, no-store"
        response["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self'; font-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
        )
        response["Referrer-Policy"] = "same-origin"
        return response

from accounts.views import Login, Password
from django.contrib.auth.views import LogoutView
from django.http import JsonResponse
from django.urls import path
from learning import views

urlpatterns = [
    path("health/", lambda request: JsonResponse({"status": "ok"})),
    path("login/", Login.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("password/", Password.as_view(), name="password"),
    path("", views.home, name="home"),
    path("study/<uuid:item_id>/", views.item, name="item"),
    path("api/answer/<uuid:item_id>/", views.answer, name="answer"),
    path("bookmark/<uuid:item_id>/", views.bookmark, name="bookmark"),
    path("stats/", views.stats, name="stats"),
    path("api/filters/home/", views.filter_preview, {"kind": "home"}, name="home-preview"),
    path("api/filters/stats/", views.filter_preview, {"kind": "stats"}, name="stats-preview"),
    path("history/", views.history, name="history"),
    path("history/<int:answer_id>/", views.history_detail, name="history_detail"),
    path("image/<uuid:item_id>/<int:ref_id>/", views.image, name="image"),
]

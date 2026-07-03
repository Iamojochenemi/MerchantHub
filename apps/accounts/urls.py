"""URL configuration for the ``accounts`` app."""

from django.urls import path

from apps.accounts.views import CurrentUserView, LoginView, RegistrationView

app_name = "accounts"

urlpatterns = [
    path("register/", RegistrationView.as_view(), name="register"),
    path("login/", LoginView.as_view(), name="login"),
    path("me/", CurrentUserView.as_view(), name="me"),
]


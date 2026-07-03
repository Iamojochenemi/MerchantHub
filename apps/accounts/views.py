"""
API views for the ``accounts`` app.

Keeps views thin: validation is handled by serializers and business
logic is delegated to services.
"""

from rest_framework import generics, permissions, status
from rest_framework.request import Request
from rest_framework.response import Response

from apps.accounts.serializers import (
    CurrentUserSerializer,
    LoginSerializer,
    RegistrationSerializer,
)
from apps.accounts.services import LoginService


class RegistrationView(generics.GenericAPIView):
    """Handle new user registration.

    Accepts ``email``, ``password``, ``first_name``, ``last_name``,
    and optionally ``workspace_name``.  Delegates creation to
    ``RegistrationSerializer`` which in turn uses
    ``RegistrationService`` for the atomic multi-model transaction.

    On success returns ``HTTP 201`` with a confirmation message.
    No tokens are issued at this endpoint.
    """

    authentication_classes: list = []
    permission_classes = [permissions.AllowAny]
    serializer_class = RegistrationSerializer

    def post(self, request: Request, *args, **kwargs) -> Response:
        """Validate input, create user + workspace, return confirmation."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            {"message": "Registration successful."},
            status=status.HTTP_201_CREATED,
        )


class LoginView(generics.GenericAPIView):
    """Authenticate a user and return a JWT token pair.

    Accepts ``email`` and ``password``.  Delegates validation to
    ``LoginSerializer`` (which authenticates credentials) and
    token generation to ``LoginService``.

    On success returns ``HTTP 200`` with ``access`` and ``refresh``
    JWT tokens.
    """

    authentication_classes: list = []
    permission_classes = [permissions.AllowAny]
    serializer_class = LoginSerializer

    def post(self, request: Request, *args, **kwargs) -> Response:
        """Validate credentials and return JWT token pair."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        tokens = LoginService.login(user)
        return Response(tokens, status=status.HTTP_200_OK)


class CurrentUserView(generics.RetrieveAPIView):
    """Return the currently authenticated user's profile.

    No database lookup is performed — the user is taken directly from
    the request (``self.request.user``).  The response includes basic
    profile fields plus the user's owned workspace summary (``id``,
    ``name``, ``slug``) and their role within it.

    Requires a valid JWT access token in the ``Authorization`` header.
    """

    permission_classes = [permissions.IsAuthenticated]
    serializer_class = CurrentUserSerializer

    def get_object(self):
        """Return the authenticated user without querying the database."""
        return self.request.user

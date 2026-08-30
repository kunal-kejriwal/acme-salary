"""Session auth for the single HR account.

No user model of our own: the deploy-time superuser is the HR manager's
account, and Django's session machinery does the rest. That keeps this to
three endpoints with no schema of their own.
"""

from django.contrib.auth import authenticate, login, logout
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.serializers import LoginSerializer, UserSerializer

#: One message for every failure. Distinguishing "no such user" from "wrong
#: password" turns the login form into a user directory.
INVALID_CREDENTIALS = "Invalid username or password."


@method_decorator(ensure_csrf_cookie, name="dispatch")
class LoginView(APIView):
    """Exchange credentials for a session cookie.

    `authentication_classes` is empty on purpose: SessionAuthentication would
    enforce CSRF on this request, and there is no session to protect yet. The
    response carries a fresh CSRF cookie for the unsafe requests that follow.
    """

    authentication_classes = []
    permission_classes = [AllowAny]
    serializer_class = LoginSerializer

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # authenticate() also rejects inactive accounts.
        user = authenticate(request, **serializer.validated_data)
        if user is None:
            return Response(
                {"detail": INVALID_CREDENTIALS},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        login(request, user)
        return Response(UserSerializer(user).data)


class LogoutView(APIView):
    """End the session. Requires one, so a stale tab gets a clear 403."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


@method_decorator(ensure_csrf_cookie, name="dispatch")
class MeView(APIView):
    """Who am I? The SPA's bootstrap probe.

    Answers 401 rather than the 403 the rest of the API gives, because this is
    the one endpoint whose *job* is to report "not signed in" and the SPA
    routes on the answer. Everything else keeps DRF's session default, which
    is 403 because SessionAuthentication sends no WWW-Authenticate header.

    It also seeds the CSRF cookie the login form needs before anyone has
    signed in.
    """

    permission_classes = [AllowAny]

    def get(self, request):
        if not request.user.is_authenticated:
            return Response(
                {"detail": "Not authenticated."},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        return Response(UserSerializer(request.user).data)

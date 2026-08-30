"""Session auth for the single HR account.

No user model of our own: the deploy-time superuser is the HR manager's
account, and Django's auth stack does the rest.
"""

import datetime as dt
from decimal import Decimal

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from apps.employees.services import create_employee

LOGIN_URL = "/api/v1/auth/login/"
LOGOUT_URL = "/api/v1/auth/logout/"
ME_URL = "/api/v1/auth/me/"

PASSWORD = "not-a-real-password"


@pytest.fixture
def credentials(hr_user):
    return {"username": hr_user.get_username(), "password": PASSWORD}


class TestLogin:
    def test_valid_credentials_return_200(self, anonymous_client, credentials):
        response = anonymous_client.post(LOGIN_URL, credentials, format="json")
        assert response.status_code == status.HTTP_200_OK

    def test_returns_the_signed_in_user(self, anonymous_client, credentials):
        body = anonymous_client.post(LOGIN_URL, credentials, format="json").json()
        assert body["username"] == credentials["username"]

    def test_never_returns_the_password(self, anonymous_client, credentials):
        body = anonymous_client.post(LOGIN_URL, credentials, format="json").json()
        assert "password" not in body

    def test_establishes_a_session(self, anonymous_client, credentials):
        anonymous_client.post(LOGIN_URL, credentials, format="json")
        assert "sessionid" in anonymous_client.cookies

    def test_sets_a_csrf_cookie_for_later_unsafe_requests(
        self, anonymous_client, credentials
    ):
        """The SPA needs this to send X-CSRFToken on the next PATCH."""
        anonymous_client.post(LOGIN_URL, credentials, format="json")
        assert "csrftoken" in anonymous_client.cookies

    def test_wrong_password_is_rejected(self, anonymous_client, credentials):
        response = anonymous_client.post(
            LOGIN_URL, {**credentials, "password": "wrong"}, format="json"
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_unknown_user_is_rejected(self, anonymous_client, db):
        response = anonymous_client.post(
            LOGIN_URL, {"username": "nobody", "password": "x"}, format="json"
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_does_not_leak_whether_the_account_exists(
        self, anonymous_client, credentials
    ):
        """Same answer either way, or login becomes a user directory."""
        wrong_password = anonymous_client.post(
            LOGIN_URL, {**credentials, "password": "wrong"}, format="json"
        ).json()
        no_such_user = anonymous_client.post(
            LOGIN_URL, {"username": "nobody", "password": "wrong"}, format="json"
        ).json()
        assert wrong_password == no_such_user

    def test_failed_login_establishes_no_session(self, anonymous_client, credentials):
        anonymous_client.post(
            LOGIN_URL, {**credentials, "password": "wrong"}, format="json"
        )
        assert anonymous_client.get(ME_URL).status_code == (
            status.HTTP_401_UNAUTHORIZED
        )

    def test_missing_password_is_a_validation_error(self, anonymous_client, db):
        response = anonymous_client.post(
            LOGIN_URL, {"username": "someone"}, format="json"
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "password" in response.json()

    def test_missing_username_is_a_validation_error(self, anonymous_client, db):
        response = anonymous_client.post(
            LOGIN_URL, {"password": "x"}, format="json"
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "username" in response.json()

    def test_deactivated_account_cannot_sign_in(
        self, anonymous_client, hr_user, credentials
    ):
        hr_user.is_active = False
        hr_user.save()
        response = anonymous_client.post(LOGIN_URL, credentials, format="json")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestMe:
    def test_anonymous_gets_401(self, anonymous_client, db):
        """401, not 403: this is the SPA's "am I signed in?" probe, and the
        answer needs to be unambiguous enough to route on."""
        assert anonymous_client.get(ME_URL).status_code == (
            status.HTTP_401_UNAUTHORIZED
        )

    def test_signed_in_user_is_returned(self, anonymous_client, credentials):
        anonymous_client.post(LOGIN_URL, credentials, format="json")
        response = anonymous_client.get(ME_URL)
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["username"] == credentials["username"]

    def test_sets_a_csrf_cookie_when_anonymous(self, anonymous_client, db):
        """The login form needs a CSRF token before anyone has signed in."""
        anonymous_client.get(ME_URL)
        assert "csrftoken" in anonymous_client.cookies


class TestLogout:
    def test_returns_204(self, anonymous_client, credentials):
        anonymous_client.post(LOGIN_URL, credentials, format="json")
        assert anonymous_client.post(LOGOUT_URL).status_code == (
            status.HTTP_204_NO_CONTENT
        )

    def test_ends_the_session(self, anonymous_client, credentials):
        anonymous_client.post(LOGIN_URL, credentials, format="json")
        anonymous_client.post(LOGOUT_URL)
        assert anonymous_client.get(ME_URL).status_code == (
            status.HTTP_401_UNAUTHORIZED
        )

    def test_api_is_closed_again_after_logout(self, fx_rates, anonymous_client, credentials):
        anonymous_client.post(LOGIN_URL, credentials, format="json")
        anonymous_client.post(LOGOUT_URL)
        assert anonymous_client.get("/api/v1/employees/").status_code == (
            status.HTTP_403_FORBIDDEN
        )

    def test_anonymous_logout_is_refused(self, anonymous_client, db):
        assert anonymous_client.post(LOGOUT_URL).status_code == (
            status.HTTP_403_FORBIDDEN
        )


class TestSessionOpensTheRealApi:
    """End to end: the session issued by login actually gates the product."""

    def test_employees_are_closed_before_login(self, fx_rates, anonymous_client):
        assert anonymous_client.get("/api/v1/employees/").status_code == (
            status.HTTP_403_FORBIDDEN
        )

    def test_employees_are_open_after_login(
        self, fx_rates, anonymous_client, credentials
    ):
        # Built here rather than via the employees fixtures, which are scoped
        # to that app's test package.
        create_employee(
            employee_code="ACME-7001",
            first_name="Asha",
            last_name="Rao",
            department="Engineering",
            job_title="Senior Engineer",
            country="IN",
            joined_on=dt.date(2021, 4, 1),
            salary_amount=Decimal("2400000.00"),
            currency="INR",
        )
        anonymous_client.post(LOGIN_URL, credentials, format="json")
        response = anonymous_client.get("/api/v1/employees/")
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["count"] == 1

    def test_a_second_client_is_not_signed_in(self, fx_rates, credentials):
        """Sessions are per-client, not global state."""
        signed_in = APIClient()
        signed_in.post(LOGIN_URL, credentials, format="json")

        other = APIClient()
        assert other.get(ME_URL).status_code == status.HTTP_401_UNAUTHORIZED

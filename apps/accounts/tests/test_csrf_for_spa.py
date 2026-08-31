"""CSRF on writes, and why the SPA is served same-origin with the API.

Reproduces a production failure. The SPA was on vercel.app and the API on
railway.app. Django set the `csrftoken` cookie on the API's domain, and the
browser would send it back -- but JavaScript on the Vercel origin could not
*read* it, because `document.cookie` only exposes cookies belonging to the
current document's domain. The SPA could not build the `X-CSRFToken` header,
so every write was rejected.

It surfaced as "sign out is broken" only because login carries no
authenticator and therefore no CSRF enforcement. Everything else -- the
salary edit included -- was equally broken.

The fix was architectural rather than a patch to the cookie flags: Vercel
proxies /api to the API, so the browser only ever sees one origin. Cookies
are first-party again, readable by JS, and unaffected by third-party cookie
blocking. Handing the token back in the response body would have fixed the
header and left the session cookie itself at the mercy of incognito.

These tests cover the half that stays true regardless of origin: writes
require the header, and the token Django sets in the cookie is the one that
satisfies it. They use `enforce_csrf_checks=True`, without which the whole
mechanism is bypassed and none of them can fail.

Note that the test client is not a browser -- it can read its own cookie
jar. That is what makes these assertions about Django's contract rather
than about the browser behaviour that caused the incident.
"""

import datetime as dt
from decimal import Decimal

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from apps.employees.models import Employee
from apps.employees.services import create_employee

LOGIN_URL = "/api/v1/auth/login/"
LOGOUT_URL = "/api/v1/auth/logout/"
ME_URL = "/api/v1/auth/me/"

PASSWORD = "not-a-real-password"


@pytest.fixture
def credentials(hr_user):
    return {"username": hr_user.get_username(), "password": PASSWORD}


@pytest.fixture
def strict_client():
    """A client that actually enforces CSRF, as a browser does."""
    return APIClient(enforce_csrf_checks=True)


@pytest.fixture
def employee(fx_rates):
    return create_employee(
        employee_code="ACME-5001",
        first_name="Asha",
        last_name="Rao",
        department="Engineering",
        job_title="Senior Engineer",
        country="IN",
        joined_on=dt.date(2021, 4, 1),
        salary_amount=Decimal("2400000.00"),
        currency="INR",
    )


def sign_in(client, credentials) -> str:
    """Sign in and return the CSRF token from the cookie.

    Same-origin, this is exactly what the SPA reads out of document.cookie.
    """
    response = client.post(LOGIN_URL, credentials, format="json")
    assert response.status_code == status.HTTP_200_OK, response.data
    return client.cookies["csrftoken"].value


class TestLoginEstablishesTheToken:
    """Same-origin, the cookie is the SPA's source for the header."""

    def test_login_sets_a_csrf_cookie(self, strict_client, credentials):
        strict_client.post(LOGIN_URL, credentials, format="json")
        assert "csrftoken" in strict_client.cookies

    def test_the_cookie_carries_a_real_value(self, strict_client, credentials):
        token = sign_in(strict_client, credentials)
        assert len(token) >= 32

    def test_me_sets_a_csrf_cookie_before_anyone_signs_in(self, strict_client, db):
        """The login form needs a token, and /auth/me is the app's first call."""
        strict_client.get(ME_URL)
        assert "csrftoken" in strict_client.cookies

    def test_login_still_returns_the_user(self, strict_client, credentials):
        body = strict_client.post(LOGIN_URL, credentials, format="json").json()
        assert body["username"] == credentials["username"]

    def test_the_password_is_still_never_echoed(self, strict_client, credentials):
        body = strict_client.post(LOGIN_URL, credentials, format="json").json()
        assert "password" not in body


class TestWritesRequireTheHeader:
    """The half that was failing in production.

    Each of these asserts the request is refused *without* the header, which
    is what makes the paired success test meaningful rather than decorative.
    """

    def test_logout_is_refused_without_the_header(self, strict_client, credentials):
        sign_in(strict_client, credentials)
        response = strict_client.post(LOGOUT_URL)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_logout_succeeds_with_the_header(self, strict_client, credentials):
        token = sign_in(strict_client, credentials)
        response = strict_client.post(LOGOUT_URL, headers={"X-CSRFToken": token})
        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_salary_edit_is_refused_without_the_header(
        self, strict_client, credentials, employee
    ):
        """The demo moment, and it was broken too -- not just sign out."""
        sign_in(strict_client, credentials)
        response = strict_client.patch(
            f"/api/v1/employees/{employee.pk}/",
            {"salary_amount": "3000000.00"},
            format="json",
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_salary_edit_succeeds_with_the_header(
        self, strict_client, credentials, employee
    ):
        token = sign_in(strict_client, credentials)
        response = strict_client.patch(
            f"/api/v1/employees/{employee.pk}/",
            {"salary_amount": "3000000.00"},
            format="json",
            headers={"X-CSRFToken": token},
        )
        assert response.status_code == status.HTTP_200_OK

    def test_the_edit_actually_lands(self, strict_client, credentials, employee):
        token = sign_in(strict_client, credentials)
        strict_client.patch(
            f"/api/v1/employees/{employee.pk}/",
            {"salary_amount": "3000000.00"},
            format="json",
            headers={"X-CSRFToken": token},
        )
        employee.refresh_from_db()
        assert employee.salary_amount == Decimal("3000000.00")

    def test_the_audit_row_is_still_written(
        self, strict_client, credentials, employee
    ):
        token = sign_in(strict_client, credentials)
        strict_client.patch(
            f"/api/v1/employees/{employee.pk}/",
            {"salary_amount": "3000000.00"},
            format="json",
            headers={"X-CSRFToken": token},
        )
        assert employee.salary_changes.count() == 1

    def test_delete_is_refused_without_the_header(
        self, strict_client, credentials, employee
    ):
        sign_in(strict_client, credentials)
        response = strict_client.delete(f"/api/v1/employees/{employee.pk}/")
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert Employee.objects.count() == 1


class TestLoginRemainsReachable:
    """Login must not need a token, or there is no way to obtain one."""

    def test_login_works_with_no_csrf_header_at_all(self, strict_client, credentials):
        response = strict_client.post(LOGIN_URL, credentials, format="json")
        assert response.status_code == status.HTTP_200_OK

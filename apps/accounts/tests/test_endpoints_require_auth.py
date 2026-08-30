"""Every API route refuses anonymous callers.

The route list is walked out of the URLconf rather than typed here, so an
endpoint added in a later phase is covered by this sweep the moment it
registers -- with no edit to this file. That is the whole point: a hardcoded
list silently stops covering the thing it was written to protect.
"""

import re

import pytest
from django.urls import URLPattern, URLResolver, get_resolver

#: Stand-in values for path converters, so a route template becomes a URL that
#: actually resolves. Permission checks run before the object lookup, so these
#: never need to match a real row.
UUID_SAMPLE = "00000000-0000-4000-8000-000000000000"

CONVERTER_SAMPLES = {
    "uuid": UUID_SAMPLE,
    "int": "1",
    "slug": "sample",
    "str": "sample",
    "path": "sample",
}

#: DRF's SimpleRouter emits regex patterns, while path() emits route patterns,
#: so both spellings of a URL parameter have to be handled.
ROUTE_PARAM = re.compile(r"<([^>]+)>")
REGEX_GROUP = re.compile(r"\(\?P<(?P<name>\w+)>(?P<expr>[^)]*)\)")

API_PREFIX = "api/v1/"
#: The auth endpoints are the way in, so they cannot require being in.
EXCLUDED_PREFIX = "api/v1/auth/"


def _strip_anchors(fragment):
    """Remove a fragment's own regex anchors.

    Per fragment, not over the joined route: a global strip of "^" would eat
    the negation inside a character class like [^/.]+ and quietly corrupt the
    pattern.
    """
    if fragment.startswith("^"):
        fragment = fragment[1:]
    if fragment.endswith("$"):
        fragment = fragment[:-1]
    return fragment


def _walk(patterns, prefix=""):
    for entry in patterns:
        fragment = _strip_anchors(str(entry.pattern))
        if isinstance(entry, URLResolver):
            yield from _walk(entry.url_patterns, prefix + fragment)
        elif isinstance(entry, URLPattern):
            yield prefix + fragment


def _concretise(route):
    def from_converter(match):
        spec = match.group(1)
        converter = spec.split(":")[0] if ":" in spec else "str"
        return CONVERTER_SAMPLES.get(converter, "sample")

    def from_group(match):
        # A numeric group needs a number; everything else takes the UUID,
        # which satisfies the routers' default [^/.]+.
        return "1" if r"\d" in match.group("expr") else UUID_SAMPLE

    # Regex groups first. ROUTE_PARAM's <...> would otherwise match the <pk>
    # inside (?P<pk>...) and mangle the group before it can be replaced.
    route = REGEX_GROUP.sub(from_group, route)
    route = ROUTE_PARAM.sub(from_converter, route)
    return "/" + route


def api_routes():
    """Every registered /api/v1 route except the auth endpoints."""
    found = {
        route
        for route in _walk(get_resolver().url_patterns)
        if route.startswith(API_PREFIX) and not route.startswith(EXCLUDED_PREFIX)
    }
    return sorted(found)


class TestTheSweepIsNotVacuous:
    """A broken walker would make every sweep below pass by finding nothing."""

    def test_routes_were_discovered(self):
        assert len(api_routes()) >= 2

    def test_the_employee_list_is_among_them(self):
        assert any("employees" in route for route in api_routes())

    def test_a_detail_route_is_among_them(self):
        assert any("pk" in route for route in api_routes())

    def test_auth_endpoints_are_excluded(self):
        assert not [r for r in api_routes() if "auth/" in r]

    def test_converters_are_substituted_out(self):
        assert all(
            "<" not in _concretise(route) and "?P" not in _concretise(route)
            for route in api_routes()
        )


@pytest.mark.parametrize("route", api_routes())
def test_route_refuses_anonymous_callers(db, anonymous_client, route):
    """403, not 401.

    DRF's SessionAuthentication sends no WWW-Authenticate header, so DRF
    downgrades 401 to 403. /auth/me deliberately answers 401 instead, because
    it is the SPA's "am I signed in?" probe and 401 is the unambiguous answer
    there; the rest of the API keeps DRF's default rather than fighting it.
    """
    response = anonymous_client.get(_concretise(route))
    assert response.status_code == 403, (route, response.status_code)


@pytest.mark.parametrize("method", ["post", "put", "patch", "delete"])
def test_unsafe_methods_are_refused_too(db, anonymous_client, method):
    response = getattr(anonymous_client, method)("/api/v1/employees/")
    assert response.status_code == 403

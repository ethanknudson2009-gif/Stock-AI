"""Tests for the tunnel password gate helpers."""

from ui.auth import came_through_cloudflare, check_password


def test_cloudflare_header_detection_is_case_insensitive():
    assert came_through_cloudflare({"Cf-Ray": "abc"}) and came_through_cloudflare({"cf-ray": "abc"})
    assert not came_through_cloudflare({"Host": "localhost:8501"})


def test_password_check_is_exact_and_fails_closed():
    assert check_password("s3cret-pass", "s3cret-pass")
    assert not check_password("wrong", "s3cret-pass")
    assert not check_password("", "s3cret-pass")
    assert not check_password("anything", None) and not check_password("", "")   # unset password never matches

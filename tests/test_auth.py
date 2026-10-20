"""Tests for the tunnel password gate helpers."""

from ui import auth
from ui.auth import came_through_cloudflare, check_password, is_local_request, lockout_remaining


def test_cloudflare_header_detection_is_case_insensitive():
    assert came_through_cloudflare({"Cf-Ray": "abc"}) and came_through_cloudflare({"cf-ray": "abc"})
    assert not came_through_cloudflare({"Host": "localhost:8501"})


def test_password_check_is_exact_and_fails_closed():
    assert check_password("s3cret-pass", "s3cret-pass")
    assert not check_password("wrong", "s3cret-pass")
    assert not check_password("", "s3cret-pass")
    assert not check_password("anything", None) and not check_password("", "")   # unset password never matches


def test_only_direct_localhost_visits_skip_the_gate():
    assert is_local_request({"Host": "localhost:8501"}) and is_local_request({"host": "127.0.0.1:8501"})
    assert is_local_request({"Host": "[::1]:8501"})
    assert not is_local_request({"Host": "192.168.8.175:8501"})                       # another device on the Wi-Fi
    assert not is_local_request({"Host": "x.trycloudflare.com", "Cf-Ray": "1"})        # the tunnel
    assert not is_local_request({"Host": "localhost:8501", "Cf-Ray": "1"})             # spoofed Host behind Cloudflare
    assert not is_local_request({})                                                    # no Host header at all


def test_repeated_wrong_passwords_lock_everyone_out_for_a_while():
    auth._failures.clear()
    t0 = 1000.0
    assert lockout_remaining(t0) == 0
    auth._failures.extend([t0 + i for i in range(auth.MAX_FAILS)])
    assert lockout_remaining(t0 + 10) > 0                      # locked after 5 misses, even from a "new session"
    assert lockout_remaining(t0 + 10 + auth.LOCKOUT + 5) == 0   # and it expires
    auth._failures.clear()

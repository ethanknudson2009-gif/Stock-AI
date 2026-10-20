"""Password gate for visitors who arrive through the Cloudflare tunnel.

Only a request addressed to this machine itself (Host: localhost / 127.0.0.1) skips the gate. Anything else
-- the Cloudflare tunnel, or another device on the Wi-Fi reaching the Mac's IP -- must log in. (Streamlit is
also started bound to 127.0.0.1 so the LAN cannot reach it at all; the Host check is the second lock.)
If no APP_PASSWORD is configured, such requests are refused outright (fail closed).
"""

import hmac
import os
import time

import streamlit as st


def came_through_cloudflare(headers) -> bool:
    return any(k.lower() == "cf-ray" for k in headers.keys())


def is_local_request(headers) -> bool:
    """True only for a direct visit to localhost (no Cloudflare header, Host names this machine)."""
    if came_through_cloudflare(headers):
        return False
    host = next((v for k, v in headers.items() if k.lower() == "host"), "").strip().lower()
    name = host[1:host.index("]")] if host.startswith("[") and "]" in host else host.rsplit(":", 1)[0]
    return name in {"localhost", "127.0.0.1", "::1"}


MAX_FAILS, FAIL_WINDOW, LOCKOUT = 5, 600.0, 300.0
_failures: list[float] = []     # process-wide, so opening a fresh browser session doesn't reset the count


def lockout_remaining(now: float | None = None) -> float:
    """Seconds left on the global lockout (0 = not locked). Locks after MAX_FAILS misses within FAIL_WINDOW."""
    now = time.time() if now is None else now
    recent = [t for t in _failures if now - t < FAIL_WINDOW]
    _failures[:] = recent
    if len(recent) >= MAX_FAILS:
        return max(0.0, recent[-1] + LOCKOUT - now)
    return 0.0


def check_password(supplied: str, expected: str | None) -> bool:
    """Constant-time comparison; an unset or empty expected password never matches."""
    return bool(expected) and hmac.compare_digest(supplied.encode(), expected.encode())


def gate() -> None:
    """Call once near the top of app.py, after theme setup. Stops the script unless the visitor may proceed."""
    if is_local_request(st.context.headers):
        return
    expected = os.getenv("APP_PASSWORD")
    if not expected:
        st.error("This site is reachable from the internet but no APP_PASSWORD is set in .env, so it stays locked.")
        st.stop()
    ss = st.session_state
    if ss.get("authed"):
        return
    st.markdown("### Stock AI")
    st.caption("Private — enter the password to continue.")
    with st.form("login"):
        pw = st.text_input("Password", type="password", label_visibility="collapsed", placeholder="Password")
        ok = st.form_submit_button("Unlock", type="primary")
    if ok:
        wait = lockout_remaining()
        if wait > 0:
            st.error(f"Too many wrong passwords. Try again in {int(wait // 60) + 1} min.")
            st.stop()
        if check_password(pw, expected):
            ss["authed"] = True
            st.rerun()
        _failures.append(time.time())
        ss["fails"] = ss.get("fails", 0) + 1
        time.sleep(min(2 ** ss["fails"], 30) / 4)        # slow down guessing
        st.error("Wrong password.")
    st.stop()

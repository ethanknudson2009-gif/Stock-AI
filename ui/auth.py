"""Password gate for visitors who arrive through the Cloudflare tunnel.

Cloudflare adds a `Cf-Ray` header to every proxied request and a client cannot remove it, so its presence
means "came from the internet". Local visits (no header) skip the gate. If the request came through
Cloudflare and no APP_PASSWORD is configured, the app refuses to show anything (fail closed).
"""

import hmac
import os
import time

import streamlit as st


def came_through_cloudflare(headers) -> bool:
    return any(k.lower() == "cf-ray" for k in headers.keys())


def check_password(supplied: str, expected: str | None) -> bool:
    """Constant-time comparison; an unset or empty expected password never matches."""
    return bool(expected) and hmac.compare_digest(supplied.encode(), expected.encode())


def gate() -> None:
    """Call once near the top of app.py, after theme setup. Stops the script unless the visitor may proceed."""
    if not came_through_cloudflare(st.context.headers):
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
        if check_password(pw, expected):
            ss["authed"] = True
            st.rerun()
        ss["fails"] = ss.get("fails", 0) + 1
        time.sleep(min(2 ** ss["fails"], 30) / 4)        # slow down guessing
        st.error("Wrong password.")
    st.stop()

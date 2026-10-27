"""Thin client for TypeSafe's Jev (System One) API: send some text, get typed answers back with probabilities."""

import os
import time

import requests

URL = "https://api.typesafe.ai/v1/systemone"
MODEL = "jev-latest"

# What we ask about each stock that is about to report. Typed answers only -- the model can't invent an option.
QUESTIONS = {
    "beat": {"type": "noul",
             "instructions": "The company is likely to beat analyst earnings expectations this quarter, judging by the news and estimates."},
    "reaction": {"type": "choice",
                 "instructions": "How the stock is likely to move the first trading day after it reports.",
                 "criteria": {"up": "The stock rises meaningfully (about 2% or more).",
                              "flat": "The stock moves little (within about 2%).",
                              "down": "The stock falls meaningfully (about 2% or more)."}},
}


class JevError(RuntimeError):
    pass


def ask(state: str, questions: dict | None = None, retries: int = 3, timeout: int = 30) -> dict:
    """POST one state plus typed questions; returns the `answers` dict. Retries on network errors and 5xx/429."""
    key = os.environ.get("TYPESAFE_API_KEY")
    if not key:
        raise JevError("TYPESAFE_API_KEY is not set (add it to .env)")
    body = {"state": state, "model": MODEL, "questions": questions or QUESTIONS}
    last = None
    for attempt in range(retries):
        try:
            r = requests.post(URL, json=body, timeout=timeout,
                              headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
        except requests.RequestException as e:
            last = f"{type(e).__name__}"
        else:
            if r.status_code == 200:
                return r.json()["answers"]
            last = f"HTTP {r.status_code}"
            if r.status_code not in (429, 500, 502, 503, 504):
                raise JevError(f"Jev rejected the request ({last})")     # bad key / bad format: retrying won't help
        time.sleep(2 ** attempt)
    raise JevError(f"Jev unreachable after {retries} tries ({last})")

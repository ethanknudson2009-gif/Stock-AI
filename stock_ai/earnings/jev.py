"""Thin client for TypeSafe's Jev (System One) API: send some text, get typed answers back with probabilities."""

import hashlib
import json
import os
import time
from pathlib import Path

import requests

URL = "https://api.typesafe.ai/v1/systemone"
CACHE = Path(__file__).resolve().parent.parent.parent / "logs" / "jev_cache.json"
CACHE_DAYS = 3
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


USAGE = {"calls": 0, "input_tokens": 0, "output_tokens": 0}   # running totals for this process, so the job can log its cost


class JevError(RuntimeError):
    pass


def _load_cache() -> dict:
    try:
        return json.loads(CACHE.read_text())
    except (OSError, ValueError):
        return {}


def _save_cache(cache: dict, key_hash: str, answers: dict) -> None:
    cutoff = time.time() - CACHE_DAYS * 86400
    fresh = {k: v for k, v in cache.items() if v.get("t", 0) >= cutoff}
    fresh[key_hash] = {"t": time.time(), "answers": answers}
    try:
        CACHE.parent.mkdir(exist_ok=True)
        tmp = CACHE.with_suffix(".tmp")
        tmp.write_text(json.dumps(fresh))
        tmp.replace(CACHE)                                  # atomic: a crash can't leave half a file
    except OSError:
        pass


def ask(state: str, questions: dict | None = None, retries: int = 3, timeout: int = 30) -> dict:
    """POST one state plus typed questions; returns the `answers` dict. Retries on network errors and 5xx/429."""
    key = os.environ.get("TYPESAFE_API_KEY")
    if not key:
        raise JevError("TYPESAFE_API_KEY is not set (add it to .env)")
    body = {"state": state, "model": MODEL, "questions": questions or QUESTIONS}
    key_hash = hashlib.sha1(json.dumps(body, sort_keys=True).encode()).hexdigest()
    cache = _load_cache()
    if key_hash in cache:                                   # identical question already answered: no new call, no new cost
        USAGE["cached"] = USAGE.get("cached", 0) + 1
        return cache[key_hash]["answers"]
    last = None
    for attempt in range(retries):
        try:
            r = requests.post(URL, json=body, timeout=timeout,
                              headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
        except requests.RequestException as e:
            last = f"{type(e).__name__}"
        else:
            if r.status_code == 200:
                body_json = r.json()
                u = body_json.get("usage", {})
                USAGE["calls"] += 1
                USAGE["input_tokens"] += u.get("input_tokens", 0)
                USAGE["output_tokens"] += u.get("output_tokens", 0)
                _save_cache(cache, key_hash, body_json["answers"])
                return body_json["answers"]
            last = f"HTTP {r.status_code}"
            if r.status_code not in (429, 500, 502, 503, 504):
                raise JevError(f"Jev rejected the request ({last})")     # bad key / bad format: retrying won't help
        time.sleep(2 ** attempt)
    raise JevError(f"Jev unreachable after {retries} tries ({last})")

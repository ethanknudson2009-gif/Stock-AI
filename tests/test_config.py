"""Tests for Settings redaction, environment loading, and the default universe."""

import re
from pathlib import Path

from stock_ai.config import DEFAULT_UNIVERSE, Settings, load_settings

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_settings_repr_redacted():
    secret = "sk-live-SUPERSECRET-abcd1234"
    s = Settings(alpaca_api_key=secret, alpaca_secret_key="xyz9876543")
    for text in (repr(s), str(s), s.redacted(), f"{s}"):
        assert "SUPERSECRET" not in text
        assert secret not in text
        assert "xyz98" not in text
        assert "****1234" in text
        assert "****6543" in text


def test_settings_unset_keys_show_none():
    assert "anthropic_api_key=None" in repr(Settings())


def test_load_settings_reads_env_and_treats_empty_as_unset():
    s = load_settings({"ALPACA_API_KEY": "key123456", "ALPACA_SECRET_KEY": ""})
    assert s.alpaca_api_key == "key123456"
    assert s.alpaca_secret_key is None
    assert s.typesafe_api_key is None


def test_load_dotenv_only_called_from_entry_points():
    callers = [
        p.relative_to(REPO_ROOT).as_posix()
        for p in REPO_ROOT.rglob("*.py")
        if ".venv" not in p.parts and "tests" not in p.parts
        and re.search(r"\bload_dotenv\(", p.read_text())
    ]
    assert set(callers) <= {"main.py", "app.py", "bot.py"}
    assert "main.py" in callers


def test_default_universe_is_20_to_50_unique_uppercase_tickers():
    assert 20 <= len(DEFAULT_UNIVERSE) <= 50
    assert len(set(DEFAULT_UNIVERSE)) == len(DEFAULT_UNIVERSE)
    assert all(t == t.upper() and t.isalpha() for t in DEFAULT_UNIVERSE)


def test_env_example_documents_every_settings_key():
    example = (REPO_ROOT / ".env.example").read_text()
    for key in ("ANTHROPIC_API_KEY", "ALPACA_API_KEY", "ALPACA_SECRET_KEY", "TYPESAFE_API_KEY"):
        assert key in example


def test_settings_scrub_removes_secret_from_error_text():
    s = Settings(alpaca_api_key="PKREALKEY12345678")
    msg = s.scrub("401 Unauthorized for key PKREALKEY12345678 at /v2/orders")
    assert "PKREALKEY" not in msg
    assert "****5678" in msg


def test_streamlit_config_hides_error_details():
    config = (REPO_ROOT / ".streamlit" / "config.toml").read_text()
    assert re.search(r"showErrorDetails\s*=\s*(false|\"none\")", config)

"""Typed settings read from environment variables, with secrets redacted in repr.

python-dotenv is NOT invoked here — each entry point (main.py, app.py, bot.py)
calls it exactly once, then reads keys through `load_settings()`.
"""

import os
from dataclasses import dataclass, fields


def _redact(value: str | None) -> str:
    """Show only the last 4 characters of a secret, or 'None' if unset."""
    if not value:
        return "None"
    if len(value) <= 4:
        return "'****'"
    return f"'****{value[-4:]}'"


@dataclass(frozen=True)
class Settings:
    """API keys used by the toolkit. All optional until the phase that needs them."""

    anthropic_api_key: str | None = None
    alpaca_api_key: str | None = None
    alpaca_secret_key: str | None = None
    typesafe_api_key: str | None = None

    def redacted(self) -> str:
        """Safe-to-log representation: every value masked to its last 4 characters."""
        parts = ", ".join(f"{f.name}={_redact(getattr(self, f.name))}" for f in fields(self))
        return f"Settings({parts})"

    def __repr__(self) -> str:
        return self.redacted()

    __str__ = __repr__

    def scrub(self, text: str) -> str:
        """Replace any secret value that appears inside `text` with its redacted form."""
        for f in fields(self):
            value = getattr(self, f.name)
            if value:
                text = text.replace(value, _redact(value).strip("'"))
        return text


def load_settings(environ: dict[str, str] | None = None) -> Settings:
    """Build Settings from `environ` (defaults to os.environ). Empty strings count as unset."""
    env = os.environ if environ is None else environ
    return Settings(
        anthropic_api_key=env.get("ANTHROPIC_API_KEY") or None,
        alpaca_api_key=env.get("ALPACA_API_KEY") or None,
        alpaca_secret_key=env.get("ALPACA_SECRET_KEY") or None,
        typesafe_api_key=env.get("TYPESAFE_API_KEY") or None,
    )

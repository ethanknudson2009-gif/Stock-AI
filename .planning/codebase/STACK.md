# Technology Stack

**Analysis Date:** 2026-09-29

## Languages

**Primary:**
- Python 3.12 (3.12.7 per `.venv/pyvenv.cfg`) - Entire codebase (`main.py`, `stock_ai/`, `tests/`)

**Secondary:**
- None detected

## Runtime

**Environment:**
- CPython 3.12.7
- Virtual environment at `.venv/` (created via `python3 -m venv .venv`), excluded from git via `.gitignore`

**Package Manager:**
- pip
- Lockfile: missing (no `requirements.lock`, `Pipfile.lock`, or `poetry.lock` present) — `requirements.txt` uses loose `>=` version constraints only

## Frameworks

**Core:**
- None (no web framework) — this is a CLI/data-science toolkit, not a service
- `argparse` (stdlib) - CLI argument parsing and subcommand dispatch, see `main.py`

**Testing:**
- pytest (implied by `tests/` layout and `test_*.py` naming in `tests/test_indicators.py`) - not pinned in `requirements.txt`; ensure it's installed separately or added as a dev dependency

**Build/Dev:**
- None detected (no bundler, no `Makefile`, no `pyproject.toml`, no `setup.py`)

## Key Dependencies

**Critical:**
- `pandas>=2.2` - Core dataframe representation for price history, features, and backtest results throughout `stock_ai/`
- `numpy>=1.26` - Numerical operations backing pandas
- `yfinance>=0.2` - Sole market data source; wraps Yahoo Finance in `stock_ai/data/loader.py`
- `scikit-learn>=1.5` - `RandomForestClassifier` and `train_test_split` used in `stock_ai/models/classifier.py`

**Infrastructure:**
- `python-dotenv>=1.0` - Loads `.env` for optional API keys (declared as a dependency but not yet imported/used anywhere in `stock_ai/` — dead dependency today)
- `matplotlib>=3.9` - Declared for plotting but not currently imported anywhere in `stock_ai/` or `main.py` (unused today, likely intended for future backtest visualization)

## Configuration

**Environment:**
- `.env.example` documents two optional variables: `ALPACA_API_KEY`, `ALPACA_SECRET_KEY` (both commented out, "only needed if you swap yfinance for a paid data/broker API")
- `.env` is gitignored and not present in the repo; no code currently reads these variables (no `os.environ`/`dotenv.load_dotenv()` calls found in `stock_ai/` or `main.py`)

**Build:**
- No build config files present. Project runs directly via `python main.py <command>`.

## Platform Requirements

**Development:**
- Python 3.12+ toolchain
- `pip install -r requirements.txt` inside a virtualenv (see `README.md` Setup section)

**Production:**
- No deployment target defined — this is a local CLI script, not a deployed service. No Docker, CI, or hosting config present.

---

*Stack analysis: 2026-09-29*

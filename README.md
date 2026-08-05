# kalakal-agent

An auditable Dota 2 prediction-market agent for Jupiter, built with Gemini, Google ADK, and Google Cloud.

## Status

Slice 1 scaffold only: an installable, typed, empty Python package skeleton with
quality tooling. No application behavior exists yet.

## Prerequisites

- Python 3.10 or newer

## Local setup (Windows PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

## Quality checks

```powershell
python -m ruff check .
python -m ruff format --check .
python -m mypy src tests
python -m pytest
```

## Secrets

No wallet keys, seed phrases, or credentials of any kind belong in this
repository. `.env.example` carries placeholders only; real values stay outside
Git.

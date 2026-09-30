# Vantrilex Assistant OS — developer entry points (Windows-first: make via choco, cmd shell)
PY      = .venv/Scripts/python.exe
SETUPPY = py -3.12

.PHONY: help setup lint format test security docs-guard coverage gate run-core run-bridge

help:
	@echo Available targets:
	@echo   setup      - create .venv (Python 3.12) and install dependencies
	@echo   lint       - ruff check + ruff format --check
	@echo   format     - ruff format (write changes)
	@echo   test       - pytest
	@echo   security   - bandit scan over src/
	@echo   docs-guard - verify canonical documentation set is present
	@echo   coverage   - tiered branch coverage (98% per core module, 90% total)
	@echo   gate       - lint + test + security + docs-guard + coverage
	@echo   run-core   - run the VPS core (aiogram + orchestrator)
	@echo   run-bridge - run the Windows PC bridge daemon

setup:
	$(SETUPPY) -m venv .venv
	$(PY) -m pip install --upgrade pip
	$(PY) -m pip install -r requirements.txt -r requirements-dev.txt

lint:
	$(PY) -m ruff check .
	$(PY) -m ruff format --check .

format:
	$(PY) -m ruff format .

test:
	$(PY) -m pytest

security:
	$(PY) scripts/security_gate.py

docs-guard:
	$(PY) scripts/docs_guard.py

coverage:
	$(PY) scripts/check_tiered_coverage.py

gate: lint test security docs-guard coverage

run-core:
	$(PY) -m src.main

run-bridge:
	$(PY) -m bridge.daemon

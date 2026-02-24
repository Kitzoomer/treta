test:
	pytest

lint:
	ruff check .

format-check:
	black --check .

security:
	bandit -r .
	pip-audit || true

audit:
	python scripts/audit.py

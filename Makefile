.PHONY: install dev test lint clean setup

setup:
	python3 -m venv .venv
	.venv/bin/pip install --upgrade pip
	.venv/bin/pip install .
	@echo "✅ D-BUG installed! Run: source .venv/bin/activate && dbug --help"

install:
	pip install .

dev:
	uvicorn dbug.api.app:app --reload --port 8000

test:
	pytest tests/ -v --cov=dbug

lint:
	ruff check dbug/ tests/
	ruff format dbug/ tests/

clean:
	rm -rf __pycache__ .pytest_cache .mypy_cache .coverage htmlcov dist build *.egg-info chroma_db/ .dbug_cache.db

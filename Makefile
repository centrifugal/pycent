.PHONY: test lint lint-fix lint-ci mypy bench

dev:
	pip install poetry
	poetry install

test:
	poetry run pytest -vv tests

mypy:
	poetry run mypy cent tests benchmarks

lint:
	poetry run ruff .

lint-fix:
	poetry run ruff . --fix

lint-ci:
	poetry run ruff . --output-format=github

bench:
	poetry run pytest benchmarks --benchmark-verbose

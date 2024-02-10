.PHONY: proto test lint lint-fix lint-ci

dev:
	pip install poetry
	poetry install

proto:
	poetry run python -m grpc_tools.protoc -I . --python_betterproto_out=./cent/proto cent/proto/apiproto.proto

test:
	poetry run pytest -vv tests

lint:
	poetry run ruff .

lint-fix:
	poetry run ruff . --fix

lint-ci:
	poetry run ruff . --output-format=github

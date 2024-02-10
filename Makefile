.PHONY: proto test lint lint-fix lint-ci

dev:
	pip install poetry
	poetry install

proto:
	poetry run python -m grpc_tools.protoc -I . --python_betterproto_out=./cent/proto cent/proto/apiproto.proto

test:
	pytest -vv tests

lint:
	ruff .

lint-fix:
	ruff . --fix

lint-ci:
	ruff . --output-format=github

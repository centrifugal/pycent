PY ?= env/bin/python

# The Centrifugo release `make sync-proto` takes api.proto and proxy.proto
# from: a tag, such as v6.10.2. There is no default, so that nothing is synced
# from an unreleased branch by accident.
CENTRIFUGO_REF ?=

.PHONY: help
help: ## Show the targets
	@grep -E '^[a-z-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-18s %s\n", $$1, $$2}'

.PHONY: dev
dev: ## Install cent and its dev dependencies into the venv
	$(PY) -m pip install -e . --group dev

.PHONY: generate
generate: ## Regenerate cent/_api.py from proto/api.proto
	$(PY) gen/generate.py

.PHONY: generate-check
generate-check: ## Fail when the generated code is stale
	$(PY) gen/generate.py --check

.PHONY: lint
lint: ## ruff and mypy --strict
	$(PY) -m ruff check .
	$(PY) -m ruff format --check .
	$(PY) -m mypy

.PHONY: test
test: ## Unit tests
	$(PY) -m pytest -q

.PHONY: test-integration
test-integration: ## Integration tests, against the Centrifugo of testdata/ on :8100
	$(PY) -m pytest -q -m integration

.PHONY: check
check: generate-check lint test ## What CI runs, but integration

.PHONY: sync-proto
sync-proto: ## Copy api.proto and proxy.proto from Centrifugo at CENTRIFUGO_REF (a tag), and regenerate
	@if [ -z "$(CENTRIFUGO_REF)" ]; then echo "set CENTRIFUGO_REF to a Centrifugo tag, e.g. make sync-proto CENTRIFUGO_REF=v6.10.2"; exit 1; fi
	@base=https://raw.githubusercontent.com/centrifugal/centrifugo/$(CENTRIFUGO_REF)/internal; \
	curl -fsSL $$base/apiproto/api.proto -o proto/api.proto.new || { rm -f proto/api.proto.new; echo "no api.proto at Centrifugo $(CENTRIFUGO_REF)"; exit 1; }; \
	curl -fsSL $$base/proxyproto/proxy.proto -o proto/proxy.proto.new || { rm -f proto/*.new; echo "no proxy.proto at Centrifugo $(CENTRIFUGO_REF)"; exit 1; }; \
	grep -q '^service CentrifugoApi' proto/api.proto.new || { rm -f proto/*.new; echo "not Centrifugo's api.proto"; exit 1; }; \
	grep -q '^service CentrifugoProxy' proto/proxy.proto.new || { rm -f proto/*.new; echo "not Centrifugo's proxy.proto"; exit 1; }; \
	mv proto/api.proto.new proto/api.proto; mv proto/proxy.proto.new proto/proxy.proto
	$(MAKE) generate

.PHONY: help install test test-unit test-api test-one test-k

PYTHON ?= python3
PYTEST ?= $(PYTHON) -m pytest
RUNNER ?= bash scripts/run_mocked_external_api_tests.sh
CASE ?=
K ?=

help:
	@echo "可用命令:"
	@echo "  make install              安装依赖"
	@echo "  make test                 跑全量本地回归"
	@echo "  make test-unit            跑本地单元测试"
	@echo "  make test-api             跑全部接口测试"
	@echo "  make test-one CASE=...    按 -k 跑单条/单组接口测试"
	@echo "  make test-k K=...         按 -k 跑任意关键字筛选"

install:
	$(PYTHON) -m pip install -r requirements.txt

test:
	$(RUNNER) -q

test-unit:
	$(PYTEST) tests/test_mock_api_unit.py tests/test_external_public_apis_unit.py -q

test-api:
	$(PYTEST) tests/test_external_public_apis.py -q

test-one:
	@if [ -z "$(CASE)" ]; then echo "请传入 CASE，例如: make test-one CASE=API-061"; exit 1; fi
	$(PYTEST) tests/test_external_public_apis.py -q -k "$(CASE)"

test-k:
	@if [ -z "$(K)" ]; then echo "请传入 K，例如: make test-k K=DummyJSON"; exit 1; fi
	$(PYTEST) tests/test_external_public_apis.py -q -k "$(K)"

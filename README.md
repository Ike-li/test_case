# test_case
这是一个基于 `pytest` 的接口自动化测试样例仓库，当前已经切到“纯本地 mock 驱动”模式：

- 对外演示的接口来源覆盖 `httpbin`、`JSONPlaceholder`、`DummyJSON`
- 执行时默认不访问第三方公网
- 通过本地 FastAPI mock 服务稳定复现外部接口行为
- 支持数据驱动用例、前置 setup、鉴权链路、状态码/字段/结构/响应头/响应时间断言

## 安装依赖

```bash
python3 -m pip install -r requirements.txt
```

或者直接：

```bash
make install
```

## 运行说明

当前仓库的外部接口测试已经默认切到本地 mock 模式，不依赖第三方公网接口。

### 1. 跑纯单元测试

```bash
python3 -m pytest tests/test_mock_api_unit.py tests/test_external_public_apis_unit.py -q
make test-unit
```

### 2. 直接跑接口测试

直接用 `pytest` 跑 `external_api` 用例时，会自动：

- 启动本地 mock 服务
- 注入本地 `BASE_URL / JSONPLACEHOLDER_BASE_URL / DUMMYJSON_BASE_URL`
- 校验 mock 服务配置指纹，避免误复用旧配置实例
- 测试结束后关闭服务

示例：

```bash
python3 -m pytest tests/test_external_public_apis.py -q
make test-api
```

单条或按关键字筛选：

```bash
python3 -m pytest tests/test_external_public_apis.py -q -k API-061
python3 -m pytest tests/test_external_public_apis.py -q -k DummyJSON
python3 -m pytest tests/test_external_public_apis.py -q -k httpbin
make test-one CASE=API-061
make test-k K=DummyJSON
```

### 3. 使用脚本跑完整本地回归

脚本也会先启动本地 mock 服务，再执行测试，最后自动关闭：

```bash
bash scripts/run_mocked_external_api_tests.sh -q
make test
```

按关键字筛选：

```bash
bash scripts/run_mocked_external_api_tests.sh -q -k API-061
```

如果你显式传入了 `BASE_URL`、`JSONPLACEHOLDER_BASE_URL`、`DUMMYJSON_BASE_URL`、`DUMMYJSON_USERNAME`、`DUMMYJSON_PASSWORD`，脚本和裸 `pytest` 都会优先使用你的配置，而不是强制覆盖成默认值。

## 当前测试范围

当前本地 mock 已覆盖以下三类接口源对应的测试行为：

- `httpbin`
- `JSONPlaceholder`
- `DummyJSON`

总测试数当前为：

- `119` 条接口测试
- `25` 条本地单元测试
- 全量回归合计 `144` 条测试

## 仓库结构

```text
.
├── Makefile                         # 常用测试命令入口
├── scripts/
│   └── run_mocked_external_api_tests.sh
├── tests/
│   ├── conftest.py                  # pytest fixture 与本地 mock 生命周期管理
│   ├── data/
│   │   └── external_api_cases.py    # 用例数据、环境变量默认值、Body 模板
│   ├── mock_api/
│   │   └── app.py                   # 本地 FastAPI mock 服务
│   ├── utils/
│   │   ├── assertions.py            # 通用断言
│   │   └── http_client.py           # 请求执行器、模板解析、setup 状态提取
│   ├── test_external_public_apis.py
│   ├── test_external_public_apis_unit.py
│   └── test_mock_api_unit.py
├── pytest.ini
└── requirements.txt
```

## 备注

- 如果一次 pytest 会话里收集到了 `external_api` 用例，`tests/conftest.py` 会自动托管本地 mock 服务生命周期。
- 如果只跑普通单测，不会启动 mock 服务。
- 本地 mock 服务默认监听 `127.0.0.1:18080`。
- 如果端口上已经有同名 mock 服务，但配置指纹和当前 `DUMMYJSON_USERNAME / DUMMYJSON_PASSWORD` 不一致，测试会直接报错，避免跑到旧实例上。
- 当前已经覆盖一批负例，包括鉴权失败、状态码异常和资源不存在的 `404` 场景。
- 更详细的用例维护约定见 [CONTRIBUTING.md](/Users/henrylee/code/test_case/CONTRIBUTING.md:1)。

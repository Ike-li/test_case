# 用例维护说明

## 目标

这个仓库维护的是“外部接口自动化测试样例”，但执行时默认依赖本地 mock 服务，而不是第三方公网接口。

新增或修改用例时，优先保证：

- 用例可重复执行
- 断言具体，不做泛化检查
- mock 契约和用例数据保持一致
- `pytest` 裸跑模式和脚本模式行为一致

## 新增用例的基本要求

- 用例数据统一放在 [tests/data/external_api_cases.py](/Users/henrylee/code/test_case/tests/data/external_api_cases.py:1)
- 每条用例至少包含状态码断言和另一类有效断言
- 不要把默认响应时间断言当成主要覆盖
- 排序、筛选、分页、刷新 token 这类场景必须断言“语义结果”，不能只断言字段存在
- 负例尽量明确断言错误码和错误字段

## 修改 mock 时的要求

- mock 实现在 [tests/mock_api/app.py](/Users/henrylee/code/test_case/tests/mock_api/app.py:1)
- 如果新增了用例依赖的端点或字段，要同步补 mock
- 如果调整了 mock 返回结构，要同步更新数据用例和单测
- 对“资源不存在”这类场景，优先返回贴近真实接口语义的 `404`

## 回归命令

常用命令：

```bash
make test-unit
make test-api
make test
make test-one CASE=API-061
make test-k K=DummyJSON
```

不用 `make` 也可以直接执行：

```bash
python3 -m pytest tests/test_mock_api_unit.py tests/test_external_public_apis_unit.py -q
python3 -m pytest tests/test_external_public_apis.py -q
bash scripts/run_mocked_external_api_tests.sh -q
```

## 提交前建议

- 先跑 `make test-unit`
- 再跑 `make test`
- 如果只改了部分 provider，也至少补一次对应关键字筛选回归

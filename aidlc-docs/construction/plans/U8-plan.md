# U8 AgentCore Full Integration — Consolidated Plan

本 plan 把 U8 的 Functional Design / NFR Requirements / NFR Design / Infrastructure Design / Code Generation 合并成一个**跨阶段执行清单**，所有 AI-DLC 规范要求的子产物放在 `../U8-agentcore/<stage>/` 下。

## Plan Checklist

### Functional Design
- [x] `functional-design/agentcore-api-map.md` — 6 服务 API 映射（使用什么 SDK 方法、输入输出）
- [x] `functional-design/memory-namespace-model.md` — Memory event / namespace / strategy 设计
- [x] `functional-design/gateway-tool-schema.md` — 6 个 Gateway Target 的 JSON Schema

### NFR Requirements
- [x] `nfr-requirements/nfr.md` — 复用 U8 requirements-delta 中 NFR-U8-1..7，细化到指标/阈值

### NFR Design
- [x] `nfr-design/patterns.md` — 退避、熔断、token 缓存、OTEL fallback 模式

### Infrastructure Design
- [x] `infrastructure-design/infra.md` — CDK stack 重写清单、IAM、SSM、Lambda 布局

### Code Generation Plan
- [x] Phase A — Packages（`agentcore-runtime-client`、`agentcore-gateway-client`、`observability-adapter/otel_bootstrap.py`）
- [x] Phase B — Client 升级（`agentcore_memory.py`、`workload_identity.py`、`tier2_browser.py`）
- [x] Phase C — Gateway Lambdas（6 个 `lambdas/gateway-*`）
- [x] Phase D — CDK Stack 重写（`agentcore_stack.py`）
- [x] Phase E — MemoryFacade 架构简化 + worker main.py 注入 OTEL bootstrap
- [x] Phase F — 集成测试骨架（`tests/integration/test_agentcore_e2e.py`）

## 执行顺序
Phase A → B → C → D → E → F。每 Phase 完成后更新此 checkbox。

# 集成测试指令 — NovelGen

**日期**：2026-04-30
**范围**：跨 Unit / 跨服务集成测试

---

## 1. 测试矩阵

| Suite | 范围 | 主要 Unit |
|---|---|---|
| `tests/integration/test_u1_smoke.py` | 平台冒烟 | U1 |
| `tests/integration/test_u2_ingestion.py` | 上传 → DDB / S3 落盘 | U2 |
| `tests/integration/test_u3_analysis.py` | Analysis workflow + Memory 写入 | U3 |
| `tests/integration/test_u4_generation.py` | Outline + Chapter stream 契约 | U4 |
| `tests/integration/test_u5_critic.py` | CritiqueReport + ConflictItem 状态机 + GEN_SCAN# 串行 | U5 |
| `tests/integration/test_u7_admin.py` | Admin API RBAC + 乐观锁 + 缓存 | U7 |
| `tests/e2e/u6-smoke.spec.ts` | 用户 SPA 关键路径 + axe | U6 |
| `tests/e2e/u7-admin-smoke.spec.ts` | 管理 SPA 关键路径 + axe | U7 |

---

## 2. 运行 Python 集成测试（本地 moto）

```bash
uv pip install --system pytest pytest-asyncio "moto[all]"
export AWS_DEFAULT_REGION=us-east-1
pytest -q tests/integration
```

关键场景：
- **U5 Conflict 冻结状态机**（`test_u5_critic.py::test_conflict_rewrite_loop_freezes_on_third`）
- **U5 GEN_SCAN# 并发串行**（moto DDB + 条件更新）
- **U7 require_admin_role 403 / 200**
- **U7 model_config 409 乐观锁**
- **U7 Monitoring 分钟桶缓存命中**

---

## 3. 端到端（Playwright + axe-core）

```bash
# 前置：本地 dev 栈启动
# 终端 1：
pnpm --filter @novelgen/bff-user dev
# 终端 2：
pnpm --filter @novelgen/frontend-user dev
# 终端 3：
pnpm --filter @novelgen/frontend-admin dev
# 终端 4（api-service 暂可由 mock server 代替）：
cd services/api && uvicorn novelgen_api.main:app --reload

# 安装 Playwright 浏览器
pnpm exec playwright install chromium webkit

# 运行端到端测试
pnpm exec playwright test tests/e2e
```

配置文件：`tests/e2e/playwright.config.ts`（chromium + webkit 双浏览器矩阵）。

---

## 4. 契约测试（OpenAPI schema 校验）

```bash
# 1) 启动 services/api
uvicorn novelgen_api.main:app --reload

# 2) 对比本地生成的 OpenAPI 与 @novelgen/api-client 中记录的 schema
OPENAPI_URL=http://localhost:8000/openapi.json \
  pnpm -F @novelgen/api-client generate

git diff --exit-code packages/api-client-ts/src/generated/
```

在 CI 中：若 diff 非空且未提交 → CI 失败，强制后端变更必须同步生成前端类型。

---

## 5. 跨服务事件链路测试（推荐在 staging 环境手动执行）

`scripts/e2e-pipeline.sh`（建议增补，属 Build and Test 后续补充项）：

1. 调 `POST /api/v1/novels/upload` 上传样本 EPUB
2. 轮询 job → `SUCCEEDED`
3. 调 `POST /api/v1/novels/{id}/analyze` → 等待 analysis job 完成
4. 验证 Memory Facade `recall()` 返回 Fact 数量 > 0
5. 调 `POST /api/v1/generations` + `POST /outline` + `POST /approve-outline` + `POST /start`
6. 打开 SSE 订阅 `GET /generations/{gid}/chapters/1/stream`，验证 TTFT < 5s
7. 第 10 章完成后等待 `consistency.report_ready` 事件
8. 对同一 ConflictItem 触发 3 次重写，验证 frozen=true + 409 响应

此脚本建议在 staging 环境每日凌晨执行一次（GitHub Actions `workflow_dispatch`）。

---

## 6. 数据清理

每次集成测试跑完：
- moto 模拟资源随进程销毁
- 真实 staging 数据由 `scripts/cleanup-staging.sh` 按 `test_run_id` 前缀删除

---

## 7. 已知限制

- **AgentCore SDK 未 GA**：U3 的 AgentCore Memory / Runtime 在集成测试中以 adapter fake 为主；真实 staging 环境依赖 AWS bedrock-agentcore preview 访问
- **Bedrock 配额**：若 Opus Throttle 频繁，可降级到 Sonnet 或放宽 P95 门槛
- **Neptune Serverless 冷启动**：分析路径 P95 可能受首次 NCU 预热影响；集成测试首次运行允许放宽 30s

# 单元测试指令 — NovelGen

**日期**：2026-04-30
**范围**：每个 Unit 的模块级单元测试

---

## 1. Python 单元测试（pytest + pytest-asyncio + moto）

### 1.1 安装测试依赖
```bash
uv pip install --system pytest pytest-asyncio "moto[all]" freezegun respx
```

### 1.2 运行全部 Python 单元测试
```bash
pytest -q \
  packages/shared-types-py \
  packages/memory-facade \
  packages/storage-adapter \
  services/worker-ingestion \
  services/worker-analysis \
  services/worker-generation \
  services/worker-critic \
  services/worker-consistency
```

### 1.3 单独运行某个 service
```bash
pytest -q services/worker-critic
pytest -q services/worker-consistency -k "scan_cursor"
```

### 1.4 Python 测试覆盖的关键 suite

| 路径 | 关键用例 |
|---|---|
| `packages/shared-types-py/tests/test_critique.py` | 6 种 ConflictType 枚举 / CritiqueReport 往返 / score 范围 / extra=forbid / ConsistencyReport scan_to≥scan_from |
| `services/worker-critic/tests/test_context.py` | `pick_recent_summaries` 边界（current=2，count=5 → 仅 [1]） / `render_prompt` 替换所有占位符 |
| `services/worker-critic/tests/test_agent.py` | Tool Use 响应抽取 / Tool 未调用抛 `CriticAgentError` / `minimal_failure_report` 标记 minimal=True |
| `services/worker-critic/tests/test_metrics.py` | EMF payload shape + Score bucket 边界 |
| `services/worker-consistency/tests/test_scan_cursor.py` | moto DDB — 首次 advance 接受 / 乱序拒绝 / 单调推进 |
| `services/worker-consistency/tests/test_agent.py` | `_assemble` 保留 memory_unavailable 标志 / 6 种 ConflictType 枚举一致 |
| `services/worker-consistency/tests/test_context.py` | `render_prompt` 章节 idx 升序渲染 |

---

## 2. TypeScript 单元测试（Vitest）

### 2.1 运行全部
```bash
pnpm -r test
```

### 2.2 单独 app / package
```bash
pnpm --filter @novelgen/bff-user test
```

### 2.3 TypeScript 测试覆盖

| 路径 | 关键用例 |
|---|---|
| `apps/bff-user/tests/cookies.test.ts` | HS256 sign/verify 往返 / 篡改拒绝 / 空输入 / 不同 key 拒验证 |
| `apps/bff-user/tests/session-store.test.ts` | set/get/delete / LRU 淘汰 / updateAgeOnGet |
| `apps/bff-user/tests/csrf.test.ts` | 安全方法放行 / POST 无 token 返回 403 / 三方匹配 200 |
| `apps/bff-user/tests/emf.test.ts` | EMF payload shape + attrs 作为维度 |

---

## 3. CI 门槛建议

```yaml
# .github/workflows/ci.yml 片段
- name: Python unit tests
  run: |
    uv pip install --system pytest pytest-asyncio "moto[all]"
    pytest -q --maxfail=1 packages services

- name: TS unit tests
  run: pnpm -r test --coverage.enabled

- name: Lighthouse（仅 PR）
  run: pnpm -F @novelgen/frontend-user lhci
  continue-on-error: false
```

覆盖率目标（非强制，建议跟踪）：
- 关键 service（worker-critic / worker-consistency / BFF session）≥ 70% 行覆盖率
- 领域模型（shared-types-py/critique）≥ 90%

---

## 4. 本地开发循环

```bash
# 只跑当前修改的包
pytest -q services/worker-critic -x

# 监听模式
uv run ptw services/worker-critic -- -q

# TypeScript
pnpm --filter @novelgen/bff-user test --watch
```

---

## 5. 常见坑

| 症状 | 原因 / 处理 |
|---|---|
| `aioboto3 Session` 在 pytest 中卡住 | 启用 `pytest-asyncio` 的 `asyncio_mode=auto` |
| moto DDB 找不到表 | 确认使用 `@mock_aws` fixture，并在 fixture 内 `create_table` |
| Vitest jsdom 缺 `TextEncoder` | 在 `test-setup.ts` 中 polyfill，或在 vite.config 设 `environment: "jsdom"` |

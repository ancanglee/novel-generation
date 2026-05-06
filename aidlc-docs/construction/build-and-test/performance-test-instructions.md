# 性能测试指令 — NovelGen

**日期**：2026-04-30
**范围**：对齐 US-NFR-01/02 与每个 Unit NFR 的性能验证

---

## 1. NFR 指标清单（来自各 Unit NFR Requirements）

| 指标 | 目标 | 来源 |
|---|---|---|
| 100 万字端到端分析 P95 | < 15 分钟 | US-NFR-01 |
| 单章生成 P95 | < 60 秒 | US-NFR-02 |
| SSE TTFT P95 | < 3 秒（U4 后端）/ < 5 秒（U6 端到端上屏） | U4 NFR / U6 NFR-U6-1.4 |
| Critic 单章 P95 | < 60 秒 | NFR-U5-1 |
| Consistency 扫描 P95 | < 4 分钟 | NFR-U5-2 |
| Admin 列表 P95 | < 500 ms | NFR-U7-1.3 |
| CloudWatch 聚合 P95 | < 3 秒 | NFR-U7-1.4 |
| Lighthouse Mobile | ≥ 85 | NFR-U6-1.1 / NFR-U7-1.1 |
| 首屏 Bundle | ≤ 200 / 220 KB gzipped | NFR-U6-1.2 / NFR-U7-1.2 |

---

## 2. 工具

| 工具 | 用途 |
|---|---|
| Locust | HTTP API / SSE 并发 |
| k6 | 轻量脚本化压测（备选） |
| Lighthouse CI | 前端性能分 |
| `bundlesize` / 手工 `du -sh dist/assets/*.gz` | Bundle 预算校验 |
| CloudWatch Synthetics | 生产端监测 |

安装：
```bash
uv pip install --system locust
pnpm dlx @lhci/cli@0.14 autorun --version
```

---

## 3. 场景 A — Chapter 生成流式（US-NFR-02）

**脚本**：`perf/chapter_stream.py`

```python
from locust import HttpUser, task, between
import sseclient, json, time

class ChapterStreamUser(HttpUser):
    wait_time = between(2, 5)

    @task
    def stream_chapter(self):
        t0 = time.monotonic()
        # 前置：创建 generation + 批准 outline，这里使用已准备好的 gid
        gid = self.environment.parsed_options.gid
        with self.client.get(
            f"/api/v1/generations/{gid}/chapters/1/stream",
            stream=True, catch_response=True,
        ) as resp:
            first_byte = None
            client = sseclient.SSEClient(resp)
            for event in client.events():
                if event.event == "delta" and first_byte is None:
                    first_byte = time.monotonic() - t0
                    self.environment.events.request.fire(
                        request_type="SSE_TTFT",
                        name="ttft",
                        response_time=first_byte * 1000,
                        response_length=0,
                        exception=None,
                    )
                if event.event == "completed":
                    total = time.monotonic() - t0
                    self.environment.events.request.fire(
                        request_type="SSE_TOTAL",
                        name="chapter",
                        response_time=total * 1000,
                        response_length=0,
                        exception=None,
                    )
                    resp.success()
                    break
```

运行：
```bash
locust -f perf/chapter_stream.py --host=https://app.novelgen.staging \
       --users=30 --spawn-rate=3 --run-time=15m \
       --gid=$TEST_GEN_ID
```

门槛：
- TTFT P95 < 3000 ms（后端）；浏览器端（端到端）门槛 < 5000 ms
- 单章完成时间 P95 < 60s
- 错误率 < 1%

---

## 4. 场景 B — Consistency 扫描（NFR-U5-2）

```python
# perf/consistency_scan.py
from locust import HttpUser, task

class ConsistencyUser(HttpUser):
    @task
    def trigger_scan(self):
        # 假设已有 50 章 Generation；触发 scan_to=30 的事件
        gid = self.environment.parsed_options.gid
        self.client.post(
            f"/internal/consistency/force-trigger?gid={gid}&scan_to=30"
        )
```

门槛：扫描从入队到 `consistency.report_ready` 事件 P95 < 4 分钟（通过 CloudWatch 统计）。

---

## 5. 场景 C — Admin API 延迟（NFR-U7-1.3 / 1.4）

```python
# perf/admin_queries.py
class AdminUser(HttpUser):
    @task(weight=5)
    def list_users(self):
        self.client.get("/api/v1/admin/users?limit=50")

    @task(weight=3)
    def model_configs(self):
        self.client.get("/api/v1/admin/model-configs")

    @task(weight=1)
    def monitoring(self):
        self.client.get("/api/v1/admin/monitoring/summary?from=...&to=...")
```

门槛：
- `/admin/users` / `/model-configs` P95 < 500 ms
- `/monitoring/summary` 首次 P95 < 3000 ms；缓存命中 P95 < 100 ms

---

## 6. 场景 D — Lighthouse（两个 SPA）

```bash
# 用户端 SPA
pnpm --filter @novelgen/frontend-user build
pnpm dlx @lhci/cli autorun \
  --collect.url=http://localhost:4173 \
  --collect.numberOfRuns=3 \
  --assert.preset=lighthouse:recommended \
  --assert.assertions.categories:performance=">=0.85"

# 管理端 SPA（同样 ≥ 0.85）
```

---

## 7. 场景 E — Bundle 预算

```bash
pnpm --filter @novelgen/frontend-user build
# 检查 dist/assets 下每个 chunk 的 gzip 大小
find apps/frontend-user/dist/assets -name "*.js" -exec sh -c '
  size=$(gzip -c "$1" | wc -c)
  echo "$size  $(basename $1)"' _ {} \; | sort -rn

# 阈值：首屏 main / vendor 合计 ≤ 200 KB gzipped
# 次级 chunk 预算参见 NFR-U6-1.3
```

管理端 frontend-admin 采用类似校验（≤ 220 KB）。

---

## 8. 场景 F — 端到端 100 万字（US-NFR-01）

**前置**：准备 100 万字测试小说（建议 Project Gutenberg 英译版或自生成）。

步骤：
1. POST /novels/upload → 等待 `SUCCEEDED`
2. POST /novels/{id}/analyze → 观察 `analysis.completed` 事件时间戳差
3. 记录端到端耗时，目标 P95 < 15 分钟

运行 5 次取 P95。若首次超标，检查：
- Neptune NCU 是否已预热
- Opus/Sonnet Throttle 日志
- AgentCore Memory write 耗时

---

## 9. 报表

每次跑完：
- CloudWatch Dashboard `novelgen/{env}/perf` 保存一份快照
- Locust HTML 报告上传到 `s3://novelgen-perf-reports-{env}/{YYYYMMDD}/`
- 若触发任一 NFR 违规 → 在 GitHub Issues 打开 `perf:regression` 标签

---

## 10. 常见故障

| 症状 | 建议 |
|---|---|
| TTFT P95 抖动 | Neptune 冷启动 / Bedrock 区域拥塞；检查 `SseTtftMs` 按小时的分布 |
| Consistency 超标 | 10 章 S3 并发读取慢 → 调高 worker `asyncio.gather` 并发度 |
| Admin monitoring P95 > 3s | TTLCache 未命中；确认 CloudWatch `GetMetricData` 无 Throttle |
| Lighthouse < 85 | 检查是否误把 React Flow / ECharts 打入首屏 chunk |

# U2 Ingestion Service — 非功能需求（NFR Requirements）

**Unit**：U2 Ingestion Service
**阶段**：NFR Requirements
**日期**：2026-04-27
**Inheritance**: 继承 U1（region / 99.5% SLA / AWS managed 加密 / 无 API 限流 / token metric 告警 / 按需 serverless）

---

## 1. 性能

### NFR-1.1 采集延迟（U2-N1=B 宽松）
- 上传 + 解析 + 章节切分完成：**P95 < 2 分钟**
- URL 抓取（Tier 1）：P95 < 90 秒
- URL 抓取（Tier 2 Browser 降级）：P95 < 150 秒
- 搜索候选列表返回（跨 5 源）：P95 < 30 秒

### NFR-1.2 单文件解析超时（U2-N3=B）
- 单文件解析最大时长：**3 分钟**（允许大 PDF 的 OCR 分支）
- 超时则 Job → FAILED，error_code=`UPSTREAM_PARSE_TIMEOUT`

### NFR-1.3 Browser 会话超时
- Tier 2 AgentCore Browser 单会话 timeout = 60s
- 超时不降级，直接算该页面失败

---

## 2. 可靠性

### NFR-2.1 Tier 2 降级告警（U2-N2=A）
- Metric：`CrawlTierDowngraded{host}` / `SearchTierDowngraded{source}`
- Alarm：**降级率 > 30%（5 min 窗口）** → SNS `novelgen-admin-alerts`
- 解读：说明目标站反爬加剧或站点结构变化，需人工评估是否停用该源

### NFR-2.2 抓取失败回退
- Tier 1 失败 → Tier 2
- Tier 2 失败 → Job FAILED，UI 建议用户手动上传

### NFR-2.3 章节切分质量
- `LlmChapterSplitInvoked` 比例 < 20%（高于此值说明启发式规则需改进）
- 切分 confidence < 0.6 的 Novel 标记 warning，admin 可定期审阅

---

## 3. 缓存与存储

### NFR-3.1 抓取缓存（U2-N5=B）
- `teams/{team_id}/crawl-cache/sha256(url).html`
- **S3 Lifecycle：7 天过期**
- 命中缓存时直接使用，不走 Tier 1/2

### NFR-3.2 上传临时文件
- `teams/{team_id}/uploads/tmp/{uuid}` 上传完成后 24h 清理
- 若已成功转为 raw.md，临时文件立即删除

---

## 4. 安全与合规

### NFR-4.1 搜索关键词过滤（U2-N6=A）
- **不过滤**（用户自担责任）
- 但搜索引擎来源（Baidu/Bing）的下载仍强制 audit（R9.2）

### NFR-4.2 robots.txt 合规
- 硬性要求：robots.txt disallow 不允许通过 Browser 绕过
- User-Agent 固定 `NovelGenBot/0.1 (+https://novelgen.example.com/bot)`

### NFR-4.3 多租户继承 U1
- S3 key 前缀 + DynamoDB PK 前缀双层守卫（已在 storage-adapter 强制）

---

## 5. 可维护性

### NFR-5.1 第三方依赖策略（U2-N4=B）
- **`~=x.y` minor 自动升级**（example: `ebooklib~=0.18`）
- Dependabot 每周检查 major 版本
- 每月运行 `pip-audit` 扫描 CVE

### NFR-5.2 Parser 合同测试
- 每个 parser 配 ≥ 3 个样本文件（不同大小/编码/特殊字符）
- CI 中每次运行：小样本解析 + 章节切分 assertion

---

## 6. 可观测

### NFR-6.1 关键 metric（U2 扩展 U1 基础）
| Metric | 用途 |
|---|---|
| `IngestionDurationMs{format}` | 按原始格式 |
| `IngestionChapterCount{format}` | 切分质量 |
| `LlmChapterSplitInvoked` | 启发式失败率 |
| `RobotsTxtBlocked{host}` | 合规拒绝统计 |
| `SearchEngineDownloadRequested{source}` | Baidu/Bing 下载触发 |
| `CrawlTierDowngraded{host}` | URL 抓取降级 |
| `SearchTierDowngraded{source}` | 搜索源降级 |
| `BrowserSessionCount{source}` | Browser 使用（成本）|

### NFR-6.2 告警
| Alarm | 阈值 |
|---|---|
| `U2CrawlDowngradeRateHigh` | `CrawlTierDowngraded / (CrawlTier1 + Tier2) > 30%` (5 min) |
| `U2SearchDowngradeRateHigh` | 同上 |
| `U2BrowserOverused` | BrowserSessionCount > 100/h |
| `U2IngestionTimeout` | IngestionDurationMs P95 > 120000 ms (2 min) |

---

## 7. 成本

### NFR-7.1 预估附加成本
U2 在 U1 基础上的增量：
- AgentCore Browser：约 $0.05/session（估算），每日 100 次降级 ≈ $5/日 = $150/月
- trafilatura / httpx 本地计算：已包含在 ECS 费用
- 额外 S3 crawl-cache 7d 存储：可忽略（< $1/月）

### NFR-7.2 Browser 使用上限
- 软上限：`BrowserSessionCount / hour > 100` 触发告警
- 无硬限，依赖 admin 人工介入

---

## 8. 约束与假设

1. 所有依赖都在 Python 3.12 上可用
2. trafilatura 足以处理主流中文小说站的正文抽取
3. Baidu/Bing 的 HTML 结构短期内稳定（若变更可能触发大规模降级，此时 metric 会告警）
4. AgentCore Browser 的网络速度与公网相当

---

## 9. 继承 U1 的 NFR（不重复声明）

- 区域 us-east-1 / 99.5% SLA / 单 AZ 容忍
- AWS managed KMS 加密 / TLS 1.2+
- CloudWatch + AgentCore Observability（不引入 X-Ray / OTel）
- 手动部署（GitHub Actions 只跑 lint/test/build）
- 按需 serverless 为主（DynamoDB on-demand / OpenSearch Serverless / Fargate Spot 混合）
- 无 API 限流；token metric 告警作为成本护栏

# U6 Frontend + BFF — 业务规则（Business Rules）

**Unit**：U6 Frontend + BFF
**阶段**：Functional Design
**日期**：2026-04-28

---

## R1. 鉴权与会话

### R1.1 登录流程
- 用户点击 "登录" → 跳转 Cognito Hosted UI → 回调 `/auth/callback?code=...`
- BFF 在 `/auth/callback` 用 code 换 token → 写 httpOnly `sid` cookie（签名 + 24h 过期）
- SPA 首次加载时调 BFF `GET /auth/me`，若 401 → 重定向 Hosted UI

### R1.2 会话刷新
- BFF 在每个 `/api/*` 请求前检查 `expiresAt`：< 5 分钟时用 refreshToken 刷新；失败则清 cookie 并回 401
- 前端收到 401 → 清空 TanStack Query 缓存 → 跳转登录

### R1.3 非 admin 限定
- 本 Unit 面向 Role != admin 的用户。若 principal.role == admin，SPA 仍可用，但 **左侧导航增加 "Admin Console" 链接跳转到 U7**
- 所有 `/admin/*` 路由不在本 SPA 注册

---

## R2. 团队上下文

### R2.1 Team 切换
- 如用户属于多 Team，TopBar 提供 Team 选择器；选中后 `X-Team-Id` header 自动附在所有 BFF 请求上
- 切换 Team 时：`queryClient.clear()` 清空缓存，避免跨 Team 数据泄漏

### R2.2 权限显示
- `TeamRole == OWNER` 显示 "邀请成员" / "移除小说" 按钮
- `TeamRole == MEMBER` 这些按钮灰化 + 悬浮提示 "需 Owner 权限"

---

## R3. 采集（Ingestion, US-02-*）

### R3.1 文件上传
- 支持格式：TXT / EPUB / PDF / DOCX / MD（继承 U2）
- 前端大文件（>10MB）分片并发上传（BFF 代理 S3 multipart）—— 单片 5MB，最大并发 3
- 上传完成 → 轮询 `GET /jobs/{id}` 直到 `status=SUCCEEDED` → 自动刷新小说库列表

### R3.2 公版书搜索
- 搜索框防抖 400ms，至少 2 字符
- 搜索结果显示来源（Project Gutenberg / 中国哲学书电子化计划 等）
- 点击 "添加" → 触发 `POST /novels/search-and-download` → 跳转 Job 详情

### R3.3 URL 抓取
- 用户输入 URL + 可选指定章节范围
- 前端提示 "可能需 30~180 秒，可切走查看其它页面"

---

## R4. 分析查看（US-03-*）

### R4.1 未分析的小说
- 小说详情页显示 "开始分析" 按钮 → `POST /novels/{id}/analyze` → 跳转 Job 详情

### R4.2 分析中
- 进度条 + 预计剩余时间（按 100 万字 15 分钟外推）
- 子步骤可视化：粗读 → 分类 → 并行（人物/地图/风格）→ 细读 Map State

### R4.3 分析完成
- Tabs：**类型 / 人物 / 地图 / 风格 / 细读摘要**
- **人物图（F5=A React Flow）**：
  - Node = Character，label = name + role
  - Edge = Relation，label = 关系类型（亲属/主仆/对手...）
  - 双击 Node 打开 Character 详情抽屉（属性 + 章节出现频率）
- **风格雷达（F6=A ECharts radar）**：6 维度（tone/pace/detail_density/dialogue_ratio/emotion_intensity/scope）
- **地图（F6=A ECharts geo 自定义坐标系）**：虚构地点用自定义 coords，真实地点用 geo 自然映射

---

## R5. 生成配置（US-04-*, US-05-*）

### R5.1 模式选择
- 两种 Mode：`clean_room`（仿写）/ `continuation`（续写）
- 仿写需选 1-3 本参考小说 + 权重滑杆（合计 100%）
- 续写需选单本基础小说 + 起始章节

### R5.2 风格向量调节
- 6 维滑杆（0-100）+ 每维 "解释" 文本 input（admin 可校准，见 U7）
- "复制参考小说风格" 快捷按钮 → 读取 AnalysisReport.style_vector 预填

### R5.3 提交创建
- `POST /generations` → 返回 `{ generation_id, status: 'DRAFT' }` → 跳转大纲页

---

## R6. 大纲（US-05-*）

### R6.1 大纲生成
- 进大纲页若未生成 → 自动触发 `POST /generations/{gid}/outline` → 阻塞等待 Job 完成（P95 < 3 分钟，NFR-U4）
- 支持 "重新生成" 按钮（保留前版本用于回滚对比）

### R6.2 大纲审阅与编辑
- 按章列出 {chapter_idx, title, summary, key_beats}
- 每行可编辑（inline textarea），失焦自动保存到本地草稿（Zustand + localStorage）
- 右侧 "AI 建议" 面板显示 Outline Review Agent 输出
- 用户点 "批准并开始生成" → `POST /generations/{gid}/approve-outline` + `POST /generations/{gid}/start` → 跳转章节页

---

## R7. 章节生成与审阅（US-06-*）

### R7.1 流式渲染（F3=A）
- 进入章节页 → 建立 SSE 连接 `GET /generations/{gid}/chapters/{n}/stream`
- 收到 `event: delta, data: {text}` → `buffer += text` → requestAnimationFrame 批量渲染（避免掉帧）
- 光标元素 `<span class="cursor-blink"/>` 跟随 buffer 末尾
- TTFT 计时：首个 delta 到达时记 `firstByteAt`，用于 NFR 监控上报

### R7.2 SSE 重连（Last-Event-ID）
- EventSource 断线 → 自动重连，前端把 `lastEventId` 放 `Last-Event-ID` header（F2=A 透传后，ApiService 负责回放）
- 最多 5 次重试，指数退避 1s/2s/4s/8s/16s；耗尽 → phase='failed'，提示 "连接不稳定，请刷新"

### R7.3 Cancel
- 用户点 "取消" → `POST /generations/{gid}/chapters/{n}/cancel` → phase='cancelling'
- 收到 `event: cancelled` 或 `event: error` → phase='cancelled'；buffer 保留只读
- UI 持续 loading ≤ 8 秒（NFR-U4 cancel 响应）

### R7.4 章节完成后
- 收到 `event: completed` → phase='completed'
- 触发 TanStack Query `invalidate(qk.chapter(gid, n))` → 重新拉完整 ChapterDraftDto（含 markdown 格式化版）
- 下方自动拉取 `critique` 与 `consistency-reports` 并展示

### R7.5 ConflictItem 面板（F4=A）
- 右侧 `ConflictPanel` 组件始终可见（章节生成页默认展开，其它页默认收起）
- 每 ConflictItem 显示：
  - 类型 icon（6 种 ConflictType）
  - 章节引用（点击 → 滚动到章节 + 高亮段落）
  - Summary + Evidence 可展开
  - 两按钮：**Ignore**（立即 POST /ignore，乐观更新 UI 灰化）/ **Rewrite**（弹确认框 → POST /rewrite）
- `frozen=true` → 按钮灰化 + 悬浮提示 "已尝试 3 次，请手动编辑"
- Rewrite 成功 → 新章节进入生成流（phase reset to streaming）

---

## R8. 重写（US-06-04）

### R8.1 普通重写（无 Conflict 触发）
- 章节页 "重写本章" → Modal 输入 instruction → `POST /generations/{gid}/chapters/{n}/rewrite` → 新流式
- UI 提示 "本章已被重写 X 次（上限 5 次，U4 NFR）"

### R8.2 Conflict 驱动重写（与 R7.5 合并路径）
- 自动把 ConflictItem.summary 作为 instruction
- 成功后 Zustand `useChapterStreamStore.reset()` → 切换到新流

---

## R9. 导出（US-07-*）

### R9.1 触发导出
- 生成完成后章节列表页 "导出" 按钮 → `POST /generations/{gid}/export?format=epub|markdown|pdf|docx`
- 返回 Job ID → 轮询状态 → 完成后 BFF 生成 pre-signed S3 URL 提供下载

### R9.2 在线阅读
- 独立页面 `/read/:gid`，左侧目录 + 右侧章节 markdown 渲染
- 可切换主题（light/dark/sepia）、字号（14~22px）、行距
- 阅读位置 localStorage 记录

---

## R10. 错误呈现与可观测

### R10.1 全局错误边界
- `ErrorBoundary` 包裹根路由；捕获异常 → 显示友好 fallback + 重置按钮 + 上报 window.reportError

### R10.2 API 错误
- 4xx：toast + 保留上下文（如 409 Conflict Frozen → 提示文案 "多次尝试未解决，请手动编辑"）
- 5xx：toast "服务暂时不可用"；Sentry / CloudWatch RUM 上报

### R10.3 监控上报
- 关键指标：TTFT、流式 duration、Cancel latency、SSE 重连次数、Lighthouse 页面加载
- 通过 BFF `POST /telemetry` 上报 CloudWatch EMF（命名空间 `novelgen/frontend`）

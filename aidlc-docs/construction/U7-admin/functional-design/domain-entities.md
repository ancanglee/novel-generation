# U7 Admin — 领域实体（Domain Entities）

**Unit**：U7 Admin Frontend + API
**阶段**：Functional Design
**日期**：2026-04-30

---

## 0. 范围说明

U7 几乎不产生新的核心领域实体；它主要**读写已有配置实体**（users、teams、model_configs、audit_events、analysis_schemas、outline_templates）。本文聚焦管理端视角的 DTO 与 UI 状态。

**不在此 Unit 范围内（F6=C）**：`TeamBudget` / `CostGuardRule` 实体 —— 推迟到 V2 实现。

---

## 1. 后端 DTO（管理端 API 响应）

### 1.1 UserAdminDto
```ts
interface UserAdminDto {
  user_id: string;
  email: string;
  display_name: string;
  team_id: string;
  team_name: string;
  global_role: "regular_user" | "admin" | "content_moderator";
  team_role: "owner" | "member" | "moderator";
  status: "active" | "disabled";
  created_at: string;
  last_login_at?: string | null;
}
```

### 1.2 TeamAdminDto
```ts
interface TeamAdminDto {
  team_id: string;
  name: string;
  owner_user_id: string;
  status: "active" | "disabled";
  member_count: number;
  novels_count: number;
  generations_count: number;
  created_at: string;
}
```

### 1.3 ModelConfigDto（F3=A 9 个阶段独立）
```ts
type ModelStage =
  | "classification" | "character" | "map" | "style"
  | "outline" | "chapter" | "self_critique"
  | "critic" | "consistency";

interface ModelEntry {
  model_id: "claude-opus-4-7" | "claude-sonnet-4-6" | "claude-sonnet-4-7" | "claude-haiku-4-5";
  max_output_tokens: number;
  temperature: number;
  top_p?: number;
}

interface ModelConfigDto {
  stage: ModelStage;
  primary: ModelEntry;
  fallback?: ModelEntry;    // 可选，Throttle 后的降级模型
  updated_by: string;
  updated_at: string;
}
```

### 1.4 AnalysisSchemaDto（管理端维护的类型模板）
```ts
interface AnalysisSchemaDto {
  schema_id: string;
  name: string;              // 例：都市言情 / 历史小说 / 武侠
  version: number;
  fields: Array<{
    key: string;
    label: string;
    type: "text" | "number" | "enum" | "list";
    options?: string[];
    required: boolean;
  }>;
  updated_by: string;
  updated_at: string;
}
```

### 1.5 OutlineTemplateDto
```ts
interface OutlineTemplateDto {
  template_id: string;
  name: string;
  description: string;
  default_chapter_count: number;
  beats: Array<{ chapter_idx: number; summary: string; }>;
  updated_by: string;
  updated_at: string;
}
```

### 1.6 AuditEventDto
```ts
interface AuditEventDto {
  event_id: string;
  timestamp: string;
  actor_user_id: string;
  actor_email: string;
  action: string;            // 例：「admin.model_config.update」
  resource_type: string;
  resource_id: string;
  team_id: string;
  details: Record<string, unknown>;
}
```

### 1.7 MonitoringSummaryDto（F4=B 管理端 API 聚合）
```ts
interface MonitoringSummaryDto {
  period: { from: string; to: string; };
  totals: {
    novels_ingested: number;
    generations_started: number;
    generations_succeeded: number;
    generations_failed: number;
    chapters_generated: number;
  };
  latency: {
    ingestion_p95_ms: number;
    analysis_p95_ms: number;
    chapter_p95_ms: number;
    critic_p95_ms: number;
    consistency_p95_ms: number;
  };
  tokens: Array<{ stage: ModelStage; input: number; output: number; }>;
  sse_ttft_p95_ms: number;
  error_rate_percent: number;
}
```

### 1.8 AlertRuleDto（U1 已有 AlertRule 的 pydantic 模型）
```ts
interface AlertRuleDto {
  rule_id: string;
  metric: "TokenUsage" | "ChapterDurationP95" | "CriticFailureRate" | "SseTtftP95" | string;
  threshold: number;
  comparison: "gt" | "lt" | "gte" | "lte";
  window_minutes: number;
  severity: "warn" | "critical";
  enabled: boolean;
  updated_by: string;
  updated_at: string;
}
```

### 1.9 ConcurrencyConfigDto（AD6=F 管理端可配细读并发）
```ts
interface ConcurrencyConfigDto {
  deep_read_default: number;
  deep_read_max: number;
  chapter_parallel_max: number;
  updated_by: string;
  updated_at: string;
}
```

---

## 2. 管理端 SPA UI 状态（Zustand stores）

### 2.1 `useAdminSessionStore`
```ts
interface AdminSessionState {
  principal: Principal | null;  // 必须 globalRole == "admin"
  ready: boolean;
  setPrincipal(p: Principal | null): void;
  markReady(): void;
  isAdmin(): boolean;
}
```

### 2.2 `useConfigDraftStore`（模型配置 / 并发配置的「未保存草稿」）
```ts
interface ConfigDraftState {
  modelDrafts: Partial<Record<ModelStage, ModelConfigDto>>;
  concurrencyDraft: ConcurrencyConfigDto | null;
  setModelDraft(stage: ModelStage, cfg: ModelConfigDto): void;
  clearModelDraft(stage: ModelStage): void;
  setConcurrencyDraft(cfg: ConcurrencyConfigDto): void;
  clearAll(): void;
}
```

### 2.3 `useAuditFilterStore`
```ts
interface AuditFilterState {
  dateFrom: string | null;
  dateTo: string | null;
  teamId: string | null;
  userId: string | null;
  actionContains: string;
  page: number;
  set(patch: Partial<Omit<AuditFilterState, "set" | "reset">>): void;
  reset(): void;
}
```

### 2.4 `useMonitoringRangeStore`
```ts
type RangePreset = "1h" | "24h" | "7d" | "30d" | "custom";

interface MonitoringRangeState {
  preset: RangePreset;
  from: string;
  to: string;
  set(preset: RangePreset, from?: string, to?: string): void;
}
```

---

## 3. TanStack Query 的 Query Key 规范

```ts
export const adminQk = {
  users: (cursor?: string) => ["admin", "users", cursor ?? ""] as const,
  teams: () => ["admin", "teams"] as const,
  modelConfigs: () => ["admin", "model-configs"] as const,
  modelConfig: (stage: string) => ["admin", "model-configs", stage] as const,
  schemas: () => ["admin", "analysis-schemas"] as const,
  templates: () => ["admin", "outline-templates"] as const,
  auditEvents: (filter: string) => ["admin", "audit", filter] as const,
  monitoring: (range: string) => ["admin", "monitoring", range] as const,
  alertRules: () => ["admin", "alerts"] as const,
  concurrency: () => ["admin", "concurrency"] as const,
} as const;
```

---

## 4. 不在此 Unit 的实体（已剔除）

- **TeamBudget / CostGuardRule / BudgetBreachEvent**（F6=C，推迟到 V2 实现）
- Moderation queue UI（U5 F4=D 决策，审核员域未实现）

---

## 5. 与 U6 的复用

- `@novelgen/api-client::ApiClient` 复用（相同的 CSRF cookie 与 401 重定向行为）
- `@novelgen/ui::{Button, Dialog, Toast, Badge, Spinner}` + `ChapterReader`（只读）
- `@novelgen/types` DTO 类型直接引用；管理端专属 DTO 放在 `packages/shared-types-ts/src/admin.ts`

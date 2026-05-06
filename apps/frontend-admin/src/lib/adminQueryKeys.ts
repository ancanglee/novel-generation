export const adminQk = {
  me: () => ["admin", "me"] as const,
  users: (limit: number) => ["admin", "users", limit] as const,
  teams: () => ["admin", "teams"] as const,
  modelConfigs: () => ["admin", "model-configs"] as const,
  modelConfig: (stage: string) => ["admin", "model-configs", stage] as const,
  schemas: () => ["admin", "analysis-schemas"] as const,
  templates: () => ["admin", "outline-templates"] as const,
  audit: (filter: string) => ["admin", "audit", filter] as const,
  auditEvent: (id: string) => ["admin", "audit", "event", id] as const,
  monitoring: (from: string, to: string) => ["admin", "monitoring", from, to] as const,
  alerts: () => ["admin", "alerts"] as const,
  concurrency: () => ["admin", "concurrency"] as const,
} as const;

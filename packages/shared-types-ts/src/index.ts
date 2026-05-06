// Shared TypeScript types mirroring Python pydantic models in `novelgen-types`.

export type UUID = string;

export enum GlobalRole {
  Regular = "regular_user",
  Admin = "admin",
  Moderator = "content_moderator",
}

export enum TeamRole {
  Owner = "owner",
  Member = "member",
  Moderator = "moderator",
}

export interface User {
  user_id: UUID;
  email: string;
  display_name: string;
  team_id: UUID;
  global_role: GlobalRole;
  status: "active" | "disabled";
  created_at: string;
  last_login_at?: string | null;
}

export interface Team {
  team_id: UUID;
  name: string;
  owner_user_id: UUID;
  status: "active" | "disabled";
  created_at: string;
}

export interface Principal {
  user_id: UUID;
  team_id: UUID;
  email: string;
  global_role: GlobalRole;
  team_role: TeamRole;
  jwt_expiry: string;
  request_id: string;
}

export enum JobStatus {
  Queued = "QUEUED",
  Running = "RUNNING",
  Succeeded = "SUCCEEDED",
  Failed = "FAILED",
  Canceled = "CANCELED",
}

export enum JobType {
  Ingestion = "ingestion",
  Analysis = "analysis",
  Outline = "outline",
  Chapter = "chapter",
  Critic = "critic",
  Consistency = "consistency",
  Moderation = "moderation",
  Export = "export",
}

export interface TokenUsage {
  input_tokens: number;
  output_tokens: number;
  model: string;
}

export interface Job {
  job_id: UUID;
  team_id: UUID;
  owner_user_id: UUID;
  job_type: JobType;
  subject_id: UUID;
  status: JobStatus;
  progress: number;
  error_code?: string | null;
  error_message?: string | null;
  cancel_requested: boolean;
  step_functions_execution_arn?: string | null;
  payload: Record<string, unknown>;
  result_ref?: string | null;
  token_usage: TokenUsage;
  started_at?: string | null;
  ended_at?: string | null;
  created_at: string;
}

export enum ModelStage {
  Classification = "classification",
  Character = "character",
  Map = "map",
  Style = "style",
  Outline = "outline",
  Chapter = "chapter",
  SelfCritique = "self_critique",
  Critic = "critic",
  Consistency = "consistency",
}

export interface ApiError {
  error: {
    code: string;
    message: string;
    request_id: string;
  };
}

export * from "./critique";

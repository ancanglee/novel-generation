// U5 Critic & Consistency types — mirrors `novelgen_types.critique` in Python.

import type { UUID } from "./index";

export enum Severity {
  Info = "info",
  Warn = "warn",
  Error = "error",
}

export enum IssueDimension {
  Plot = "plot",
  Character = "character",
  Style = "style",
  Pacing = "pacing",
  Logic = "logic",
}

export enum ConflictType {
  CharacterState = "character_state",
  PlotHole = "plot_hole",
  Timeline = "timeline",
  Location = "location",
  Relation = "relation",
  Worldbuilding = "worldbuilding",
}

export enum ConflictUserAction {
  Open = "open",
  Ignored = "ignored",
  RewriteRequested = "rewrite_requested",
}

export interface Issue {
  severity: Severity;
  dimension: IssueDimension;
  message: string;
  evidence_excerpt?: string | null;
}

export interface CrossChapterConcern {
  chapter_refs: number[];
  message: string;
}

export interface CritiqueReport {
  generation_id: UUID;
  team_id: UUID;
  chapter_idx: number;
  model: string;
  score: number;
  layer1_confirmed: string[];
  layer1_overridden: string[];
  layer2_issues: Issue[];
  cross_chapter_concerns: CrossChapterConcern[];
  summary: string;
  minimal: boolean;
  created_at: string;
}

export interface ConflictItem {
  conflict_id: UUID;
  generation_id: UUID;
  team_id: UUID;
  scan_to: number;
  type: ConflictType;
  chapter_refs: number[];
  summary: string;
  evidence: string[];
  rewrite_attempts: number;
  frozen: boolean;
  user_action: ConflictUserAction;
  created_at: string;
  updated_at: string;
}

export interface ConsistencyReport {
  generation_id: UUID;
  team_id: UUID;
  scan_from: number;
  scan_to: number;
  model: string;
  conflict_ids: UUID[];
  memory_unavailable: boolean;
  characters_scanned: UUID[];
  minimal: boolean;
  created_at: string;
}

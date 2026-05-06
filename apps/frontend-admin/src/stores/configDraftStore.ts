import { create } from "zustand";

export type ModelStage =
  | "classification" | "character" | "map" | "style"
  | "outline" | "chapter" | "self_critique"
  | "critic" | "consistency";

export interface ModelConfigDraft {
  stage: ModelStage;
  primary: {
    model_id: string;
    max_output_tokens: number;
    temperature: number;
    top_p?: number;
  };
  fallback?: ModelConfigDraft["primary"];
  expected_version: number;
}

interface ConfigDraftState {
  modelDrafts: Partial<Record<ModelStage, ModelConfigDraft>>;
  setModelDraft(stage: ModelStage, draft: ModelConfigDraft): void;
  clearModelDraft(stage: ModelStage): void;
  clearAll(): void;
}

export const useConfigDraftStore = create<ConfigDraftState>((set) => ({
  modelDrafts: {},
  setModelDraft: (stage, draft) =>
    set((s) => ({ modelDrafts: { ...s.modelDrafts, [stage]: draft } })),
  clearModelDraft: (stage) =>
    set((s) => {
      const next = { ...s.modelDrafts };
      delete next[stage];
      return { modelDrafts: next };
    }),
  clearAll: () => set({ modelDrafts: {} }),
}));

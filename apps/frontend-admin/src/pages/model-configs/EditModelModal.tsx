import { ApiConflictFrozenError } from "@novelgen/api-client";
import { Button, Dialog, Toast } from "@novelgen/ui";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import type { ModelConfigRow } from "../../hooks/useModelConfigsQuery";
import { adminQk } from "../../lib/adminQueryKeys";
import { api } from "../../lib/api";

const MODEL_OPTIONS = [
  "claude-opus-4-7",
  "claude-sonnet-4-7",
  "claude-sonnet-4-6",
  "claude-haiku-4-5",
];

interface Props {
  row: ModelConfigRow;
  onClose(): void;
}

interface VersionConflictErrorShape {
  status?: number;
  code?: string;
}

export function EditModelModal({ row, onClose }: Props) {
  const qc = useQueryClient();
  const [model, setModel] = useState(row.primary.model_id);
  const [maxTokens, setMaxTokens] = useState(row.primary.max_output_tokens);
  const [temperature, setTemperature] = useState(row.primary.temperature);
  const [error, setError] = useState<string | null>(null);

  const putMut = useMutation({
    mutationFn: () =>
      api.request(`/api/v1/admin/model-configs/${row.stage}`, {
        method: "PUT",
        body: {
          primary: {
            model_id: model,
            max_output_tokens: maxTokens,
            temperature,
          },
          fallback: row.fallback ?? undefined,
          expected_version: row.version,
        },
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: adminQk.modelConfigs() });
      onClose();
    },
    onError: (err) => {
      const e = err as VersionConflictErrorShape;
      if (e.status === 409) {
        setError("已被他人修改，请刷新页面后再试");
      } else {
        setError("保存失败，请稍后重试");
      }
    },
  });

  return (
    <Dialog
      open
      onOpenChange={(next) => {
        if (!next) onClose();
      }}
      title={`编辑模型配置 · ${row.stage}`}
      footer={
        <>
          <Button variant="ghost" size="sm" onClick={onClose}>
            取消
          </Button>
          <Button size="sm" loading={putMut.isPending} onClick={() => putMut.mutate()}>
            保存
          </Button>
        </>
      }
    >
      <div className="space-y-3">
        <Field label="模型">
          <select
            value={model}
            onChange={(e) => setModel(e.target.value)}
            className="h-9 w-full rounded-md border px-2 text-sm"
          >
            {MODEL_OPTIONS.map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
          </select>
        </Field>
        <Field label="最大输出 tokens">
          <input
            type="number"
            min={1}
            max={8192}
            value={maxTokens}
            onChange={(e) => setMaxTokens(Number.parseInt(e.target.value, 10))}
            className="h-9 w-full rounded-md border px-2 text-sm"
          />
        </Field>
        <Field label="temperature (0-1)">
          <input
            type="number"
            min={0}
            max={1}
            step={0.1}
            value={temperature}
            onChange={(e) => setTemperature(Number.parseFloat(e.target.value))}
            className="h-9 w-full rounded-md border px-2 text-sm"
          />
        </Field>
        {error ? <Toast variant="error" title="保存失败" description={error} /> : null}
      </div>
    </Dialog>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs text-muted-foreground">{label}</span>
      {children}
    </label>
  );
}

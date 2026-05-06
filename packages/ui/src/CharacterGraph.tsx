import { lazy, Suspense } from "react";
import { Spinner } from "./primitives/Spinner";

export interface CharacterNode {
  id: string;
  name: string;
  role?: string;
  importance?: number;
}

export interface CharacterEdge {
  id: string;
  source: string;
  target: string;
  relation: string;
}

export interface CharacterGraphProps {
  nodes: CharacterNode[];
  edges: CharacterEdge[];
  onSelectNode?(nodeId: string): void;
}

// React Flow is heavy — lazy load it so the analysis chunk stays within budget.
const GraphImpl = lazy(() => import("./internal/CharacterGraphImpl"));

export function CharacterGraph(props: CharacterGraphProps) {
  return (
    <Suspense fallback={<div className="flex h-full items-center justify-center"><Spinner label="加载人物关系图" /></div>}>
      <GraphImpl {...props} />
    </Suspense>
  );
}

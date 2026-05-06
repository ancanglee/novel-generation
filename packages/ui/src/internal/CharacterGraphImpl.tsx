// Real React Flow implementation, split into its own chunk via CharacterGraph's lazy import.
import { Background, Controls, type Edge, type Node, ReactFlow } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { useMemo } from "react";
import type { CharacterEdge, CharacterGraphProps, CharacterNode } from "../CharacterGraph";

function layoutNodes(chars: CharacterNode[]): Node[] {
  // Simple circular layout — avoids dagre/dagre-d3 dependency.
  const radius = Math.max(180, chars.length * 40);
  return chars.map((c, idx) => {
    const angle = (idx / Math.max(chars.length, 1)) * 2 * Math.PI;
    return {
      id: c.id,
      data: { label: `${c.name}${c.role ? ` · ${c.role}` : ""}` },
      position: {
        x: radius * Math.cos(angle),
        y: radius * Math.sin(angle),
      },
      type: "default",
    } satisfies Node;
  });
}

function toEdges(edges: CharacterEdge[]): Edge[] {
  return edges.map((e) => ({
    id: e.id,
    source: e.source,
    target: e.target,
    label: e.relation,
    animated: false,
  }));
}

export default function CharacterGraphImpl({ nodes, edges, onSelectNode }: CharacterGraphProps) {
  const rfNodes = useMemo(() => layoutNodes(nodes), [nodes]);
  const rfEdges = useMemo(() => toEdges(edges), [edges]);

  return (
    <div className="h-full w-full">
      <ReactFlow
        nodes={rfNodes}
        edges={rfEdges}
        fitView
        onNodeClick={(_, node) => onSelectNode?.(node.id)}
        proOptions={{ hideAttribution: true }}
      >
        <Background />
        <Controls />
      </ReactFlow>
    </div>
  );
}

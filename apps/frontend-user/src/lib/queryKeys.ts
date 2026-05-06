export const qk = {
  auth: () => ["auth", "me"] as const,
  novels: () => ["novels"] as const,
  novel: (id: string) => ["novels", id] as const,
  analysis: (novelId: string) => ["novels", novelId, "analysis"] as const,
  characters: (novelId: string) => ["novels", novelId, "characters"] as const,
  style: (novelId: string) => ["novels", novelId, "style"] as const,
  generations: () => ["generations"] as const,
  generation: (gid: string) => ["generations", gid] as const,
  outline: (gid: string) => ["generations", gid, "outline"] as const,
  chapter: (gid: string, n: number) => ["generations", gid, "chapters", n] as const,
  critique: (gid: string, n: number) => ["generations", gid, "chapters", n, "critique"] as const,
  consistency: (gid: string, sinceChapter: number) =>
    ["generations", gid, "consistency", sinceChapter] as const,
  job: (id: string) => ["jobs", id] as const,
} as const;

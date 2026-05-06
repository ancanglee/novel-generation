# novelgen-memory-facade

Abstract interface unifying AgentCore Memory + Amazon Neptune + OpenSearch Serverless.

U1 ships the interface only. The concrete implementation lives in U3 Understanding Agents.

## Interface

- `remember(team, novel, facts)` — upsert Facts by business key
- `recall(team, novel, query, top_k)` — retrieve related facts
- `get_character(team, novel, character_id, at_chapter)` — point-in-time character snapshot
- `upsert_graph(team, novel, nodes, edges)` — knowledge graph writes (Neptune)
- `neighbors(team, novel, node_id, edge_type, depth)` — graph traversal
- `index_vector(team, novel, chunk_id, embedding, payload)` — vector index
- `search_similar(team, novel, embedding, top_k, filters)` — kNN
- `hybrid_search(team, novel, query_text, query_embed, top_k)` — BM25 + vector
- `embed(text)` — Titan Embeddings V2

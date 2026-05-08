# AgentCore Gateway Tool Schemas

6 个 Target，每个对应一个 Lambda。Tool schema 使用 **MCP inline tool schema**（JSON Schema 2020-12）。

## Common
- `authorizerConfiguration`：Gateway 级别使用 **customJWTAuthorizer**，`discoveryUrl=<agentcore-identity-oidc-discovery>`，`allowedAudience=["agentcore-runtime"]`。
- `roleArn`：`novelgen-{env}-gateway-role`（由 CDK 创建），允许 `lambda:InvokeFunction` 指向 6 个 Lambda。
- 所有 Lambda Runtime = Python 3.12；timeout=30s；memory=1024MB；VPC 可选（需要 Neptune 的才挂）。

---

## Target 1: `memory-facade`

### Tools
```jsonc
[
  {
    "name": "remember",
    "description": "Persist novel facts into AgentCore Memory (semantic + graph + vector)",
    "inputSchema": {
      "type": "object",
      "properties": {
        "team_id": {"type": "string"},
        "novel_id": {"type": "string"},
        "facts": {
          "type": "array",
          "items": {
            "type": "object",
            "properties": {
              "fact_key": {"type": "string"},
              "fact_type": {"type": "string"},
              "content": {"type": "object"},
              "source_chapter": {"type": ["integer","null"]}
            },
            "required": ["fact_key","fact_type","content"],
            "additionalProperties": false
          }
        }
      },
      "required": ["team_id","novel_id","facts"],
      "additionalProperties": false
    }
  },
  {
    "name": "recall",
    "description": "Retrieve facts for a natural language query",
    "inputSchema": {
      "type": "object",
      "properties": {
        "team_id": {"type":"string"},
        "novel_id": {"type":"string"},
        "query": {"type":"string"},
        "top_k": {"type":"integer","default":20}
      },
      "required": ["team_id","novel_id","query"],
      "additionalProperties": false
    }
  },
  {
    "name": "get_character",
    "description": "Get the character snapshot closest to (but not after) at_chapter",
    "inputSchema": {
      "type": "object",
      "properties": {
        "team_id": {"type":"string"},
        "novel_id": {"type":"string"},
        "character_id": {"type":"string"},
        "at_chapter": {"type":["integer","null"]}
      },
      "required": ["team_id","novel_id","character_id"],
      "additionalProperties": false
    }
  }
]
```

## Target 2: `graph-ops`

```jsonc
[
  {"name":"upsert_node","inputSchema":{
    "type":"object","required":["label","team_id","novel_id","node_id","properties"],
    "properties":{"label":{"type":"string"},"team_id":{"type":"string"},"novel_id":{"type":"string"},"node_id":{"type":"string"},"properties":{"type":"object"}},
    "additionalProperties": false}},
  {"name":"upsert_edge","inputSchema":{
    "type":"object","required":["from_label","to_label","edge_type","team_id","novel_id","from_id","to_id","properties"],
    "properties":{"from_label":{"type":"string"},"to_label":{"type":"string"},"edge_type":{"type":"string"},"team_id":{"type":"string"},"novel_id":{"type":"string"},"from_id":{"type":"string"},"to_id":{"type":"string"},"properties":{"type":"object"}},
    "additionalProperties": false}},
  {"name":"neighbors","inputSchema":{
    "type":"object","required":["team_id","novel_id","node_id"],
    "properties":{"team_id":{"type":"string"},"novel_id":{"type":"string"},"node_id":{"type":"string"},"edge_type":{"type":["string","null"]},"limit":{"type":"integer","default":50}},
    "additionalProperties": false}}
]
```

## Target 3: `vector-ops`

```jsonc
[
  {"name":"index_vector","inputSchema":{
    "type":"object","required":["team_id","novel_id","chunk_id","embedding","payload"],
    "properties":{"team_id":{"type":"string"},"novel_id":{"type":"string"},"chunk_id":{"type":"string"},"embedding":{"type":"array","items":{"type":"number"}},"payload":{"type":"object"}},
    "additionalProperties": false}},
  {"name":"search_similar","inputSchema":{
    "type":"object","required":["team_id","novel_id","embedding"],
    "properties":{"team_id":{"type":"string"},"novel_id":{"type":"string"},"embedding":{"type":"array","items":{"type":"number"}},"top_k":{"type":"integer","default":10},"filters":{"type":["object","null"]}},
    "additionalProperties": false}},
  {"name":"hybrid_search","inputSchema":{
    "type":"object","required":["team_id","novel_id","query_text","query_embed"],
    "properties":{"team_id":{"type":"string"},"novel_id":{"type":"string"},"query_text":{"type":"string"},"query_embed":{"type":"array","items":{"type":"number"}},"top_k":{"type":"integer","default":10}},
    "additionalProperties": false}}
]
```

## Target 4: `ingestion-fetch`

```jsonc
[
  {"name":"fetch_public_domain","inputSchema":{
    "type":"object","required":["source_id","query"],
    "properties":{"source_id":{"enum":["gutenberg","ctext","wikisource"]},"query":{"type":"string"},"limit":{"type":"integer","default":5}},
    "additionalProperties": false}},
  {"name":"fetch_url","inputSchema":{
    "type":"object","required":["url"],
    "properties":{"url":{"type":"string","format":"uri"}},
    "additionalProperties": false}}
]
```

## Target 5: `ingestion-browser`

```jsonc
[
  {"name":"render_with_browser","inputSchema":{
    "type":"object","required":["url","job_id"],
    "properties":{"url":{"type":"string","format":"uri"},"job_id":{"type":"string"},"timeout_seconds":{"type":"integer","default":60}},
    "additionalProperties": false}}
]
```

## Target 6: `ddb-jobs`

```jsonc
[
  {"name":"put_checkpoint","inputSchema":{
    "type":"object","required":["team_id","job_id","step","state"],
    "properties":{"team_id":{"type":"string"},"job_id":{"type":"string"},"step":{"type":"string"},"state":{"type":"object"}},
    "additionalProperties": false}},
  {"name":"get_checkpoint","inputSchema":{
    "type":"object","required":["team_id","job_id","step"],
    "properties":{"team_id":{"type":"string"},"job_id":{"type":"string"},"step":{"type":"string"}},
    "additionalProperties": false}},
  {"name":"advance_scan_cursor","inputSchema":{
    "type":"object","required":["team_id","novel_id","chapter_idx"],
    "properties":{"team_id":{"type":"string"},"novel_id":{"type":"string"},"chapter_idx":{"type":"integer"}},
    "additionalProperties": false}}
]
```

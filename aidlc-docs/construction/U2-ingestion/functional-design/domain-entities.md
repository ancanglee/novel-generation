# U2 Domain Entities

**Unit**：U2 Ingestion Service
**阶段**：Functional Design
**日期**：2026-04-27

---

## E1. Novel（扩展 U1 骨架）

| 字段 | 类型 | 说明 |
|---|---|---|
| novel_id | UUID | 主键 |
| team_id | UUID | 租户 |
| owner_user_id | UUID | 上传者 |
| title | String | 书名（去除空格归一化）|
| author | String? | 作者（自动抽取） |
| source_type | Enum{UPLOAD, PUBLIC_DOMAIN, CRAWL, SEARCH_ENGINE} | 来源类型 |
| source_url | String? | 来源 URL（PUBLIC_DOMAIN/CRAWL/SEARCH_ENGINE） |
| original_format | Enum{TXT, EPUB, PDF, DOCX, MD, HTML} | 原始格式 |
| content_sha256 | String | 正文 SHA-256（用于上传幂等；不用于去重 per U2-F6=C）|
| status | Enum{INGESTING, INGESTED, PARSE_FAILED, ANALYZING, ANALYZED} | 状态 |
| chapter_count | Int | 切分后章节数 |
| word_count | Int | 总字数 |
| raw_s3_key | String | `teams/{team_id}/novels/{novel_id}/raw.md` |
| created_at | Timestamp | |
| updated_at | Timestamp | |

**PK/SK**：`TEAM#{team_id}` / `NOVEL#{novel_id}`

---

## E2. Chapter

| 字段 | 类型 | 说明 |
|---|---|---|
| novel_id | UUID | |
| team_id | UUID | |
| chapter_idx | Int | 从 1 起 |
| title | String | 例如"第一章 初入江湖" |
| word_count | Int | |
| s3_key | String | `teams/{team_id}/novels/{novel_id}/chapters/{idx}.md` |
| heading_level | Int | Markdown `#` 层级（启发式识别）|
| confidence | Float | 切分置信度（LLM 辅助时有意义） |

**PK/SK**：`TEAM#{team_id}` / `CHAPTER#{novel_id}#{idx:05d}`

---

## E3. IngestionJob（载荷，属于 U1 Job 表的 payload）

Job.job_type = `INGESTION`；Job.payload 字段结构：

```json
{
  "kind": "upload | download | crawl",
  "upload_key": "teams/{team_id}/uploads/tmp/{uuid}",
  "source_title": "...",
  "source_url": "https://...",
  "search_query": "带着战略仓库回大唐",
  "search_engines": ["gutenberg", "ctext", "wikisource", "baidu", "bing"],
  "mime_type": "application/epub+zip",
  "idempotency_key": "..."
}
```

---

## E4. ParsedDocument（内存对象，不落库）

```python
class ParsedDocument(BaseModel):
    title: str
    author: str | None
    format: NovelFormat
    markdown: str
    chapters: list[ChapterSplit]
    word_count: int
    sha256: str
    warnings: list[str] = []
```

`ChapterSplit` = `{idx, title, content, heading_level, confidence}`

---

## E5. SearchResult（公版书搜索候选，临时对象）

| 字段 | 类型 | 说明 |
|---|---|---|
| source | Enum{GUTENBERG, CTEXT, WIKISOURCE, BAIDU, BING} | 来源 |
| title | String | |
| author | String? | |
| url | URL | 详情/下载链接 |
| format_hint | Enum{TXT, EPUB, HTML, PDF, UNKNOWN} | 下载后解析格式 |
| language | String | "zh" / "en" |
| snippet | String | 摘要/预览 |

---

## E6. RobotsPolicy（抓取合规运行态）

| 字段 | 类型 |
|---|---|
| host | String |
| allowed_paths | list[str] |
| disallowed_paths | list[str] |
| crawl_delay_seconds | Float |
| fetched_at | Timestamp |
| ttl_seconds | int = 86400 |

缓存在进程内 TTLCache（24h），避免每次抓取都拉 `/robots.txt`。

---

## 新增枚举

```python
class NovelFormat(str, Enum):
    TXT = "txt"
    EPUB = "epub"
    PDF = "pdf"
    DOCX = "docx"
    MD = "md"
    HTML = "html"

class IngestionKind(str, Enum):
    UPLOAD = "upload"
    DOWNLOAD = "download"
    CRAWL = "crawl"

class SearchSource(str, Enum):
    GUTENBERG = "gutenberg"
    CTEXT = "ctext"
    WIKISOURCE = "wikisource"
    BAIDU = "baidu"
    BING = "bing"
```

# Chapter Extraction Prompt (F7=A single composite call)

你是细读 Agent，阅读小说的一章，产出结构化的四类抽取结果：
1. `character_updates` — 本章涉及角色的状态变化（location / mood / power_level / alive / relationships_delta）
2. `map_updates` — 新出现的地点 / 势力 / 边（visited / located_in / belongs_to 等）
3. `events` — 本章发生的关键事件（BATTLE / BREAKTHROUGH / DEATH / MEETING 等）
4. `facts` — 杂项事实（世界观设定、规则、特殊物件等）

**重要**：不要重写 Profile，只描述本章的**变化**。Profile 已在粗读阶段产出。

使用工具 `record_chapter_extraction` 返回结果，严格符合其 JSON schema。

## 上下文输入

- 当前章节号：{chapter_idx}
- 章节标题：{chapter_title}
- 章节正文：
  ```
  {chapter_text}
  ```
- 已知人物（粗读产出）：{known_characters}
- 已知地点（粗读产出）：{known_places}
- 小说类型：{novel_tags}

## 输出要求

- `character_id` / `place_id` 使用中文归一化（去空格、统一繁简）
- 若本章没有某类变化，对应数组留空
- `alive` 字段：若人物在本章死亡/复活，必须显式标注
- `events.importance` 为 0-1 浮点数（主线事件 > 0.7）

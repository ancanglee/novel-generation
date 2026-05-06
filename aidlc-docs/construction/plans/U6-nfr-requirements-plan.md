# U6 Frontend (User) + BFF — 非功能需求计划

**Unit**：U6 Frontend + BFF
**阶段**：NFR Requirements
**日期**：2026-04-28

---

## 上下文摘要
U6 是面向终端用户的 Web 界面。NFR 聚焦：页面加载 / 首次互动 / 流式渲染 / Bundle 大小 / 可访问性 / 国际化 / 错误恢复 / 监控上报。继承 U1 (CloudFront 海外加速)、U4 (TTFT ≤ 3s) 的底座约束。

---

## 第 1 部分 — 澄清问题（6 个）

### Question U6-N1 — Lighthouse 性能目标
Lighthouse Mobile 性能分（NFR US-NFR-05 衍生）：

A) **Performance ≥ 85**（进取，需 code-split + image optimize + CLS 控制）✓
B) **Performance ≥ 75**（宽松）
C) **Performance ≥ 90**（激进，受 React Flow + ECharts 拖累）
D) 其他
[回答]：A

### Question U6-N2 — Bundle 大小预算
首屏 JS 预算（gzipped）：

A) **≤ 200 KB 首屏关键路径 + 懒加载其余**（现代 SPA 实践）✓
B) **≤ 350 KB 首屏 + 懒加载**（宽松）
C) **≤ 150 KB 首屏**（激进，React + TanStack Query + router 本身接近 100KB）
D) 其他
[回答]：A

### Question U6-N3 — SSE TTFT（前端感知）
"开始生成" 按钮点击 → 首个 delta 到达并渲染到屏幕（含 SPA 层开销 + BFF 透传 + ApiService 响应）：

A) **P95 < 5 秒**（U4 已保证 TTFT ≤ 3s，留 2s 给前端 + BFF 穿透）✓
B) **P95 < 3 秒**（激进，需 BFF 零延迟）
C) **P95 < 8 秒**（宽松）
D) 其他
[回答]：A

### Question U6-N4 — 可访问性（A11y）基线
WCAG 合规程度：

A) **WCAG 2.1 AA**（对比度 / 键盘导航 / ARIA 语义，axe-core 自动化通过）✓
B) **WCAG 2.1 A**（最低，键盘可达即可）
C) **仅 lint-level 检查**（不做测试）
D) 其他
[回答]：A

### Question U6-N5 — 国际化（i18n）
当前 Stories 全中文（UI 文案也是中文）。是否预留 i18n？

A) **中文 only，代码字面量 + 词表文档，暂不上 i18n 库**（简单）
B) **react-i18next + 中英双语占位（英语仅骨架，未真正翻译）**（预留扩展）✓
C) **全量 i18n + 完整英语翻译**（成本高）
D) 其他
[回答]：A

### Question U6-N6 — 浏览器兼容
最低支持浏览器：

A) **Chrome/Edge 115+ / Safari 16+ / Firefox 115+**（2023 后）✓
B) **更激进：2024+ (Chrome 125+ / Safari 17+)**（可用更多 CSS 特性）
C) **兼容 IE11 / Chrome 90**（拖累现代特性）
D) 其他
[回答]：A

---

## 第 2 部分 — 执行清单（批准后）

- [x] Step U6N-1: 生成 `nfr-requirements.md`
- [x] Step U6N-2: 生成 `tech-stack-decisions.md`
- [x] Step U6N-3: 更新 aidlc-state.md

---

## 第 3 部分 — 推荐
- **N1=A** Lighthouse ≥ 85 —— 可达、与 React Flow+ECharts 的 bundle 体量兼容
- **N2=A** 首屏 ≤ 200 KB gzipped + 懒加载 ECharts / React Flow 子 chunk
- **N3=A** P95 < 5s TTFT（与 U4 NFR 留 2s 缓冲）
- **N4=A** WCAG 2.1 AA + axe-core CI
- **N5=B** 中英双语骨架（真翻译留待 future PR）—— 投入少但免再重构
- **N6=A** Chrome 115+ / Safari 16+ / Firefox 115+（支持 ES2022、CSS subgrid、container queries）

export const conflict = {
  panelTitle: "一致性冲突",
  empty: "暂无一致性冲突",
  actions: {
    ignore: "忽略",
    rewrite: "重写",
  },
  frozenTooltip: "已尝试 3 次未能解决，请手动编辑",
  rewriteModalTitle: "重写冲突章节",
  rewriteModalBody: "将使用此冲突摘要作为重写指令触发新章节生成。",
  typeLabels: {
    character_state: "人物状态",
    plot_hole: "情节漏洞",
    timeline: "时间线",
    location: "地理位置",
    relation: "人物关系",
    worldbuilding: "世界观",
  },
  errors: {
    frozen: "多次尝试未能解决，请手动编辑",
    rewriteFailed: "重写请求失败，请稍后重试",
  },
} as const;

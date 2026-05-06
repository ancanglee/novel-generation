export const chapter = {
  title: (n: number) => `第 ${n} 章`,
  actions: {
    cancel: "取消生成",
    rewrite: "重写本章",
    approve: "采纳本章",
    exportDocx: "导出 DOCX",
  },
  phase: {
    idle: "待开始",
    connecting: "连接中…",
    streaming: "生成中",
    completed: "已完成",
    cancelling: "取消中…",
    cancelled: "已取消",
    failed: "生成失败",
  },
  stream: {
    reconnecting: (n: number) => `连接不稳定，正在重连（第 ${n} 次）…`,
    failed: "连接不稳定，请刷新页面重试",
    cursorAnnouncement: "正在生成章节内容",
  },
  rewrite: {
    modalTitle: "重写确认",
    modalBody: "重写将基于最新的参考信息与风格向量重新生成本章，原内容将被覆盖。",
    instructionLabel: "额外指令（可选）",
    hitMaxAttempts: (n: number) => `已重写 ${n} 次（上限）`,
  },
} as const;

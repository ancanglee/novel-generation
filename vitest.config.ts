import { defineConfig } from "vitest/config";

// 根级 vitest 配置：排除 Playwright 端到端测试。
export default defineConfig({
  test: {
    exclude: ["**/node_modules/**", "**/dist/**", "**/build/**", "**/cdk.out/**", "tests/e2e/**"],
  },
});

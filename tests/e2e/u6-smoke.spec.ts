// U6 Smoke E2E: sign-in fallback → novels → generation shell → conflict-panel.
// Focuses on UI surfaces that can be verified without a real backend — the
// test either uses MSW / Playwright route interception or a staging API.
// Build-and-Test phase will extend this with backend fixtures.

import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

test.describe("U6 user smoke", () => {
  test("shows login prompt when unauthenticated", async ({ page }) => {
    await page.route("**/auth/me", (route) =>
      route.fulfill({
        status: 401,
        body: JSON.stringify({
          error: { code: "UNAUTHENTICATED", message: "未登录", request_id: "x" },
        }),
      }),
    );
    await page.goto("/");
    await expect(page.getByText("欢迎使用 NovelGen")).toBeVisible();
    await expect(page.getByRole("link", { name: "登录" })).toBeVisible();
  });

  test("dashboard renders after session", async ({ page }) => {
    await page.route("**/auth/me", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          principal: {
            userId: "u1",
            teamId: "t1",
            email: "u1@example.com",
            globalRole: "regular_user",
            teamRole: "member",
          },
          csrf: "csrf-token",
        }),
      }),
    );
    await page.route("**/api/v1/dashboard/summary", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          novels_count: 3,
          generations_count: 1,
          recent_jobs: [],
        }),
      }),
    );
    await page.goto("/");
    await expect(page.getByRole("heading", { name: "仪表盘" })).toBeVisible();
    await expect(page.getByText("小说库")).toBeVisible();

    const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze();
    const serious = results.violations.filter(
      (v) => v.impact === "serious" || v.impact === "critical",
    );
    expect(serious, serious.map((v) => v.id).join(",")).toHaveLength(0);
  });

  test("conflict panel shows frozen chip when frozen=true", async ({ page }) => {
    await page.route("**/auth/me", (route) =>
      route.fulfill({
        status: 200,
        body: JSON.stringify({
          principal: {
            userId: "u1",
            teamId: "t1",
            email: "u@x",
            globalRole: "regular_user",
            teamRole: "member",
          },
          csrf: "t",
        }),
      }),
    );
    await page.route("**/api/v1/generations/G1/chapters/1/stream", (route) => {
      const body = [
        "event: start\ndata: {}\n\n",
        'event: delta\nid: 1\ndata: {"text":"第一句。"}\n\n',
        "event: completed\ndata: {}\n\n",
      ].join("");
      route.fulfill({
        status: 200,
        contentType: "text/event-stream",
        body,
      });
    });
    await page.route("**/api/v1/generations/G1/consistency-reports*", (route) =>
      route.fulfill({
        status: 200,
        body: JSON.stringify({
          reports: [
            {
              scan_to: 5,
              report: {
                conflicts: [
                  {
                    conflict_id: "c1",
                    generation_id: "G1",
                    team_id: "t1",
                    scan_to: 5,
                    type: "timeline",
                    chapter_refs: [3],
                    summary: "季节不一致",
                    evidence: [],
                    rewrite_attempts: 3,
                    frozen: true,
                    user_action: "rewrite_requested",
                    created_at: new Date().toISOString(),
                    updated_at: new Date().toISOString(),
                  },
                ],
              },
            },
          ],
        }),
      }),
    );

    await page.goto("/generations/G1/chapters/1");
    await expect(page.getByText("一致性冲突（1）")).toBeVisible();
    await expect(page.getByText("已冻结")).toBeVisible();
    // Rewrite button disabled.
    const rewriteBtn = page.getByRole("button", { name: "重写" }).first();
    await expect(rewriteBtn).toBeDisabled();
  });
});

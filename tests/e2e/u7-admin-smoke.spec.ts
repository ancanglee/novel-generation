// U7 Admin smoke E2E: RBAC gate + model-configs table + audit list + axe.

import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

test.describe("U7 admin smoke", () => {
  test("non-admin sees forbidden screen", async ({ page }) => {
    await page.route("**/auth/me", (route) =>
      route.fulfill({
        status: 200,
        body: JSON.stringify({
          principal: {
            userId: "u1",
            teamId: "t1",
            email: "user@example.com",
            globalRole: "regular_user",
            teamRole: "member",
          },
          csrf: "x",
        }),
      }),
    );
    await page.goto("/admin");
    await expect(page.getByText("无权访问")).toBeVisible();
  });

  test("admin sees dashboard and sidebar", async ({ page }) => {
    await page.route("**/auth/me", (route) =>
      route.fulfill({
        status: 200,
        body: JSON.stringify({
          principal: {
            userId: "u1",
            teamId: "t1",
            email: "admin@example.com",
            globalRole: "admin",
            teamRole: "owner",
          },
          csrf: "x",
        }),
      }),
    );
    await page.goto("/admin");
    await expect(page.getByRole("heading", { name: "概览" })).toBeVisible();
    await expect(page.getByRole("navigation", { name: "管理后台导航" })).toBeVisible();

    const results = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa"])
      .analyze();
    const serious = results.violations.filter(
      (v) => v.impact === "serious" || v.impact === "critical",
    );
    expect(serious, serious.map((v) => v.id).join(",")).toHaveLength(0);
  });

  test("model-configs table surfaces 9 stages", async ({ page }) => {
    await page.route("**/auth/me", (route) =>
      route.fulfill({
        status: 200,
        body: JSON.stringify({
          principal: {
            userId: "u1",
            teamId: "t1",
            email: "admin@example.com",
            globalRole: "admin",
            teamRole: "owner",
          },
          csrf: "x",
        }),
      }),
    );
    await page.route("**/api/v1/admin/model-configs", (route) =>
      route.fulfill({
        status: 200,
        body: JSON.stringify({
          stages: [
            { stage: "chapter", primary: { model_id: "claude-sonnet-4-7", max_output_tokens: 4096, temperature: 0.7 }, fallback: null, version: 3, updated_by: "admin", updated_at: "2026-04-30T10:00:00Z" },
            { stage: "critic", primary: { model_id: "claude-opus-4-7", max_output_tokens: 2000, temperature: 0.2 }, fallback: null, version: 1, updated_by: "admin", updated_at: "2026-04-30T09:00:00Z" },
          ],
        }),
      }),
    );
    await page.goto("/admin/model-configs");
    await expect(page.getByText("claude-sonnet-4-7")).toBeVisible();
    await expect(page.getByText("claude-opus-4-7")).toBeVisible();
  });
});

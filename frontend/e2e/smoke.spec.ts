import { expect, test } from "@playwright/test";

const email = process.env.E2E_EMAIL || "";
const password = process.env.E2E_PASSWORD || "";

test.describe("candidate smokes", () => {
  test.skip(!email || !password, "Set E2E_EMAIL and E2E_PASSWORD against local Vite+API.");

  test("login, Home, Applications, Jobs, Automation", async ({ page }) => {
    await page.goto("/login");
    await page.getByLabel(/email/i).fill(email);
    await page.getByPlaceholder("Your password").fill(password);
    await page.getByRole("button", { name: /log in to workspace|log in|sign in/i }).click();
    await expect(page).toHaveURL(/\/app/, { timeout: 20_000 });

    await page.goto("/app");
    await expect(page.getByRole("heading", { name: /home|dashboard/i }).first()).toBeVisible();

    await page.goto("/app/applications");
    await expect(page.getByRole("heading", { name: /applications/i }).first()).toBeVisible();

    await page.goto("/app/jobs");
    await expect(page.getByRole("heading", { name: /jobs/i }).first()).toBeVisible();

    await page.goto("/app/automation");
    await expect(page.getByRole("heading", { name: /automation/i }).first()).toBeVisible();
  });
});

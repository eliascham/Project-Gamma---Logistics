import { test, expect } from "./fixtures";

test.describe("Dashboard", () => {
  test("shows stat cards", async ({ authenticatedPage: page }) => {
    await page.goto("/");

    await expect(page.getByText("Total Documents")).toBeVisible();
    await expect(page.getByText("Pending")).toBeVisible();
    await expect(page.getByText("Extracted")).toBeVisible();
    await expect(page.getByText("Failed")).toBeVisible();
  });

  test("shows quick action buttons", async ({ authenticatedPage: page }) => {
    await page.goto("/");

    await expect(
      page.getByRole("button", { name: /Upload Document/ }),
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: /Cost Allocations/ }),
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: /Ask a Question/ }),
    ).toBeVisible();
  });

  test("shows Knowledge Base section", async ({
    authenticatedPage: page,
  }) => {
    await page.goto("/");

    await expect(page.getByText("Knowledge Base")).toBeVisible();
  });

  test("shows Guardrails & Operations section", async ({
    authenticatedPage: page,
  }) => {
    await page.goto("/");

    await expect(page.getByText("Guardrails & Operations")).toBeVisible();
  });
});

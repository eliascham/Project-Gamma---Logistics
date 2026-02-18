import { test, expect } from "./fixtures";
import { NAV_LABELS, ROUTE_TITLES, TEST_USER } from "./helpers/constants";

test.describe("Navigation", () => {
  test("sidebar shows all nav items", async ({ authenticatedPage: page }) => {
    await page.goto("/");

    const sidebar = page.locator("aside");
    for (const label of NAV_LABELS) {
      await expect(sidebar.getByText(label, { exact: true })).toBeVisible();
    }
  });

  test("sidebar shows user info", async ({ authenticatedPage: page }) => {
    await page.goto("/");

    await expect(page.getByText(TEST_USER.name)).toBeVisible();
    await expect(page.getByText(TEST_USER.email)).toBeVisible();
  });

  test("sidebar shows branding and version", async ({
    authenticatedPage: page,
  }) => {
    await page.goto("/");

    const sidebar = page.locator("aside");
    await expect(sidebar.getByText("Project Gamma")).toBeVisible();
    await expect(sidebar.getByText("v0.4.0")).toBeVisible();
  });

  test("clicking nav items navigates to correct pages", async ({
    authenticatedPage: page,
  }) => {
    await page.goto("/");

    const sidebar = page.locator("aside");

    // Test a subset of routes to keep the test focused
    const routes: [string, string][] = [
      ["/documents", "Documents"],
      ["/allocations", "Cost Allocations"],
      ["/chat", "Document Q&A"],
      ["/reviews", "Review Queue"],
      ["/anomalies", "Anomalies"],
      ["/reconciliation", "Reconciliation"],
      ["/data-explorer", "Data Explorer"],
      ["/audit", "Audit Log"],
    ];

    for (const [path, expectedTitle] of routes) {
      const navLabel = Object.entries(ROUTE_TITLES).find(
        ([k]) => k === path,
      );
      // Find the sidebar link matching this path
      const link = sidebar.locator(`a[href="${path}"]`);
      await link.click();
      await expect(page).toHaveURL(path);
      await expect(page.locator("h1")).toContainText(expectedTitle);
    }
  });

  test("theme toggle switches dark/light mode", async ({
    authenticatedPage: page,
  }) => {
    await page.goto("/");

    // Find theme toggle button in the sidebar (bottom area)
    const sidebar = page.locator("aside");
    const themeButton = sidebar.getByRole("button", { name: /theme/i });

    // Click to toggle theme
    await themeButton.click();

    // Check that the html element has either 'dark' or 'light' class
    const htmlClass = await page
      .locator("html")
      .getAttribute("class");
    expect(htmlClass).toMatch(/dark|light/);

    // Toggle again
    await themeButton.click();

    const htmlClassAfter = await page
      .locator("html")
      .getAttribute("class");
    // Should have changed
    expect(htmlClassAfter).not.toBe(htmlClass);
  });
});

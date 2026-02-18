import { test, expect } from "./fixtures";
import { ROUTE_TITLES } from "./helpers/constants";

const routes = Object.entries(ROUTE_TITLES).map(([path, title]) => ({
  path,
  title,
}));

test.describe("Smoke tests", () => {
  for (const { path, title } of routes) {
    test(`${path} renders "${title}" heading`, async ({
      authenticatedPage: page,
    }) => {
      const errors: string[] = [];
      page.on("pageerror", (error) => errors.push(error.message));

      await page.goto(path);

      // Dashboard uses h2, header uses h1 — check both
      const heading = page.locator("h1, h2").filter({ hasText: title });
      await expect(heading.first()).toBeVisible();

      expect(errors).toEqual([]);
    });
  }
});

import { test as base, type Page } from "@playwright/test";
import { STORAGE_KEY, TEST_USER } from "../helpers/constants";

type AuthFixtures = {
  authenticatedPage: Page;
};

export const test = base.extend<AuthFixtures>({
  authenticatedPage: async ({ page }, use) => {
    // Navigate to /login first to establish the origin
    await page.goto("/login");

    // Seed localStorage with test user auth
    await page.evaluate(
      ({ key, user }) => {
        localStorage.setItem(key, JSON.stringify(user));
      },
      { key: STORAGE_KEY, user: TEST_USER },
    );

    await use(page);
  },
});

export { expect } from "@playwright/test";

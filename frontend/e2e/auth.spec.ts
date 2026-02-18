import { test, expect } from "@playwright/test";
import { STORAGE_KEY, PROTECTED_ROUTES } from "./helpers/constants";

test.describe("Authentication", () => {
  test.describe("Protected route redirects", () => {
    for (const route of PROTECTED_ROUTES) {
      test(`${route} redirects to /login when unauthenticated`, async ({
        page,
      }) => {
        await page.goto(route);
        await expect(page).toHaveURL(/\/login/);
      });
    }
  });

  test("email login flow", async ({ page }) => {
    await page.goto("/login");

    await page.getByLabel("Email address").fill("user@company.com");
    await page.getByLabel("Password").fill("password123");
    await page.getByRole("button", { name: "Sign in" }).click();

    // Wait for redirect to dashboard
    await expect(page).toHaveURL("/", { timeout: 10_000 });
  });

  test("Google SSO login", async ({ page }) => {
    await page.goto("/login");
    await page.getByRole("button", { name: "Continue with Google" }).click();
    await expect(page).toHaveURL("/", { timeout: 10_000 });
  });

  test("Microsoft SSO login", async ({ page }) => {
    await page.goto("/login");
    await page
      .getByRole("button", { name: "Continue with Microsoft" })
      .click();
    await expect(page).toHaveURL("/", { timeout: 10_000 });
  });

  test("logout clears session and redirects to /login", async ({ page }) => {
    // Log in first via email
    await page.goto("/login");
    await page.getByLabel("Email address").fill("user@company.com");
    await page.getByLabel("Password").fill("password123");
    await page.getByRole("button", { name: "Sign in" }).click();
    await expect(page).toHaveURL("/", { timeout: 10_000 });

    // Click the sign out button
    await page.getByTitle("Sign out").click();
    await expect(page).toHaveURL(/\/login/);

    // Verify localStorage is cleared
    const stored = await page.evaluate(
      (key) => localStorage.getItem(key),
      STORAGE_KEY,
    );
    expect(stored).toBeNull();
  });

  test("already authenticated user on /login redirects to /", async ({
    page,
  }) => {
    // Log in first
    await page.goto("/login");
    await page.getByLabel("Email address").fill("user@company.com");
    await page.getByLabel("Password").fill("password123");
    await page.getByRole("button", { name: "Sign in" }).click();
    await expect(page).toHaveURL("/", { timeout: 10_000 });

    // Navigate back to /login
    await page.goto("/login");
    await expect(page).toHaveURL("/", { timeout: 10_000 });
  });
});

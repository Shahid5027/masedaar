import { expect, test } from "@playwright/test";

async function signIn(page: import("@playwright/test").Page, username: string, password: string) {
  await page.goto("/login");
  await page.getByLabel(/Username or Email/i).fill(username);
  await page.getByLabel(/Password/i).fill(password);
  await page.getByRole("button", { name: /Sign In/i }).click();
  await expect(page).toHaveURL(/\/$/);
}

test.describe("EDUCORE PS3 Phase 5 End-to-End Browser Verification", () => {
  test("redirects unauthenticated visits to /login and rejects invalid credentials", async ({ page }) => {
    await page.goto("/");
    await expect(page).toHaveURL(/\/login$/);

    await page.getByLabel(/Username or Email/i).fill("nobody");
    await page.getByLabel(/Password/i).fill("WrongPassword1!");
    await page.getByRole("button", { name: /Sign In/i }).click();
    await expect(page.getByRole("alert")).toBeVisible();
  });

  test("enforces viewer RBAC restrictions across navigation, UI controls, and direct routes", async ({
    page,
  }) => {
    await signIn(page, "viewer.e2e", "ViewerPass123!");
    await expect(page.getByText("E2E Viewer")).toBeVisible();

    // Viewer sees Overview & Model Analytics, never admin/counsellor workspaces or Run Predictions
    await expect(page.getByRole("link", { name: "Overview" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Model Analytics" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Data Management" })).toHaveCount(0);
    await expect(page.getByRole("link", { name: "Student Risk Analysis" })).toHaveCount(0);
    await expect(page.getByRole("link", { name: "Interventions" })).toHaveCount(0);
    await expect(page.getByRole("link", { name: "Administration" })).toHaveCount(0);
    await expect(page.getByRole("button", { name: /Run Predictions/i })).toHaveCount(0);
    await expect(page.getByRole("button", { name: /Notifications/i })).toHaveCount(0);

    // Direct navigation to restricted routes renders 403 Access Restricted
    for (const route of ["/data", "/students", "/interventions", "/admin"]) {
      await page.goto(route);
      await expect(page.getByText(/403 — Access Restricted/i)).toBeVisible();
    }

    // Viewer can view Model Analytics metrics without Train Model button
    await page.goto("/model");
    await expect(page.getByText(/Accuracy/i)).toBeVisible();
    await expect(page.getByRole("button", { name: /Train Model/i })).toHaveCount(0);

    // Sign out cleanly
    await page.getByRole("button", { name: /Sign Out/i }).click();
    await expect(page).toHaveURL(/\/login$/);
  });

  test("supports counsellor student analysis, intervention lifecycle, notifications, and session expiry", async ({
    page,
    context,
  }) => {
    await signIn(page, "counsellor.e2e", "CounsellorPass123!");
    await expect(page.getByText("E2E Counsellor")).toBeVisible();

    // Counsellor sees Students & Interventions, NOT Data Management or Administration
    await expect(page.getByRole("link", { name: "Student Risk Analysis" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Interventions" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Data Management" })).toHaveCount(0);
    await expect(page.getByRole("link", { name: "Administration" })).toHaveCount(0);

    // Direct route block check
    await page.goto("/admin");
    await expect(page.getByText(/403 — Access Restricted/i)).toBeVisible();

    // Student Risk Analysis search + profile + explainability
    await page.goto("/students");
    const searchInput = page.getByLabel("Search by Student ID");
    await searchInput.fill("SYNTH-STU-0001");
    await expect(page.getByRole("link", { name: "SYNTH-STU-0001" })).toBeVisible();
    await page.getByRole("link", { name: "SYNTH-STU-0001" }).click();
    await expect(page).toHaveURL(/\/students\/SYNTH-STU-0001/);
    await expect(page.getByRole("heading", { name: /Student SYNTH-STU-0001/i })).toBeVisible();
    // Admin-only rescore button must not appear for counsellor
    await expect(page.getByRole("button", { name: /Re-Score Student|Generate Risk Score/i })).toHaveCount(0);

    // Interventions lifecycle: create, assign, follow-up, note, transition status, verify history
    await page.goto("/interventions");
    await page.getByRole("button", { name: /Create Intervention/i }).click();
    await page.getByLabel(/Student ID/i).fill("SYNTH-STU-0001");
    await page
      .getByLabel(/Action Description/i)
      .fill("Phase 5 E2E advisor support planning session");
    await page
      .getByRole("button", { name: /^Create Intervention$/i })
      .last()
      .click();

    await expect(page.getByText(/Created intervention #/i)).toBeVisible();
    await page.getByLabel(/Assigned Counsellor/i).fill("counsellor.e2e");
    await page.getByLabel(/Workflow Status/i).selectOption("IN_PROGRESS");
    await page.getByLabel(/Follow-Up Date/i).fill("2026-12-15");
    await page.getByLabel(/Counsellor Notes & Outcomes/i).fill("Scheduled E2E advising session");
    await page.getByRole("button", { name: /Save Changes/i }).click();

    await expect(page.getByText(/Saved intervention #.*v2/i)).toBeVisible();
    await expect(page.getByText(/Verified Audit Actor & Version/i)).toBeVisible();
    await expect(page.getByText(/counsellor\.e2e \(counsellor\)/i).first()).toBeVisible();

    // Open in-app Notifications bell
    await page.getByRole("button", { name: /Notifications/i }).click();
    await expect(page.getByRole("dialog", { name: /In-app notifications/i })).toBeVisible();
    const scanDone = page.waitForResponse((res) =>
      res.url().includes("/notifications") && res.request().method() === "GET" && res.status() === 200
    );
    await page.getByRole("button", { name: /Scan Due/i }).click();
    await scanDone;
    await page.getByRole("button", { name: /Notifications/i }).click();

    // Session expiry / invalidation redirect check
    await context.clearCookies();
    await page.getByRole("button", { name: /Refresh/i }).first().click();
    await expect(page).toHaveURL(/\/login\?reason=expired/);
    await expect(page.getByText(/session expired/i)).toBeVisible();
  });

  test("supports administrator operations, user provisioning, audit log inspection, and case archival", async ({
    page,
  }) => {
    await signIn(page, "admin.e2e", "AdminPass123!");
    await expect(page.getByText("E2E Administrator")).toBeVisible();
    await expect(page.getByRole("link", { name: "Data Management" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Administration" })).toBeVisible();

    // Admin workspace: telemetry, user creation, audit log inspection
    await page.goto("/admin");
    await expect(page.getByText("Operational Telemetry")).toBeVisible();
    await page.getByLabel("Username").fill("counsellor.new");
    await page.getByLabel("Institutional Email").fill("new.counsellor@university.edu");
    await page.getByLabel("Full Name").fill("New Counsellor");
    await page.getByLabel(/Temporary Password/i).fill("ValidPass123!");
    await page.getByRole("button", { name: /Create Account/i }).click();
    await expect(page.getByText(/Created user 'counsellor\.new'/i)).toBeVisible();
    await expect(page.getByText(/LOGIN_SUCCESS/i).first()).toBeVisible();

    // Archive an intervention case as admin
    await page.goto("/interventions");
    await page.getByRole("button", { name: "Manage" }).first().click();
    await expect(page.getByRole("button", { name: /Archive Case/i })).toBeVisible();
    await page.getByRole("button", { name: /Archive Case/i }).click();
    await expect(page.getByText(/Archived intervention #/i)).toBeVisible();

    // Sign out
    await page.getByRole("button", { name: /Sign Out/i }).click();
    await expect(page).toHaveURL(/\/login$/);
  });
});


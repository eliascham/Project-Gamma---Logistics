export const STORAGE_KEY = "gamma-auth";

export const TEST_USER = {
  name: "Test User",
  email: "test@company.com",
  method: "email" as const,
};

/** Sidebar nav labels (order matches sidebar.tsx) */
export const NAV_LABELS = [
  "Dashboard",
  "Documents",
  "Upload",
  "Allocations",
  "Q&A Chat",
  "Review Queue",
  "Anomalies",
  "Reconciliation",
  "Data Explorer",
  "Audit Log",
] as const;

/** Route path → header h1 text (from header.tsx routeTitles) */
export const ROUTE_TITLES: Record<string, string> = {
  "/": "Dashboard",
  "/documents": "Documents",
  "/documents/upload": "Upload Document",
  "/allocations": "Cost Allocations",
  "/chat": "Document Q&A",
  "/reviews": "Review Queue",
  "/anomalies": "Anomalies",
  "/reconciliation": "Reconciliation",
  "/data-explorer": "Data Explorer",
  "/audit": "Audit Log",
};

/** All protected routes (used for redirect tests) */
export const PROTECTED_ROUTES = Object.keys(ROUTE_TITLES);

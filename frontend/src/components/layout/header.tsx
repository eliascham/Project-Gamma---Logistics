"use client";

import { usePathname } from "next/navigation";
import { Badge } from "@/components/ui/badge";
import { useAuth } from "@/lib/auth-context";

const routeTitles: Record<string, string> = {
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

const ssoLabels: Record<string, string> = {
  google: "Google SSO",
  microsoft: "Microsoft SSO",
  email: "Email",
};

export function Header() {
  const pathname = usePathname();
  const { user } = useAuth();
  const title = routeTitles[pathname] || "Detail";

  return (
    <header className="flex h-14 items-center justify-between border-b px-6">
      <div className="flex items-center gap-3">
        <h1 className="text-sm font-semibold">{title}</h1>
        <span className="text-xs text-muted-foreground">
          Logistics Operations Intelligence
        </span>
      </div>
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-1.5">
          <div className="size-2 rounded-full bg-green-500" />
          <span className="text-xs text-muted-foreground">Online</span>
        </div>
        {user && (
          <Badge variant="secondary" className="text-xs gap-1.5">
            {ssoLabels[user.method] || user.method}
          </Badge>
        )}
        <Badge variant="outline" className="text-xs">
          Phase 4
        </Badge>
      </div>
    </header>
  );
}

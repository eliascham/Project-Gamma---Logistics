"use client";

import { usePathname } from "next/navigation";
import { Badge } from "@/components/ui/badge";

const routeTitles: Record<string, string> = {
  "/": "Dashboard",
  "/documents": "Documents",
  "/documents/upload": "Upload Document",
};

export function Header() {
  const pathname = usePathname();
  const title = routeTitles[pathname] || "Document Detail";

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
        <Badge variant="outline" className="text-xs">
          Phase 2
        </Badge>
      </div>
    </header>
  );
}

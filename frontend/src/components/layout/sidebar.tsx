"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { motion } from "framer-motion";
import { LayoutDashboard, FileText, Upload, Zap } from "lucide-react";
import { Separator } from "@/components/ui/separator";
import { ThemeToggle } from "@/components/ui/theme-toggle";

const navItems = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/documents", label: "Documents", icon: FileText },
  { href: "/documents/upload", label: "Upload", icon: Upload },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="flex w-60 flex-col border-r bg-sidebar">
      <div className="flex h-14 items-center gap-2.5 px-4">
        <div className="flex size-8 items-center justify-center rounded-lg bg-primary">
          <Zap className="size-4 text-primary-foreground" />
        </div>
        <span className="font-semibold tracking-tight">Project Gamma</span>
      </div>
      <Separator />
      <nav className="flex-1 space-y-1 p-3">
        {navItems.map((item) => {
          const isActive =
            item.href === "/"
              ? pathname === "/"
              : pathname.startsWith(item.href) && item.href !== "/";
          const Icon = item.icon;

          return (
            <Link key={item.href} href={item.href} className="relative block">
              {isActive && (
                <motion.div
                  layoutId="sidebar-active"
                  className="absolute inset-0 rounded-lg bg-accent"
                  transition={{ type: "spring", stiffness: 350, damping: 30 }}
                />
              )}
              <motion.div
                whileHover={{ x: 2 }}
                transition={{ type: "spring", stiffness: 300, damping: 20 }}
                className={`relative flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition-colors ${
                  isActive
                    ? "font-medium text-accent-foreground"
                    : "text-muted-foreground hover:text-foreground"
                }`}
              >
                <Icon className="size-4" />
                {item.label}
              </motion.div>
            </Link>
          );
        })}
      </nav>
      <div className="flex items-center justify-between border-t p-3">
        <span className="text-xs text-muted-foreground">v0.2.0</span>
        <ThemeToggle />
      </div>
    </aside>
  );
}

"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import {
  ClipboardCheck,
  Clock,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Loader2,
  Shield,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import {
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { PageTransition } from "@/components/shared/page-transition";
import { AnimatedCard } from "@/components/shared/animated-card";
import { EmptyState } from "@/components/shared/empty-state";
import { TableRowSkeleton } from "@/components/shared/loading-skeleton";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface ReviewStats {
  pending: number;
  approved: number;
  rejected: number;
  escalated: number;
}

interface ReviewItem {
  id: string;
  title: string;
  entity_type: string;
  review_type: string;
  severity: string;
  status: string;
  dollar_amount: number | null;
  created_at: string;
}

const statusConfig: Record<
  string,
  { variant: "default" | "secondary" | "destructive" | "outline"; className?: string }
> = {
  pending_review: { variant: "outline", className: "border-yellow-500 text-yellow-600" },
  approved: { variant: "default", className: "bg-green-600 hover:bg-green-700" },
  rejected: { variant: "destructive" },
  escalated: { variant: "outline", className: "border-orange-500 text-orange-600" },
  auto_approved: { variant: "secondary", className: "bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300" },
};

const severityConfig: Record<
  string,
  { variant: "default" | "secondary" | "destructive" | "outline"; className?: string }
> = {
  low: { variant: "secondary", className: "bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300" },
  medium: { variant: "outline", className: "border-yellow-500 text-yellow-600" },
  high: { variant: "outline", className: "border-orange-500 text-orange-600" },
  critical: { variant: "destructive" },
};

const listContainer = { hidden: {}, show: { transition: { staggerChildren: 0.04 } } };
const listItem = { hidden: { opacity: 0, x: -10 }, show: { opacity: 1, x: 0 } };

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

function formatCurrency(amount: number | null): string {
  if (amount == null) return "--";
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
  }).format(amount);
}

export default function ReviewsPage() {
  const router = useRouter();
  const [items, setItems] = useState<ReviewItem[]>([]);
  const [stats, setStats] = useState<ReviewStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const [queueRes, statsRes] = await Promise.all([
          fetch(`${API_BASE}/api/v1/reviews/queue`),
          fetch(`${API_BASE}/api/v1/reviews/stats`),
        ]);
        if (queueRes.ok) {
          const queueData = await queueRes.json();
          setItems(queueData.items || []);
        }
        if (statsRes.ok) {
          const statsData = await statsRes.json();
          setStats(statsData);
        }
      } catch (err: unknown) {
        setError(err instanceof Error ? err.message : "Failed to load review queue");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  const statCards = [
    {
      label: "Pending",
      value: stats?.pending ?? 0,
      icon: Clock,
      color: "text-yellow-600 dark:text-yellow-400",
    },
    {
      label: "Approved",
      value: stats?.approved ?? 0,
      icon: CheckCircle2,
      color: "text-green-600 dark:text-green-400",
    },
    {
      label: "Rejected",
      value: stats?.rejected ?? 0,
      icon: XCircle,
      color: "text-red-600 dark:text-red-400",
    },
    {
      label: "Escalated",
      value: stats?.escalated ?? 0,
      icon: AlertTriangle,
      color: "text-orange-600 dark:text-orange-400",
    },
  ];

  return (
    <PageTransition>
      <div className="space-y-6">
        {/* Header */}
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Review Queue</h2>
          <p className="text-muted-foreground">
            Human-in-the-loop review for flagged items
          </p>
        </div>

        {/* Stats cards */}
        <div className="grid gap-4 md:grid-cols-4">
          {statCards.map((card, i) => (
            <AnimatedCard key={card.label} delay={i * 0.05}>
              <CardHeader className="pb-2">
                <CardDescription className="flex items-center gap-2">
                  <card.icon className={`size-4 ${card.color}`} />
                  {card.label}
                </CardDescription>
                <CardTitle className={`text-2xl tabular-nums ${card.color}`}>
                  {card.value}
                </CardTitle>
              </CardHeader>
            </AnimatedCard>
          ))}
        </div>

        {error && (
          <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive">
            {error}
          </div>
        )}

        {/* Table */}
        {loading ? (
          <TableRowSkeleton rows={5} />
        ) : items.length === 0 ? (
          <EmptyState
            icon={ClipboardCheck}
            title="No items in review queue"
            description="All items have been reviewed. New items will appear here when they require human approval."
          />
        ) : (
          <motion.div
            variants={listContainer}
            initial="hidden"
            animate="show"
          >
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Title</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Severity</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Dollar Amount</TableHead>
                  <TableHead>Created</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {items.map((item) => {
                  const sc = statusConfig[item.status] || { variant: "outline" as const };
                  const sev = severityConfig[item.severity] || { variant: "outline" as const };
                  return (
                    <motion.tr
                      key={item.id}
                      variants={listItem}
                      onClick={() => router.push(`/reviews/${item.id}`)}
                      className="cursor-pointer transition-colors hover:bg-accent/50"
                    >
                      <TableCell>
                        <div className="flex items-center gap-2.5">
                          <Shield className="size-4 text-muted-foreground" />
                          <span className="font-medium">{item.title}</span>
                        </div>
                      </TableCell>
                      <TableCell>
                        <span className="rounded bg-muted px-1.5 py-0.5 text-xs font-mono uppercase">
                          {item.review_type}
                        </span>
                      </TableCell>
                      <TableCell>
                        <Badge variant={sev.variant} className={sev.className}>
                          {item.severity}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <Badge variant={sc.variant} className={sc.className}>
                          {item.status.replace(/_/g, " ")}
                        </Badge>
                      </TableCell>
                      <TableCell className="tabular-nums">
                        {formatCurrency(item.dollar_amount)}
                      </TableCell>
                      <TableCell className="text-muted-foreground">
                        {formatDate(item.created_at)}
                      </TableCell>
                    </motion.tr>
                  );
                })}
              </TableBody>
            </Table>
          </motion.div>
        )}
      </div>
    </PageTransition>
  );
}

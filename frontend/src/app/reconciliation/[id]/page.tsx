"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { motion } from "framer-motion";
import {
  ArrowLeft,
  GitCompare,
  Loader2,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Clock,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  CardContent,
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
import { AnimatedCard } from "@/components/shared/animated-card";
import { PageTransition } from "@/components/shared/page-transition";
import { TableRowSkeleton } from "@/components/shared/loading-skeleton";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface ReconciliationRecord {
  id: string;
  source_system: string;
  reference: string;
  record_type: string;
  match_status: string;
  confidence: number;
  reasoning: string;
}

interface ReconciliationRunDetail {
  id: string;
  name: string;
  status: string;
  match_rate: number;
  total_records: number;
  matched_count: number;
  mismatched_count: number;
  records: ReconciliationRecord[];
  created_at: string;
}

const matchStatusConfig: Record<
  string,
  { variant: "default" | "secondary" | "destructive" | "outline"; className?: string; icon: typeof CheckCircle2 }
> = {
  matched: { variant: "default", className: "bg-green-600 hover:bg-green-700", icon: CheckCircle2 },
  mismatch: { variant: "destructive", icon: XCircle },
  partial_match: { variant: "outline", className: "border-yellow-500 text-yellow-600", icon: AlertTriangle },
  pending: { variant: "secondary", icon: Clock },
};

const sourceConfig: Record<string, { className: string }> = {
  TMS: { className: "bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300" },
  WMS: { className: "bg-purple-100 text-purple-700 dark:bg-purple-900 dark:text-purple-300" },
  ERP: { className: "bg-emerald-100 text-emerald-700 dark:bg-emerald-900 dark:text-emerald-300" },
};

const listContainer = { hidden: {}, show: { transition: { staggerChildren: 0.03 } } };
const listItem = { hidden: { opacity: 0, x: -10 }, show: { opacity: 1, x: 0 } };

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function getMatchRateColor(rate: number): string {
  if (rate >= 0.8) return "bg-green-500";
  if (rate >= 0.6) return "bg-yellow-500";
  return "bg-red-500";
}

function getMatchRateTextColor(rate: number): string {
  if (rate >= 0.8) return "text-green-600 dark:text-green-400";
  if (rate >= 0.6) return "text-yellow-600 dark:text-yellow-400";
  return "text-red-600 dark:text-red-400";
}

export default function ReconciliationDetailPage() {
  const params = useParams();
  const router = useRouter();
  const runId = params.id as string;

  const [run, setRun] = useState<ReconciliationRunDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const res = await fetch(`${API_BASE}/api/v1/reconciliation/${runId}`);
        if (!res.ok) throw new Error("Failed to load reconciliation run");
        const data = await res.json();
        setRun(data);
      } catch (err: unknown) {
        setError(err instanceof Error ? err.message : "Failed to load");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [runId]);

  if (loading) {
    return (
      <PageTransition>
        <div className="flex items-center justify-center py-20">
          <Loader2 className="size-6 animate-spin text-muted-foreground" />
        </div>
      </PageTransition>
    );
  }

  if (!run) {
    return (
      <PageTransition>
        <div className="text-center py-20 text-muted-foreground">
          Reconciliation run not found.
        </div>
      </PageTransition>
    );
  }

  const ratePercent = Math.round(run.match_rate * 100);

  return (
    <PageTransition>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center gap-4">
          <Button
            variant="ghost"
            size="icon"
            onClick={() => router.push("/reconciliation")}
          >
            <ArrowLeft className="size-4" />
          </Button>
          <div className="flex-1">
            <h2 className="text-2xl font-bold tracking-tight">{run.name}</h2>
            <p className="text-muted-foreground">
              Created {formatDate(run.created_at)}
            </p>
          </div>
          <Badge
            variant={run.status === "completed" ? "default" : "secondary"}
          >
            {run.status}
          </Badge>
        </div>

        {error && (
          <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive">
            {error}
          </div>
        )}

        {/* Summary cards */}
        <div className="grid gap-4 md:grid-cols-4">
          <AnimatedCard delay={0}>
            <CardHeader className="pb-2">
              <CardDescription>Total Records</CardDescription>
              <CardTitle className="text-2xl tabular-nums">
                {run.total_records}
              </CardTitle>
            </CardHeader>
          </AnimatedCard>

          <AnimatedCard delay={0.05}>
            <CardHeader className="pb-2">
              <CardDescription className="flex items-center gap-2">
                <CheckCircle2 className="size-4 text-green-600" />
                Matched
              </CardDescription>
              <CardTitle className="text-2xl tabular-nums text-green-600 dark:text-green-400">
                {run.matched_count}
              </CardTitle>
            </CardHeader>
          </AnimatedCard>

          <AnimatedCard delay={0.1}>
            <CardHeader className="pb-2">
              <CardDescription className="flex items-center gap-2">
                <XCircle className="size-4 text-red-600" />
                Mismatched
              </CardDescription>
              <CardTitle className="text-2xl tabular-nums text-red-600 dark:text-red-400">
                {run.mismatched_count}
              </CardTitle>
            </CardHeader>
          </AnimatedCard>

          <AnimatedCard delay={0.15}>
            <CardHeader className="pb-2">
              <CardDescription>Match Rate</CardDescription>
              <div className="space-y-2">
                <CardTitle className={`text-2xl tabular-nums ${getMatchRateTextColor(run.match_rate)}`}>
                  {ratePercent}%
                </CardTitle>
                <div className="h-2 rounded-full bg-muted overflow-hidden">
                  <motion.div
                    className={`h-full rounded-full ${getMatchRateColor(run.match_rate)}`}
                    initial={{ width: 0 }}
                    animate={{ width: `${ratePercent}%` }}
                    transition={{ duration: 1, ease: "easeOut" }}
                  />
                </div>
              </div>
            </CardHeader>
          </AnimatedCard>
        </div>

        {/* Records table */}
        <AnimatedCard delay={0.2}>
          <CardHeader>
            <CardTitle>Records</CardTitle>
            <CardDescription>
              Individual reconciliation records across source systems
            </CardDescription>
          </CardHeader>
          <CardContent>
            {run.records.length === 0 ? (
              <p className="text-sm text-muted-foreground text-center py-8">
                No records in this reconciliation run.
              </p>
            ) : (
              <motion.div
                variants={listContainer}
                initial="hidden"
                animate="show"
              >
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Source</TableHead>
                      <TableHead>Reference</TableHead>
                      <TableHead>Type</TableHead>
                      <TableHead>Match Status</TableHead>
                      <TableHead>Confidence</TableHead>
                      <TableHead>Reasoning</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {run.records.map((record) => {
                      const ms = matchStatusConfig[record.match_status] || {
                        variant: "outline" as const,
                        icon: Clock,
                      };
                      const src = sourceConfig[record.source_system] || {
                        className: "bg-muted",
                      };
                      const StatusIcon = ms.icon;
                      const confidencePercent = Math.round(record.confidence * 100);
                      return (
                        <motion.tr
                          key={record.id}
                          variants={listItem}
                          className="transition-colors hover:bg-accent/50"
                        >
                          <TableCell>
                            <Badge variant="secondary" className={src.className}>
                              {record.source_system}
                            </Badge>
                          </TableCell>
                          <TableCell>
                            <span className="font-mono text-sm">{record.reference}</span>
                          </TableCell>
                          <TableCell>
                            <span className="rounded bg-muted px-1.5 py-0.5 text-xs font-mono uppercase">
                              {record.record_type}
                            </span>
                          </TableCell>
                          <TableCell>
                            <Badge variant={ms.variant} className={ms.className}>
                              <StatusIcon className="size-3 mr-1" />
                              {record.match_status.replace(/_/g, " ")}
                            </Badge>
                          </TableCell>
                          <TableCell>
                            <span className="text-sm font-medium tabular-nums">
                              {confidencePercent}%
                            </span>
                          </TableCell>
                          <TableCell className="max-w-[300px]">
                            <span className="text-sm text-muted-foreground truncate block">
                              {record.reasoning}
                            </span>
                          </TableCell>
                        </motion.tr>
                      );
                    })}
                  </TableBody>
                </Table>
              </motion.div>
            )}
          </CardContent>
        </AnimatedCard>
      </div>
    </PageTransition>
  );
}

"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import {
  GitCompare,
  Loader2,
  PlayCircle,
  Sparkles,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { PageTransition } from "@/components/shared/page-transition";
import { EmptyState } from "@/components/shared/empty-state";
import { TableRowSkeleton } from "@/components/shared/loading-skeleton";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface ReconciliationRun {
  id: string;
  name: string;
  status: string;
  match_rate: number;
  total_records: number;
  created_at: string;
}

const statusConfig: Record<
  string,
  { variant: "default" | "secondary" | "destructive" | "outline"; label: string }
> = {
  pending: { variant: "outline", label: "Pending" },
  running: { variant: "secondary", label: "Running" },
  completed: { variant: "default", label: "Completed" },
  failed: { variant: "destructive", label: "Failed" },
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

export default function ReconciliationPage() {
  const router = useRouter();
  const [runs, setRuns] = useState<ReconciliationRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [seeding, setSeeding] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadRuns = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/v1/reconciliation`);
      if (res.ok) {
        const data = await res.json();
        setRuns(data.runs || []);
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load reconciliation runs");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadRuns();
  }, []);

  const handleRun = async () => {
    setRunning(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/api/v1/reconciliation/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
      });
      if (!res.ok) {
        const detail = await res.text();
        throw new Error(detail || "Reconciliation failed");
      }
      await loadRuns();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Reconciliation failed");
    } finally {
      setRunning(false);
    }
  };

  const handleSeed = async () => {
    setSeeding(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/api/v1/reconciliation/seed`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
      });
      if (!res.ok) {
        const detail = await res.text();
        throw new Error(detail || "Seed failed");
      }
      await loadRuns();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Seed failed");
    } finally {
      setSeeding(false);
    }
  };

  return (
    <PageTransition>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-2xl font-bold tracking-tight">
              Reconciliation
            </h2>
            <p className="text-muted-foreground">
              Cross-system data matching and reconciliation
            </p>
          </div>
          <div className="flex items-center gap-2">
            <motion.div whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }}>
              <Button
                variant="outline"
                className="gap-2"
                onClick={handleSeed}
                disabled={seeding}
              >
                {seeding ? (
                  <Loader2 className="size-4 animate-spin" />
                ) : (
                  <Sparkles className="size-4" />
                )}
                Seed Mock Data
              </Button>
            </motion.div>
            <motion.div whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }}>
              <Button
                className="gap-2"
                onClick={handleRun}
                disabled={running}
              >
                {running ? (
                  <Loader2 className="size-4 animate-spin" />
                ) : (
                  <PlayCircle className="size-4" />
                )}
                {running ? "Running..." : "Run Reconciliation"}
              </Button>
            </motion.div>
          </div>
        </div>

        {error && (
          <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive">
            {error}
          </div>
        )}

        {/* Table */}
        {loading ? (
          <TableRowSkeleton rows={5} />
        ) : runs.length === 0 ? (
          <EmptyState
            icon={GitCompare}
            title="No reconciliation runs"
            description="Seed mock data and run a reconciliation to match records across TMS, WMS, and ERP systems."
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
                  <TableHead>Name</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Match Rate</TableHead>
                  <TableHead>Records</TableHead>
                  <TableHead>Created</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {runs.map((run) => {
                  const sc = statusConfig[run.status] || { variant: "outline" as const, label: run.status };
                  const ratePercent = Math.round(run.match_rate * 100);
                  return (
                    <motion.tr
                      key={run.id}
                      variants={listItem}
                      onClick={() => router.push(`/reconciliation/${run.id}`)}
                      className="cursor-pointer transition-colors hover:bg-accent/50"
                    >
                      <TableCell>
                        <div className="flex items-center gap-2.5">
                          <GitCompare className="size-4 text-muted-foreground" />
                          <span className="font-medium">{run.name}</span>
                        </div>
                      </TableCell>
                      <TableCell>
                        <Badge variant={sc.variant}>{sc.label}</Badge>
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center gap-3 min-w-[140px]">
                          <div className="flex-1 h-2 rounded-full bg-muted overflow-hidden">
                            <motion.div
                              className={`h-full rounded-full ${getMatchRateColor(run.match_rate)}`}
                              initial={{ width: 0 }}
                              animate={{ width: `${ratePercent}%` }}
                              transition={{ duration: 0.8, ease: "easeOut" }}
                            />
                          </div>
                          <span className={`text-sm font-medium tabular-nums ${getMatchRateTextColor(run.match_rate)}`}>
                            {ratePercent}%
                          </span>
                        </div>
                      </TableCell>
                      <TableCell className="tabular-nums">
                        {run.total_records}
                      </TableCell>
                      <TableCell className="text-muted-foreground">
                        {formatDate(run.created_at)}
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

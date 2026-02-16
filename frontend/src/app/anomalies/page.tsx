"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import {
  AlertTriangle,
  Loader2,
  RefreshCw,
  Shield,
  CheckCircle2,
  XCircle,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
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

interface Anomaly {
  id: string;
  title: string;
  anomaly_type: string;
  severity: string;
  resolved: boolean;
  created_at: string;
}

interface AnomalyStats {
  total: number;
  by_severity: Record<string, number>;
  resolved: number;
  unresolved: number;
}

const severityConfig: Record<
  string,
  { variant: "default" | "secondary" | "destructive" | "outline"; className?: string }
> = {
  low: { variant: "secondary", className: "bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300" },
  medium: { variant: "outline", className: "border-yellow-500 text-yellow-600" },
  high: { variant: "outline", className: "border-orange-500 text-orange-600" },
  critical: { variant: "destructive" },
};

const severityOrder: Record<string, number> = { critical: 0, high: 1, medium: 2, low: 3 };

const listContainer = { hidden: {}, show: { transition: { staggerChildren: 0.04 } } };
const listItem = { hidden: { opacity: 0, x: -10 }, show: { opacity: 1, x: 0 } };

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

export default function AnomaliesPage() {
  const router = useRouter();
  const [anomalies, setAnomalies] = useState<Anomaly[]>([]);
  const [stats, setStats] = useState<AnomalyStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [scanning, setScanning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadData = async () => {
    try {
      const [listRes, statsRes] = await Promise.all([
        fetch(`${API_BASE}/api/v1/anomalies`),
        fetch(`${API_BASE}/api/v1/anomalies/stats`),
      ]);
      if (listRes.ok) {
        const listData = await listRes.json();
        setAnomalies(listData.anomalies || []);
      }
      if (statsRes.ok) {
        const statsData = await statsRes.json();
        setStats(statsData);
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load anomalies");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleScan = async () => {
    setScanning(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/api/v1/anomalies/scan`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
      });
      if (!res.ok) {
        const detail = await res.text();
        throw new Error(detail || "Scan failed");
      }
      // Reload data after scan
      await loadData();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Scan failed");
    } finally {
      setScanning(false);
    }
  };

  const severityCards = ["critical", "high", "medium", "low"].map((sev) => ({
    label: sev.charAt(0).toUpperCase() + sev.slice(1),
    value: stats?.by_severity?.[sev] ?? 0,
    severity: sev,
  }));

  const severityColors: Record<string, string> = {
    critical: "text-red-600 dark:text-red-400",
    high: "text-orange-600 dark:text-orange-400",
    medium: "text-yellow-600 dark:text-yellow-400",
    low: "text-blue-600 dark:text-blue-400",
  };

  const severityIcons: Record<string, typeof AlertTriangle> = {
    critical: XCircle,
    high: AlertTriangle,
    medium: AlertTriangle,
    low: Shield,
  };

  return (
    <PageTransition>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-2xl font-bold tracking-tight">Anomalies</h2>
            <p className="text-muted-foreground">
              AI-detected anomalies in documents and allocations
            </p>
          </div>
          <motion.div whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }}>
            <Button
              className="gap-2"
              onClick={handleScan}
              disabled={scanning}
            >
              {scanning ? (
                <Loader2 className="size-4 animate-spin" />
              ) : (
                <RefreshCw className="size-4" />
              )}
              {scanning ? "Scanning..." : "Run Anomaly Scan"}
            </Button>
          </motion.div>
        </div>

        {/* Stats cards by severity */}
        <div className="grid gap-4 md:grid-cols-4">
          {severityCards.map((card, i) => {
            const Icon = severityIcons[card.severity];
            return (
              <AnimatedCard key={card.severity} delay={i * 0.05}>
                <CardHeader className="pb-2">
                  <CardDescription className="flex items-center gap-2">
                    <Icon className={`size-4 ${severityColors[card.severity]}`} />
                    {card.label}
                  </CardDescription>
                  <CardTitle className={`text-2xl tabular-nums ${severityColors[card.severity]}`}>
                    {card.value}
                  </CardTitle>
                </CardHeader>
              </AnimatedCard>
            );
          })}
        </div>

        {error && (
          <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive">
            {error}
          </div>
        )}

        {/* Table */}
        {loading ? (
          <TableRowSkeleton rows={5} />
        ) : anomalies.length === 0 ? (
          <EmptyState
            icon={AlertTriangle}
            title="No anomalies detected"
            description="Run an anomaly scan to check for issues in your documents and allocations."
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
                  <TableHead>Resolved</TableHead>
                  <TableHead>Created</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {anomalies
                  .sort((a, b) => (severityOrder[a.severity] ?? 99) - (severityOrder[b.severity] ?? 99))
                  .map((anomaly) => {
                    const sev = severityConfig[anomaly.severity] || { variant: "outline" as const };
                    return (
                      <motion.tr
                        key={anomaly.id}
                        variants={listItem}
                        onClick={() => router.push(`/anomalies/${anomaly.id}`)}
                        className="cursor-pointer transition-colors hover:bg-accent/50"
                      >
                        <TableCell>
                          <div className="flex items-center gap-2.5">
                            <AlertTriangle className="size-4 text-muted-foreground" />
                            <span className="font-medium">{anomaly.title}</span>
                          </div>
                        </TableCell>
                        <TableCell>
                          <span className="rounded bg-muted px-1.5 py-0.5 text-xs font-mono uppercase">
                            {anomaly.anomaly_type}
                          </span>
                        </TableCell>
                        <TableCell>
                          <Badge variant={sev.variant} className={sev.className}>
                            {anomaly.severity}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          {anomaly.resolved ? (
                            <CheckCircle2 className="size-4 text-green-600" />
                          ) : (
                            <XCircle className="size-4 text-red-500" />
                          )}
                        </TableCell>
                        <TableCell className="text-muted-foreground">
                          {formatDate(anomaly.created_at)}
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

"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { motion } from "framer-motion";
import {
  ArrowLeft,
  AlertTriangle,
  CheckCircle2,
  Loader2,
  FileText,
  DollarSign,
  ExternalLink,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { AnimatedCard } from "@/components/shared/animated-card";
import { PageTransition } from "@/components/shared/page-transition";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface AnomalyDetail {
  id: string;
  title: string;
  anomaly_type: string;
  severity: string;
  description: string;
  details: Record<string, unknown>;
  entity_type: string | null;
  entity_id: string | null;
  document_id: string | null;
  allocation_id: string | null;
  resolved: boolean;
  resolved_by: string | null;
  resolution_notes: string | null;
  created_at: string;
  updated_at: string;
}

const severityConfig: Record<
  string,
  { variant: "default" | "secondary" | "destructive" | "outline"; className?: string; color: string }
> = {
  low: { variant: "secondary", className: "bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300", color: "text-blue-600" },
  medium: { variant: "outline", className: "border-yellow-500 text-yellow-600", color: "text-yellow-600" },
  high: { variant: "outline", className: "border-orange-500 text-orange-600", color: "text-orange-600" },
  critical: { variant: "destructive", color: "text-red-600" },
};

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function AnomalyDetailPage() {
  const params = useParams();
  const router = useRouter();
  const anomalyId = params.id as string;

  const [anomaly, setAnomaly] = useState<AnomalyDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [resolving, setResolving] = useState(false);
  const [notes, setNotes] = useState("");
  const [error, setError] = useState<string | null>(null);

  const loadAnomaly = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/v1/anomalies/${anomalyId}`);
      if (!res.ok) throw new Error("Failed to load anomaly");
      const data = await res.json();
      setAnomaly(data);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAnomaly();
  }, [anomalyId]);

  const handleResolve = async () => {
    setResolving(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/api/v1/anomalies/${anomalyId}/resolve`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          notes,
          resolved_by: "user",
        }),
      });
      if (!res.ok) {
        const detail = await res.text();
        throw new Error(detail || "Resolve failed");
      }
      const updated = await res.json();
      setAnomaly(updated);
      setNotes("");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Resolve failed");
    } finally {
      setResolving(false);
    }
  };

  if (loading) {
    return (
      <PageTransition>
        <div className="flex items-center justify-center py-20">
          <Loader2 className="size-6 animate-spin text-muted-foreground" />
        </div>
      </PageTransition>
    );
  }

  if (!anomaly) {
    return (
      <PageTransition>
        <div className="text-center py-20 text-muted-foreground">
          Anomaly not found.
        </div>
      </PageTransition>
    );
  }

  const sev = severityConfig[anomaly.severity] || {
    variant: "outline" as const,
    color: "text-muted-foreground",
  };

  return (
    <PageTransition>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center gap-4">
          <Button
            variant="ghost"
            size="icon"
            onClick={() => router.push("/anomalies")}
          >
            <ArrowLeft className="size-4" />
          </Button>
          <div className="flex-1">
            <h2 className="text-2xl font-bold tracking-tight">{anomaly.title}</h2>
            <p className="text-muted-foreground">
              {anomaly.anomaly_type.replace(/_/g, " ")} &middot; Detected {formatDate(anomaly.created_at)}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Badge variant={sev.variant} className={sev.className}>
              {anomaly.severity}
            </Badge>
            {anomaly.resolved ? (
              <Badge variant="default" className="bg-green-600 hover:bg-green-700">
                Resolved
              </Badge>
            ) : (
              <Badge variant="outline" className="border-red-500 text-red-600">
                Unresolved
              </Badge>
            )}
          </div>
        </div>

        {error && (
          <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive">
            {error}
          </div>
        )}

        {/* Summary cards */}
        <div className="grid gap-4 md:grid-cols-3">
          <AnimatedCard delay={0}>
            <CardHeader className="pb-2">
              <CardDescription className="flex items-center gap-2">
                <AlertTriangle className={`size-4 ${sev.color}`} />
                Type
              </CardDescription>
              <CardTitle className="text-sm font-mono">
                {anomaly.anomaly_type}
              </CardTitle>
            </CardHeader>
          </AnimatedCard>

          <AnimatedCard delay={0.05}>
            <CardHeader className="pb-2">
              <CardDescription className="flex items-center gap-2">
                <FileText className="size-4" />
                Entity
              </CardDescription>
              <CardTitle className="text-sm font-mono truncate">
                {anomaly.entity_type ? `${anomaly.entity_type} / ${anomaly.entity_id}` : "--"}
              </CardTitle>
            </CardHeader>
          </AnimatedCard>

          <AnimatedCard delay={0.1}>
            <CardHeader className="pb-2">
              <CardDescription>Status</CardDescription>
              <CardTitle className="text-sm">
                {anomaly.resolved
                  ? `Resolved by ${anomaly.resolved_by || "system"}`
                  : "Awaiting resolution"}
              </CardTitle>
            </CardHeader>
          </AnimatedCard>
        </div>

        {/* AI Description */}
        <AnimatedCard delay={0.15}>
          <CardHeader>
            <CardTitle>AI Description</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm leading-relaxed">{anomaly.description}</p>
          </CardContent>
        </AnimatedCard>

        {/* Details JSON */}
        {anomaly.details && Object.keys(anomaly.details).length > 0 && (
          <AnimatedCard delay={0.2}>
            <CardHeader>
              <CardTitle>Details</CardTitle>
              <CardDescription>Raw anomaly data</CardDescription>
            </CardHeader>
            <CardContent>
              <pre className="rounded-lg bg-muted p-4 text-xs font-mono overflow-x-auto">
                {JSON.stringify(anomaly.details, null, 2)}
              </pre>
            </CardContent>
          </AnimatedCard>
        )}

        {/* Related links */}
        {(anomaly.document_id || anomaly.allocation_id) && (
          <AnimatedCard delay={0.25}>
            <CardHeader>
              <CardTitle>Related Resources</CardTitle>
            </CardHeader>
            <CardContent className="flex gap-3">
              {anomaly.document_id && (
                <Button
                  variant="outline"
                  className="gap-2"
                  onClick={() => router.push(`/documents/${anomaly.document_id}`)}
                >
                  <FileText className="size-4" />
                  View Document
                  <ExternalLink className="size-3" />
                </Button>
              )}
              {anomaly.allocation_id && (
                <Button
                  variant="outline"
                  className="gap-2"
                  onClick={() => router.push(`/allocations/${anomaly.allocation_id}`)}
                >
                  <DollarSign className="size-4" />
                  View Allocation
                  <ExternalLink className="size-3" />
                </Button>
              )}
            </CardContent>
          </AnimatedCard>
        )}

        {/* Resolution history */}
        {anomaly.resolved && anomaly.resolution_notes && (
          <AnimatedCard delay={0.3}>
            <CardHeader>
              <CardTitle>Resolution</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              <div className="flex items-center gap-2 text-sm">
                <CheckCircle2 className="size-4 text-green-600" />
                <span className="text-muted-foreground">Resolved by:</span>
                <span className="font-medium">{anomaly.resolved_by}</span>
              </div>
              <p className="rounded-md bg-muted p-3 text-sm">{anomaly.resolution_notes}</p>
              <div className="text-xs text-muted-foreground">
                Updated: {formatDate(anomaly.updated_at)}
              </div>
            </CardContent>
          </AnimatedCard>
        )}

        {/* Resolve form */}
        {!anomaly.resolved && (
          <AnimatedCard delay={0.3}>
            <CardHeader>
              <CardTitle>Resolve Anomaly</CardTitle>
              <CardDescription>
                Mark this anomaly as resolved after investigation.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <label className="text-sm font-medium text-muted-foreground">
                  Resolution Notes
                </label>
                <textarea
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  placeholder="Describe how this anomaly was resolved..."
                  rows={3}
                  className="mt-1.5 w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm shadow-xs placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:border-ring"
                />
              </div>
              <motion.div whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }}>
                <Button
                  className="gap-2 bg-green-600 hover:bg-green-700 text-white"
                  onClick={handleResolve}
                  disabled={resolving}
                >
                  {resolving ? (
                    <Loader2 className="size-4 animate-spin" />
                  ) : (
                    <CheckCircle2 className="size-4" />
                  )}
                  {resolving ? "Resolving..." : "Resolve"}
                </Button>
              </motion.div>
            </CardContent>
          </AnimatedCard>
        )}
      </div>
    </PageTransition>
  );
}

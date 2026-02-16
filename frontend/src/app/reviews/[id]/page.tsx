"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { motion } from "framer-motion";
import {
  ArrowLeft,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Loader2,
  Shield,
  DollarSign,
  Tag,
  FileText,
  ExternalLink,
  Info,
  Lightbulb,
  Scale,
  Zap,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { AnimatedCard } from "@/components/shared/animated-card";
import { PageTransition } from "@/components/shared/page-transition";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface EvidenceItem {
  label: string;
  value: string;
  type: string;
}

interface SuggestedAction {
  label: string;
  action: string;
  notes: string;
  variant: string;
}

interface ReviewContext {
  anomaly_type: string | null;
  anomaly_details: Record<string, unknown> | null;
  document_name: string | null;
  document_id: string | null;
  allocation_id: string | null;
  allocation_total: number | null;
  evidence: EvidenceItem[];
  suggested_actions: SuggestedAction[];
  guidance: string | null;
}

interface ReviewItem {
  id: string;
  title: string;
  description: string;
  entity_type: string;
  entity_id: string;
  item_type: string | null;
  severity: string;
  status: string;
  dollar_amount: number | null;
  reviewed_by: string | null;
  review_notes: string | null;
  created_at: string;
  updated_at: string;
  review_metadata: Record<string, unknown> | null;
  context: ReviewContext | null;
}

const statusConfig: Record<
  string,
  { variant: "default" | "secondary" | "destructive" | "outline"; className?: string; label: string }
> = {
  pending_review: { variant: "outline", className: "border-yellow-500 text-yellow-600", label: "Pending Review" },
  approved: { variant: "default", className: "bg-green-600 hover:bg-green-700", label: "Approved" },
  rejected: { variant: "destructive", label: "Rejected" },
  escalated: { variant: "outline", className: "border-orange-500 text-orange-600", label: "Escalated" },
  auto_approved: { variant: "secondary", className: "bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300", label: "Auto-Approved" },
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

const anomalyTypeLabels: Record<string, string> = {
  duplicate_invoice: "Duplicate Invoice",
  budget_overrun: "Budget Overrun",
  misallocated_cost: "Low Confidence Allocation",
  missing_approval: "Missing Approval",
  reconciliation_mismatch: "Reconciliation Mismatch",
  unusual_amount: "Unusual Amount",
};

const actionIcons: Record<string, typeof CheckCircle2> = {
  approve: CheckCircle2,
  reject: XCircle,
  escalate: AlertTriangle,
};

function formatCurrency(amount: number | null): string {
  if (amount == null) return "--";
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
  }).format(amount);
}

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function ReviewDetailPage() {
  const params = useParams();
  const router = useRouter();
  const reviewId = params.id as string;

  const [item, setItem] = useState<ReviewItem | null>(null);
  const [loading, setLoading] = useState(true);
  const [acting, setActing] = useState(false);
  const [notes, setNotes] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);

  const loadItem = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/v1/reviews/${reviewId}`);
      if (!res.ok) throw new Error("Failed to load review item");
      const data = await res.json();
      setItem(data);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadItem();
  }, [reviewId]);

  const handleAction = async (action: string, prefillNotes?: string) => {
    setActing(true);
    setError(null);
    setActionSuccess(null);
    const finalNotes = prefillNotes || notes;
    try {
      const res = await fetch(`${API_BASE}/api/v1/reviews/${reviewId}/action`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action,
          notes: finalNotes,
          reviewed_by: "user",
        }),
      });
      if (!res.ok) {
        const detail = await res.text();
        throw new Error(detail || "Action failed");
      }
      const updated = await res.json();
      // Preserve context from the detail response (action endpoint returns base response)
      setItem({ ...item, ...updated, context: item?.context ?? null } as ReviewItem);
      setNotes("");
      setActionSuccess(`Item ${action}d successfully.`);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Action failed");
    } finally {
      setActing(false);
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

  if (!item) {
    return (
      <PageTransition>
        <div className="text-center py-20 text-muted-foreground">
          Review item not found.
        </div>
      </PageTransition>
    );
  }

  const status = statusConfig[item.status] || {
    variant: "outline" as const,
    label: item.status,
  };
  const sev = severityConfig[item.severity] || { variant: "outline" as const };
  const isPending = item.status === "pending_review";
  const ctx = item.context;
  const anomalyLabel = ctx?.anomaly_type
    ? anomalyTypeLabels[ctx.anomaly_type] || ctx.anomaly_type.replace(/_/g, " ")
    : null;

  return (
    <PageTransition>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center gap-4">
          <Button
            variant="ghost"
            size="icon"
            onClick={() => router.push("/reviews")}
          >
            <ArrowLeft className="size-4" />
          </Button>
          <div className="flex-1">
            <h2 className="text-2xl font-bold tracking-tight">{item.title}</h2>
            <p className="text-muted-foreground">
              Review Item &middot; {(item.item_type || "unknown").replace(/_/g, " ")}
              {anomalyLabel && (
                <span className="ml-2 text-xs font-medium rounded bg-muted px-1.5 py-0.5">
                  {anomalyLabel}
                </span>
              )}
            </p>
          </div>
          <Badge variant={status.variant} className={status.className}>
            {status.label}
          </Badge>
        </div>

        {error && (
          <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive">
            {error}
          </div>
        )}

        {actionSuccess && (
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            className="rounded-lg border border-green-500/50 bg-green-50 dark:bg-green-950/30 p-3 text-sm text-green-700 dark:text-green-400 flex items-center gap-2"
          >
            <CheckCircle2 className="size-4" />
            {actionSuccess}
          </motion.div>
        )}

        {/* Summary cards */}
        <div className="grid gap-4 md:grid-cols-4">
          <AnimatedCard delay={0}>
            <CardHeader className="pb-2">
              <CardDescription className="flex items-center gap-2">
                <Tag className="size-4" />
                Severity
              </CardDescription>
              <CardTitle>
                <Badge variant={sev.variant} className={sev.className}>
                  {item.severity}
                </Badge>
              </CardTitle>
            </CardHeader>
          </AnimatedCard>

          <AnimatedCard delay={0.05}>
            <CardHeader className="pb-2">
              <CardDescription className="flex items-center gap-2">
                <DollarSign className="size-4" />
                Dollar Amount
              </CardDescription>
              <CardTitle className="text-2xl tabular-nums">
                {formatCurrency(item.dollar_amount ?? ctx?.allocation_total ?? null)}
              </CardTitle>
            </CardHeader>
          </AnimatedCard>

          {ctx?.document_name && (
            <AnimatedCard delay={0.1}>
              <CardHeader className="pb-2">
                <CardDescription className="flex items-center gap-2">
                  <FileText className="size-4" />
                  Document
                </CardDescription>
                <CardTitle className="text-sm truncate">
                  {ctx.document_name}
                </CardTitle>
              </CardHeader>
            </AnimatedCard>
          )}

          <AnimatedCard delay={0.15}>
            <CardHeader className="pb-2">
              <CardDescription className="flex items-center gap-2">
                <Shield className="size-4" />
                Entity
              </CardDescription>
              <CardTitle className="text-xs font-mono truncate">
                {item.entity_type}
              </CardTitle>
            </CardHeader>
          </AnimatedCard>
        </div>

        {/* Guidance callout */}
        {ctx?.guidance && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
            className="rounded-lg border border-blue-200 dark:border-blue-800 bg-blue-50 dark:bg-blue-950/30 p-4"
          >
            <div className="flex items-start gap-3">
              <Lightbulb className="size-5 text-blue-600 dark:text-blue-400 mt-0.5 shrink-0" />
              <div>
                <h4 className="font-semibold text-sm text-blue-900 dark:text-blue-200 mb-1">
                  Reviewer Guidance
                </h4>
                <p className="text-sm text-blue-800 dark:text-blue-300 leading-relaxed">
                  {ctx.guidance}
                </p>
              </div>
            </div>
          </motion.div>
        )}

        <div className="grid gap-6 lg:grid-cols-2">
          {/* Left column: Description + Evidence + Related Items */}
          <div className="space-y-6">
            {/* Description */}
            <AnimatedCard delay={0.2}>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Info className="size-4" />
                  Description
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm leading-relaxed">{item.description}</p>
              </CardContent>
            </AnimatedCard>

            {/* Evidence panel */}
            {ctx?.evidence && ctx.evidence.length > 0 && (
              <AnimatedCard delay={0.25}>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Scale className="size-4" />
                    Evidence
                  </CardTitle>
                  <CardDescription>
                    Data supporting this flag — review before taking action
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="space-y-3">
                    {ctx.evidence.map((ev, i) => (
                      <motion.div
                        key={i}
                        initial={{ opacity: 0, x: -10 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ delay: 0.3 + i * 0.05 }}
                        className="flex items-start justify-between gap-4 rounded-md border bg-muted/30 px-3 py-2.5"
                      >
                        <span className="text-xs font-medium text-muted-foreground shrink-0">
                          {ev.label}
                        </span>
                        <span
                          className={`text-sm text-right font-mono ${
                            ev.type === "currency"
                              ? "tabular-nums font-semibold"
                              : ev.type === "percentage"
                              ? "tabular-nums text-orange-600 dark:text-orange-400 font-semibold"
                              : ev.type === "link"
                              ? "text-blue-600 dark:text-blue-400 underline cursor-pointer"
                              : ""
                          }`}
                          onClick={
                            ev.type === "link" && ctx?.document_id
                              ? () => router.push(`/documents/${ctx.document_id}`)
                              : undefined
                          }
                        >
                          {ev.value}
                        </span>
                      </motion.div>
                    ))}
                  </div>
                </CardContent>
              </AnimatedCard>
            )}

            {/* Related entities links */}
            {(ctx?.document_id || ctx?.allocation_id) && (
              <AnimatedCard delay={0.3}>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <ExternalLink className="size-4" />
                    Related Items
                  </CardTitle>
                </CardHeader>
                <CardContent className="flex flex-wrap gap-2">
                  {ctx?.document_id && (
                    <Button
                      variant="outline"
                      size="sm"
                      className="gap-2"
                      onClick={() => router.push(`/documents/${ctx.document_id}`)}
                    >
                      <FileText className="size-3.5" />
                      View Document
                    </Button>
                  )}
                  {ctx?.allocation_id && (
                    <Button
                      variant="outline"
                      size="sm"
                      className="gap-2"
                      onClick={() => router.push(`/allocations/${ctx.allocation_id}`)}
                    >
                      <DollarSign className="size-3.5" />
                      View Allocation
                    </Button>
                  )}
                </CardContent>
              </AnimatedCard>
            )}
          </div>

          {/* Right column: Quick Actions + Manual Action + History */}
          <div className="space-y-6">
            {/* Quick actions */}
            {isPending && ctx?.suggested_actions && ctx.suggested_actions.length > 0 && (
              <AnimatedCard delay={0.25}>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Zap className="size-4" />
                    Quick Actions
                  </CardTitle>
                  <CardDescription>
                    One-click actions with pre-filled review notes
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-2">
                  {ctx.suggested_actions.map((sa, i) => {
                    const Icon = actionIcons[sa.action] || CheckCircle2;
                    return (
                      <motion.div
                        key={i}
                        initial={{ opacity: 0, y: 5 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: 0.3 + i * 0.08 }}
                      >
                        <button
                          onClick={() => handleAction(sa.action, sa.notes)}
                          disabled={acting}
                          className={`w-full flex items-start gap-3 rounded-lg border p-3 text-left transition-all hover:shadow-sm disabled:opacity-50 ${
                            sa.variant === "success"
                              ? "border-green-200 dark:border-green-800 hover:bg-green-50 dark:hover:bg-green-950/30"
                              : sa.variant === "danger"
                              ? "border-red-200 dark:border-red-800 hover:bg-red-50 dark:hover:bg-red-950/30"
                              : "border-orange-200 dark:border-orange-800 hover:bg-orange-50 dark:hover:bg-orange-950/30"
                          }`}
                        >
                          <Icon
                            className={`size-5 mt-0.5 shrink-0 ${
                              sa.variant === "success"
                                ? "text-green-600"
                                : sa.variant === "danger"
                                ? "text-red-600"
                                : "text-orange-600"
                            }`}
                          />
                          <div className="flex-1 min-w-0">
                            <div className="font-medium text-sm">{sa.label}</div>
                            <div className="text-xs text-muted-foreground mt-0.5 line-clamp-2">
                              {sa.notes}
                            </div>
                          </div>
                          <Badge
                            variant="outline"
                            className={`shrink-0 text-[10px] ${
                              sa.variant === "success"
                                ? "border-green-300 text-green-700 dark:border-green-700 dark:text-green-400"
                                : sa.variant === "danger"
                                ? "border-red-300 text-red-700 dark:border-red-700 dark:text-red-400"
                                : "border-orange-300 text-orange-700 dark:border-orange-700 dark:text-orange-400"
                            }`}
                          >
                            {sa.action}
                          </Badge>
                        </button>
                      </motion.div>
                    );
                  })}
                </CardContent>
              </AnimatedCard>
            )}

            {/* Manual action with custom notes */}
            {isPending && (
              <AnimatedCard delay={0.35}>
                <CardHeader>
                  <CardTitle>Custom Action</CardTitle>
                  <CardDescription>
                    Write your own review notes and choose an action
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div>
                    <label className="text-sm font-medium text-muted-foreground">
                      Notes
                    </label>
                    <textarea
                      value={notes}
                      onChange={(e) => setNotes(e.target.value)}
                      placeholder="Add review notes..."
                      rows={3}
                      className="mt-1.5 w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm shadow-xs placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:border-ring"
                    />
                  </div>
                  <div className="flex gap-2">
                    <motion.div whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }}>
                      <Button
                        className="gap-2 bg-green-600 hover:bg-green-700 text-white"
                        onClick={() => handleAction("approve")}
                        disabled={acting}
                      >
                        {acting ? (
                          <Loader2 className="size-4 animate-spin" />
                        ) : (
                          <CheckCircle2 className="size-4" />
                        )}
                        Approve
                      </Button>
                    </motion.div>
                    <motion.div whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }}>
                      <Button
                        variant="destructive"
                        className="gap-2"
                        onClick={() => handleAction("reject")}
                        disabled={acting}
                      >
                        <XCircle className="size-4" />
                        Reject
                      </Button>
                    </motion.div>
                    <motion.div whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }}>
                      <Button
                        variant="outline"
                        className="gap-2 border-orange-500 text-orange-600 hover:bg-orange-50 dark:hover:bg-orange-950"
                        onClick={() => handleAction("escalate")}
                        disabled={acting}
                      >
                        <AlertTriangle className="size-4" />
                        Escalate
                      </Button>
                    </motion.div>
                  </div>
                </CardContent>
              </AnimatedCard>
            )}

            {/* Review history */}
            {item.reviewed_by && (
              <AnimatedCard delay={0.4}>
                <CardHeader>
                  <CardTitle>Review History</CardTitle>
                </CardHeader>
                <CardContent className="space-y-2">
                  <div className="flex items-center gap-2 text-sm">
                    <span className="text-muted-foreground">Reviewed by:</span>
                    <span className="font-medium">{item.reviewed_by}</span>
                  </div>
                  {item.review_notes && (
                    <div className="text-sm">
                      <span className="text-muted-foreground">Notes:</span>
                      <p className="mt-1 rounded-md bg-muted p-3">{item.review_notes}</p>
                    </div>
                  )}
                  <div className="text-xs text-muted-foreground">
                    Updated: {formatDate(item.updated_at)}
                  </div>
                </CardContent>
              </AnimatedCard>
            )}
          </div>
        </div>
      </div>
    </PageTransition>
  );
}

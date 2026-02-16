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

interface ReviewItem {
  id: string;
  title: string;
  description: string;
  entity_type: string;
  entity_id: string;
  review_type: string;
  severity: string;
  status: string;
  dollar_amount: number | null;
  reviewed_by: string | null;
  review_notes: string | null;
  created_at: string;
  updated_at: string;
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

  const handleAction = async (action: "approve" | "reject" | "escalate") => {
    setActing(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/api/v1/reviews/${reviewId}/action`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action,
          notes,
          reviewed_by: "user",
        }),
      });
      if (!res.ok) {
        const detail = await res.text();
        throw new Error(detail || "Action failed");
      }
      const updated = await res.json();
      setItem(updated);
      setNotes("");
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
              Review Item &middot; {item.review_type.replace(/_/g, " ")}
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

        {/* Info cards */}
        <div className="grid gap-4 md:grid-cols-3">
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
                {formatCurrency(item.dollar_amount)}
              </CardTitle>
            </CardHeader>
          </AnimatedCard>

          <AnimatedCard delay={0.1}>
            <CardHeader className="pb-2">
              <CardDescription className="flex items-center gap-2">
                <Shield className="size-4" />
                Entity
              </CardDescription>
              <CardTitle className="text-sm font-mono truncate">
                {item.entity_type} / {item.entity_id}
              </CardTitle>
            </CardHeader>
          </AnimatedCard>
        </div>

        {/* Description */}
        <AnimatedCard delay={0.15}>
          <CardHeader>
            <CardTitle>Description</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm leading-relaxed">{item.description}</p>
          </CardContent>
        </AnimatedCard>

        {/* Review history */}
        {item.reviewed_by && (
          <AnimatedCard delay={0.2}>
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

        {/* Actions */}
        {isPending && (
          <AnimatedCard delay={0.25}>
            <CardHeader>
              <CardTitle>Take Action</CardTitle>
              <CardDescription>
                Review the details above and approve, reject, or escalate this item.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <label className="text-sm font-medium text-muted-foreground">
                  Notes (optional)
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
      </div>
    </PageTransition>
  );
}

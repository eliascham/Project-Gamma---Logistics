"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { motion } from "framer-motion";
import {
  ArrowLeft,
  CheckCircle2,
  DollarSign,
  Loader2,
  PlayCircle,
  XCircle,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { AnimatedCard } from "@/components/shared/animated-card";
import { PageTransition } from "@/components/shared/page-transition";
import { AllocationTable } from "@/components/allocations/allocation-table";
import {
  getDocument,
  getAllocation,
  triggerAllocation,
  approveAllocation,
} from "@/lib/api-client";
import type { Document } from "@/types/document";
import type { AllocationLineItem, CostAllocation, AllocationStatus } from "@/types/allocation";

const statusConfig: Record<
  AllocationStatus,
  { variant: "default" | "secondary" | "destructive" | "outline"; label: string }
> = {
  pending: { variant: "outline", label: "Pending" },
  allocated: { variant: "secondary", label: "Allocated" },
  review_needed: { variant: "secondary", label: "Review Needed" },
  approved: { variant: "default", label: "Approved" },
  rejected: { variant: "destructive", label: "Rejected" },
};

function formatCurrency(amount: number, currency: string): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency,
  }).format(amount);
}

export default function AllocationDetailPage() {
  const params = useParams();
  const router = useRouter();
  const documentId = params.id as string;

  const [document, setDocument] = useState<Document | null>(null);
  const [allocation, setAllocation] = useState<CostAllocation | null>(null);
  const [loading, setLoading] = useState(true);
  const [allocating, setAllocating] = useState(false);
  const [approving, setApproving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load document and try to fetch existing allocation
  useEffect(() => {
    async function load() {
      try {
        const doc = await getDocument(documentId);
        setDocument(doc);

        // Try loading existing allocation (404 = not yet allocated)
        try {
          const alloc = await getAllocation(documentId);
          setAllocation(alloc);
        } catch {
          // No allocation yet — that's fine
        }
      } catch (err: unknown) {
        setError(err instanceof Error ? err.message : "Failed to load");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [documentId]);

  const handleRunAllocation = async () => {
    setAllocating(true);
    setError(null);
    try {
      const result = await triggerAllocation(documentId);
      setAllocation(result);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Allocation failed");
    } finally {
      setAllocating(false);
    }
  };

  const handleApprove = async (action: "approved" | "rejected") => {
    if (!allocation) return;
    setApproving(true);
    try {
      const updated = await approveAllocation(allocation.id, action);
      setAllocation(updated);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Action failed");
    } finally {
      setApproving(false);
    }
  };

  const handleItemUpdated = (updated: AllocationLineItem) => {
    if (!allocation) return;
    setAllocation({
      ...allocation,
      line_items: allocation.line_items.map((li) =>
        li.id === updated.id ? updated : li
      ),
    });
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

  const status = allocation
    ? statusConfig[allocation.status]
    : null;

  const reviewCount = allocation?.line_items.filter(
    (li) => li.status === "needs_review"
  ).length ?? 0;

  return (
    <PageTransition>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center gap-4">
          <Button
            variant="ghost"
            size="icon"
            onClick={() => router.push("/allocations")}
          >
            <ArrowLeft className="size-4" />
          </Button>
          <div className="flex-1">
            <h2 className="text-2xl font-bold tracking-tight">
              Cost Allocation
            </h2>
            <p className="text-muted-foreground">
              {document?.original_filename}
            </p>
          </div>
          {status && <Badge variant={status.variant}>{status.label}</Badge>}
        </div>

        {error && (
          <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive">
            {error}
          </div>
        )}

        {/* No allocation yet — show run button */}
        {!allocation && (
          <AnimatedCard>
            <CardContent className="flex flex-col items-center py-12 text-center">
              <DollarSign className="size-12 text-muted-foreground/40 mb-4" />
              <h3 className="text-lg font-semibold">
                No allocation yet
              </h3>
              <p className="mt-1 max-w-sm text-sm text-muted-foreground">
                Run cost allocation to automatically map line items to project
                codes, cost centers, and GL accounts using AI.
              </p>
              <motion.div
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
              >
                <Button
                  className="mt-6 gap-2"
                  onClick={handleRunAllocation}
                  disabled={allocating}
                >
                  {allocating ? (
                    <Loader2 className="size-4 animate-spin" />
                  ) : (
                    <PlayCircle className="size-4" />
                  )}
                  {allocating ? "Allocating..." : "Run Allocation"}
                </Button>
              </motion.div>
            </CardContent>
          </AnimatedCard>
        )}

        {/* Allocation results */}
        {allocation && (
          <>
            {/* Summary cards */}
            <div className="grid gap-4 md:grid-cols-4">
              <AnimatedCard delay={0}>
                <CardHeader className="pb-2">
                  <CardDescription>Total Amount</CardDescription>
                  <CardTitle className="text-2xl tabular-nums">
                    {allocation.total_amount != null
                      ? formatCurrency(
                          allocation.total_amount,
                          allocation.currency
                        )
                      : "—"}
                  </CardTitle>
                </CardHeader>
              </AnimatedCard>

              <AnimatedCard delay={0.05}>
                <CardHeader className="pb-2">
                  <CardDescription>Line Items</CardDescription>
                  <CardTitle className="text-2xl tabular-nums">
                    {allocation.line_items.length}
                  </CardTitle>
                </CardHeader>
              </AnimatedCard>

              <AnimatedCard delay={0.1}>
                <CardHeader className="pb-2">
                  <CardDescription>Needs Review</CardDescription>
                  <CardTitle className="text-2xl tabular-nums">
                    <span
                      className={
                        reviewCount > 0
                          ? "text-amber-600 dark:text-amber-400"
                          : ""
                      }
                    >
                      {reviewCount}
                    </span>
                  </CardTitle>
                </CardHeader>
              </AnimatedCard>

              <AnimatedCard delay={0.15}>
                <CardHeader className="pb-2">
                  <CardDescription>Model</CardDescription>
                  <CardTitle className="text-sm font-mono truncate">
                    {allocation.allocated_by_model || "—"}
                  </CardTitle>
                </CardHeader>
              </AnimatedCard>
            </div>

            {/* Line items table */}
            <AnimatedCard delay={0.2}>
              <CardHeader>
                <CardTitle>Line Items</CardTitle>
                <CardDescription>
                  {reviewCount > 0
                    ? `${reviewCount} item${reviewCount > 1 ? "s" : ""} need manual review — click the pencil icon to override.`
                    : "All items allocated with high confidence."}
                </CardDescription>
              </CardHeader>
              <CardContent>
                <AllocationTable
                  lineItems={allocation.line_items}
                  onItemUpdated={handleItemUpdated}
                />
              </CardContent>
            </AnimatedCard>

            {/* Approve / Reject actions */}
            {(allocation.status === "allocated" ||
              allocation.status === "review_needed") && (
              <AnimatedCard delay={0.25}>
                <CardContent className="flex items-center justify-between py-4">
                  <p className="text-sm text-muted-foreground">
                    Review the allocations above, then approve or reject.
                  </p>
                  <div className="flex gap-2">
                    <motion.div
                      whileHover={{ scale: 1.02 }}
                      whileTap={{ scale: 0.98 }}
                    >
                      <Button
                        variant="outline"
                        className="gap-2 text-destructive hover:text-destructive"
                        onClick={() => handleApprove("rejected")}
                        disabled={approving}
                      >
                        <XCircle className="size-4" />
                        Reject
                      </Button>
                    </motion.div>
                    <motion.div
                      whileHover={{ scale: 1.02 }}
                      whileTap={{ scale: 0.98 }}
                    >
                      <Button
                        className="gap-2"
                        onClick={() => handleApprove("approved")}
                        disabled={approving}
                      >
                        {approving ? (
                          <Loader2 className="size-4 animate-spin" />
                        ) : (
                          <CheckCircle2 className="size-4" />
                        )}
                        Approve
                      </Button>
                    </motion.div>
                  </div>
                </CardContent>
              </AnimatedCard>
            )}
          </>
        )}
      </div>
    </PageTransition>
  );
}

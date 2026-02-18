"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import {
  FileText,
  Clock,
  CheckCircle,
  AlertTriangle,
  Upload,
  ArrowRight,
  DollarSign,
  MessageSquare,
  Database,
  ClipboardCheck,
  GitCompare,
  Shield,
} from "lucide-react";
import {
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { AnimatedCard } from "@/components/shared/animated-card";
import { PageTransition } from "@/components/shared/page-transition";
import { getDocuments, getRAGStats } from "@/lib/api-client";
import type { Document } from "@/types/document";
import type { RagStats } from "@/types/rag";

const container = {
  hidden: {},
  show: { transition: { staggerChildren: 0.1 } },
};

const item = {
  hidden: { opacity: 0, y: 20 },
  show: { opacity: 1, y: 0, transition: { type: "spring" as const, damping: 15 } },
};

const statCards = [
  {
    title: "Total Documents",
    key: "total" as const,
    icon: FileText,
    gradient: "from-blue-500/10 to-blue-600/5",
    iconColor: "text-blue-500",
  },
  {
    title: "Pending",
    key: "pending" as const,
    icon: Clock,
    gradient: "from-amber-500/10 to-amber-600/5",
    iconColor: "text-amber-500",
  },
  {
    title: "Extracted",
    key: "extracted" as const,
    icon: CheckCircle,
    gradient: "from-green-500/10 to-green-600/5",
    iconColor: "text-green-500",
  },
  {
    title: "Failed",
    key: "failed" as const,
    icon: AlertTriangle,
    gradient: "from-red-500/10 to-red-600/5",
    iconColor: "text-red-500",
  },
];

const statusVariant: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
  pending: "outline",
  processing: "secondary",
  extracted: "default",
  failed: "destructive",
};

function formatRelativeTime(dateStr: string): string {
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  if (diffMins < 1) return "just now";
  if (diffMins < 60) return `${diffMins}m ago`;
  const diffHours = Math.floor(diffMins / 60);
  if (diffHours < 24) return `${diffHours}h ago`;
  const diffDays = Math.floor(diffHours / 24);
  return `${diffDays}d ago`;
}

export default function Dashboard() {
  const router = useRouter();
  const [stats, setStats] = useState({ total: 0, pending: 0, extracted: 0, failed: 0 });
  const [ragStats, setRagStats] = useState<RagStats | null>(null);
  const [recentDocs, setRecentDocs] = useState<Document[]>([]);
  const [loading, setLoading] = useState(true);
  const [reviewStats, setReviewStats] = useState<{ pending_review: number; total: number } | null>(null);
  const [anomalyStats, setAnomalyStats] = useState<{ unresolved: number; total: number } | null>(null);
  const [reconStats, setReconStats] = useState<{ avg_match_rate: number | null; total_runs: number } | null>(null);

  const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  useEffect(() => {
    getDocuments(1, 100)
      .then((data) => {
        const docs = data.documents;
        setStats({
          total: data.total,
          pending: docs.filter((d) => d.status === "pending" || d.status === "processing").length,
          extracted: docs.filter((d) => d.status === "extracted").length,
          failed: docs.filter((d) => d.status === "failed").length,
        });
        setRecentDocs(docs.slice(0, 5));
      })
      .catch(() => {})
      .finally(() => setLoading(false));

    getRAGStats().then(setRagStats).catch(() => {});

    // Phase 4 stats
    fetch(`${API_BASE}/api/v1/reviews/stats`).then(r => r.json()).then(setReviewStats).catch(() => {});
    fetch(`${API_BASE}/api/v1/anomalies/stats`).then(r => r.json()).then(setAnomalyStats).catch(() => {});
    fetch(`${API_BASE}/api/v1/reconciliation/stats`).then(r => r.json()).then(setReconStats).catch(() => {});
  }, []);

  return (
    <PageTransition>
      <div className="space-y-8">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Dashboard</h2>
          <p className="text-muted-foreground">Logistics document processing overview</p>
        </div>

        {/* Stat Cards */}
        <motion.div
          className="grid gap-4 md:grid-cols-2 lg:grid-cols-4"
          variants={container}
          initial="hidden"
          animate="show"
        >
          {statCards.map((card) => {
            const Icon = card.icon;
            return (
              <motion.div key={card.key} variants={item}>
                <AnimatedCard className="relative overflow-hidden">
                  <div className={`absolute inset-0 bg-gradient-to-br ${card.gradient}`} />
                  <CardHeader className="relative flex flex-row items-center justify-between space-y-0 pb-2">
                    <CardTitle className="text-sm font-medium">{card.title}</CardTitle>
                    <motion.div whileHover={{ rotate: 12 }} transition={{ type: "spring" }}>
                      <Icon className={`size-4 ${card.iconColor}`} />
                    </motion.div>
                  </CardHeader>
                  <CardContent className="relative">
                    {loading ? (
                      <Skeleton className="h-9 w-16" />
                    ) : (
                      <motion.div
                        className="text-3xl font-bold"
                        initial={{ opacity: 0, scale: 0.5 }}
                        animate={{ opacity: 1, scale: 1 }}
                        transition={{ type: "spring", delay: 0.2 }}
                      >
                        {stats[card.key]}
                      </motion.div>
                    )}
                  </CardContent>
                </AnimatedCard>
              </motion.div>
            );
          })}
        </motion.div>

        <div className="grid gap-6 lg:grid-cols-2">
          {/* Recent Documents */}
          <AnimatedCard delay={0.3}>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>Recent Documents</CardTitle>
                  <CardDescription>Latest uploads</CardDescription>
                </div>
                <Link href="/documents">
                  <Button variant="ghost" size="sm">
                    View all <ArrowRight className="ml-1 size-3" />
                  </Button>
                </Link>
              </div>
            </CardHeader>
            <CardContent>
              {loading ? (
                <div className="space-y-3">
                  {Array.from({ length: 3 }).map((_, i) => (
                    <Skeleton key={i} className="h-10 w-full" />
                  ))}
                </div>
              ) : recentDocs.length === 0 ? (
                <p className="py-4 text-center text-sm text-muted-foreground">No documents yet</p>
              ) : (
                <div className="space-y-1">
                  {recentDocs.map((doc, i) => (
                    <motion.div
                      key={doc.id}
                      initial={{ opacity: 0, x: -10 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: 0.4 + i * 0.05 }}
                      onClick={() => router.push(`/documents/${doc.id}`)}
                      className="flex cursor-pointer items-center justify-between rounded-lg px-3 py-2.5 transition-colors hover:bg-accent/50"
                    >
                      <div className="flex items-center gap-3">
                        <FileText className="size-4 text-muted-foreground" />
                        <span className="text-sm font-medium">{doc.original_filename}</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <Badge variant={statusVariant[doc.status] || "outline"} className="text-xs">
                          {doc.status}
                        </Badge>
                        <span className="text-xs text-muted-foreground">
                          {formatRelativeTime(doc.created_at)}
                        </span>
                      </div>
                    </motion.div>
                  ))}
                </div>
              )}
            </CardContent>
          </AnimatedCard>

          {/* Quick Actions */}
          <AnimatedCard delay={0.4}>
            <CardHeader>
              <CardTitle>Quick Actions</CardTitle>
              <CardDescription>Get started with document processing</CardDescription>
            </CardHeader>
            <CardContent className="flex flex-col gap-3">
              <Link href="/documents/upload">
                <motion.div whileHover={{ scale: 1.01 }} whileTap={{ scale: 0.99 }}>
                  <Button className="w-full justify-start gap-2">
                    <Upload className="size-4" /> Upload Document
                  </Button>
                </motion.div>
              </Link>
              <Link href="/allocations">
                <motion.div whileHover={{ scale: 1.01 }} whileTap={{ scale: 0.99 }}>
                  <Button variant="outline" className="w-full justify-start gap-2">
                    <DollarSign className="size-4" /> Cost Allocations
                  </Button>
                </motion.div>
              </Link>
              <Link href="/chat">
                <motion.div whileHover={{ scale: 1.01 }} whileTap={{ scale: 0.99 }}>
                  <Button variant="outline" className="w-full justify-start gap-2">
                    <MessageSquare className="size-4" /> Ask a Question
                  </Button>
                </motion.div>
              </Link>
            </CardContent>
          </AnimatedCard>

          {/* RAG Knowledge Base */}
          <AnimatedCard delay={0.5}>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>Knowledge Base</CardTitle>
                  <CardDescription>RAG document embeddings</CardDescription>
                </div>
                <Link href="/chat">
                  <Button variant="ghost" size="sm">
                    Ask Q&A <ArrowRight className="ml-1 size-3" />
                  </Button>
                </Link>
              </div>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-3 gap-4">
                <div className="text-center">
                  <Database className="size-4 mx-auto text-muted-foreground mb-1" />
                  <div className="text-2xl font-bold">{ragStats?.total_embeddings ?? "—"}</div>
                  <div className="text-xs text-muted-foreground">Chunks</div>
                </div>
                <div className="text-center">
                  <FileText className="size-4 mx-auto text-muted-foreground mb-1" />
                  <div className="text-2xl font-bold">{ragStats?.total_documents_ingested ?? "—"}</div>
                  <div className="text-xs text-muted-foreground">Documents</div>
                </div>
                <div className="text-center">
                  <MessageSquare className="size-4 mx-auto text-muted-foreground mb-1" />
                  <div className="text-2xl font-bold">{ragStats?.total_queries ?? "—"}</div>
                  <div className="text-xs text-muted-foreground">Queries</div>
                </div>
              </div>
            </CardContent>
          </AnimatedCard>
        </div>

        {/* Phase 4: Guardrails Widgets */}
        <div>
          <h3 className="mb-4 text-lg font-semibold">Guardrails & Operations</h3>
          <div className="grid gap-4 md:grid-cols-3">
            <AnimatedCard delay={0.6}>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Review Queue</CardTitle>
                <ClipboardCheck className="size-4 text-amber-500" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{reviewStats?.pending_review ?? "—"}</div>
                <p className="text-xs text-muted-foreground">
                  pending reviews of {reviewStats?.total ?? 0} total
                </p>
                <Link href="/reviews">
                  <Button variant="ghost" size="sm" className="mt-2 p-0 text-xs">
                    View queue <ArrowRight className="ml-1 size-3" />
                  </Button>
                </Link>
              </CardContent>
            </AnimatedCard>

            <AnimatedCard delay={0.7}>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Active Anomalies</CardTitle>
                <AlertTriangle className="size-4 text-orange-500" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{anomalyStats?.unresolved ?? "—"}</div>
                <p className="text-xs text-muted-foreground">
                  unresolved of {anomalyStats?.total ?? 0} total
                </p>
                <Link href="/anomalies">
                  <Button variant="ghost" size="sm" className="mt-2 p-0 text-xs">
                    View anomalies <ArrowRight className="ml-1 size-3" />
                  </Button>
                </Link>
              </CardContent>
            </AnimatedCard>

            <AnimatedCard delay={0.8}>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Reconciliation</CardTitle>
                <GitCompare className="size-4 text-blue-500" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">
                  {reconStats?.avg_match_rate != null
                    ? `${(reconStats.avg_match_rate * 100).toFixed(0)}%`
                    : "—"}
                </div>
                <p className="text-xs text-muted-foreground">
                  avg match rate ({reconStats?.total_runs ?? 0} runs)
                </p>
                <Link href="/reconciliation">
                  <Button variant="ghost" size="sm" className="mt-2 p-0 text-xs">
                    View runs <ArrowRight className="ml-1 size-3" />
                  </Button>
                </Link>
              </CardContent>
            </AnimatedCard>
          </div>
        </div>
      </div>
    </PageTransition>
  );
}

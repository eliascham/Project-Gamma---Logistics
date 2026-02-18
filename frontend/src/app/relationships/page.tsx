"use client";

import { useEffect, useState, useCallback } from "react";
import { motion } from "framer-motion";
import {
  Link2,
  Loader2,
  Search,
  Sparkles,
  Hash,
  FileText,
  Zap,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Card,
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
import { PageTransition } from "@/components/shared/page-transition";
import { AnimatedCard } from "@/components/shared/animated-card";
import { EmptyState } from "@/components/shared/empty-state";
import { TableRowSkeleton } from "@/components/shared/loading-skeleton";
import {
  getRelationships,
  detectRelationships,
} from "@/lib/api-client";
import type { DocumentRelationship, RelationshipType } from "@/types/relationship";

const RELATIONSHIP_TYPES: RelationshipType[] = [
  "fulfills",
  "invoices",
  "supports",
  "adjusts",
  "certifies",
  "clears",
  "confirms",
  "notifies",
];

const typeBadgeConfig: Record<RelationshipType, string> = {
  fulfills: "bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300",
  invoices: "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300",
  supports: "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300",
  adjusts: "bg-orange-100 text-orange-700 dark:bg-orange-900 dark:text-orange-300",
  certifies: "bg-purple-100 text-purple-700 dark:bg-purple-900 dark:text-purple-300",
  clears: "bg-cyan-100 text-cyan-700 dark:bg-cyan-900 dark:text-cyan-300",
  confirms: "bg-emerald-100 text-emerald-700 dark:bg-emerald-900 dark:text-emerald-300",
  notifies: "bg-yellow-100 text-yellow-700 dark:bg-yellow-900 dark:text-yellow-300",
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

function truncateId(id: string): string {
  return id.length > 12 ? `${id.slice(0, 8)}...` : id;
}

export default function RelationshipsPage() {
  const [relationships, setRelationships] = useState<DocumentRelationship[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [typeFilter, setTypeFilter] = useState<string>("all");

  // Auto-detect state
  const [detectDocId, setDetectDocId] = useState("");
  const [detecting, setDetecting] = useState(false);
  const [showDetect, setShowDetect] = useState(false);
  const [detectResult, setDetectResult] = useState<string | null>(null);

  const loadRelationships = useCallback(async () => {
    try {
      const data = await getRelationships();
      setRelationships(data);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load relationships");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadRelationships();
  }, [loadRelationships]);

  const handleDetect = async () => {
    if (!detectDocId.trim()) return;
    setDetecting(true);
    setDetectResult(null);
    setError(null);
    try {
      const detected = await detectRelationships(detectDocId.trim());
      setDetectResult(`Detected ${detected.length} relationship${detected.length !== 1 ? "s" : ""}`);
      setDetectDocId("");
      await loadRelationships();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Detection failed");
    } finally {
      setDetecting(false);
    }
  };

  const filtered = typeFilter === "all"
    ? relationships
    : relationships.filter((r) => r.relationship_type === typeFilter);

  const uniqueDocs = new Set<string>();
  relationships.forEach((r) => {
    uniqueDocs.add(r.source_document_id);
    uniqueDocs.add(r.target_document_id);
  });

  const autoDetectedCount = relationships.filter((r) => r.created_by === "system" || r.created_by === "auto").length;
  const manualCount = relationships.length - autoDetectedCount;

  const statCards = [
    { label: "Total Relationships", value: relationships.length, icon: Link2, color: "text-blue-600 dark:text-blue-400" },
    { label: "Auto-Detected", value: autoDetectedCount, icon: Zap, color: "text-green-600 dark:text-green-400" },
    { label: "Manual", value: manualCount, icon: FileText, color: "text-orange-600 dark:text-orange-400" },
    { label: "Unique Documents", value: uniqueDocs.size, icon: Hash, color: "text-purple-600 dark:text-purple-400" },
  ];

  return (
    <PageTransition>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-2xl font-bold tracking-tight">
              Document Relationships
            </h2>
            <p className="text-muted-foreground">
              Links between logistics documents discovered automatically or created manually
            </p>
          </div>
          <motion.div whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }}>
            <Button
              className="gap-2"
              onClick={() => setShowDetect(!showDetect)}
            >
              <Search className="size-4" />
              Auto-Detect
            </Button>
          </motion.div>
        </div>

        {/* Auto-Detect Panel */}
        {showDetect && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
          >
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-base">Auto-Detect Relationships</CardTitle>
                <CardDescription>
                  Enter a document ID to scan for related documents
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="flex items-center gap-3">
                  <Input
                    placeholder="Document ID"
                    value={detectDocId}
                    onChange={(e) => setDetectDocId(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && handleDetect()}
                    className="max-w-sm"
                  />
                  <Button
                    onClick={handleDetect}
                    disabled={detecting || !detectDocId.trim()}
                    className="gap-2"
                  >
                    {detecting ? (
                      <Loader2 className="size-4 animate-spin" />
                    ) : (
                      <Sparkles className="size-4" />
                    )}
                    {detecting ? "Detecting..." : "Detect"}
                  </Button>
                </div>
                {detectResult && (
                  <p className="mt-2 text-sm text-green-600 dark:text-green-400">
                    {detectResult}
                  </p>
                )}
              </CardContent>
            </Card>
          </motion.div>
        )}

        {/* Stats Cards */}
        {!loading && relationships.length > 0 && (
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
        )}

        {/* Filter */}
        {!loading && relationships.length > 0 && (
          <div className="flex items-center gap-2">
            <span className="text-sm text-muted-foreground">Filter by type:</span>
            <select
              value={typeFilter}
              onChange={(e) => setTypeFilter(e.target.value)}
              className="h-9 rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-xs focus-visible:border-ring focus-visible:ring-ring/50 focus-visible:ring-[3px] outline-none"
            >
              <option value="all">All Types</option>
              {RELATIONSHIP_TYPES.map((type) => (
                <option key={type} value={type}>
                  {type.charAt(0).toUpperCase() + type.slice(1)}
                </option>
              ))}
            </select>
          </div>
        )}

        {error && (
          <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive">
            {error}
          </div>
        )}

        {/* Table */}
        {loading ? (
          <TableRowSkeleton rows={5} />
        ) : filtered.length === 0 && typeFilter !== "all" ? (
          <EmptyState
            icon={Link2}
            title={`No "${typeFilter}" relationships`}
            description="Try selecting a different type filter or auto-detect new relationships."
          />
        ) : filtered.length === 0 ? (
          <EmptyState
            icon={Link2}
            title="No relationships found"
            description="Upload and extract documents, then auto-detect relationships."
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
                  <TableHead>Source Document</TableHead>
                  <TableHead>Target Document</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Reference</TableHead>
                  <TableHead>Confidence</TableHead>
                  <TableHead>Created</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filtered.map((rel) => {
                  const badgeClass = typeBadgeConfig[rel.relationship_type] || "";
                  const confidencePercent = Math.round(rel.confidence * 100);
                  return (
                    <motion.tr
                      key={rel.id}
                      variants={listItem}
                      className="transition-colors hover:bg-accent/50"
                    >
                      <TableCell>
                        <span className="font-mono text-sm" title={rel.source_document_id}>
                          {truncateId(rel.source_document_id)}
                        </span>
                      </TableCell>
                      <TableCell>
                        <span className="font-mono text-sm" title={rel.target_document_id}>
                          {truncateId(rel.target_document_id)}
                        </span>
                      </TableCell>
                      <TableCell>
                        <Badge variant="secondary" className={badgeClass}>
                          {rel.relationship_type}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-muted-foreground text-sm">
                        {rel.reference_value || "--"}
                      </TableCell>
                      <TableCell>
                        <span className={`tabular-nums font-medium ${
                          confidencePercent >= 80
                            ? "text-green-600 dark:text-green-400"
                            : confidencePercent >= 60
                              ? "text-yellow-600 dark:text-yellow-400"
                              : "text-red-600 dark:text-red-400"
                        }`}>
                          {confidencePercent}%
                        </span>
                      </TableCell>
                      <TableCell className="text-muted-foreground">
                        {formatDate(rel.created_at)}
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

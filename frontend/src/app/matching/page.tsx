"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import {
  GitMerge,
  Loader2,
  PlayCircle,
  Check,
  X,
  ChevronDown,
  ChevronRight,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
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
import { runThreeWayMatch } from "@/lib/api-client";
import type { ThreeWayMatchResult, FieldMatch, LineItemMatch } from "@/types/matching";

const statusConfig: Record<string, { className: string; label: string }> = {
  full_match: { className: "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300", label: "Full Match" },
  partial_match: { className: "bg-yellow-100 text-yellow-700 dark:bg-yellow-900 dark:text-yellow-300", label: "Partial Match" },
  mismatch: { className: "bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300", label: "Mismatch" },
  incomplete: { className: "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300", label: "Incomplete" },
};

const listContainer = { hidden: {}, show: { transition: { staggerChildren: 0.04 } } };
const listItem = { hidden: { opacity: 0, x: -10 }, show: { opacity: 1, x: 0 } };

function FieldMatchTable({ fields, title }: { fields: FieldMatch[]; title: string }) {
  if (fields.length === 0) return null;
  return (
    <AnimatedCard delay={0.1}>
      <CardHeader className="pb-3">
        <CardTitle className="text-base">{title}</CardTitle>
      </CardHeader>
      <CardContent>
        <motion.div variants={listContainer} initial="hidden" animate="show">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Field</TableHead>
                <TableHead>Source Value</TableHead>
                <TableHead>Target Value</TableHead>
                <TableHead>Match</TableHead>
                <TableHead>Confidence</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {fields.map((field, i) => (
                <motion.tr key={`${field.field_name}-${i}`} variants={listItem} className="transition-colors hover:bg-accent/50">
                  <TableCell className="font-medium">{field.field_name}</TableCell>
                  <TableCell className="font-mono text-sm">
                    {field.source_value != null ? String(field.source_value) : "--"}
                  </TableCell>
                  <TableCell className="font-mono text-sm">
                    {field.target_value != null ? String(field.target_value) : "--"}
                  </TableCell>
                  <TableCell>
                    {field.matched ? (
                      <Check className="size-4 text-green-600 dark:text-green-400" />
                    ) : (
                      <X className="size-4 text-red-600 dark:text-red-400" />
                    )}
                  </TableCell>
                  <TableCell>
                    <span className={`tabular-nums font-medium ${
                      field.confidence >= 0.8
                        ? "text-green-600 dark:text-green-400"
                        : field.confidence >= 0.6
                          ? "text-yellow-600 dark:text-yellow-400"
                          : "text-red-600 dark:text-red-400"
                    }`}>
                      {Math.round(field.confidence * 100)}%
                    </span>
                  </TableCell>
                </motion.tr>
              ))}
            </TableBody>
          </Table>
        </motion.div>
      </CardContent>
    </AnimatedCard>
  );
}

function LineItemMatchSection({ items }: { items: LineItemMatch[] }) {
  const [expanded, setExpanded] = useState<Record<number, boolean>>({});

  if (items.length === 0) return null;

  return (
    <AnimatedCard delay={0.15}>
      <CardHeader className="pb-3">
        <CardTitle className="text-base">Line Item Matches</CardTitle>
      </CardHeader>
      <CardContent>
        <motion.div variants={listContainer} initial="hidden" animate="show">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-10"></TableHead>
                <TableHead>PO Item</TableHead>
                <TableHead>Invoice Item</TableHead>
                <TableHead>Match</TableHead>
                <TableHead>Confidence</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {items.map((item, i) => {
                const isExpanded = expanded[i] ?? false;
                return (
                  <motion.tr
                    key={i}
                    variants={listItem}
                    className="transition-colors hover:bg-accent/50 cursor-pointer"
                    onClick={() => setExpanded((prev) => ({ ...prev, [i]: !isExpanded }))}
                  >
                    <TableCell>
                      {item.field_matches.length > 0 && (
                        isExpanded
                          ? <ChevronDown className="size-4 text-muted-foreground" />
                          : <ChevronRight className="size-4 text-muted-foreground" />
                      )}
                    </TableCell>
                    <TableCell className="tabular-nums">
                      {item.po_index != null ? `#${item.po_index + 1}` : "--"}
                    </TableCell>
                    <TableCell className="tabular-nums">
                      {item.invoice_index != null ? `#${item.invoice_index + 1}` : "--"}
                    </TableCell>
                    <TableCell>
                      {item.overall_matched ? (
                        <Check className="size-4 text-green-600 dark:text-green-400" />
                      ) : (
                        <X className="size-4 text-red-600 dark:text-red-400" />
                      )}
                    </TableCell>
                    <TableCell>
                      <span className={`tabular-nums font-medium ${
                        item.confidence >= 0.8
                          ? "text-green-600 dark:text-green-400"
                          : item.confidence >= 0.6
                            ? "text-yellow-600 dark:text-yellow-400"
                            : "text-red-600 dark:text-red-400"
                      }`}>
                        {Math.round(item.confidence * 100)}%
                      </span>
                    </TableCell>
                  </motion.tr>
                );
              })}
            </TableBody>
          </Table>
          {/* Expanded field details rendered outside the table */}
          {items.map((item, i) => (
            expanded[i] && item.field_matches.length > 0 ? (
              <motion.div
                key={`detail-${i}`}
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: "auto" }}
                className="border-t px-4 py-3"
              >
                <p className="text-xs font-medium text-muted-foreground mb-2">
                  Field Details for PO #{item.po_index != null ? item.po_index + 1 : "?"} / Invoice #{item.invoice_index != null ? item.invoice_index + 1 : "?"}
                </p>
                <div className="space-y-1">
                  {item.field_matches.map((fm, fi) => (
                    <div key={fi} className="flex items-center gap-3 text-sm">
                      {fm.matched ? (
                        <Check className="size-3 text-green-600 dark:text-green-400 shrink-0" />
                      ) : (
                        <X className="size-3 text-red-600 dark:text-red-400 shrink-0" />
                      )}
                      <span className="font-medium min-w-[120px]">{fm.field_name}</span>
                      <span className="font-mono text-muted-foreground">
                        {fm.source_value != null ? String(fm.source_value) : "--"}
                      </span>
                      <span className="text-muted-foreground">vs</span>
                      <span className="font-mono text-muted-foreground">
                        {fm.target_value != null ? String(fm.target_value) : "--"}
                      </span>
                    </div>
                  ))}
                </div>
              </motion.div>
            ) : null
          ))}
        </motion.div>
      </CardContent>
    </AnimatedCard>
  );
}

export default function MatchingPage() {
  const [poDocId, setPoDocId] = useState("");
  const [bolDocId, setBolDocId] = useState("");
  const [invoiceDocId, setInvoiceDocId] = useState("");
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<ThreeWayMatchResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleRunMatch = async () => {
    setRunning(true);
    setError(null);
    setResult(null);
    try {
      const data: Record<string, string> = {};
      if (poDocId.trim()) data.po_document_id = poDocId.trim();
      if (bolDocId.trim()) data.bol_document_id = bolDocId.trim();
      if (invoiceDocId.trim()) data.invoice_document_id = invoiceDocId.trim();
      const matchResult = await runThreeWayMatch(data);
      setResult(matchResult);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Match failed");
    } finally {
      setRunning(false);
    }
  };

  const hasInput = poDocId.trim() || bolDocId.trim() || invoiceDocId.trim();
  const sc = result ? statusConfig[result.status] || statusConfig.incomplete : null;
  const confidencePercent = result ? Math.round(result.overall_confidence * 100) : 0;

  return (
    <PageTransition>
      <div className="space-y-6">
        {/* Header */}
        <div>
          <h2 className="text-2xl font-bold tracking-tight">3-Way Matching</h2>
          <p className="text-muted-foreground">
            Compare Purchase Orders, Bills of Lading, and Invoices for consistency
          </p>
        </div>

        {/* Input Form */}
        <AnimatedCard delay={0}>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">Document IDs</CardTitle>
            <CardDescription>
              Enter document IDs to compare. All fields are optional.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid gap-4 md:grid-cols-3">
              <div className="space-y-2">
                <Label htmlFor="po-id">PO Document ID</Label>
                <Input
                  id="po-id"
                  placeholder="Enter PO document ID"
                  value={poDocId}
                  onChange={(e) => setPoDocId(e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="bol-id">BOL / Packing List Document ID</Label>
                <Input
                  id="bol-id"
                  placeholder="Enter BOL document ID"
                  value={bolDocId}
                  onChange={(e) => setBolDocId(e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="inv-id">Invoice Document ID</Label>
                <Input
                  id="inv-id"
                  placeholder="Enter invoice document ID"
                  value={invoiceDocId}
                  onChange={(e) => setInvoiceDocId(e.target.value)}
                />
              </div>
            </div>
            <div className="mt-4">
              <motion.div whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }} className="inline-block">
                <Button
                  onClick={handleRunMatch}
                  disabled={running || !hasInput}
                  className="gap-2"
                >
                  {running ? (
                    <Loader2 className="size-4 animate-spin" />
                  ) : (
                    <PlayCircle className="size-4" />
                  )}
                  {running ? "Running..." : "Run Match"}
                </Button>
              </motion.div>
            </div>
          </CardContent>
        </AnimatedCard>

        {error && (
          <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive">
            {error}
          </div>
        )}

        {/* Results */}
        {running && (
          <div className="flex flex-col items-center justify-center py-12 gap-4">
            <Loader2 className="size-8 animate-spin text-primary" />
            <p className="text-sm text-muted-foreground">Running 3-way match analysis...</p>
          </div>
        )}

        {!running && !result && !error && (
          <EmptyState
            icon={GitMerge}
            title="Run a 3-way match to compare documents"
            description="Enter document IDs above and click Run Match to compare Purchase Orders, Bills of Lading, and Invoices."
          />
        )}

        {result && !running && (
          <div className="space-y-6">
            {/* Overall Result */}
            <AnimatedCard delay={0.05}>
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                  <CardTitle className="text-base">Match Result</CardTitle>
                  {sc && (
                    <Badge variant="secondary" className={sc.className}>
                      {sc.label}
                    </Badge>
                  )}
                </div>
              </CardHeader>
              <CardContent>
                <div className="flex items-center gap-6">
                  <div className="text-center">
                    <div className={`text-4xl font-bold tabular-nums ${
                      confidencePercent >= 80
                        ? "text-green-600 dark:text-green-400"
                        : confidencePercent >= 60
                          ? "text-yellow-600 dark:text-yellow-400"
                          : "text-red-600 dark:text-red-400"
                    }`}>
                      {confidencePercent}%
                    </div>
                    <p className="text-xs text-muted-foreground mt-1">Overall Confidence</p>
                  </div>
                  <div className="flex-1">
                    <p className="text-sm text-muted-foreground">{result.summary}</p>
                  </div>
                </div>
              </CardContent>
            </AnimatedCard>

            {/* PO to Invoice Comparison */}
            <FieldMatchTable fields={result.po_to_invoice} title="PO to Invoice Comparison" />

            {/* PO to BOL Comparison */}
            <FieldMatchTable fields={result.po_to_bol} title="PO to BOL Comparison" />

            {/* Line Item Matches */}
            <LineItemMatchSection items={result.line_item_matches} />
          </div>
        )}
      </div>
    </PageTransition>
  );
}

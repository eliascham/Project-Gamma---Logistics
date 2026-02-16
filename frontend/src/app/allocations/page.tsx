"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { DollarSign, FileText, Loader2, Sparkles } from "lucide-react";
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
import { getDocuments, seedAllocationRules } from "@/lib/api-client";
import type { Document } from "@/types/document";

const allocationStatusConfig: Record<
  string,
  { variant: "default" | "secondary" | "destructive" | "outline"; label: string }
> = {
  pending: { variant: "outline", label: "Not Allocated" },
  extracted: { variant: "secondary", label: "Ready" },
  allocated: { variant: "default", label: "Allocated" },
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

export default function AllocationsPage() {
  const router = useRouter();
  const [documents, setDocuments] = useState<Document[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [seeding, setSeeding] = useState(false);

  useEffect(() => {
    getDocuments()
      .then((data) => {
        // Only show documents that have been extracted (ready for allocation)
        const extracted = data.documents.filter(
          (d) => d.status === "extracted"
        );
        setDocuments(extracted);
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  const handleSeedRules = async () => {
    setSeeding(true);
    try {
      await seedAllocationRules();
    } catch (err) {
      console.error("Failed to seed rules:", err);
    } finally {
      setSeeding(false);
    }
  };

  return (
    <PageTransition>
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-2xl font-bold tracking-tight">
              Cost Allocations
            </h2>
            <p className="text-muted-foreground">
              AI-powered cost allocation for extracted invoices
            </p>
          </div>
          <motion.div whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }}>
            <Button
              variant="outline"
              className="gap-2"
              onClick={handleSeedRules}
              disabled={seeding}
            >
              {seeding ? (
                <Loader2 className="size-4 animate-spin" />
              ) : (
                <Sparkles className="size-4" />
              )}
              Seed Demo Rules
            </Button>
          </motion.div>
        </div>

        {loading ? (
          <TableRowSkeleton rows={5} />
        ) : error ? (
          <p className="text-destructive">
            Failed to load documents: {error}
          </p>
        ) : documents.length === 0 ? (
          <EmptyState
            icon={DollarSign}
            title="No documents ready"
            description="Extract documents first, then come back here to run cost allocation."
            actionLabel="Go to Documents"
            onAction={() => router.push("/documents")}
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
                  <TableHead>Document</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Uploaded</TableHead>
                  <TableHead>Allocation Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {documents.map((doc) => (
                  <motion.tr
                    key={doc.id}
                    variants={listItem}
                    onClick={() =>
                      router.push(`/allocations/${doc.id}`)
                    }
                    className="cursor-pointer transition-colors hover:bg-accent/50"
                  >
                    <TableCell>
                      <div className="flex items-center gap-2.5">
                        <FileText className="size-4 text-muted-foreground" />
                        <span className="font-medium">
                          {doc.original_filename}
                        </span>
                      </div>
                    </TableCell>
                    <TableCell>
                      <span className="rounded bg-muted px-1.5 py-0.5 text-xs font-mono uppercase">
                        {doc.file_type}
                      </span>
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {formatDate(doc.created_at)}
                    </TableCell>
                    <TableCell>
                      <Badge variant="secondary">Ready</Badge>
                    </TableCell>
                  </motion.tr>
                ))}
              </TableBody>
            </Table>
          </motion.div>
        )}
      </div>
    </PageTransition>
  );
}

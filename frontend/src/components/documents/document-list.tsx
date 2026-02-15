"use client";

import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { FileText, Loader2, Upload } from "lucide-react";
import type { Document } from "@/types/document";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { EmptyState } from "@/components/shared/empty-state";

const statusConfig: Record<
  string,
  { variant: "default" | "secondary" | "destructive" | "outline"; label: string }
> = {
  pending: { variant: "outline", label: "Pending" },
  processing: { variant: "secondary", label: "Processing" },
  extracted: { variant: "default", label: "Extracted" },
  failed: { variant: "destructive", label: "Failed" },
};

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
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

const listContainer = { hidden: {}, show: { transition: { staggerChildren: 0.04 } } };
const listItem = { hidden: { opacity: 0, x: -10 }, show: { opacity: 1, x: 0 } };

export function DocumentList({ documents }: { documents: Document[] }) {
  const router = useRouter();

  if (documents.length === 0) {
    return (
      <EmptyState
        icon={FileText}
        title="No documents yet"
        description="Upload your first logistics document to get started with extraction."
        actionLabel="Upload Document"
        onAction={() => router.push("/documents/upload")}
      />
    );
  }

  return (
    <motion.div variants={listContainer} initial="hidden" animate="show">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Filename</TableHead>
            <TableHead>Type</TableHead>
            <TableHead>Size</TableHead>
            <TableHead>Status</TableHead>
            <TableHead>Uploaded</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {documents.map((doc) => {
            const status = statusConfig[doc.status] || statusConfig.pending;
            return (
              <motion.tr
                key={doc.id}
                variants={listItem}
                onClick={() => router.push(`/documents/${doc.id}`)}
                className="cursor-pointer transition-colors hover:bg-accent/50"
              >
                <TableCell>
                  <div className="flex items-center gap-2.5">
                    <FileText className="size-4 text-muted-foreground" />
                    <span className="font-medium">{doc.original_filename}</span>
                  </div>
                </TableCell>
                <TableCell>
                  <span className="rounded bg-muted px-1.5 py-0.5 text-xs font-mono uppercase">
                    {doc.file_type}
                  </span>
                </TableCell>
                <TableCell className="text-muted-foreground">
                  {formatFileSize(doc.file_size)}
                </TableCell>
                <TableCell>
                  <Badge variant={status.variant} className="gap-1">
                    {doc.status === "processing" && (
                      <Loader2 className="size-3 animate-spin" />
                    )}
                    {doc.status === "pending" && (
                      <span className="size-1.5 rounded-full bg-amber-500 animate-pulse" />
                    )}
                    {status.label}
                  </Badge>
                </TableCell>
                <TableCell className="text-muted-foreground">
                  {formatDate(doc.created_at)}
                </TableCell>
              </motion.tr>
            );
          })}
        </TableBody>
      </Table>
    </motion.div>
  );
}

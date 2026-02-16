"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { motion } from "framer-motion";
import {
  ArrowLeft,
  FileText,
  Image,
  FileSpreadsheet,
  Loader2,
  Play,
  DollarSign,
  Database,
} from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { PageTransition } from "@/components/shared/page-transition";
import { DocumentDetailSkeleton } from "@/components/shared/loading-skeleton";
import { StatusTimeline } from "@/components/documents/status-timeline";
import { ExtractionResultView } from "@/components/documents/extraction-result-view";
import { useExtractionPolling } from "@/hooks/use-extraction-polling";
import {
  getDocument,
  getExtraction,
  triggerExtraction,
  triggerAllocation,
  ingestDocument,
} from "@/lib/api-client";
import type { Document } from "@/types/document";
import type { ExtractionResponse } from "@/types/extraction";

const docTypeLabels: Record<string, string> = {
  freight_invoice: "Freight Invoice",
  bill_of_lading: "Bill of Lading",
  unknown: "Unknown",
};

function getFileIcon(fileType: string) {
  if (fileType === "csv") return FileSpreadsheet;
  if (["png", "jpg", "jpeg", "tiff", "tif"].includes(fileType)) return Image;
  return FileText;
}

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

export default function DocumentDetailPage() {
  const params = useParams();
  const router = useRouter();
  const documentId = params.id as string;

  const [document, setDocument] = useState<Document | null>(null);
  const [extraction, setExtraction] = useState<ExtractionResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [extracting, setExtracting] = useState(false);
  const [allocating, setAllocating] = useState(false);
  const [ingesting, setIngesting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const { status, setStatus } = useExtractionPolling({
    documentId,
    initialStatus: document?.status || "pending",
    enabled: !!document && (document.status === "processing"),
  });

  // Fetch document on mount
  useEffect(() => {
    async function load() {
      try {
        const doc = await getDocument(documentId);
        setDocument(doc);
        setStatus(doc.status);

        if (doc.status === "extracted") {
          try {
            const ext = await getExtraction(documentId);
            setExtraction(ext);
          } catch {
            // Extraction data might not exist yet
          }
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load document");
      } finally {
        setLoading(false);
      }
    }

    load();
  }, [documentId, setStatus]);

  // When polling detects extraction is complete, fetch extraction data
  useEffect(() => {
    if (status === "extracted" && !extraction) {
      getExtraction(documentId)
        .then(setExtraction)
        .catch(() => {});
      // Also refresh the document record
      getDocument(documentId)
        .then(setDocument)
        .catch(() => {});
    }
  }, [status, extraction, documentId]);

  async function handleRunExtraction() {
    setExtracting(true);
    setStatus("processing");
    toast.info("Starting extraction pipeline...");

    try {
      const result = await triggerExtraction(documentId);
      setExtraction(result);
      setStatus("extracted");

      // Refresh document
      const doc = await getDocument(documentId);
      setDocument(doc);

      toast.success("Extraction complete!");
    } catch (err) {
      setStatus("failed");
      toast.error(
        err instanceof Error ? err.message : "Extraction failed"
      );
    } finally {
      setExtracting(false);
    }
  }

  if (loading) {
    return (
      <PageTransition>
        <DocumentDetailSkeleton />
      </PageTransition>
    );
  }

  if (error || !document) {
    return (
      <PageTransition>
        <div className="space-y-4">
          <Button variant="ghost" onClick={() => router.push("/documents")} className="gap-2">
            <ArrowLeft className="size-4" /> Back to Documents
          </Button>
          <p className="text-destructive">{error || "Document not found"}</p>
        </div>
      </PageTransition>
    );
  }

  const FileIcon = getFileIcon(document.file_type);
  const currentStatus = status;

  return (
    <PageTransition>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center gap-4">
          <Button
            variant="ghost"
            size="icon"
            onClick={() => router.push("/documents")}
          >
            <ArrowLeft className="size-4" />
          </Button>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-3">
              <FileIcon className="size-5 text-muted-foreground shrink-0" />
              <h2 className="text-xl font-bold tracking-tight truncate">
                {document.original_filename}
              </h2>
            </div>
            <p className="text-sm text-muted-foreground mt-0.5">
              Uploaded {formatDate(document.created_at)}
            </p>
          </div>
        </div>

        {/* Main Grid */}
        <div className="grid gap-6 lg:grid-cols-3">
          {/* Left Column — Metadata */}
          <div className="space-y-4">
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.1 }}
            >
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="text-base">Document Info</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div className="flex justify-between text-sm">
                    <span className="text-muted-foreground">Type</span>
                    <span className="rounded bg-muted px-1.5 py-0.5 font-mono text-xs uppercase">
                      {document.file_type}
                    </span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-muted-foreground">Size</span>
                    <span>{formatFileSize(document.file_size)}</span>
                  </div>
                  {document.page_count && (
                    <div className="flex justify-between text-sm">
                      <span className="text-muted-foreground">Pages</span>
                      <span>{document.page_count}</span>
                    </div>
                  )}
                  {document.document_type && (
                    <div className="flex justify-between text-sm">
                      <span className="text-muted-foreground">Doc Type</span>
                      <Badge variant="secondary" className="text-xs">
                        {docTypeLabels[document.document_type] || document.document_type}
                      </Badge>
                    </div>
                  )}
                  <Separator />
                  <StatusTimeline status={currentStatus} />
                </CardContent>
              </Card>
            </motion.div>

            {/* Action Buttons */}
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.2 }}
              className="space-y-2"
            >
              {(currentStatus === "pending" || currentStatus === "failed") && (
                <Button
                  onClick={handleRunExtraction}
                  disabled={extracting}
                  className="w-full gap-2"
                >
                  {extracting ? (
                    <Loader2 className="size-4 animate-spin" />
                  ) : (
                    <Play className="size-4" />
                  )}
                  {extracting ? "Extracting..." : "Run Extraction"}
                </Button>
              )}

              {currentStatus === "extracted" && (
                <>
                  <Button
                    onClick={async () => {
                      setAllocating(true);
                      try {
                        await triggerAllocation(documentId);
                        toast.success("Allocation complete!");
                        router.push(`/allocations/${documentId}`);
                      } catch (err) {
                        toast.error(
                          err instanceof Error ? err.message : "Allocation failed"
                        );
                      } finally {
                        setAllocating(false);
                      }
                    }}
                    disabled={allocating}
                    variant="outline"
                    className="w-full gap-2"
                  >
                    {allocating ? (
                      <Loader2 className="size-4 animate-spin" />
                    ) : (
                      <DollarSign className="size-4" />
                    )}
                    {allocating ? "Allocating..." : "Run Allocation"}
                  </Button>
                  <Button
                    onClick={async () => {
                      setIngesting(true);
                      try {
                        await ingestDocument(documentId);
                        toast.success("Added to knowledge base!");
                      } catch (err) {
                        toast.error(
                          err instanceof Error ? err.message : "Ingestion failed"
                        );
                      } finally {
                        setIngesting(false);
                      }
                    }}
                    disabled={ingesting}
                    variant="outline"
                    className="w-full gap-2"
                  >
                    {ingesting ? (
                      <Loader2 className="size-4 animate-spin" />
                    ) : (
                      <Database className="size-4" />
                    )}
                    {ingesting ? "Ingesting..." : "Add to Knowledge Base"}
                  </Button>
                </>
              )}
            </motion.div>
          </div>

          {/* Right Column — Extraction Results */}
          <div className="lg:col-span-2">
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.2 }}
            >
              {extraction ? (
                <ExtractionResultView extraction={extraction} />
              ) : currentStatus === "processing" || extracting ? (
                <Card>
                  <CardContent className="flex flex-col items-center justify-center py-16 gap-4">
                    <Loader2 className="size-8 animate-spin text-primary" />
                    <div className="text-center">
                      <p className="font-medium">Extraction in progress</p>
                      <p className="text-sm text-muted-foreground mt-1">
                        Running classification and data extraction...
                      </p>
                    </div>
                  </CardContent>
                </Card>
              ) : currentStatus === "pending" ? (
                <Card>
                  <CardContent className="flex flex-col items-center justify-center py-16 gap-4">
                    <FileText className="size-8 text-muted-foreground/50" />
                    <div className="text-center">
                      <p className="font-medium">No extraction yet</p>
                      <p className="text-sm text-muted-foreground mt-1">
                        Click &quot;Run Extraction&quot; to process this document
                      </p>
                    </div>
                  </CardContent>
                </Card>
              ) : currentStatus === "failed" ? (
                <Card>
                  <CardContent className="flex flex-col items-center justify-center py-16 gap-4">
                    <div className="rounded-full bg-destructive/10 p-3">
                      <FileText className="size-6 text-destructive" />
                    </div>
                    <div className="text-center">
                      <p className="font-medium">Extraction failed</p>
                      <p className="text-sm text-muted-foreground mt-1">
                        You can retry the extraction using the button on the left
                      </p>
                    </div>
                  </CardContent>
                </Card>
              ) : null}
            </motion.div>
          </div>
        </div>
      </div>
    </PageTransition>
  );
}

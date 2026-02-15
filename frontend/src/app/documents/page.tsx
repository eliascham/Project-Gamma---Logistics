"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Upload } from "lucide-react";
import { motion } from "framer-motion";
import { Button } from "@/components/ui/button";
import { DocumentList } from "@/components/documents/document-list";
import { TableRowSkeleton } from "@/components/shared/loading-skeleton";
import { PageTransition } from "@/components/shared/page-transition";
import { getDocuments } from "@/lib/api-client";
import type { Document } from "@/types/document";

export default function DocumentsPage() {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getDocuments()
      .then((data) => setDocuments(data.documents))
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  return (
    <PageTransition>
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-2xl font-bold tracking-tight">Documents</h2>
            <p className="text-muted-foreground">
              Manage uploaded logistics documents
            </p>
          </div>
          <Link href="/documents/upload">
            <motion.div whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }}>
              <Button className="gap-2">
                <Upload className="size-4" />
                Upload Document
              </Button>
            </motion.div>
          </Link>
        </div>

        {loading ? (
          <TableRowSkeleton rows={5} />
        ) : error ? (
          <p className="text-destructive">Failed to load documents: {error}</p>
        ) : (
          <DocumentList documents={documents} />
        )}
      </div>
    </PageTransition>
  );
}

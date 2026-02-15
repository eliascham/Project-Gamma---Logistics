"use client";

import { PageTransition } from "@/components/shared/page-transition";
import { DocumentUploadForm } from "@/components/documents/document-upload-form";

export default function UploadPage() {
  return (
    <PageTransition>
      <div className="space-y-6">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Upload Document</h2>
          <p className="text-muted-foreground">
            Upload a logistics document for extraction and processing
          </p>
        </div>
        <DocumentUploadForm />
      </div>
    </PageTransition>
  );
}

"use client";

import { useEffect, useRef, useState } from "react";
import { getDocument } from "@/lib/api-client";
import type { DocumentStatus } from "@/types/document";

interface UseExtractionPollingOptions {
  documentId: string;
  initialStatus: DocumentStatus;
  intervalMs?: number;
  enabled?: boolean;
}

export function useExtractionPolling({
  documentId,
  initialStatus,
  intervalMs = 3000,
  enabled = true,
}: UseExtractionPollingOptions) {
  const [status, setStatus] = useState<DocumentStatus>(initialStatus);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const shouldPoll =
    enabled && (status === "pending" || status === "processing");

  useEffect(() => {
    if (!shouldPoll) return;

    async function poll() {
      try {
        const doc = await getDocument(documentId);
        setStatus(doc.status);
      } catch {
        // Silently ignore polling errors
      }
    }

    intervalRef.current = setInterval(poll, intervalMs);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [documentId, intervalMs, shouldPoll]);

  return { status, setStatus };
}

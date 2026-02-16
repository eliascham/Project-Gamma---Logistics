import type { CostAllocation, AllocationLineItem, AllocationRule } from "@/types/allocation";
import type { Document, DocumentListResponse, DocumentUploadResponse } from "@/types/document";
import type { ExtractionResponse } from "@/types/extraction";
import type { RagQueryResponse, RagStats } from "@/types/rag";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const headers: Record<string, string> = {};
  // Only set Content-Type for requests with a JSON string body
  if (options?.body && typeof options.body === "string") {
    headers["Content-Type"] = "application/json";
  }

  const res = await fetch(`${API_BASE}/api/v1${path}`, {
    ...options,
    headers: { ...headers, ...(options?.headers as Record<string, string>) },
  });

  if (!res.ok) {
    const detail = await res.text().catch(() => "Unknown error");
    throw new ApiError(res.status, detail);
  }

  return res.json();
}

export async function getDocuments(
  page = 1,
  perPage = 20,
): Promise<DocumentListResponse> {
  return apiFetch<DocumentListResponse>(
    `/documents?page=${page}&per_page=${perPage}`,
  );
}

export async function getDocument(id: string): Promise<Document> {
  return apiFetch<Document>(`/documents/${id}`);
}

export async function uploadDocument(
  file: File,
): Promise<DocumentUploadResponse> {
  const formData = new FormData();
  formData.append("file", file);

  const res = await fetch(`${API_BASE}/api/v1/documents`, {
    method: "POST",
    body: formData,
  });

  if (!res.ok) {
    const detail = await res.text().catch(() => "Upload failed");
    throw new ApiError(res.status, detail);
  }

  return res.json();
}

export async function getExtraction(
  documentId: string,
): Promise<ExtractionResponse> {
  return apiFetch<ExtractionResponse>(`/extractions/${documentId}`);
}

export async function triggerExtraction(
  documentId: string,
): Promise<ExtractionResponse> {
  return apiFetch<ExtractionResponse>(`/extractions/${documentId}`, {
    method: "POST",
  });
}

export function uploadDocumentWithProgress(
  file: File,
  onProgress: (percent: number) => void,
): Promise<DocumentUploadResponse> {
  return new Promise((resolve, reject) => {
    const formData = new FormData();
    formData.append("file", file);

    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API_BASE}/api/v1/documents`);

    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) {
        onProgress(Math.round((e.loaded / e.total) * 100));
      }
    };

    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(JSON.parse(xhr.responseText));
      } else {
        reject(new ApiError(xhr.status, xhr.responseText));
      }
    };

    xhr.onerror = () => reject(new Error("Upload failed"));
    xhr.send(formData);
  });
}

export async function getHealth() {
  return apiFetch("/health");
}

// ── Cost Allocation ──────────────────────────────────────────────

export async function triggerAllocation(
  documentId: string,
): Promise<CostAllocation> {
  return apiFetch<CostAllocation>(`/allocations/${documentId}`, {
    method: "POST",
  });
}

export async function getAllocation(
  documentId: string,
): Promise<CostAllocation> {
  return apiFetch<CostAllocation>(`/allocations/${documentId}`);
}

export async function overrideLineItem(
  lineItemId: string,
  override: {
    project_code?: string;
    cost_center?: string;
    gl_account?: string;
  },
): Promise<AllocationLineItem> {
  return apiFetch<AllocationLineItem>(
    `/allocations/line-items/${lineItemId}`,
    {
      method: "PUT",
      body: JSON.stringify(override),
    },
  );
}

export async function approveAllocation(
  allocationId: string,
  action: "approved" | "rejected",
): Promise<CostAllocation> {
  return apiFetch<CostAllocation>(
    `/allocations/${allocationId}/approve`,
    {
      method: "POST",
      body: JSON.stringify({ action }),
    },
  );
}

export async function getAllocationRules(): Promise<AllocationRule[]> {
  return apiFetch<AllocationRule[]>("/allocations/rules/list");
}

export async function seedAllocationRules(): Promise<{ message: string }> {
  return apiFetch<{ message: string }>("/allocations/rules/seed", {
    method: "POST",
  });
}

// ── RAG Q&A ──────────────────────────────────────────────────────

export async function askQuestion(
  question: string,
): Promise<RagQueryResponse> {
  return apiFetch<RagQueryResponse>("/rag/query", {
    method: "POST",
    body: JSON.stringify({ question }),
  });
}

export async function ingestDocument(
  documentId: string,
): Promise<{ message: string }> {
  return apiFetch<{ message: string }>(`/rag/ingest/${documentId}`, {
    method: "POST",
  });
}

export async function seedRAGData(): Promise<{ message: string }> {
  return apiFetch<{ message: string }>("/rag/ingest/seed", {
    method: "POST",
  });
}

export async function getRAGStats(): Promise<RagStats> {
  return apiFetch<RagStats>("/rag/stats");
}

// ── Review Queue ─────────────────────────────────────────────────

export async function getReviewQueue(
  params?: { status?: string; item_type?: string; page?: number; per_page?: number },
) {
  const qs = new URLSearchParams();
  if (params?.status) qs.set("status", params.status);
  if (params?.item_type) qs.set("item_type", params.item_type);
  if (params?.page) qs.set("page", String(params.page));
  if (params?.per_page) qs.set("per_page", String(params.per_page));
  return apiFetch(`/reviews/queue?${qs.toString()}`);
}

export async function getReviewItem(id: string) {
  return apiFetch(`/reviews/${id}`);
}

export async function reviewAction(
  id: string,
  action: string,
  notes?: string,
) {
  return apiFetch(`/reviews/${id}/action`, {
    method: "POST",
    body: JSON.stringify({ action, notes, reviewed_by: "user" }),
  });
}

export async function getReviewStats() {
  return apiFetch("/reviews/stats");
}

// ── Anomalies ────────────────────────────────────────────────────

export async function scanAnomalies(documentId?: string) {
  return apiFetch("/anomalies/scan", {
    method: "POST",
    body: JSON.stringify({ document_id: documentId || null }),
  });
}

export async function getAnomalies(
  params?: { anomaly_type?: string; severity?: string; is_resolved?: boolean; page?: number },
) {
  const qs = new URLSearchParams();
  if (params?.anomaly_type) qs.set("anomaly_type", params.anomaly_type);
  if (params?.severity) qs.set("severity", params.severity);
  if (params?.is_resolved !== undefined) qs.set("is_resolved", String(params.is_resolved));
  if (params?.page) qs.set("page", String(params.page));
  return apiFetch(`/anomalies/list?${qs.toString()}`);
}

export async function getAnomaly(id: string) {
  return apiFetch(`/anomalies/${id}`);
}

export async function resolveAnomaly(id: string, notes?: string) {
  return apiFetch(`/anomalies/${id}/resolve`, {
    method: "POST",
    body: JSON.stringify({ resolved_by: "user", resolution_notes: notes }),
  });
}

export async function getAnomalyStats() {
  return apiFetch("/anomalies/stats");
}

// ── Reconciliation ───────────────────────────────────────────────

export async function runReconciliation(name?: string) {
  return apiFetch("/reconciliation/run", {
    method: "POST",
    body: JSON.stringify({ name, run_by: "user" }),
  });
}

export async function seedReconciliationData() {
  return apiFetch("/reconciliation/seed", { method: "POST" });
}

export async function getReconciliationRuns(page = 1) {
  return apiFetch(`/reconciliation/runs?page=${page}`);
}

export async function getReconciliationRun(id: string) {
  return apiFetch(`/reconciliation/${id}`);
}

export async function getReconciliationStats() {
  return apiFetch("/reconciliation/stats");
}

// ── Audit ────────────────────────────────────────────────────────

export async function getAuditEvents(
  params?: { entity_type?: string; event_type?: string; page?: number },
) {
  const qs = new URLSearchParams();
  if (params?.entity_type) qs.set("entity_type", params.entity_type);
  if (params?.event_type) qs.set("event_type", params.event_type);
  if (params?.page) qs.set("page", String(params.page));
  return apiFetch(`/audit/events?${qs.toString()}`);
}

export async function generateAuditReport() {
  return apiFetch("/audit/reports", {
    method: "POST",
    body: JSON.stringify({ include_summary: true }),
  });
}

export async function getAuditStats() {
  return apiFetch("/audit/stats");
}

// ── MCP ──────────────────────────────────────────────────────────

export async function getMcpStatus() {
  return apiFetch("/mcp/status");
}

export async function seedMcpData() {
  return apiFetch("/mcp/seed", { method: "POST" });
}

export async function getMcpStats() {
  return apiFetch("/mcp/stats");
}

export async function getMcpRecords(
  params?: { source?: string; record_type?: string; search?: string; page?: number; per_page?: number },
) {
  const qs = new URLSearchParams();
  if (params?.source) qs.set("source", params.source);
  if (params?.record_type) qs.set("record_type", params.record_type);
  if (params?.search) qs.set("search", params.search);
  if (params?.page) qs.set("page", String(params.page));
  if (params?.per_page) qs.set("per_page", String(params.per_page));
  return apiFetch(`/mcp/records?${qs.toString()}`);
}

export async function getMcpBudgets() {
  return apiFetch("/mcp/budgets");
}

// ── Metrics ──────────────────────────────────────────────────────

export async function getMetrics() {
  return apiFetch("/metrics");
}

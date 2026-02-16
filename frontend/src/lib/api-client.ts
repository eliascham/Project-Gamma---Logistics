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

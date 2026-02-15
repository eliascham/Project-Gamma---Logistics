export type DocumentStatus = "pending" | "processing" | "extracted" | "failed";
export type DocumentType = "freight_invoice" | "bill_of_lading" | "unknown";

export interface Document {
  id: string;
  filename: string;
  original_filename: string;
  file_type: string;
  mime_type: string;
  file_size: number;
  status: DocumentStatus;
  document_type: DocumentType | null;
  page_count: number | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface DocumentListResponse {
  documents: Document[];
  total: number;
  page: number;
  per_page: number;
}

export interface DocumentUploadResponse {
  id: string;
  filename: string;
  original_filename: string;
  file_type: string;
  file_size: number;
  status: DocumentStatus;
  uploaded_at: string;
}

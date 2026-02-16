export interface SourceChunk {
  document_id: string | null;
  document_name: string | null;
  source_type: string;
  snippet: string;
  relevance_score: number;
}

export interface RagQueryResponse {
  id: string;
  question: string;
  answer: string;
  sources: SourceChunk[];
  model_used: string;
  processing_time_ms: number;
}

export interface RagStats {
  total_embeddings: number;
  total_documents_ingested: number;
  total_sop_chunks: number;
  total_queries: number;
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  sources?: SourceChunk[];
  processing_time_ms?: number;
  timestamp: string;
}

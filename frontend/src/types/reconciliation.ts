export interface ReconciliationRecord {
  id: string;
  run_id: string;
  source: string;
  record_type: string | null;
  reference_number: string | null;
  record_data: Record<string, unknown> | null;
  match_status: string | null;
  matched_with_id: string | null;
  match_confidence: number | null;
  match_reasoning: string | null;
  mismatch_details: Record<string, unknown> | null;
  created_at: string;
}

export interface ReconciliationRun {
  id: string;
  name: string | null;
  description: string | null;
  status: string | null;
  total_records: number | null;
  matched_count: number | null;
  mismatch_count: number | null;
  match_rate: number | null;
  run_by: string | null;
  model_used: string | null;
  processing_time_ms: number | null;
  summary: Record<string, unknown> | null;
  records: ReconciliationRecord[];
  created_at: string;
}

export interface ReconciliationRunListResponse {
  runs: ReconciliationRun[];
  total: number;
  page: number;
  per_page: number;
}

export interface ReconciliationStats {
  total_runs: number;
  total_records: number;
  avg_match_rate: number | null;
  last_run_at: string | null;
}

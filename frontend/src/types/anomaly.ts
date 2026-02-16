export interface AnomalyFlag {
  id: string;
  document_id: string | null;
  allocation_id: string | null;
  anomaly_type: string;
  severity: string;
  title: string;
  description: string | null;
  details: Record<string, unknown> | null;
  is_resolved: boolean;
  resolved_by: string | null;
  resolved_at: string | null;
  resolution_notes: string | null;
  review_item_id: string | null;
  created_at: string;
}

export interface AnomalyFlagListResponse {
  anomalies: AnomalyFlag[];
  total: number;
  page: number;
  per_page: number;
}

export interface AnomalyStats {
  total: number;
  unresolved: number;
  by_type: Record<string, number>;
  by_severity: Record<string, number>;
}

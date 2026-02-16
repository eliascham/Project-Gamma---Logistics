export interface ReviewItem {
  id: string;
  status: string;
  item_type: string | null;
  entity_id: string | null;
  entity_type: string | null;
  title: string | null;
  description: string | null;
  severity: string | null;
  assigned_to: string | null;
  reviewed_by: string | null;
  reviewed_at: string | null;
  review_notes: string | null;
  auto_approve_eligible: boolean;
  dollar_amount: number | null;
  created_at: string;
}

export interface ReviewItemListResponse {
  items: ReviewItem[];
  total: number;
  page: number;
  per_page: number;
}

export interface ReviewQueueStats {
  total: number;
  pending_review: number;
  approved: number;
  rejected: number;
  escalated: number;
  auto_approved: number;
}

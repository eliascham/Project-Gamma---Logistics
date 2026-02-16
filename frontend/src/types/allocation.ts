export type AllocationStatus = "pending" | "allocated" | "review_needed" | "approved" | "rejected";
export type LineItemStatus = "auto_approved" | "needs_review" | "manually_overridden";

export interface AllocationLineItem {
  id: string;
  line_item_index: number;
  description: string;
  amount: number;
  project_code: string | null;
  cost_center: string | null;
  gl_account: string | null;
  confidence: number | null;
  reasoning: string | null;
  status: LineItemStatus;
  override_project_code: string | null;
  override_cost_center: string | null;
  override_gl_account: string | null;
}

export interface CostAllocation {
  id: string;
  document_id: string | null;
  status: AllocationStatus;
  line_items: AllocationLineItem[];
  total_amount: number | null;
  currency: string;
  allocated_by_model: string | null;
  processing_time_ms: number | null;
  created_at: string;
}

export interface AllocationRule {
  id: string;
  rule_name: string;
  description: string | null;
  match_pattern: string;
  project_code: string;
  cost_center: string;
  gl_account: string;
  priority: number;
  is_active: boolean;
}

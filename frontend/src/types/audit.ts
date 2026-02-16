export interface AuditEvent {
  id: string;
  event_type: string | null;
  event_data: Record<string, unknown> | null;
  entity_type: string | null;
  entity_id: string | null;
  action: string | null;
  actor: string | null;
  actor_type: string | null;
  previous_state: Record<string, unknown> | null;
  new_state: Record<string, unknown> | null;
  rationale: string | null;
  model_used: string | null;
  created_at: string;
}

export interface AuditEventListResponse {
  events: AuditEvent[];
  total: number;
  page: number;
  per_page: number;
}

export interface AuditStats {
  total_events: number;
  events_by_type: Record<string, number>;
  events_by_actor_type: Record<string, number>;
  recent_events: AuditEvent[];
}

export type RelationshipType = "fulfills" | "invoices" | "supports" | "adjusts" | "certifies" | "clears" | "confirms" | "notifies"

export interface DocumentRelationship {
  id: string
  source_document_id: string
  target_document_id: string
  relationship_type: RelationshipType
  reference_field: string | null
  reference_value: string | null
  confidence: number
  created_by: string
  created_at: string
}

export interface DocumentRelationshipCreate {
  source_document_id: string
  target_document_id: string
  relationship_type: string
  reference_field?: string
  reference_value?: string
  confidence?: number
}

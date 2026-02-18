export type MatchStatus = "full_match" | "partial_match" | "mismatch" | "incomplete"

export interface FieldMatch {
  field_name: string
  matched: boolean
  source_value: any
  target_value: any
  confidence: number
  reason: string
}

export interface LineItemMatch {
  po_index: number | null
  invoice_index: number | null
  field_matches: FieldMatch[]
  overall_matched: boolean
  confidence: number
}

export interface ThreeWayMatchResult {
  status: MatchStatus
  overall_confidence: number
  po_to_invoice: FieldMatch[]
  po_to_bol: FieldMatch[]
  line_item_matches: LineItemMatch[]
  summary: string
}

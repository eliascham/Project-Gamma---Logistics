import type { DocumentType } from "./document";

export interface ExtractionResponse {
  document_id: string;
  document_type: DocumentType;
  extraction: Record<string, unknown>;
  raw_extraction: Record<string, unknown> | null;
  model_used: string;
  processing_time_ms: number | null;
  confidence_notes: string | null;
}

export interface LineItem {
  description: string;
  quantity: number;
  unit: string;
  unit_price: number;
  total: number;
}

export interface FreightInvoiceExtraction {
  invoice_number: string;
  invoice_date: string | null;
  vendor_name: string;
  shipper_name: string | null;
  consignee_name: string | null;
  origin: string | null;
  destination: string | null;
  currency: string;
  line_items: LineItem[];
  subtotal: number | null;
  tax_amount: number | null;
  total_amount: number;
  notes: string | null;
}

export interface AddressInfo {
  name: string;
  address: string | null;
}

export interface LocationInfo {
  city: string | null;
  state: string | null;
  country: string | null;
  port: string | null;
}

export interface BillOfLadingExtraction {
  bol_number: string;
  issue_date: string | null;
  carrier_name: string | null;
  carrier_scac: string | null;
  shipper: AddressInfo | null;
  consignee: AddressInfo | null;
  notify_party: string | null;
  origin: LocationInfo | null;
  destination: LocationInfo | null;
  vessel_name: string | null;
  voyage_number: string | null;
  container_numbers: string[];
  cargo_description: string | null;
  package_count: number | null;
  gross_weight: number | null;
  weight_unit: string | null;
  volume: number | null;
  volume_unit: string | null;
  freight_charges: number | null;
  freight_payment_type: string | null;
  special_instructions: string | null;
  notes: string | null;
}

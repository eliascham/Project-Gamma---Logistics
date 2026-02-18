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

// --- Shared Sub-Models ---

export interface PartyInfo {
  name: string;
  address: string | null;
  city: string | null;
  state: string | null;
  country: string | null;
  postal_code: string | null;
  tax_id: string | null;
  contact_name: string | null;
  phone: string | null;
  email: string | null;
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

// --- Freight Invoice ---

export interface LineItem {
  description: string;
  quantity: number;
  unit: string;
  unit_price: number;
  total: number;
}

export interface DemurrageDetail {
  container_number: string;
  free_time_days: number | null;
  free_time_start: string | null;
  free_time_end: string | null;
  charge_start_date: string | null;
  charge_end_date: string | null;
  daily_rate: number | null;
  total_chargeable_days: number | null;
  fmc_compliance_statement: boolean | null;
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
  invoice_variant: string | null;
  demurrage_details: DemurrageDetail[] | null;
}

// --- Bill of Lading ---

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

// --- Commercial Invoice (P0) ---

export interface CommercialLineItem {
  item_number: string | null;
  description: string;
  hs_code: string | null;
  country_of_origin: string | null;
  quantity: number;
  unit: string;
  unit_price: number;
  total: number;
}

export interface CommercialInvoiceExtraction {
  invoice_number: string;
  invoice_date: string | null;
  seller: PartyInfo;
  buyer: PartyInfo;
  consignee: PartyInfo | null;
  ship_from: LocationInfo | null;
  ship_to: LocationInfo | null;
  country_of_origin: string | null;
  country_of_export: string | null;
  currency: string;
  incoterms: string | null;
  incoterms_location: string | null;
  payment_terms: string | null;
  line_items: CommercialLineItem[];
  subtotal: number | null;
  freight_charges: number | null;
  insurance_charges: number | null;
  discount_amount: number | null;
  tax_amount: number | null;
  total_amount: number;
  transport_reference: string | null;
  vessel_or_flight: string | null;
  export_reason: string | null;
  notes: string | null;
  invoice_variant: string | null;
}

// --- Purchase Order (P0) ---

export interface POLineItem {
  line_number: number | null;
  item_number: string | null;
  description: string;
  hs_code: string | null;
  quantity: number;
  unit: string;
  unit_price: number;
  total: number;
}

export interface PurchaseOrderExtraction {
  po_number: string;
  po_date: string | null;
  buyer: PartyInfo;
  supplier: PartyInfo;
  ship_to: PartyInfo | null;
  currency: string;
  incoterms: string | null;
  incoterms_location: string | null;
  payment_terms: string | null;
  delivery_date: string | null;
  shipping_method: string | null;
  line_items: POLineItem[];
  subtotal: number | null;
  tax_amount: number | null;
  shipping_amount: number | null;
  total_amount: number;
  notes: string | null;
  status: string | null;
}

// --- Packing List (P0) ---

export interface PackingItem {
  item_number: string | null;
  description: string;
  quantity: number;
  unit: string | null;
  package_type: string | null;
  package_count: number | null;
  gross_weight: number | null;
  net_weight: number | null;
  dimensions: string | null;
  marks: string | null;
}

export interface PackingListExtraction {
  packing_list_number: string | null;
  packing_date: string | null;
  invoice_number: string | null;
  po_number: string | null;
  seller: PartyInfo | null;
  buyer: PartyInfo | null;
  consignee: PartyInfo | null;
  ship_from: LocationInfo | null;
  ship_to: LocationInfo | null;
  transport_reference: string | null;
  vessel_or_flight: string | null;
  container_numbers: string[];
  items: PackingItem[];
  total_packages: number | null;
  total_gross_weight: number | null;
  total_net_weight: number | null;
  weight_unit: string | null;
  total_volume: number | null;
  volume_unit: string | null;
  marks_and_numbers: string | null;
  notes: string | null;
}

// --- Arrival Notice (P1) ---

export interface ArrivalCharge {
  charge_type: string;
  amount: number;
  currency: string | null;
}

export interface ArrivalNoticeExtraction {
  notice_number: string | null;
  notice_date: string | null;
  carrier: PartyInfo | null;
  shipper: PartyInfo | null;
  consignee: PartyInfo | null;
  notify_party: PartyInfo | null;
  bol_number: string | null;
  booking_number: string | null;
  vessel_name: string | null;
  voyage_number: string | null;
  port_of_loading: string | null;
  port_of_discharge: string | null;
  place_of_delivery: string | null;
  eta: string | null;
  ata: string | null;
  container_numbers: string[];
  cargo_description: string | null;
  package_count: number | null;
  gross_weight: number | null;
  weight_unit: string | null;
  volume: number | null;
  volume_unit: string | null;
  freight_terms: string | null;
  charges: ArrivalCharge[];
  total_charges: number | null;
  currency: string | null;
  free_time_days: number | null;
  last_free_day: string | null;
  documents_required: string[];
  notes: string | null;
}

// --- Air Waybill (P1) ---

export interface AWBCharge {
  charge_code: string | null;
  charge_type: string;
  amount: number;
  prepaid_or_collect: string | null;
}

export interface AirWaybillExtraction {
  awb_number: string;
  awb_type: string | null;
  master_awb_number: string | null;
  issue_date: string | null;
  airline_code: string | null;
  airline_name: string | null;
  shipper: PartyInfo | null;
  consignee: PartyInfo | null;
  issuing_agent: PartyInfo | null;
  airport_of_departure: string | null;
  airport_of_destination: string | null;
  routing: string[];
  flight_number: string | null;
  flight_date: string | null;
  cargo_description: string | null;
  pieces: number | null;
  gross_weight: number | null;
  chargeable_weight: number | null;
  weight_unit: string | null;
  dimensions: string | null;
  volume: number | null;
  rate_class: string | null;
  rate: number | null;
  freight_charges: number | null;
  declared_value_carriage: number | null;
  declared_value_customs: number | null;
  insurance_amount: number | null;
  other_charges: AWBCharge[];
  total_charges: number | null;
  payment_type: string | null;
  currency: string | null;
  handling_info: string | null;
  sci: string | null;
  notes: string | null;
}

// --- Debit/Credit Note (P1) ---

export interface AdjustmentLineItem {
  description: string;
  original_amount: number | null;
  adjusted_amount: number;
  difference: number | null;
  quantity: number | null;
  unit: string | null;
  reason: string | null;
}

export interface DebitCreditNoteExtraction {
  note_number: string;
  note_type: string;
  note_date: string | null;
  original_invoice_number: string | null;
  original_invoice_date: string | null;
  issuer: PartyInfo | null;
  recipient: PartyInfo | null;
  currency: string;
  reason: string | null;
  line_items: AdjustmentLineItem[];
  subtotal: number | null;
  tax_amount: number | null;
  total_amount: number;
  notes: string | null;
}

// --- CBP 7501 Customs Entry (P2) ---

export interface EntryLineItem {
  line_number: number | null;
  hts_number: string;
  description: string;
  country_of_origin: string | null;
  quantity: number | null;
  unit: string | null;
  entered_value: number;
  duty_rate: number | null;
  duty_amount: number | null;
  ad_cvd_rate: string | null;
  ad_cvd_amount: number | null;
}

export interface CustomsEntryExtraction {
  entry_number: string;
  entry_type: string | null;
  summary_date: string | null;
  entry_date: string | null;
  port_code: string | null;
  surety_number: string | null;
  bond_type: string | null;
  importing_carrier: string | null;
  mode_of_transport: string | null;
  country_of_origin: string | null;
  exporting_country: string | null;
  import_date: string | null;
  importer_number: string | null;
  importer_name: string | null;
  consignee_number: string | null;
  consignee_name: string | null;
  manufacturer_id: string | null;
  bol_or_awb: string | null;
  line_items: EntryLineItem[];
  total_entered_value: number | null;
  total_duty: number | null;
  total_tax: number | null;
  total_other: number | null;
  total_amount: number | null;
  notes: string | null;
}

// --- Proof of Delivery (P2) ---

export interface DeliveryItem {
  description: string;
  quantity_expected: number | null;
  quantity_delivered: number | null;
  unit: string | null;
  condition: string | null;
  notes: string | null;
}

export interface ProofOfDeliveryExtraction {
  pod_number: string | null;
  delivery_date: string | null;
  delivery_time: string | null;
  carrier_name: string | null;
  driver_name: string | null;
  shipper: PartyInfo | null;
  consignee: PartyInfo | null;
  delivery_address: string | null;
  bol_number: string | null;
  order_number: string | null;
  tracking_number: string | null;
  items: DeliveryItem[];
  total_packages: number | null;
  total_weight: number | null;
  weight_unit: string | null;
  receiver_name: string | null;
  receiver_signature: boolean;
  condition: string | null;
  condition_notes: string | null;
  has_photo: boolean;
  gps_coordinates: string | null;
  notes: string | null;
}

// --- Certificate of Origin (P2) ---

export interface OriginItem {
  description: string;
  hs_code: string | null;
  quantity: number | null;
  unit: string | null;
  origin_criterion: string | null;
  country_of_origin: string | null;
}

export interface CertificateOfOriginExtraction {
  certificate_number: string | null;
  issue_date: string | null;
  certificate_type: string | null;
  exporter: PartyInfo | null;
  producer: PartyInfo | null;
  importer: PartyInfo | null;
  country_of_origin: string;
  country_of_destination: string | null;
  transport_details: string | null;
  invoice_number: string | null;
  items: OriginItem[];
  origin_criterion: string | null;
  blanket_period_start: string | null;
  blanket_period_end: string | null;
  issuing_authority: string | null;
  certifier_name: string | null;
  certification_date: string | null;
  notes: string | null;
}

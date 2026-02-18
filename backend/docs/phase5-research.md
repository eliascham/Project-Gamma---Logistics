# Phase 5: Document Intelligence Expansion - Research Findings

## Table of Contents

1. [Existing Codebase Analysis](#1-existing-codebase-analysis)
2. [Document Type Schemas](#2-document-type-schemas)
   - [P0: Commercial Invoice](#21-commercial-invoice-p0)
   - [P0: Purchase Order](#22-purchase-order-p0)
   - [P0: Packing List](#23-packing-list-p0)
   - [P1: Arrival Notice](#24-arrival-notice-p1)
   - [P1: Air Waybill (AWB/HAWB)](#25-air-waybill-awbhawb-p1)
   - [P1: Debit/Credit Notes](#26-debitcredit-notes-p1)
   - [P2: CBP 7501 (Customs Entry Summary)](#27-cbp-7501-customs-entry-summary-p2)
   - [P2: Proof of Delivery](#28-proof-of-delivery-p2)
   - [P2: Certificate of Origin](#29-certificate-of-origin-p2)
3. [Document Relationship Model](#3-document-relationship-model)
4. [Invoice Variant Classification](#4-invoice-variant-classification)
5. [3-Way PO-BOL-Invoice Matching](#5-3-way-po-bol-invoice-matching)
6. [Implementation Recommendations](#6-implementation-recommendations)
7. [Edge Cases and Gotchas](#7-edge-cases-and-gotchas)

---

## 1. Existing Codebase Analysis

### Current Document Types

The system currently supports two document types via `DocumentType` enum in `schemas/extraction.py`:

- `FREIGHT_INVOICE` - `FreightInvoiceExtraction` (13 fields + `LineItem` sub-model)
- `BILL_OF_LADING` - `BillOfLadingExtraction` (22 fields + `AddressInfo`, `LocationInfo` sub-models)
- `UNKNOWN` - fallback

### Current Architecture Patterns

**Extraction pipeline** (`document_extractor/pipeline.py`):
1. Parse document (PDF/image/CSV) via `DocumentParser`
2. Classify via Haiku (`DocumentClassifier`) - returns `DocumentType` enum
3. Pass 1: Extract with Sonnet via `ClaudeService.extract()` - validates against Pydantic model
4. Pass 2: Review/refine via `ClaudeService.review_extraction()`

**Key integration points that must change:**
- `DocumentType` enum - must add 9 new values
- `ClaudeService._get_schema_for_type()` - maps doc type to JSON schema template
- `ClaudeService.extract()` - validates against Pydantic model per type
- `ClaudeService.review_extraction()` - validates against Pydantic model per type
- `DocumentClassifier.CLASSIFICATION_PROMPT` - must list all new types
- Cost allocation pipeline - currently only works with freight invoices; needs to handle commercial invoices and debit/credit notes

**Shared sub-models to reuse:**
- `AddressInfo` (name + address) - reuse for all party blocks
- `LocationInfo` (city/state/country/port) - reuse for origin/destination
- `LineItem` (description/quantity/unit/unit_price/total) - reuse for invoice-like documents

### Database Model

`Document` model stores `document_type` as a `String(50)` (not an enum column), so adding new types requires no migration for the document_type field itself. The `DocumentStatus` enum (pending/processing/extracted/failed) is generic enough for all document types.

---

## 2. Document Type Schemas

### 2.1 Commercial Invoice (P0)

**Industry standard:** Required for all international shipments. Used by customs to assess duties/taxes. Must align with the commercial terms of sale.

**Key standards:** WCO, ICC Incoterms 2020, HS Convention

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `invoice_number` | `str` | Yes | Unique invoice reference number |
| `invoice_date` | `date \| None` | No | Date of invoice issuance |
| `seller` | `PartyInfo` | Yes | Exporter/seller name, address, contact, tax_id |
| `buyer` | `PartyInfo` | Yes | Importer/buyer name, address, contact, tax_id |
| `consignee` | `PartyInfo \| None` | No | Ship-to party if different from buyer |
| `ship_from` | `LocationInfo \| None` | No | Origin/port of loading |
| `ship_to` | `LocationInfo \| None` | No | Destination/port of discharge |
| `country_of_origin` | `str \| None` | No | Country where goods were manufactured |
| `country_of_export` | `str \| None` | No | Country from which goods are shipped |
| `currency` | `str` | Yes | Currency code (ISO 4217) |
| `incoterms` | `str \| None` | No | Trade terms (EXW, FOB, CIF, DDP, etc.) |
| `incoterms_location` | `str \| None` | No | Named place for Incoterms |
| `payment_terms` | `str \| None` | No | Payment terms (Net 30, LC, etc.) |
| `line_items` | `list[CommercialLineItem]` | Yes | Line items with HS codes |
| `subtotal` | `float \| None` | No | Subtotal before adjustments |
| `freight_charges` | `float \| None` | No | Freight cost (for CIF/CFR terms) |
| `insurance_charges` | `float \| None` | No | Insurance cost (for CIF terms) |
| `discount_amount` | `float \| None` | No | Total discount applied |
| `tax_amount` | `float \| None` | No | Tax/VAT amount |
| `total_amount` | `float` | Yes | Total invoice value |
| `transport_reference` | `str \| None` | No | BOL/AWB number |
| `vessel_or_flight` | `str \| None` | No | Vessel name or flight number |
| `export_reason` | `str \| None` | No | Reason for export (sale, repair, return, gift, sample) |
| `notes` | `str \| None` | No | Additional terms or notes |

**CommercialLineItem sub-model:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `item_number` | `str \| None` | No | SKU, part number, or item code |
| `description` | `str` | Yes | Full description of goods |
| `hs_code` | `str \| None` | No | Harmonized System code (6-10 digits) |
| `country_of_origin` | `str \| None` | No | Country of origin per item (if varies) |
| `quantity` | `float` | Yes | Number of units |
| `unit` | `str` | Yes | Unit of measure |
| `unit_price` | `float` | Yes | Price per unit |
| `total` | `float` | Yes | Line total |

**PartyInfo sub-model** (new, extends AddressInfo):

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | `str` | Yes | Company or person name |
| `address` | `str \| None` | No | Full street address |
| `city` | `str \| None` | No | City |
| `state` | `str \| None` | No | State/province |
| `country` | `str \| None` | No | Country |
| `postal_code` | `str \| None` | No | ZIP/postal code |
| `tax_id` | `str \| None` | No | Tax/VAT/EIN number |
| `contact_name` | `str \| None` | No | Contact person name |
| `phone` | `str \| None` | No | Phone number |
| `email` | `str \| None` | No | Email address |

**Relationship to existing schemas:** The `FreightInvoiceExtraction` focuses on carrier charges; the `CommercialInvoiceExtraction` focuses on goods value and trade terms. They share the concept of line items but commercial invoices add HS codes and per-item origin tracking.

---

### 2.2 Purchase Order (P0)

**Industry standard:** Issued by buyer to supplier. Key anchor document for 3-way matching. References expected delivery terms.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `po_number` | `str` | Yes | Purchase order number |
| `po_date` | `date \| None` | No | Date PO was issued |
| `buyer` | `PartyInfo` | Yes | Buying organization |
| `supplier` | `PartyInfo` | Yes | Supplier/vendor |
| `ship_to` | `PartyInfo \| None` | No | Delivery destination if different from buyer |
| `currency` | `str` | Yes | Currency code |
| `incoterms` | `str \| None` | No | Trade terms |
| `incoterms_location` | `str \| None` | No | Named place |
| `payment_terms` | `str \| None` | No | Payment terms |
| `delivery_date` | `date \| None` | No | Expected/requested delivery date |
| `shipping_method` | `str \| None` | No | Requested shipping method (ocean, air, ground) |
| `line_items` | `list[POLineItem]` | Yes | Ordered items |
| `subtotal` | `float \| None` | No | Subtotal |
| `tax_amount` | `float \| None` | No | Tax amount |
| `shipping_amount` | `float \| None` | No | Shipping charges |
| `total_amount` | `float` | Yes | Total PO value |
| `notes` | `str \| None` | No | Special instructions or terms |
| `status` | `str \| None` | No | PO status (open, partial, closed) if visible |

**POLineItem sub-model:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `line_number` | `int \| None` | No | PO line number |
| `item_number` | `str \| None` | No | SKU/part number |
| `description` | `str` | Yes | Item description |
| `hs_code` | `str \| None` | No | HS code if specified |
| `quantity` | `float` | Yes | Ordered quantity |
| `unit` | `str` | Yes | Unit of measure |
| `unit_price` | `float` | Yes | Price per unit |
| `total` | `float` | Yes | Line total |

---

### 2.3 Packing List (P0)

**Industry standard:** Accompanies commercial invoice for customs declaration. Lists physical packaging details (weight, dimensions, carton count). Must match commercial invoice quantities.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `packing_list_number` | `str \| None` | No | Packing list reference number |
| `date` | `date \| None` | No | Date of issuance |
| `invoice_number` | `str \| None` | No | Associated commercial invoice number |
| `po_number` | `str \| None` | No | Associated PO number |
| `seller` | `PartyInfo \| None` | No | Exporter/seller |
| `buyer` | `PartyInfo \| None` | No | Importer/buyer |
| `consignee` | `PartyInfo \| None` | No | Ship-to party |
| `ship_from` | `LocationInfo \| None` | No | Origin |
| `ship_to` | `LocationInfo \| None` | No | Destination |
| `transport_reference` | `str \| None` | No | BOL/AWB number |
| `vessel_or_flight` | `str \| None` | No | Vessel name or flight number |
| `container_numbers` | `list[str]` | No | Container numbers |
| `items` | `list[PackingItem]` | Yes | Packed items |
| `total_packages` | `int \| None` | No | Total number of packages/cartons |
| `total_gross_weight` | `float \| None` | No | Total gross weight |
| `total_net_weight` | `float \| None` | No | Total net weight |
| `weight_unit` | `str \| None` | No | Weight unit (kg, lbs) |
| `total_volume` | `float \| None` | No | Total volume |
| `volume_unit` | `str \| None` | No | Volume unit (CBM, CFT) |
| `marks_and_numbers` | `str \| None` | No | Shipping marks |
| `notes` | `str \| None` | No | Additional notes |

**PackingItem sub-model:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `item_number` | `str \| None` | No | SKU/part number |
| `description` | `str` | Yes | Item description |
| `quantity` | `float` | Yes | Quantity of items |
| `unit` | `str \| None` | No | Unit of measure |
| `package_type` | `str \| None` | No | Box, carton, crate, drum, pallet |
| `package_count` | `int \| None` | No | Number of packages for this item |
| `gross_weight` | `float \| None` | No | Gross weight per item/line |
| `net_weight` | `float \| None` | No | Net weight per item/line |
| `dimensions` | `str \| None` | No | L x W x H (as string) |
| `marks` | `str \| None` | No | Package marks/labels |

---

### 2.4 Arrival Notice (P1)

**Industry standard:** No standardized format. Issued by carrier or freight forwarder to notify consignee of incoming shipment. Contains charges due before cargo release.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `notice_number` | `str \| None` | No | Arrival notice reference number |
| `notice_date` | `date \| None` | No | Date notice was issued |
| `carrier` | `PartyInfo \| None` | No | Carrier or freight forwarder |
| `shipper` | `PartyInfo \| None` | No | Shipper/consignor |
| `consignee` | `PartyInfo \| None` | No | Consignee/receiver |
| `notify_party` | `PartyInfo \| None` | No | Notify party |
| `bol_number` | `str \| None` | No | Associated Bill of Lading number |
| `booking_number` | `str \| None` | No | Booking reference |
| `vessel_name` | `str \| None` | No | Vessel name |
| `voyage_number` | `str \| None` | No | Voyage number |
| `port_of_loading` | `str \| None` | No | Origin port |
| `port_of_discharge` | `str \| None` | No | Destination port |
| `place_of_delivery` | `str \| None` | No | Final delivery location |
| `eta` | `date \| None` | No | Estimated time of arrival |
| `ata` | `date \| None` | No | Actual time of arrival |
| `container_numbers` | `list[str]` | No | Container numbers |
| `cargo_description` | `str \| None` | No | Description of goods |
| `package_count` | `int \| None` | No | Number of packages |
| `gross_weight` | `float \| None` | No | Total gross weight |
| `weight_unit` | `str \| None` | No | kg or lbs |
| `volume` | `float \| None` | No | Total volume |
| `volume_unit` | `str \| None` | No | CBM or CFT |
| `freight_terms` | `str \| None` | No | Prepaid or collect |
| `charges` | `list[ArrivalCharge]` | No | Itemized charges due |
| `total_charges` | `float \| None` | No | Total charges due |
| `currency` | `str` | No | Currency code |
| `free_time_days` | `int \| None` | No | Free time days allowed |
| `last_free_day` | `date \| None` | No | Last free day for container pickup |
| `documents_required` | `list[str]` | No | Required docs for release |
| `notes` | `str \| None` | No | Special instructions |

**ArrivalCharge sub-model:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `charge_type` | `str` | Yes | Type of charge (ocean freight, THC, documentation fee, etc.) |
| `amount` | `float` | Yes | Charge amount |
| `currency` | `str \| None` | No | Currency if different from header |

---

### 2.5 Air Waybill (AWB/HAWB) (P1)

**Industry standard:** IATA standard format. AWB number = 3-digit airline prefix + 7-digit serial + 1 check digit. MAWB issued by carrier; HAWB issued by freight forwarder.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `awb_number` | `str` | Yes | Air Waybill number (11-digit IATA format) |
| `awb_type` | `str \| None` | No | "master" (MAWB) or "house" (HAWB) |
| `master_awb_number` | `str \| None` | No | MAWB number (only for HAWB) |
| `issue_date` | `date \| None` | No | Date of issuance |
| `airline_code` | `str \| None` | No | IATA airline code (3-digit prefix) |
| `airline_name` | `str \| None` | No | Airline/carrier name |
| `shipper` | `PartyInfo \| None` | No | Shipper/consignor |
| `consignee` | `PartyInfo \| None` | No | Consignee/receiver |
| `issuing_agent` | `PartyInfo \| None` | No | Issuing carrier's agent |
| `airport_of_departure` | `str \| None` | No | IATA airport code + name |
| `airport_of_destination` | `str \| None` | No | IATA airport code + name |
| `routing` | `list[str]` | No | Transit airports/routing (IATA codes) |
| `flight_number` | `str \| None` | No | Flight number |
| `flight_date` | `date \| None` | No | Flight date |
| `cargo_description` | `str \| None` | No | Nature and quantity of goods |
| `pieces` | `int \| None` | No | Number of pieces |
| `gross_weight` | `float \| None` | No | Actual gross weight |
| `chargeable_weight` | `float \| None` | No | Chargeable weight (higher of actual/volumetric) |
| `weight_unit` | `str \| None` | No | K (kg) or L (lbs) |
| `dimensions` | `str \| None` | No | Dimensions (L x W x H per piece) |
| `volume` | `float \| None` | No | Total volume |
| `rate_class` | `str \| None` | No | Rate class code (M, N, Q, etc.) |
| `rate` | `float \| None` | No | Rate per unit |
| `freight_charges` | `float \| None` | No | Total freight charges |
| `declared_value_carriage` | `float \| None` | No | Declared value for carriage |
| `declared_value_customs` | `float \| None` | No | Declared value for customs |
| `insurance_amount` | `float \| None` | No | Insurance amount |
| `other_charges` | `list[AWBCharge]` | No | Other charges/fees |
| `total_charges` | `float \| None` | No | Total prepaid + collect charges |
| `payment_type` | `str \| None` | No | Prepaid (PP) or Collect (CC) |
| `currency` | `str` | No | Currency code |
| `handling_info` | `str \| None` | No | Special handling instructions |
| `sci` | `str \| None` | No | Shipper's Certification for dangerous goods |
| `notes` | `str \| None` | No | Additional notes |

**AWBCharge sub-model:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `charge_code` | `str \| None` | No | Charge code (AWC, CGC, etc.) |
| `charge_type` | `str` | Yes | Description of charge |
| `amount` | `float` | Yes | Charge amount |
| `prepaid_or_collect` | `str \| None` | No | PP or CC |

**Key difference from BOL:** AWB is not a document of title (cannot be endorsed/transferred). BOL is negotiable. AWB uses IATA airport codes; BOL uses port names. AWB has chargeable weight concept (volumetric vs actual).

---

### 2.6 Debit/Credit Notes (P1)

**Industry standard:** Debit note issued by buyer to seller (requesting price reduction); Credit note issued by seller to buyer (acknowledging adjustment). Always references an original invoice.

**DebitNoteExtraction:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `note_number` | `str` | Yes | Debit/credit note number |
| `note_type` | `str` | Yes | "debit" or "credit" |
| `note_date` | `date \| None` | No | Date of issuance |
| `original_invoice_number` | `str \| None` | No | Invoice being adjusted |
| `original_invoice_date` | `date \| None` | No | Date of original invoice |
| `issuer` | `PartyInfo \| None` | No | Party issuing the note |
| `recipient` | `PartyInfo \| None` | No | Party receiving the note |
| `currency` | `str` | Yes | Currency code |
| `reason` | `str \| None` | No | Reason for adjustment |
| `line_items` | `list[AdjustmentLineItem]` | No | Adjusted line items |
| `subtotal` | `float \| None` | No | Subtotal of adjustments |
| `tax_amount` | `float \| None` | No | Tax adjustment |
| `total_amount` | `float` | Yes | Total adjustment amount |
| `notes` | `str \| None` | No | Additional notes |

**AdjustmentLineItem sub-model:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `description` | `str` | Yes | Description of adjustment |
| `original_amount` | `float \| None` | No | Original invoiced amount |
| `adjusted_amount` | `float` | Yes | New/adjusted amount |
| `difference` | `float \| None` | No | Difference (auto-calculated) |
| `quantity` | `float \| None` | No | Quantity if applicable |
| `unit` | `str \| None` | No | Unit of measure |
| `reason` | `str \| None` | No | Per-line reason |

**Relationship to cost allocation:** Debit/credit notes adjust allocations from the original invoice. The system should link back to the original allocation and create adjustment entries, not new standalone allocations.

---

### 2.7 CBP 7501 (Customs Entry Summary) (P2)

**Industry standard:** US Customs and Border Protection Form 7501. Filed electronically within 10 business days of merchandise release. Required for all US imports.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `entry_number` | `str` | Yes | 11-digit entry number (filler + importer + check) |
| `entry_type` | `str \| None` | No | 2-digit entry type code |
| `summary_date` | `date \| None` | No | Date entry was filed |
| `entry_date` | `date \| None` | No | Date goods released from CBP custody |
| `port_code` | `str \| None` | No | US port code (4-digit) |
| `surety_number` | `str \| None` | No | 3-digit surety company code |
| `bond_type` | `str \| None` | No | Bond type code (0, 8, 9) |
| `importing_carrier` | `str \| None` | No | Vessel name or IATA airline code |
| `mode_of_transport` | `str \| None` | No | 2-digit transport mode code |
| `country_of_origin` | `str \| None` | No | Country of manufacture |
| `exporting_country` | `str \| None` | No | Country of export |
| `import_date` | `date \| None` | No | Date of importation |
| `importer_number` | `str \| None` | No | Importer's ID (IRS/EIN + 2 zeros) |
| `importer_name` | `str \| None` | No | Importer of record name |
| `consignee_number` | `str \| None` | No | Ultimate consignee number |
| `consignee_name` | `str \| None` | No | Ultimate consignee name |
| `manufacturer_id` | `str \| None` | No | Manufacturer/shipper ID |
| `bol_or_awb` | `str \| None` | No | Bill of lading or air waybill number |
| `line_items` | `list[EntryLineItem]` | Yes | Entry summary line items |
| `total_entered_value` | `float \| None` | No | Total entered value |
| `total_duty` | `float \| None` | No | Total duty owed |
| `total_tax` | `float \| None` | No | Total tax owed |
| `total_other` | `float \| None` | No | Other fees (MPF, HMF, etc.) |
| `total_amount` | `float \| None` | No | Total amount payable |
| `notes` | `str \| None` | No | Additional notes |

**EntryLineItem sub-model:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `line_number` | `int \| None` | No | Line sequence number |
| `hts_number` | `str` | Yes | Harmonized Tariff Schedule number (10-digit) |
| `description` | `str` | Yes | Description of merchandise |
| `country_of_origin` | `str \| None` | No | Country of origin per line |
| `quantity` | `float \| None` | No | Quantity |
| `unit` | `str \| None` | No | Reporting unit |
| `entered_value` | `float` | Yes | Entered value |
| `duty_rate` | `float \| None` | No | Duty rate (percentage or specific) |
| `duty_amount` | `float \| None` | No | Calculated duty |
| `ad_cvd_rate` | `str \| None` | No | Anti-dumping/countervailing duty case number |
| `ad_cvd_amount` | `float \| None` | No | AD/CVD amount |

**Relationship to cost allocation:** Customs duties and fees are significant cost allocation targets. The system should create allocation entries for duties, MPF (Merchandise Processing Fee), HMF (Harbor Maintenance Fee), and per-line duty amounts.

---

### 2.8 Proof of Delivery (P2)

**Industry standard:** No universal format. Can be paper (signed), electronic (ePOD), or photographic. Confirms goods received at destination.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `pod_number` | `str \| None` | No | POD reference number |
| `delivery_date` | `date \| None` | No | Actual delivery date |
| `delivery_time` | `str \| None` | No | Delivery time (HH:MM) |
| `carrier_name` | `str \| None` | No | Delivering carrier |
| `driver_name` | `str \| None` | No | Driver name |
| `shipper` | `PartyInfo \| None` | No | Shipper/sender |
| `consignee` | `PartyInfo \| None` | No | Receiver |
| `delivery_address` | `str \| None` | No | Actual delivery address |
| `bol_number` | `str \| None` | No | Associated BOL number |
| `order_number` | `str \| None` | No | Associated order/PO number |
| `tracking_number` | `str \| None` | No | Tracking/shipment number |
| `items` | `list[DeliveryItem]` | No | Delivered items |
| `total_packages` | `int \| None` | No | Total packages delivered |
| `total_weight` | `float \| None` | No | Total weight |
| `weight_unit` | `str \| None` | No | kg or lbs |
| `receiver_name` | `str \| None` | No | Name of person who signed |
| `receiver_signature` | `bool` | No | Whether signature is present |
| `condition` | `str \| None` | No | Delivery condition (good, damaged, partial) |
| `condition_notes` | `str \| None` | No | Damage or exception notes |
| `has_photo` | `bool` | No | Whether delivery photo exists |
| `gps_coordinates` | `str \| None` | No | GPS lat/long if available |
| `notes` | `str \| None` | No | Additional delivery notes |

**DeliveryItem sub-model:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `description` | `str` | Yes | Item description |
| `quantity_expected` | `float \| None` | No | Expected quantity |
| `quantity_delivered` | `float \| None` | No | Actual quantity delivered |
| `unit` | `str \| None` | No | Unit of measure |
| `condition` | `str \| None` | No | Item condition |
| `notes` | `str \| None` | No | Item-level notes |

**Key for reconciliation:** POD is the final link in the delivery chain. Discrepancies between expected and delivered quantities trigger claims. POD confirms the BOL was fulfilled.

---

### 2.9 Certificate of Origin (P2)

**Industry standard:** Varies by country and trade agreement. Common forms: General CO, Form A (GSP), EUR.1, USMCA CO, CAFTA-DR CO. Certified by chamber of commerce or self-certified depending on agreement.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `certificate_number` | `str \| None` | No | Certificate reference number |
| `issue_date` | `date \| None` | No | Date of issuance |
| `certificate_type` | `str \| None` | No | Type (General, Form A, EUR.1, USMCA, etc.) |
| `exporter` | `PartyInfo \| None` | No | Exporter name, address |
| `producer` | `PartyInfo \| None` | No | Producer/manufacturer (if different from exporter) |
| `importer` | `PartyInfo \| None` | No | Importer name, address |
| `country_of_origin` | `str` | Yes | Country where goods originate |
| `country_of_destination` | `str \| None` | No | Destination country |
| `transport_details` | `str \| None` | No | Vessel/flight, route, departure date |
| `invoice_number` | `str \| None` | No | Related commercial invoice number |
| `items` | `list[OriginItem]` | Yes | Items covered by certificate |
| `origin_criterion` | `str \| None` | No | Criterion met (WO, PE, PSR, etc.) |
| `blanket_period_start` | `date \| None` | No | Blanket certification start date |
| `blanket_period_end` | `date \| None` | No | Blanket certification end date |
| `issuing_authority` | `str \| None` | No | Chamber of commerce or issuing body |
| `certifier_name` | `str \| None` | No | Name of person certifying |
| `certification_date` | `date \| None` | No | Date of certification/signature |
| `notes` | `str \| None` | No | Remarks or additional info |

**OriginItem sub-model:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `description` | `str` | Yes | Description of goods |
| `hs_code` | `str \| None` | No | HS tariff classification |
| `quantity` | `float \| None` | No | Quantity |
| `unit` | `str \| None` | No | Unit of measure |
| `origin_criterion` | `str \| None` | No | Per-item origin criterion code |
| `country_of_origin` | `str \| None` | No | Per-item origin country (if varies) |

**Relationship to CBP 7501:** Country of origin from CO determines duty rates on the 7501. Preferential COs can reduce or eliminate duties under FTAs.

---

## 3. Document Relationship Model

### Design: `DocumentRelationship` Table

Documents in logistics form chains. The core chains are:

```
PO ─── links_to ──→ Commercial Invoice
PO ─── links_to ──→ Packing List
PO ─── links_to ──→ BOL / AWB
BOL ── links_to ──→ Arrival Notice
BOL ── links_to ──→ Freight Invoice
BOL ── links_to ──→ POD
Commercial Invoice ── links_to ──→ Certificate of Origin
Commercial Invoice ── links_to ──→ CBP 7501
Commercial Invoice ── links_to ──→ Packing List
Freight Invoice ── adjusted_by ──→ Debit/Credit Note
```

### Proposed Schema

**SQLAlchemy model: `DocumentRelationship`**

| Column | Type | Description |
|--------|------|-------------|
| `id` | `UUID` | Primary key |
| `source_document_id` | `UUID FK` | Source document (e.g., PO) |
| `target_document_id` | `UUID FK` | Target document (e.g., Invoice) |
| `relationship_type` | `Enum` | Type of relationship (see below) |
| `reference_field` | `String(100)` | Field that links them (e.g., "po_number", "bol_number") |
| `reference_value` | `String(500)` | Actual reference value (e.g., "PO-2024-001") |
| `confidence` | `Float` | Match confidence (1.0 = exact match, lower for fuzzy) |
| `created_by` | `String(50)` | "system" (auto-detected) or "user" (manual link) |
| `created_at` | `DateTime` | Timestamp |

**RelationshipType enum values:**

| Value | Description | Example |
|-------|-------------|---------|
| `fulfills` | Target fulfills/executes source | BOL fulfills PO |
| `invoices` | Target invoices/bills for source | Freight Invoice invoices BOL |
| `supports` | Target provides supporting evidence | Packing List supports Commercial Invoice |
| `adjusts` | Target adjusts/modifies source | Credit Note adjusts Freight Invoice |
| `certifies` | Target certifies/attests for source | CO certifies Commercial Invoice origin |
| `clears` | Target handles customs for source | CBP 7501 clears Commercial Invoice |
| `confirms` | Target confirms delivery of source | POD confirms BOL |
| `notifies` | Target notifies arrival of source | Arrival Notice notifies BOL |

### Auto-Detection Strategy

When a new document is extracted, the system should:

1. Extract reference numbers (PO numbers, BOL numbers, invoice numbers, AWB numbers)
2. Search existing documents for matching references
3. Create `DocumentRelationship` records with high confidence for exact matches
4. Flag fuzzy matches (same vendor + similar date + amount) for human review

**Reference field mapping per document type:**

| Document Type | Fields to Match Against |
|---------------|----------------------|
| Commercial Invoice | `invoice_number`, `po_number` (from buyer), `transport_reference` (BOL/AWB) |
| Purchase Order | `po_number` |
| Packing List | `invoice_number`, `po_number`, `transport_reference` |
| Arrival Notice | `bol_number`, `booking_number` |
| Air Waybill | `awb_number`, `master_awb_number` |
| Debit/Credit Note | `original_invoice_number` |
| CBP 7501 | `entry_number`, `bol_or_awb` |
| Proof of Delivery | `bol_number`, `order_number`, `tracking_number` |
| Certificate of Origin | `invoice_number` |

---

## 4. Invoice Variant Classification

### Approach: Extend `DocumentType` with Sub-Classification

Rather than creating separate document types for every invoice variant, use a two-level classification:

1. **Primary type** (in `DocumentType` enum): `freight_invoice` (existing), `commercial_invoice` (new), `debit_credit_note` (new)
2. **Sub-type** (new field on extraction): `invoice_variant` classifying the specific kind

### Invoice Variants

| Variant | Description | Key Distinguishing Features |
|---------|-------------|---------------------------|
| `standard` | Regular freight/commercial invoice | Normal line items and charges |
| `detention_demurrage` | D&D charges | Container numbers, free time days, daily rates, FMC 13 required elements |
| `accessorial` | Additional service charges | Charges like liftgate, inside delivery, residential, reweigh |
| `consolidated` | Multiple shipments on one invoice | Multiple BOL references, grouped charges |
| `pro_forma` | Preliminary/estimated invoice | Marked as pro forma, no payment expected yet |
| `debit_note` | Buyer requests reduction | References original invoice, negative adjustments |
| `credit_note` | Seller acknowledges reduction | References original invoice, reduction amounts |
| `prepayment` | Advance payment invoice | Deposit or milestone payment |

### Implementation

Add an optional `invoice_variant` field to `FreightInvoiceExtraction` and `CommercialInvoiceExtraction`:

```python
invoice_variant: str | None = Field(None, description="Invoice sub-type: standard, detention_demurrage, accessorial, consolidated, pro_forma")
```

The classifier can detect variants during the classification step (Haiku) or during Pass 1 extraction (Sonnet). Recommended: detect during Pass 1, since variant determination often requires reading the full document.

### Detention/Demurrage-Specific Fields

For D&D invoices, the extraction should additionally capture (as optional fields on FreightInvoiceExtraction or in a separate `DemurrageDetail` sub-model):

| Field | Type | Description |
|-------|------|-------------|
| `container_number` | `str` | Container being charged |
| `free_time_days` | `int` | Allowed free days |
| `free_time_start` | `date` | Free time start date |
| `free_time_end` | `date` | Free time end date |
| `charge_start_date` | `date` | First chargeable date |
| `charge_end_date` | `date` | Last chargeable date |
| `daily_rate` | `float` | Per-day rate |
| `total_chargeable_days` | `int` | Number of chargeable days |
| `fmc_compliance_statement` | `bool` | FMC compliance certification present |

---

## 5. 3-Way PO-BOL-Invoice Matching

### Overview

3-way matching verifies consistency across:
1. **Purchase Order** (what was ordered)
2. **Bill of Lading / Packing List** (what was shipped)
3. **Commercial Invoice** (what was billed)

### Matching Fields

| Match Dimension | PO Field | BOL/Packing List Field | Invoice Field | Tolerance |
|----------------|----------|----------------------|---------------|-----------|
| **Reference** | `po_number` | N/A (manual link or PO ref on BOL) | `po_number` or cross-ref | Exact match |
| **Parties** | `supplier.name` | `shipper.name` | `seller.name` | Fuzzy (normalized) |
| **Item quantity** | `line_items[].quantity` | `items[].quantity` (packing) | `line_items[].quantity` | +/- 5% or +/- 1 unit |
| **Item description** | `line_items[].description` | `items[].description` | `line_items[].description` | Fuzzy (cosine similarity) |
| **Unit price** | `line_items[].unit_price` | N/A | `line_items[].unit_price` | +/- 3% or +/- $0.01 |
| **Total value** | `total_amount` | N/A | `total_amount` | +/- 5% |
| **Weight** | N/A | `total_gross_weight` | N/A | N/A (BOL ↔ Packing List cross-check) |
| **Country of origin** | N/A | N/A | `country_of_origin` | vs. CO `country_of_origin` (exact) |

### Match Result Statuses

| Status | Meaning |
|--------|---------|
| `full_match` | All fields within tolerance |
| `partial_match` | Some fields match, some have minor discrepancies |
| `mismatch` | Significant discrepancies requiring review |
| `incomplete` | Missing one or more documents in the set |

### Tolerance Configuration (Recommended Defaults)

```python
MATCH_TOLERANCES = {
    "quantity_pct": 0.05,       # 5% quantity variance
    "quantity_abs": 1,          # or 1 unit absolute
    "unit_price_pct": 0.03,    # 3% price variance
    "unit_price_abs": 0.01,    # or $0.01 absolute
    "total_amount_pct": 0.05,  # 5% total variance
    "total_amount_abs": 100,   # or $100 absolute (whichever is greater)
}
```

### Common Mismatch Causes

1. **Quantity discrepancies:** Short shipments, over-shipments, damaged goods excluded
2. **Price differences:** Currency conversion rounding, volume discounts applied differently, surcharges added
3. **Description mismatches:** Different naming conventions between buyer and seller systems
4. **Missing PO reference:** Invoice doesn't reference PO number (common in freight invoices vs. commercial invoices)
5. **Partial fulfillment:** PO fulfilled across multiple shipments/invoices
6. **Consolidated invoices:** One invoice covering multiple POs

### Implementation: `ThreeWayMatcher`

Propose a new module `backend/app/matching_engine/` with:

- `matchers.py` - Pure matching functions (like `reconciliation_engine/matchers.py`)
- `service.py` - `ThreeWayMatchingService` orchestrator
- Reuses `DocumentRelationship` to find linked documents
- Produces `MatchResult` with per-field scores and overall status

---

## 6. Implementation Recommendations

### 6.1 Files to Modify

| File | Change |
|------|--------|
| `schemas/extraction.py` | Add 9 new extraction Pydantic models + shared sub-models (`PartyInfo`). Add new values to `DocumentType` enum. |
| `services/claude_service.py` | Add JSON schema templates for each new type. Update `_get_schema_for_type()` and `extract()`/`review_extraction()` to handle all types. |
| `document_extractor/classifier.py` | Update `CLASSIFICATION_PROMPT` with all 11 document types and their descriptions. |
| `document_extractor/pipeline.py` | No structural changes needed; the pipeline is generic. |
| `document_extractor/parser.py` | No changes needed; parser is format-agnostic. |
| `models/document.py` | No schema change needed (`document_type` is already `String(50)`). |
| `cost_allocator/pipeline.py` | Extend to handle commercial invoices + CBP 7501 duty allocations. |
| `cost_allocator/rules.py` | Add rules for customs duties, import fees, accessorial charges. |

### 6.2 New Files to Create

| File | Purpose |
|------|---------|
| `models/document_relationship.py` | `DocumentRelationship` ORM model + `RelationshipType` enum |
| `schemas/document_relationship.py` | Pydantic models for relationship CRUD |
| `api/v1/relationships.py` | API endpoints for document relationships |
| `matching_engine/matchers.py` | Pure 3-way matching functions |
| `matching_engine/service.py` | `ThreeWayMatchingService` |
| `api/v1/matching.py` | API endpoints for matching |
| `alembic/versions/005_phase5_*.py` | Migration for `document_relationships` table |

### 6.3 New Allocation Rules to Add

```python
# For commercial invoice cost allocation
{"rule_name": "Import Duties", "match_pattern": "duty, import duty, customs duty, tariff",
 "project_code": "CUSTOMS-OPS-002", "cost_center": "COMPLIANCE", "gl_account": "5220-DUTIES"},
{"rule_name": "Merchandise Processing Fee", "match_pattern": "MPF, merchandise processing",
 "project_code": "CUSTOMS-OPS-002", "cost_center": "COMPLIANCE", "gl_account": "5230-FEES"},
{"rule_name": "Harbor Maintenance Fee", "match_pattern": "HMF, harbor maintenance",
 "project_code": "PORT-OPS-009", "cost_center": "LOGISTICS-OPS", "gl_account": "5230-FEES"},
{"rule_name": "Accessorial Charges", "match_pattern": "liftgate, inside delivery, residential, reweigh, pallet jack",
 "project_code": "DOM-TRANS-003", "cost_center": "LOGISTICS-OPS", "gl_account": "5140-ACCESSORIAL"},
```

### 6.4 Classifier Prompt Update

The classifier prompt needs to distinguish 11 types. Key discriminators:

| Type | Key Signals |
|------|------------|
| `freight_invoice` | Carrier charges, ocean/air/ground transport fees |
| `commercial_invoice` | Goods values, HS codes, Incoterms, buyer/seller |
| `bill_of_lading` | BOL number, vessel/voyage, container numbers, cargo |
| `purchase_order` | PO number, ordered items, delivery date, buyer/supplier |
| `packing_list` | Package counts, weights, dimensions, carton marks |
| `arrival_notice` | ETA, charges due, cargo release info |
| `air_waybill` | AWB number (11-digit), airline, airports, flight |
| `debit_credit_note` | References original invoice, adjustment amounts |
| `customs_entry` | Entry number, HTS codes, duty amounts, CBP |
| `proof_of_delivery` | Delivery date/time, signature, receiver name |
| `certificate_of_origin` | Country of origin, origin criteria, chamber/authority |

### 6.5 Eval Ground Truth

Create at least 2 ground truth samples per new document type (18 new files). Prioritize P0 types first (Commercial Invoice, PO, Packing List = 6 files minimum for initial eval).

---

## 7. Edge Cases and Gotchas

### Document-Specific Edge Cases

1. **Commercial Invoice:**
   - Multi-currency invoices (line items in different currencies)
   - Invoices with both goods value and freight charges (CIF terms include freight + insurance)
   - HS codes can be 6, 8, or 10 digits depending on country
   - Incoterms 2020 vs older versions

2. **Purchase Order:**
   - Blanket/standing POs (no fixed quantity, just a dollar limit)
   - PO amendments/revisions (same PO number, different version)
   - Multiple delivery dates per line item

3. **Packing List:**
   - Nested packaging (boxes in cartons on pallets)
   - Mixed units (some items by piece, others by weight)
   - Packing lists without values (values are on the commercial invoice only)

4. **Arrival Notice:**
   - No standardized format - highly variable between carriers/forwarders
   - May include preliminary charges that change before final invoice
   - Multiple containers on one arrival notice

5. **Air Waybill:**
   - HAWB numbers may not follow IATA format (forwarder's own numbering)
   - Consolidated shipments: one MAWB with many HAWBs
   - Chargeable weight = max(actual weight, volumetric weight) - need to handle both

6. **Debit/Credit Notes:**
   - May reference multiple original invoices
   - Tax recalculation on adjustments varies by jurisdiction
   - Some credit notes are full reversals (100% credit)

7. **CBP 7501:**
   - HTS codes are US-specific (10-digit), not the same as HS codes (6-digit international)
   - Anti-dumping/countervailing duties are separate from regular duties
   - Multiple entry types (01=consumption, 03=consumption from FTZ, etc.)
   - Bond amounts and surety information

8. **Proof of Delivery:**
   - Handwritten signatures on scanned documents (vision required)
   - Partial deliveries (delivered ≠ ordered)
   - Damage notations are free-form text
   - No standard format - varies dramatically by carrier

9. **Certificate of Origin:**
   - Different forms for different FTAs (USMCA, CAFTA-DR, EU preferential, etc.)
   - Blanket certificates cover a period, not a single shipment
   - Self-certification vs chamber-certified (different authority levels)
   - Origin criteria codes vary by agreement (WO, PE, PSR, RVC, etc.)

### Cross-Cutting Gotchas

10. **DocumentType enum expansion:** Adding 9 new enum values to `DocumentType` in `schemas/extraction.py` is straightforward since it's a Python-only enum (not a DB enum). But the classifier must be retrained/re-prompted to handle 11 types accurately.

11. **Schema validation in ClaudeService:** The `extract()` method validates against Pydantic models. With 11 types, the if/elif chain should be refactored to a registry pattern (dict mapping `DocumentType` to Pydantic model class).

12. **Cost allocation scope:** Not all document types need cost allocation. Only freight invoices, commercial invoices, debit/credit notes, and CBP 7501 (for duties) produce allocatable line items. POs, packing lists, BOLs, arrival notices, PODs, and COs are reference/supporting documents.

13. **Large classification prompt:** With 11 types, the Haiku classifier prompt grows. Consider a two-stage classifier: first classify broad category (invoice, transport, customs, trade), then narrow within category.

14. **Testing with SQLite:** Same pattern as existing tests - mock Claude responses, validate Pydantic models. No pgvector or Postgres dependency for unit tests.

15. **Migration for DocumentRelationship table:** Needs a new Alembic migration. The `relationship_type` column should use `SAEnum` with `values_callable` (same pattern as other enums in the project).

16. **PartyInfo reuse:** The new `PartyInfo` model is a superset of existing `AddressInfo`. Consider deprecating `AddressInfo` or making `PartyInfo` extend it. For backward compatibility, keep `AddressInfo` on BOL and use `PartyInfo` on new types.

---

## Appendix: DocumentType Enum (Proposed)

```python
class DocumentType(str, enum.Enum):
    FREIGHT_INVOICE = "freight_invoice"
    BILL_OF_LADING = "bill_of_lading"
    COMMERCIAL_INVOICE = "commercial_invoice"
    PURCHASE_ORDER = "purchase_order"
    PACKING_LIST = "packing_list"
    ARRIVAL_NOTICE = "arrival_notice"
    AIR_WAYBILL = "air_waybill"
    DEBIT_CREDIT_NOTE = "debit_credit_note"
    CUSTOMS_ENTRY = "customs_entry"
    PROOF_OF_DELIVERY = "proof_of_delivery"
    CERTIFICATE_OF_ORIGIN = "certificate_of_origin"
    UNKNOWN = "unknown"
```

import enum
from datetime import date
from uuid import UUID

from pydantic import BaseModel, Field


class DocumentType(str, enum.Enum):
    """Type of logistics document, determined by classification."""

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


# --- Shared Sub-Models ---


class PartyInfo(BaseModel):
    """Party information block used across multiple document types."""

    name: str = Field(..., description="Company or person name")
    address: str | None = Field(None, description="Full street address")
    city: str | None = Field(None, description="City")
    state: str | None = Field(None, description="State/province")
    country: str | None = Field(None, description="Country")
    postal_code: str | None = Field(None, description="ZIP/postal code")
    tax_id: str | None = Field(None, description="Tax/VAT/EIN number")
    contact_name: str | None = Field(None, description="Contact person name")
    phone: str | None = Field(None, description="Phone number")
    email: str | None = Field(None, description="Email address")


# --- Freight Invoice ---


class LineItem(BaseModel):
    description: str = Field(..., description="Description of the freight service or charge")
    quantity: float = Field(..., description="Number of units")
    unit: str = Field(..., description="Unit of measure (e.g., kg, pallet, container)")
    unit_price: float = Field(..., description="Price per unit in the invoice currency")
    total: float = Field(..., description="Line total amount")


class DemurrageDetail(BaseModel):
    """Detention/demurrage detail for D&D invoices."""

    container_number: str = Field(..., description="Container being charged")
    free_time_days: int | None = Field(None, description="Allowed free days")
    free_time_start: date | None = Field(None, description="Free time start date")
    free_time_end: date | None = Field(None, description="Free time end date")
    charge_start_date: date | None = Field(None, description="First chargeable date")
    charge_end_date: date | None = Field(None, description="Last chargeable date")
    daily_rate: float | None = Field(None, description="Per-day rate")
    total_chargeable_days: int | None = Field(None, description="Number of chargeable days")
    fmc_compliance_statement: bool | None = Field(None, description="FMC compliance certification present")


class FreightInvoiceExtraction(BaseModel):
    """Structured extraction of a freight/logistics invoice."""

    invoice_number: str = Field(..., description="Invoice or document reference number")
    invoice_date: date | None = Field(None, description="Date of invoice issuance")
    vendor_name: str = Field(..., description="Name of the freight carrier or logistics provider")
    shipper_name: str | None = Field(None, description="Name of the shipper/consignor")
    consignee_name: str | None = Field(None, description="Name of the consignee/receiver")
    origin: str | None = Field(None, description="Origin location or port")
    destination: str | None = Field(None, description="Destination location or port")
    currency: str = Field("USD", description="Currency code")
    line_items: list[LineItem] = Field(default_factory=list)
    subtotal: float | None = Field(None, description="Subtotal before tax")
    tax_amount: float | None = Field(None, description="Tax amount")
    total_amount: float = Field(..., description="Total invoice amount")
    notes: str | None = Field(None, description="Any additional notes or special terms")
    invoice_variant: str | None = Field(
        None,
        description="Invoice sub-type: standard, detention_demurrage, accessorial, consolidated, pro_forma",
    )
    demurrage_details: list[DemurrageDetail] | None = Field(
        None, description="Detention/demurrage details (for D&D invoices)"
    )


# --- Bill of Lading ---


class AddressInfo(BaseModel):
    """Address block for a party on a BOL."""

    name: str = Field(..., description="Company or person name")
    address: str | None = Field(None, description="Full street address")


class LocationInfo(BaseModel):
    """Origin or destination location on a BOL."""

    city: str | None = Field(None)
    state: str | None = Field(None)
    country: str | None = Field(None)
    port: str | None = Field(None, description="Port name if applicable")


class BillOfLadingExtraction(BaseModel):
    """Structured extraction of a Bill of Lading (BOL)."""

    bol_number: str = Field(..., description="Bill of Lading number")
    issue_date: date | None = Field(None, description="Date of BOL issuance")
    carrier_name: str | None = Field(None, description="Carrier/shipping line name")
    carrier_scac: str | None = Field(None, description="Standard Carrier Alpha Code")
    shipper: AddressInfo | None = Field(None, description="Shipper/consignor details")
    consignee: AddressInfo | None = Field(None, description="Consignee/receiver details")
    notify_party: str | None = Field(None, description="Notify party name")
    origin: LocationInfo | None = Field(None, description="Origin/port of loading")
    destination: LocationInfo | None = Field(None, description="Destination/port of discharge")
    vessel_name: str | None = Field(None, description="Vessel or ship name")
    voyage_number: str | None = Field(None, description="Voyage or trip number")
    container_numbers: list[str] = Field(default_factory=list, description="Container numbers")
    cargo_description: str | None = Field(None, description="Description of goods")
    package_count: int | None = Field(None, description="Number of packages")
    gross_weight: float | None = Field(None, description="Total gross weight")
    weight_unit: str | None = Field(None, description="Weight unit (kg, lbs)")
    volume: float | None = Field(None, description="Total volume")
    volume_unit: str | None = Field(None, description="Volume unit (CBM, CFT)")
    freight_charges: float | None = Field(None, description="Freight charges amount")
    freight_payment_type: str | None = Field(
        None, description="Payment type: prepaid or collect"
    )
    special_instructions: str | None = Field(None)
    notes: str | None = Field(None)


# --- Commercial Invoice (P0) ---


class CommercialLineItem(BaseModel):
    """Line item on a commercial invoice."""

    item_number: str | None = Field(None, description="SKU, part number, or item code")
    description: str = Field(..., description="Full description of goods")
    hs_code: str | None = Field(None, description="Harmonized System code (6-10 digits)")
    country_of_origin: str | None = Field(None, description="Country of origin per item")
    quantity: float = Field(..., description="Number of units")
    unit: str = Field(..., description="Unit of measure")
    unit_price: float = Field(..., description="Price per unit")
    total: float = Field(..., description="Line total")


class CommercialInvoiceExtraction(BaseModel):
    """Structured extraction of a commercial invoice."""

    invoice_number: str = Field(..., description="Unique invoice reference number")
    invoice_date: date | None = Field(None, description="Date of invoice issuance")
    seller: PartyInfo = Field(..., description="Exporter/seller")
    buyer: PartyInfo = Field(..., description="Importer/buyer")
    consignee: PartyInfo | None = Field(None, description="Ship-to party if different from buyer")
    ship_from: LocationInfo | None = Field(None, description="Origin/port of loading")
    ship_to: LocationInfo | None = Field(None, description="Destination/port of discharge")
    country_of_origin: str | None = Field(None, description="Country where goods were manufactured")
    country_of_export: str | None = Field(None, description="Country from which goods are shipped")
    currency: str = Field(..., description="Currency code (ISO 4217)")
    incoterms: str | None = Field(None, description="Trade terms (EXW, FOB, CIF, DDP, etc.)")
    incoterms_location: str | None = Field(None, description="Named place for Incoterms")
    payment_terms: str | None = Field(None, description="Payment terms (Net 30, LC, etc.)")
    line_items: list[CommercialLineItem] = Field(..., description="Line items with HS codes")
    subtotal: float | None = Field(None, description="Subtotal before adjustments")
    freight_charges: float | None = Field(None, description="Freight cost (for CIF/CFR terms)")
    insurance_charges: float | None = Field(None, description="Insurance cost (for CIF terms)")
    discount_amount: float | None = Field(None, description="Total discount applied")
    tax_amount: float | None = Field(None, description="Tax/VAT amount")
    total_amount: float = Field(..., description="Total invoice value")
    transport_reference: str | None = Field(None, description="BOL/AWB number")
    vessel_or_flight: str | None = Field(None, description="Vessel name or flight number")
    export_reason: str | None = Field(None, description="Reason for export (sale, repair, return, gift, sample)")
    notes: str | None = Field(None, description="Additional terms or notes")
    invoice_variant: str | None = Field(
        None, description="Invoice sub-type: standard, pro_forma"
    )


# --- Purchase Order (P0) ---


class POLineItem(BaseModel):
    """Line item on a purchase order."""

    line_number: int | None = Field(None, description="PO line number")
    item_number: str | None = Field(None, description="SKU/part number")
    description: str = Field(..., description="Item description")
    hs_code: str | None = Field(None, description="HS code if specified")
    quantity: float = Field(..., description="Ordered quantity")
    unit: str = Field(..., description="Unit of measure")
    unit_price: float = Field(..., description="Price per unit")
    total: float = Field(..., description="Line total")


class PurchaseOrderExtraction(BaseModel):
    """Structured extraction of a purchase order."""

    po_number: str = Field(..., description="Purchase order number")
    po_date: date | None = Field(None, description="Date PO was issued")
    buyer: PartyInfo = Field(..., description="Buying organization")
    supplier: PartyInfo = Field(..., description="Supplier/vendor")
    ship_to: PartyInfo | None = Field(None, description="Delivery destination if different from buyer")
    currency: str = Field(..., description="Currency code")
    incoterms: str | None = Field(None, description="Trade terms")
    incoterms_location: str | None = Field(None, description="Named place")
    payment_terms: str | None = Field(None, description="Payment terms")
    delivery_date: date | None = Field(None, description="Expected/requested delivery date")
    shipping_method: str | None = Field(None, description="Requested shipping method (ocean, air, ground)")
    line_items: list[POLineItem] = Field(..., description="Ordered items")
    subtotal: float | None = Field(None, description="Subtotal")
    tax_amount: float | None = Field(None, description="Tax amount")
    shipping_amount: float | None = Field(None, description="Shipping charges")
    total_amount: float = Field(..., description="Total PO value")
    notes: str | None = Field(None, description="Special instructions or terms")
    status: str | None = Field(None, description="PO status (open, partial, closed)")


# --- Packing List (P0) ---


class PackingItem(BaseModel):
    """Item on a packing list."""

    item_number: str | None = Field(None, description="SKU/part number")
    description: str = Field(..., description="Item description")
    quantity: float = Field(..., description="Quantity of items")
    unit: str | None = Field(None, description="Unit of measure")
    package_type: str | None = Field(None, description="Box, carton, crate, drum, pallet")
    package_count: int | None = Field(None, description="Number of packages for this item")
    gross_weight: float | None = Field(None, description="Gross weight per item/line")
    net_weight: float | None = Field(None, description="Net weight per item/line")
    dimensions: str | None = Field(None, description="L x W x H (as string)")
    marks: str | None = Field(None, description="Package marks/labels")


class PackingListExtraction(BaseModel):
    """Structured extraction of a packing list."""

    packing_list_number: str | None = Field(None, description="Packing list reference number")
    packing_date: date | None = Field(None, description="Date of issuance")
    invoice_number: str | None = Field(None, description="Associated commercial invoice number")
    po_number: str | None = Field(None, description="Associated PO number")
    seller: PartyInfo | None = Field(None, description="Exporter/seller")
    buyer: PartyInfo | None = Field(None, description="Importer/buyer")
    consignee: PartyInfo | None = Field(None, description="Ship-to party")
    ship_from: LocationInfo | None = Field(None, description="Origin")
    ship_to: LocationInfo | None = Field(None, description="Destination")
    transport_reference: str | None = Field(None, description="BOL/AWB number")
    vessel_or_flight: str | None = Field(None, description="Vessel name or flight number")
    container_numbers: list[str] = Field(default_factory=list, description="Container numbers")
    items: list[PackingItem] = Field(..., description="Packed items")
    total_packages: int | None = Field(None, description="Total number of packages/cartons")
    total_gross_weight: float | None = Field(None, description="Total gross weight")
    total_net_weight: float | None = Field(None, description="Total net weight")
    weight_unit: str | None = Field(None, description="Weight unit (kg, lbs)")
    total_volume: float | None = Field(None, description="Total volume")
    volume_unit: str | None = Field(None, description="Volume unit (CBM, CFT)")
    marks_and_numbers: str | None = Field(None, description="Shipping marks")
    notes: str | None = Field(None, description="Additional notes")


# --- Arrival Notice (P1) ---


class ArrivalCharge(BaseModel):
    """Charge on an arrival notice."""

    charge_type: str = Field(..., description="Type of charge (ocean freight, THC, documentation fee, etc.)")
    amount: float = Field(..., description="Charge amount")
    currency: str | None = Field(None, description="Currency if different from header")


class ArrivalNoticeExtraction(BaseModel):
    """Structured extraction of an arrival notice."""

    notice_number: str | None = Field(None, description="Arrival notice reference number")
    notice_date: date | None = Field(None, description="Date notice was issued")
    carrier: PartyInfo | None = Field(None, description="Carrier or freight forwarder")
    shipper: PartyInfo | None = Field(None, description="Shipper/consignor")
    consignee: PartyInfo | None = Field(None, description="Consignee/receiver")
    notify_party: PartyInfo | None = Field(None, description="Notify party")
    bol_number: str | None = Field(None, description="Associated Bill of Lading number")
    booking_number: str | None = Field(None, description="Booking reference")
    vessel_name: str | None = Field(None, description="Vessel name")
    voyage_number: str | None = Field(None, description="Voyage number")
    port_of_loading: str | None = Field(None, description="Origin port")
    port_of_discharge: str | None = Field(None, description="Destination port")
    place_of_delivery: str | None = Field(None, description="Final delivery location")
    eta: date | None = Field(None, description="Estimated time of arrival")
    ata: date | None = Field(None, description="Actual time of arrival")
    container_numbers: list[str] = Field(default_factory=list, description="Container numbers")
    cargo_description: str | None = Field(None, description="Description of goods")
    package_count: int | None = Field(None, description="Number of packages")
    gross_weight: float | None = Field(None, description="Total gross weight")
    weight_unit: str | None = Field(None, description="kg or lbs")
    volume: float | None = Field(None, description="Total volume")
    volume_unit: str | None = Field(None, description="CBM or CFT")
    freight_terms: str | None = Field(None, description="Prepaid or collect")
    charges: list[ArrivalCharge] = Field(default_factory=list, description="Itemized charges due")
    total_charges: float | None = Field(None, description="Total charges due")
    currency: str | None = Field(None, description="Currency code")
    free_time_days: int | None = Field(None, description="Free time days allowed")
    last_free_day: date | None = Field(None, description="Last free day for container pickup")
    documents_required: list[str] = Field(default_factory=list, description="Required docs for release")
    notes: str | None = Field(None, description="Special instructions")


# --- Air Waybill (P1) ---


class AWBCharge(BaseModel):
    """Charge on an air waybill."""

    charge_code: str | None = Field(None, description="Charge code (AWC, CGC, etc.)")
    charge_type: str = Field(..., description="Description of charge")
    amount: float = Field(..., description="Charge amount")
    prepaid_or_collect: str | None = Field(None, description="PP or CC")


class AirWaybillExtraction(BaseModel):
    """Structured extraction of an air waybill (AWB/HAWB)."""

    awb_number: str = Field(..., description="Air Waybill number (11-digit IATA format)")
    awb_type: str | None = Field(None, description="master (MAWB) or house (HAWB)")
    master_awb_number: str | None = Field(None, description="MAWB number (only for HAWB)")
    issue_date: date | None = Field(None, description="Date of issuance")
    airline_code: str | None = Field(None, description="IATA airline code (3-digit prefix)")
    airline_name: str | None = Field(None, description="Airline/carrier name")
    shipper: PartyInfo | None = Field(None, description="Shipper/consignor")
    consignee: PartyInfo | None = Field(None, description="Consignee/receiver")
    issuing_agent: PartyInfo | None = Field(None, description="Issuing carrier's agent")
    airport_of_departure: str | None = Field(None, description="IATA airport code + name")
    airport_of_destination: str | None = Field(None, description="IATA airport code + name")
    routing: list[str] = Field(default_factory=list, description="Transit airports/routing (IATA codes)")
    flight_number: str | None = Field(None, description="Flight number")
    flight_date: date | None = Field(None, description="Flight date")
    cargo_description: str | None = Field(None, description="Nature and quantity of goods")
    pieces: int | None = Field(None, description="Number of pieces")
    gross_weight: float | None = Field(None, description="Actual gross weight")
    chargeable_weight: float | None = Field(None, description="Chargeable weight (higher of actual/volumetric)")
    weight_unit: str | None = Field(None, description="K (kg) or L (lbs)")
    dimensions: str | None = Field(None, description="Dimensions (L x W x H per piece)")
    volume: float | None = Field(None, description="Total volume")
    rate_class: str | None = Field(None, description="Rate class code (M, N, Q, etc.)")
    rate: float | None = Field(None, description="Rate per unit")
    freight_charges: float | None = Field(None, description="Total freight charges")
    declared_value_carriage: float | None = Field(None, description="Declared value for carriage")
    declared_value_customs: float | None = Field(None, description="Declared value for customs")
    insurance_amount: float | None = Field(None, description="Insurance amount")
    other_charges: list[AWBCharge] = Field(default_factory=list, description="Other charges/fees")
    total_charges: float | None = Field(None, description="Total prepaid + collect charges")
    payment_type: str | None = Field(None, description="Prepaid (PP) or Collect (CC)")
    currency: str | None = Field(None, description="Currency code")
    handling_info: str | None = Field(None, description="Special handling instructions")
    sci: str | None = Field(None, description="Shipper's Certification for dangerous goods")
    notes: str | None = Field(None, description="Additional notes")


# --- Debit/Credit Note (P1) ---


class AdjustmentLineItem(BaseModel):
    """Line item on a debit/credit note."""

    description: str = Field(..., description="Description of adjustment")
    original_amount: float | None = Field(None, description="Original invoiced amount")
    adjusted_amount: float = Field(..., description="New/adjusted amount")
    difference: float | None = Field(None, description="Difference (auto-calculated)")
    quantity: float | None = Field(None, description="Quantity if applicable")
    unit: str | None = Field(None, description="Unit of measure")
    reason: str | None = Field(None, description="Per-line reason")


class DebitCreditNoteExtraction(BaseModel):
    """Structured extraction of a debit or credit note."""

    note_number: str = Field(..., description="Debit/credit note number")
    note_type: str = Field(..., description="debit or credit")
    note_date: date | None = Field(None, description="Date of issuance")
    original_invoice_number: str | None = Field(None, description="Invoice being adjusted")
    original_invoice_date: date | None = Field(None, description="Date of original invoice")
    issuer: PartyInfo | None = Field(None, description="Party issuing the note")
    recipient: PartyInfo | None = Field(None, description="Party receiving the note")
    currency: str = Field(..., description="Currency code")
    reason: str | None = Field(None, description="Reason for adjustment")
    line_items: list[AdjustmentLineItem] = Field(default_factory=list, description="Adjusted line items")
    subtotal: float | None = Field(None, description="Subtotal of adjustments")
    tax_amount: float | None = Field(None, description="Tax adjustment")
    total_amount: float = Field(..., description="Total adjustment amount")
    notes: str | None = Field(None, description="Additional notes")


# --- CBP 7501 Customs Entry Summary (P2) ---


class EntryLineItem(BaseModel):
    """Line item on a CBP 7501 customs entry."""

    line_number: int | None = Field(None, description="Line sequence number")
    hts_number: str = Field(..., description="Harmonized Tariff Schedule number (10-digit)")
    description: str = Field(..., description="Description of merchandise")
    country_of_origin: str | None = Field(None, description="Country of origin per line")
    quantity: float | None = Field(None, description="Quantity")
    unit: str | None = Field(None, description="Reporting unit")
    entered_value: float = Field(..., description="Entered value")
    duty_rate: float | None = Field(None, description="Duty rate (percentage or specific)")
    duty_amount: float | None = Field(None, description="Calculated duty")
    ad_cvd_rate: str | None = Field(None, description="Anti-dumping/countervailing duty case number")
    ad_cvd_amount: float | None = Field(None, description="AD/CVD amount")


class CustomsEntryExtraction(BaseModel):
    """Structured extraction of a CBP 7501 customs entry summary."""

    entry_number: str = Field(..., description="11-digit entry number")
    entry_type: str | None = Field(None, description="2-digit entry type code")
    summary_date: date | None = Field(None, description="Date entry was filed")
    entry_date: date | None = Field(None, description="Date goods released from CBP custody")
    port_code: str | None = Field(None, description="US port code (4-digit)")
    surety_number: str | None = Field(None, description="3-digit surety company code")
    bond_type: str | None = Field(None, description="Bond type code (0, 8, 9)")
    importing_carrier: str | None = Field(None, description="Vessel name or IATA airline code")
    mode_of_transport: str | None = Field(None, description="2-digit transport mode code")
    country_of_origin: str | None = Field(None, description="Country of manufacture")
    exporting_country: str | None = Field(None, description="Country of export")
    import_date: date | None = Field(None, description="Date of importation")
    importer_number: str | None = Field(None, description="Importer's ID (IRS/EIN + 2 zeros)")
    importer_name: str | None = Field(None, description="Importer of record name")
    consignee_number: str | None = Field(None, description="Ultimate consignee number")
    consignee_name: str | None = Field(None, description="Ultimate consignee name")
    manufacturer_id: str | None = Field(None, description="Manufacturer/shipper ID")
    bol_or_awb: str | None = Field(None, description="Bill of lading or air waybill number")
    line_items: list[EntryLineItem] = Field(..., description="Entry summary line items")
    total_entered_value: float | None = Field(None, description="Total entered value")
    total_duty: float | None = Field(None, description="Total duty owed")
    total_tax: float | None = Field(None, description="Total tax owed")
    total_other: float | None = Field(None, description="Other fees (MPF, HMF, etc.)")
    total_amount: float | None = Field(None, description="Total amount payable")
    notes: str | None = Field(None, description="Additional notes")


# --- Proof of Delivery (P2) ---


class DeliveryItem(BaseModel):
    """Item on a proof of delivery."""

    description: str = Field(..., description="Item description")
    quantity_expected: float | None = Field(None, description="Expected quantity")
    quantity_delivered: float | None = Field(None, description="Actual quantity delivered")
    unit: str | None = Field(None, description="Unit of measure")
    condition: str | None = Field(None, description="Item condition")
    notes: str | None = Field(None, description="Item-level notes")


class ProofOfDeliveryExtraction(BaseModel):
    """Structured extraction of a proof of delivery."""

    pod_number: str | None = Field(None, description="POD reference number")
    delivery_date: date | None = Field(None, description="Actual delivery date")
    delivery_time: str | None = Field(None, description="Delivery time (HH:MM)")
    carrier_name: str | None = Field(None, description="Delivering carrier")
    driver_name: str | None = Field(None, description="Driver name")
    shipper: PartyInfo | None = Field(None, description="Shipper/sender")
    consignee: PartyInfo | None = Field(None, description="Receiver")
    delivery_address: str | None = Field(None, description="Actual delivery address")
    bol_number: str | None = Field(None, description="Associated BOL number")
    order_number: str | None = Field(None, description="Associated order/PO number")
    tracking_number: str | None = Field(None, description="Tracking/shipment number")
    items: list[DeliveryItem] = Field(default_factory=list, description="Delivered items")
    total_packages: int | None = Field(None, description="Total packages delivered")
    total_weight: float | None = Field(None, description="Total weight")
    weight_unit: str | None = Field(None, description="kg or lbs")
    receiver_name: str | None = Field(None, description="Name of person who signed")
    receiver_signature: bool = Field(False, description="Whether signature is present")
    condition: str | None = Field(None, description="Delivery condition (good, damaged, partial)")
    condition_notes: str | None = Field(None, description="Damage or exception notes")
    has_photo: bool = Field(False, description="Whether delivery photo exists")
    gps_coordinates: str | None = Field(None, description="GPS lat/long if available")
    notes: str | None = Field(None, description="Additional delivery notes")


# --- Certificate of Origin (P2) ---


class OriginItem(BaseModel):
    """Item on a certificate of origin."""

    description: str = Field(..., description="Description of goods")
    hs_code: str | None = Field(None, description="HS tariff classification")
    quantity: float | None = Field(None, description="Quantity")
    unit: str | None = Field(None, description="Unit of measure")
    origin_criterion: str | None = Field(None, description="Per-item origin criterion code")
    country_of_origin: str | None = Field(None, description="Per-item origin country (if varies)")


class CertificateOfOriginExtraction(BaseModel):
    """Structured extraction of a certificate of origin."""

    certificate_number: str | None = Field(None, description="Certificate reference number")
    issue_date: date | None = Field(None, description="Date of issuance")
    certificate_type: str | None = Field(None, description="Type (General, Form A, EUR.1, USMCA, etc.)")
    exporter: PartyInfo | None = Field(None, description="Exporter name, address")
    producer: PartyInfo | None = Field(None, description="Producer/manufacturer (if different from exporter)")
    importer: PartyInfo | None = Field(None, description="Importer name, address")
    country_of_origin: str = Field(..., description="Country where goods originate")
    country_of_destination: str | None = Field(None, description="Destination country")
    transport_details: str | None = Field(None, description="Vessel/flight, route, departure date")
    invoice_number: str | None = Field(None, description="Related commercial invoice number")
    items: list[OriginItem] = Field(..., description="Items covered by certificate")
    origin_criterion: str | None = Field(None, description="Criterion met (WO, PE, PSR, etc.)")
    blanket_period_start: date | None = Field(None, description="Blanket certification start date")
    blanket_period_end: date | None = Field(None, description="Blanket certification end date")
    issuing_authority: str | None = Field(None, description="Chamber of commerce or issuing body")
    certifier_name: str | None = Field(None, description="Name of person certifying")
    certification_date: date | None = Field(None, description="Date of certification/signature")
    notes: str | None = Field(None, description="Remarks or additional info")


# --- Type Registry ---
# Maps DocumentType to its Pydantic extraction model for validation.

EXTRACTION_MODEL_REGISTRY: dict[DocumentType, type[BaseModel]] = {
    DocumentType.FREIGHT_INVOICE: FreightInvoiceExtraction,
    DocumentType.BILL_OF_LADING: BillOfLadingExtraction,
    DocumentType.COMMERCIAL_INVOICE: CommercialInvoiceExtraction,
    DocumentType.PURCHASE_ORDER: PurchaseOrderExtraction,
    DocumentType.PACKING_LIST: PackingListExtraction,
    DocumentType.ARRIVAL_NOTICE: ArrivalNoticeExtraction,
    DocumentType.AIR_WAYBILL: AirWaybillExtraction,
    DocumentType.DEBIT_CREDIT_NOTE: DebitCreditNoteExtraction,
    DocumentType.CUSTOMS_ENTRY: CustomsEntryExtraction,
    DocumentType.PROOF_OF_DELIVERY: ProofOfDeliveryExtraction,
    DocumentType.CERTIFICATE_OF_ORIGIN: CertificateOfOriginExtraction,
}


# --- API Models ---


class ExtractionRequest(BaseModel):
    document_id: UUID


class ExtractionResponse(BaseModel):
    document_id: UUID
    document_type: DocumentType
    extraction: dict  # Validated extraction as dict
    raw_extraction: dict | None = None  # Pass 1 result (before refinement)
    model_used: str
    processing_time_ms: int | None = None
    confidence_notes: str | None = None

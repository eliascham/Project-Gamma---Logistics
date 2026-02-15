import enum
from datetime import date
from uuid import UUID

from pydantic import BaseModel, Field


class DocumentType(str, enum.Enum):
    """Type of logistics document, determined by classification."""

    FREIGHT_INVOICE = "freight_invoice"
    BILL_OF_LADING = "bill_of_lading"
    UNKNOWN = "unknown"


# --- Freight Invoice ---


class LineItem(BaseModel):
    description: str = Field(..., description="Description of the freight service or charge")
    quantity: float = Field(..., description="Number of units")
    unit: str = Field(..., description="Unit of measure (e.g., kg, pallet, container)")
    unit_price: float = Field(..., description="Price per unit in the invoice currency")
    total: float = Field(..., description="Line total amount")


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


# --- API Models ---


class ExtractionRequest(BaseModel):
    document_id: UUID


class ExtractionResponse(BaseModel):
    document_id: UUID
    document_type: DocumentType
    extraction: dict  # FreightInvoiceExtraction or BillOfLadingExtraction as dict
    raw_extraction: dict | None = None  # Pass 1 result (before refinement)
    model_used: str
    processing_time_ms: int | None = None
    confidence_notes: str | None = None

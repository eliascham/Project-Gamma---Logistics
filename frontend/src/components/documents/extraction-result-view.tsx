"use client";

import React, { useState } from "react";
import { motion } from "framer-motion";
import {
  Ship,
  FileText,
  MapPin,
  Package,
  DollarSign,
  User,
  ArrowRight,
  Clock,
  Cpu,
  Plane,
  ClipboardCheck,
  Globe,
  Truck,
  CreditCard,
  ScrollText,
  ShieldCheck,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { ExtractionResponse, PartyInfo } from "@/types/extraction";

const container = {
  hidden: {},
  show: { transition: { staggerChildren: 0.06 } },
};
const item = {
  hidden: { opacity: 0, y: 8 },
  show: { opacity: 1, y: 0 },
};

// ---------------------------------------------------------------------------
// Shared helpers
// ---------------------------------------------------------------------------

function FieldRow({ label, value }: { label: string; value: string | number | null | undefined }) {
  if (value === null || value === undefined || value === "") return null;
  return (
    <motion.div variants={item} className="flex justify-between gap-4 py-2">
      <span className="text-sm text-muted-foreground shrink-0">{label}</span>
      <span className="text-sm font-medium text-right">{String(value)}</span>
    </motion.div>
  );
}

function MonoFieldRow({ label, value }: { label: string; value: string | number | null | undefined }) {
  if (value === null || value === undefined || value === "") return null;
  return (
    <motion.div variants={item} className="flex justify-between gap-4 py-2">
      <span className="text-sm text-muted-foreground shrink-0">{label}</span>
      <span className="text-sm font-medium font-mono text-right">{String(value)}</span>
    </motion.div>
  );
}

function AmountRow({ label, value, currency }: { label: string; value: number | null | undefined; currency?: string }) {
  if (value === null || value === undefined) return null;
  const formatted = Number(value).toLocaleString(undefined, { minimumFractionDigits: 2 });
  return (
    <motion.div variants={item} className="flex justify-between gap-4 py-2">
      <span className="text-sm text-muted-foreground shrink-0">{label}</span>
      <span className="text-sm font-medium tabular-nums text-right">
        {currency ? `${currency} ` : ""}{formatted}
      </span>
    </motion.div>
  );
}

function TotalRow({ label, value, currency }: { label: string; value: number | null | undefined; currency?: string }) {
  if (value === null || value === undefined) return null;
  const formatted = Number(value).toLocaleString(undefined, { minimumFractionDigits: 2 });
  return (
    <motion.div variants={item} className="flex justify-between gap-4 py-2">
      <span className="text-sm font-semibold">{label}</span>
      <span className="text-sm font-bold text-primary tabular-nums">
        {currency ? `${currency} ` : ""}{formatted}
      </span>
    </motion.div>
  );
}

function SectionCard({
  title,
  icon: Icon,
  children,
}: {
  title: string;
  icon: React.ElementType;
  children: React.ReactNode;
}) {
  return (
    <motion.div variants={item}>
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-2 text-base">
            <Icon className="size-4 text-muted-foreground" />
            {title}
          </CardTitle>
        </CardHeader>
        <CardContent>{children}</CardContent>
      </Card>
    </motion.div>
  );
}

function PartyInfoCard({ label, party }: { label: string; party: PartyInfo | Record<string, unknown> | null | undefined }) {
  if (!party) return null;
  const p = party as Record<string, unknown>;
  if (!p.name) return null;
  return (
    <div className="rounded-lg border p-3">
      <p className="mb-1 text-xs font-medium uppercase text-muted-foreground">{label}</p>
      <p className="text-sm font-medium">{p.name as string}</p>
      {!!p.address && <p className="mt-0.5 text-xs text-muted-foreground">{String(p.address)}</p>}
      {!!(p.city || p.state || p.country) && (
        <p className="text-xs text-muted-foreground">
          {[p.city, p.state, p.postal_code, p.country].filter(Boolean).map(String).join(", ")}
        </p>
      )}
      {!!p.tax_id && <p className="text-xs text-muted-foreground font-mono mt-0.5">Tax ID: {String(p.tax_id)}</p>}
      {!!p.contact_name && <p className="text-xs text-muted-foreground mt-0.5">{String(p.contact_name)}</p>}
      {!!(p.phone || p.email) && (
        <p className="text-xs text-muted-foreground">
          {[p.phone, p.email].filter(Boolean).map(String).join(" | ")}
        </p>
      )}
    </div>
  );
}

function PartiesGrid({ parties }: { parties: { label: string; party: PartyInfo | Record<string, unknown> | null | undefined }[] }) {
  const valid = parties.filter((p) => p.party && (p.party as Record<string, unknown>).name);
  if (valid.length === 0) return null;
  return (
    <div className={`grid gap-3 ${valid.length === 1 ? "" : "sm:grid-cols-2"}`}>
      {valid.map((p) => (
        <PartyInfoCard key={p.label} label={p.label} party={p.party} />
      ))}
    </div>
  );
}

function BadgeList({ label, items }: { label: string; items: string[] | undefined | null }) {
  if (!items || items.length === 0) return null;
  return (
    <motion.div variants={item} className="py-2">
      <p className="mb-1.5 text-sm text-muted-foreground">{label}</p>
      <div className="flex flex-wrap gap-1.5">
        {items.map((c) => (
          <Badge key={c} variant="secondary" className="font-mono text-xs">
            {c}
          </Badge>
        ))}
      </div>
    </motion.div>
  );
}

function NotesSection({ notes }: { notes: string | null | undefined }) {
  if (!notes) return null;
  return (
    <SectionCard title="Notes" icon={FileText}>
      <p className="text-sm text-muted-foreground">{notes}</p>
    </SectionCard>
  );
}

// ---------------------------------------------------------------------------
// Freight Invoice
// ---------------------------------------------------------------------------

function FreightInvoiceView({ data }: { data: Record<string, unknown> }) {
  const lineItems = (data.line_items as Array<Record<string, unknown>>) || [];

  return (
    <motion.div className="space-y-4" variants={container} initial="hidden" animate="show">
      <SectionCard title="Invoice Details" icon={FileText}>
        <motion.div variants={container} initial="hidden" animate="show" className="divide-y">
          <MonoFieldRow label="Invoice Number" value={data.invoice_number as string} />
          <FieldRow label="Invoice Date" value={data.invoice_date as string} />
          <FieldRow label="Vendor" value={data.vendor_name as string} />
          <FieldRow label="Currency" value={data.currency as string} />
          {!!data.invoice_variant && (
            <motion.div variants={item} className="flex justify-between gap-4 py-2">
              <span className="text-sm text-muted-foreground">Variant</span>
              <Badge variant="outline" className="text-xs">{String(data.invoice_variant)}</Badge>
            </motion.div>
          )}
        </motion.div>
      </SectionCard>

      <SectionCard title="Parties & Route" icon={MapPin}>
        <motion.div variants={container} initial="hidden" animate="show" className="divide-y">
          <FieldRow label="Shipper" value={data.shipper_name as string} />
          <FieldRow label="Consignee" value={data.consignee_name as string} />
          {!!(data.origin || data.destination) && (
            <motion.div variants={item} className="flex items-center gap-2 py-2 text-sm">
              <span className="text-muted-foreground">{(data.origin as string) || "\u2014"}</span>
              <ArrowRight className="size-3 text-muted-foreground" />
              <span className="font-medium">{(data.destination as string) || "\u2014"}</span>
            </motion.div>
          )}
        </motion.div>
      </SectionCard>

      {lineItems.length > 0 && (
        <SectionCard title="Line Items" icon={Package}>
          <div className="rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Description</TableHead>
                  <TableHead className="text-right">Qty</TableHead>
                  <TableHead>Unit</TableHead>
                  <TableHead className="text-right">Unit Price</TableHead>
                  <TableHead className="text-right">Total</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {lineItems.map((li, i) => (
                  <TableRow key={i}>
                    <TableCell className="font-medium">{li.description as string}</TableCell>
                    <TableCell className="text-right tabular-nums">{li.quantity as number}</TableCell>
                    <TableCell>{li.unit as string}</TableCell>
                    <TableCell className="text-right tabular-nums">
                      {(li.unit_price as number)?.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                    </TableCell>
                    <TableCell className="text-right font-medium tabular-nums">
                      {(li.total as number)?.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </SectionCard>
      )}

      <SectionCard title="Totals" icon={DollarSign}>
        <motion.div variants={container} initial="hidden" animate="show" className="divide-y">
          <AmountRow label="Subtotal" value={data.subtotal as number | null} />
          <AmountRow label="Tax" value={data.tax_amount as number | null} />
          <TotalRow label="Total Amount" value={data.total_amount as number | null} currency={data.currency as string} />
        </motion.div>
      </SectionCard>

      <NotesSection notes={data.notes as string | null} />
    </motion.div>
  );
}

// ---------------------------------------------------------------------------
// Bill of Lading
// ---------------------------------------------------------------------------

function BillOfLadingView({ data }: { data: Record<string, unknown> }) {
  const shipper = data.shipper as Record<string, unknown> | null;
  const consignee = data.consignee as Record<string, unknown> | null;
  const origin = data.origin as Record<string, unknown> | null;
  const destination = data.destination as Record<string, unknown> | null;
  const containers = (data.container_numbers as string[]) || [];

  function formatLocation(loc: Record<string, unknown> | null): string {
    if (!loc) return "\u2014";
    const parts = [loc.port, loc.city, loc.state, loc.country].filter(Boolean);
    return parts.join(", ") || "\u2014";
  }

  return (
    <motion.div className="space-y-4" variants={container} initial="hidden" animate="show">
      <SectionCard title="BOL Details" icon={FileText}>
        <motion.div variants={container} initial="hidden" animate="show" className="divide-y">
          <MonoFieldRow label="BOL Number" value={data.bol_number as string} />
          <FieldRow label="Issue Date" value={data.issue_date as string} />
          <FieldRow label="Carrier" value={data.carrier_name as string} />
          <MonoFieldRow label="SCAC" value={data.carrier_scac as string} />
          <FieldRow label="Vessel" value={data.vessel_name as string} />
          <FieldRow label="Voyage" value={data.voyage_number as string} />
        </motion.div>
      </SectionCard>

      <SectionCard title="Parties" icon={User}>
        <div className="grid gap-4 sm:grid-cols-2">
          {shipper && (
            <div className="rounded-lg border p-3">
              <p className="mb-1 text-xs font-medium uppercase text-muted-foreground">Shipper</p>
              <p className="text-sm font-medium">{shipper.name as string}</p>
              {!!shipper.address && <p className="mt-0.5 text-xs text-muted-foreground">{String(shipper.address)}</p>}
            </div>
          )}
          {consignee && (
            <div className="rounded-lg border p-3">
              <p className="mb-1 text-xs font-medium uppercase text-muted-foreground">Consignee</p>
              <p className="text-sm font-medium">{consignee.name as string}</p>
              {!!consignee.address && <p className="mt-0.5 text-xs text-muted-foreground">{String(consignee.address)}</p>}
            </div>
          )}
        </div>
        <motion.div variants={container} initial="hidden" animate="show" className="mt-3 divide-y">
          <FieldRow label="Notify Party" value={data.notify_party as string} />
        </motion.div>
      </SectionCard>

      <SectionCard title="Route" icon={Ship}>
        <motion.div variants={item} className="flex items-center gap-3 py-2">
          <div className="flex-1 rounded-lg border p-3 text-center">
            <p className="text-xs text-muted-foreground">Origin</p>
            <p className="text-sm font-medium">{formatLocation(origin)}</p>
          </div>
          <ArrowRight className="size-5 shrink-0 text-muted-foreground" />
          <div className="flex-1 rounded-lg border p-3 text-center">
            <p className="text-xs text-muted-foreground">Destination</p>
            <p className="text-sm font-medium">{formatLocation(destination)}</p>
          </div>
        </motion.div>
      </SectionCard>

      <SectionCard title="Cargo" icon={Package}>
        <motion.div variants={container} initial="hidden" animate="show" className="divide-y">
          <FieldRow label="Description" value={data.cargo_description as string} />
          <FieldRow label="Packages" value={data.package_count as number} />
          <FieldRow
            label="Weight"
            value={data.gross_weight != null ? `${data.gross_weight} ${(data.weight_unit as string) || ""}` : null}
          />
          <FieldRow
            label="Volume"
            value={data.volume != null ? `${data.volume} ${(data.volume_unit as string) || ""}` : null}
          />
          <BadgeList label="Containers" items={containers} />
        </motion.div>
      </SectionCard>

      <SectionCard title="Freight" icon={DollarSign}>
        <motion.div variants={container} initial="hidden" animate="show" className="divide-y">
          <AmountRow label="Charges" value={data.freight_charges as number | null} />
          <FieldRow label="Payment Type" value={data.freight_payment_type as string} />
        </motion.div>
      </SectionCard>

      {!!(data.special_instructions || data.notes) && (
        <SectionCard title="Notes" icon={FileText}>
          {!!data.special_instructions && (
            <p className="text-sm text-muted-foreground">{String(data.special_instructions)}</p>
          )}
          {!!data.notes && <p className="mt-1 text-sm text-muted-foreground">{String(data.notes)}</p>}
        </SectionCard>
      )}
    </motion.div>
  );
}

// ---------------------------------------------------------------------------
// Commercial Invoice
// ---------------------------------------------------------------------------

function CommercialInvoiceView({ data }: { data: Record<string, unknown> }) {
  const lineItems = (data.line_items as Array<Record<string, unknown>>) || [];
  const currency = data.currency as string;

  return (
    <motion.div className="space-y-4" variants={container} initial="hidden" animate="show">
      <SectionCard title="Invoice Details" icon={FileText}>
        <motion.div variants={container} initial="hidden" animate="show" className="divide-y">
          <MonoFieldRow label="Invoice Number" value={data.invoice_number as string} />
          <FieldRow label="Invoice Date" value={data.invoice_date as string} />
          <FieldRow label="Currency" value={currency} />
          <FieldRow label="Incoterms" value={data.incoterms as string} />
          <FieldRow label="Incoterms Location" value={data.incoterms_location as string} />
          <FieldRow label="Payment Terms" value={data.payment_terms as string} />
          {!!data.invoice_variant && (
            <motion.div variants={item} className="flex justify-between gap-4 py-2">
              <span className="text-sm text-muted-foreground">Variant</span>
              <Badge variant="outline" className="text-xs">{String(data.invoice_variant)}</Badge>
            </motion.div>
          )}
        </motion.div>
      </SectionCard>

      <SectionCard title="Parties" icon={User}>
        <PartiesGrid parties={[
          { label: "Seller", party: data.seller as PartyInfo | null },
          { label: "Buyer", party: data.buyer as PartyInfo | null },
          { label: "Consignee", party: data.consignee as PartyInfo | null },
        ]} />
      </SectionCard>

      {!!(data.ship_from || data.ship_to) && (
        <SectionCard title="Shipping" icon={MapPin}>
          <motion.div variants={item} className="flex items-center gap-3 py-2">
            <div className="flex-1 rounded-lg border p-3 text-center">
              <p className="text-xs text-muted-foreground">Ship From</p>
              <p className="text-sm font-medium">
                {formatLocationInfo(data.ship_from as Record<string, unknown> | null)}
              </p>
            </div>
            <ArrowRight className="size-5 shrink-0 text-muted-foreground" />
            <div className="flex-1 rounded-lg border p-3 text-center">
              <p className="text-xs text-muted-foreground">Ship To</p>
              <p className="text-sm font-medium">
                {formatLocationInfo(data.ship_to as Record<string, unknown> | null)}
              </p>
            </div>
          </motion.div>
          <motion.div variants={container} initial="hidden" animate="show" className="divide-y mt-2">
            <FieldRow label="Country of Origin" value={data.country_of_origin as string} />
            <FieldRow label="Country of Export" value={data.country_of_export as string} />
            <FieldRow label="Transport Ref" value={data.transport_reference as string} />
            <FieldRow label="Vessel / Flight" value={data.vessel_or_flight as string} />
          </motion.div>
        </SectionCard>
      )}

      {lineItems.length > 0 && (
        <SectionCard title="Line Items" icon={Package}>
          <div className="rounded-md border overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Item #</TableHead>
                  <TableHead>Description</TableHead>
                  <TableHead className="font-mono">HS Code</TableHead>
                  <TableHead className="text-right">Qty</TableHead>
                  <TableHead>Unit</TableHead>
                  <TableHead className="text-right">Unit Price</TableHead>
                  <TableHead className="text-right">Total</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {lineItems.map((li, i) => (
                  <TableRow key={i}>
                    <TableCell className="font-mono text-xs">{(li.item_number as string) || "\u2014"}</TableCell>
                    <TableCell className="font-medium">{li.description as string}</TableCell>
                    <TableCell className="font-mono text-xs">{(li.hs_code as string) || "\u2014"}</TableCell>
                    <TableCell className="text-right tabular-nums">{li.quantity as number}</TableCell>
                    <TableCell>{li.unit as string}</TableCell>
                    <TableCell className="text-right tabular-nums">
                      {(li.unit_price as number)?.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                    </TableCell>
                    <TableCell className="text-right font-medium tabular-nums">
                      {(li.total as number)?.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </SectionCard>
      )}

      <SectionCard title="Financial Summary" icon={DollarSign}>
        <motion.div variants={container} initial="hidden" animate="show" className="divide-y">
          <AmountRow label="Subtotal" value={data.subtotal as number | null} />
          <AmountRow label="Freight Charges" value={data.freight_charges as number | null} />
          <AmountRow label="Insurance" value={data.insurance_charges as number | null} />
          <AmountRow label="Discount" value={data.discount_amount as number | null} />
          <AmountRow label="Tax" value={data.tax_amount as number | null} />
          <TotalRow label="Total Amount" value={data.total_amount as number | null} currency={currency} />
        </motion.div>
      </SectionCard>

      <NotesSection notes={data.notes as string | null} />
    </motion.div>
  );
}

// ---------------------------------------------------------------------------
// Purchase Order
// ---------------------------------------------------------------------------

function PurchaseOrderView({ data }: { data: Record<string, unknown> }) {
  const lineItems = (data.line_items as Array<Record<string, unknown>>) || [];
  const currency = data.currency as string;

  return (
    <motion.div className="space-y-4" variants={container} initial="hidden" animate="show">
      <SectionCard title="PO Details" icon={FileText}>
        <motion.div variants={container} initial="hidden" animate="show" className="divide-y">
          <MonoFieldRow label="PO Number" value={data.po_number as string} />
          <FieldRow label="PO Date" value={data.po_date as string} />
          <FieldRow label="Currency" value={currency} />
          {!!data.status && (
            <motion.div variants={item} className="flex justify-between gap-4 py-2">
              <span className="text-sm text-muted-foreground">Status</span>
              <Badge variant="secondary" className="text-xs">{String(data.status)}</Badge>
            </motion.div>
          )}
          <FieldRow label="Incoterms" value={data.incoterms as string} />
          <FieldRow label="Payment Terms" value={data.payment_terms as string} />
        </motion.div>
      </SectionCard>

      <SectionCard title="Parties" icon={User}>
        <PartiesGrid parties={[
          { label: "Buyer", party: data.buyer as PartyInfo | null },
          { label: "Supplier", party: data.supplier as PartyInfo | null },
          { label: "Ship To", party: data.ship_to as PartyInfo | null },
        ]} />
      </SectionCard>

      {lineItems.length > 0 && (
        <SectionCard title="Line Items" icon={Package}>
          <div className="rounded-md border overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Line #</TableHead>
                  <TableHead>Item #</TableHead>
                  <TableHead>Description</TableHead>
                  <TableHead className="font-mono">HS Code</TableHead>
                  <TableHead className="text-right">Qty</TableHead>
                  <TableHead>Unit</TableHead>
                  <TableHead className="text-right">Unit Price</TableHead>
                  <TableHead className="text-right">Total</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {lineItems.map((li, i) => (
                  <TableRow key={i}>
                    <TableCell className="tabular-nums">{(li.line_number as number) ?? "\u2014"}</TableCell>
                    <TableCell className="font-mono text-xs">{(li.item_number as string) || "\u2014"}</TableCell>
                    <TableCell className="font-medium">{li.description as string}</TableCell>
                    <TableCell className="font-mono text-xs">{(li.hs_code as string) || "\u2014"}</TableCell>
                    <TableCell className="text-right tabular-nums">{li.quantity as number}</TableCell>
                    <TableCell>{li.unit as string}</TableCell>
                    <TableCell className="text-right tabular-nums">
                      {(li.unit_price as number)?.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                    </TableCell>
                    <TableCell className="text-right font-medium tabular-nums">
                      {(li.total as number)?.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </SectionCard>
      )}

      <SectionCard title="Financial Summary" icon={DollarSign}>
        <motion.div variants={container} initial="hidden" animate="show" className="divide-y">
          <AmountRow label="Subtotal" value={data.subtotal as number | null} />
          <AmountRow label="Tax" value={data.tax_amount as number | null} />
          <AmountRow label="Shipping" value={data.shipping_amount as number | null} />
          <TotalRow label="Total Amount" value={data.total_amount as number | null} currency={currency} />
        </motion.div>
      </SectionCard>

      {!!(data.delivery_date || data.shipping_method) && (
        <SectionCard title="Delivery" icon={Truck}>
          <motion.div variants={container} initial="hidden" animate="show" className="divide-y">
            <FieldRow label="Expected Delivery" value={data.delivery_date as string} />
            <FieldRow label="Shipping Method" value={data.shipping_method as string} />
          </motion.div>
        </SectionCard>
      )}

      <NotesSection notes={data.notes as string | null} />
    </motion.div>
  );
}

// ---------------------------------------------------------------------------
// Packing List
// ---------------------------------------------------------------------------

function PackingListView({ data }: { data: Record<string, unknown> }) {
  const items = (data.items as Array<Record<string, unknown>>) || [];
  const containers = (data.container_numbers as string[]) || [];

  return (
    <motion.div className="space-y-4" variants={container} initial="hidden" animate="show">
      <SectionCard title="Packing List Details" icon={FileText}>
        <motion.div variants={container} initial="hidden" animate="show" className="divide-y">
          <MonoFieldRow label="PL Number" value={data.packing_list_number as string} />
          <FieldRow label="Date" value={data.packing_date as string} />
          <MonoFieldRow label="Invoice #" value={data.invoice_number as string} />
          <MonoFieldRow label="PO #" value={data.po_number as string} />
        </motion.div>
      </SectionCard>

      <SectionCard title="Parties" icon={User}>
        <PartiesGrid parties={[
          { label: "Seller", party: data.seller as PartyInfo | null },
          { label: "Buyer", party: data.buyer as PartyInfo | null },
          { label: "Consignee", party: data.consignee as PartyInfo | null },
        ]} />
      </SectionCard>

      {!!(data.transport_reference || data.vessel_or_flight || containers.length > 0) && (
        <SectionCard title="Shipping" icon={Ship}>
          <motion.div variants={container} initial="hidden" animate="show" className="divide-y">
            <FieldRow label="Transport Ref" value={data.transport_reference as string} />
            <FieldRow label="Vessel / Flight" value={data.vessel_or_flight as string} />
            <BadgeList label="Containers" items={containers} />
          </motion.div>
        </SectionCard>
      )}

      {items.length > 0 && (
        <SectionCard title="Items" icon={Package}>
          <div className="rounded-md border overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Item #</TableHead>
                  <TableHead>Description</TableHead>
                  <TableHead className="text-right">Qty</TableHead>
                  <TableHead>Pkg Type</TableHead>
                  <TableHead className="text-right">Pkg Count</TableHead>
                  <TableHead className="text-right">Gross Wt</TableHead>
                  <TableHead className="text-right">Net Wt</TableHead>
                  <TableHead>Dimensions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {items.map((it, i) => (
                  <TableRow key={i}>
                    <TableCell className="font-mono text-xs">{(it.item_number as string) || "\u2014"}</TableCell>
                    <TableCell className="font-medium">{it.description as string}</TableCell>
                    <TableCell className="text-right tabular-nums">{it.quantity as number}</TableCell>
                    <TableCell>{(it.package_type as string) || "\u2014"}</TableCell>
                    <TableCell className="text-right tabular-nums">{(it.package_count as number) ?? "\u2014"}</TableCell>
                    <TableCell className="text-right tabular-nums">{(it.gross_weight as number) ?? "\u2014"}</TableCell>
                    <TableCell className="text-right tabular-nums">{(it.net_weight as number) ?? "\u2014"}</TableCell>
                    <TableCell className="font-mono text-xs">{(it.dimensions as string) || "\u2014"}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </SectionCard>
      )}

      <SectionCard title="Totals" icon={DollarSign}>
        <motion.div variants={container} initial="hidden" animate="show" className="divide-y">
          <FieldRow label="Total Packages" value={data.total_packages as number | null} />
          <FieldRow
            label="Gross Weight"
            value={data.total_gross_weight != null ? `${data.total_gross_weight} ${(data.weight_unit as string) || ""}` : null}
          />
          <FieldRow
            label="Net Weight"
            value={data.total_net_weight != null ? `${data.total_net_weight} ${(data.weight_unit as string) || ""}` : null}
          />
          <FieldRow
            label="Volume"
            value={data.total_volume != null ? `${data.total_volume} ${(data.volume_unit as string) || ""}` : null}
          />
        </motion.div>
      </SectionCard>

      <NotesSection notes={data.notes as string | null} />
    </motion.div>
  );
}

// ---------------------------------------------------------------------------
// Arrival Notice
// ---------------------------------------------------------------------------

function ArrivalNoticeView({ data }: { data: Record<string, unknown> }) {
  const charges = (data.charges as Array<Record<string, unknown>>) || [];
  const containers = (data.container_numbers as string[]) || [];
  const docsRequired = (data.documents_required as string[]) || [];

  return (
    <motion.div className="space-y-4" variants={container} initial="hidden" animate="show">
      <SectionCard title="Notice Details" icon={FileText}>
        <motion.div variants={container} initial="hidden" animate="show" className="divide-y">
          <MonoFieldRow label="Notice Number" value={data.notice_number as string} />
          <FieldRow label="Notice Date" value={data.notice_date as string} />
          <MonoFieldRow label="BOL #" value={data.bol_number as string} />
          <FieldRow label="Vessel" value={data.vessel_name as string} />
          <FieldRow label="Voyage" value={data.voyage_number as string} />
        </motion.div>
      </SectionCard>

      <SectionCard title="Parties" icon={User}>
        <PartiesGrid parties={[
          { label: "Carrier", party: data.carrier as PartyInfo | null },
          { label: "Shipper", party: data.shipper as PartyInfo | null },
          { label: "Consignee", party: data.consignee as PartyInfo | null },
          { label: "Notify Party", party: data.notify_party as PartyInfo | null },
        ]} />
      </SectionCard>

      <SectionCard title="Schedule" icon={Clock}>
        <motion.div variants={container} initial="hidden" animate="show" className="divide-y">
          <FieldRow label="Port of Loading" value={data.port_of_loading as string} />
          <FieldRow label="Port of Discharge" value={data.port_of_discharge as string} />
          <FieldRow label="Place of Delivery" value={data.place_of_delivery as string} />
          <FieldRow label="ETA" value={data.eta as string} />
          <FieldRow label="ATA" value={data.ata as string} />
          <FieldRow label="Last Free Day" value={data.last_free_day as string} />
          <FieldRow label="Free Time Days" value={data.free_time_days as number | null} />
        </motion.div>
      </SectionCard>

      {!!(data.cargo_description || containers.length > 0) && (
        <SectionCard title="Cargo" icon={Package}>
          <motion.div variants={container} initial="hidden" animate="show" className="divide-y">
            <FieldRow label="Description" value={data.cargo_description as string} />
            <FieldRow label="Packages" value={data.package_count as number | null} />
            <FieldRow
              label="Weight"
              value={data.gross_weight != null ? `${data.gross_weight} ${(data.weight_unit as string) || ""}` : null}
            />
            <FieldRow
              label="Volume"
              value={data.volume != null ? `${data.volume} ${(data.volume_unit as string) || ""}` : null}
            />
            <BadgeList label="Containers" items={containers} />
          </motion.div>
        </SectionCard>
      )}

      {charges.length > 0 && (
        <SectionCard title="Charges" icon={DollarSign}>
          <div className="rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Charge Type</TableHead>
                  <TableHead className="text-right">Amount</TableHead>
                  <TableHead>Currency</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {charges.map((ch, i) => (
                  <TableRow key={i}>
                    <TableCell className="font-medium">{ch.charge_type as string}</TableCell>
                    <TableCell className="text-right tabular-nums">
                      {(ch.amount as number)?.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                    </TableCell>
                    <TableCell>{(ch.currency as string) || (data.currency as string) || "\u2014"}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
          <div className="mt-3">
            <TotalRow label="Total Charges" value={data.total_charges as number | null} currency={data.currency as string | undefined} />
          </div>
        </SectionCard>
      )}

      <BadgeList label="Documents Required" items={docsRequired} />

      <NotesSection notes={data.notes as string | null} />
    </motion.div>
  );
}

// ---------------------------------------------------------------------------
// Air Waybill
// ---------------------------------------------------------------------------

function AirWaybillView({ data }: { data: Record<string, unknown> }) {
  const otherCharges = (data.other_charges as Array<Record<string, unknown>>) || [];
  const routing = (data.routing as string[]) || [];
  const currency = data.currency as string | undefined;

  return (
    <motion.div className="space-y-4" variants={container} initial="hidden" animate="show">
      <SectionCard title="AWB Details" icon={Plane}>
        <motion.div variants={container} initial="hidden" animate="show" className="divide-y">
          <MonoFieldRow label="AWB Number" value={data.awb_number as string} />
          {!!data.awb_type && (
            <motion.div variants={item} className="flex justify-between gap-4 py-2">
              <span className="text-sm text-muted-foreground">Type</span>
              <Badge variant="secondary" className="text-xs font-mono">{String(data.awb_type)}</Badge>
            </motion.div>
          )}
          <MonoFieldRow label="Master AWB" value={data.master_awb_number as string} />
          <FieldRow label="Issue Date" value={data.issue_date as string} />
          <MonoFieldRow label="Airline Code" value={data.airline_code as string} />
          <FieldRow label="Airline" value={data.airline_name as string} />
        </motion.div>
      </SectionCard>

      <SectionCard title="Route" icon={MapPin}>
        <motion.div variants={item} className="flex items-center gap-3 py-2">
          <div className="flex-1 rounded-lg border p-3 text-center">
            <p className="text-xs text-muted-foreground">Departure</p>
            <p className="text-sm font-medium font-mono">{(data.airport_of_departure as string) || "\u2014"}</p>
          </div>
          <ArrowRight className="size-5 shrink-0 text-muted-foreground" />
          <div className="flex-1 rounded-lg border p-3 text-center">
            <p className="text-xs text-muted-foreground">Destination</p>
            <p className="text-sm font-medium font-mono">{(data.airport_of_destination as string) || "\u2014"}</p>
          </div>
        </motion.div>
        <motion.div variants={container} initial="hidden" animate="show" className="divide-y mt-2">
          <FieldRow label="Flight #" value={data.flight_number as string} />
          <FieldRow label="Flight Date" value={data.flight_date as string} />
          {routing.length > 0 && (
            <motion.div variants={item} className="py-2">
              <p className="mb-1.5 text-sm text-muted-foreground">Routing</p>
              <p className="text-sm font-mono">{routing.join(" \u2192 ")}</p>
            </motion.div>
          )}
        </motion.div>
      </SectionCard>

      <SectionCard title="Parties" icon={User}>
        <PartiesGrid parties={[
          { label: "Shipper", party: data.shipper as PartyInfo | null },
          { label: "Consignee", party: data.consignee as PartyInfo | null },
          { label: "Issuing Agent", party: data.issuing_agent as PartyInfo | null },
        ]} />
      </SectionCard>

      <SectionCard title="Cargo" icon={Package}>
        <motion.div variants={container} initial="hidden" animate="show" className="divide-y">
          <FieldRow label="Description" value={data.cargo_description as string} />
          <FieldRow label="Pieces" value={data.pieces as number | null} />
          <FieldRow
            label="Gross Weight"
            value={data.gross_weight != null ? `${data.gross_weight} ${(data.weight_unit as string) || ""}` : null}
          />
          <FieldRow
            label="Chargeable Weight"
            value={data.chargeable_weight != null ? `${data.chargeable_weight} ${(data.weight_unit as string) || ""}` : null}
          />
          <FieldRow label="Dimensions" value={data.dimensions as string} />
          <FieldRow label="Volume" value={data.volume as number | null} />
        </motion.div>
      </SectionCard>

      <SectionCard title="Financial" icon={DollarSign}>
        <motion.div variants={container} initial="hidden" animate="show" className="divide-y">
          <FieldRow label="Rate Class" value={data.rate_class as string} />
          <AmountRow label="Rate" value={data.rate as number | null} />
          <AmountRow label="Freight Charges" value={data.freight_charges as number | null} />
          <AmountRow label="Declared Value (Carriage)" value={data.declared_value_carriage as number | null} />
          <AmountRow label="Declared Value (Customs)" value={data.declared_value_customs as number | null} />
          <AmountRow label="Insurance" value={data.insurance_amount as number | null} />
          <FieldRow label="Payment Type" value={data.payment_type as string} />
        </motion.div>

        {otherCharges.length > 0 && (
          <div className="mt-4">
            <p className="text-sm font-medium mb-2">Other Charges</p>
            <div className="rounded-md border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Code</TableHead>
                    <TableHead>Type</TableHead>
                    <TableHead className="text-right">Amount</TableHead>
                    <TableHead>Prepaid/Collect</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {otherCharges.map((ch, i) => (
                    <TableRow key={i}>
                      <TableCell className="font-mono text-xs">{(ch.charge_code as string) || "\u2014"}</TableCell>
                      <TableCell className="font-medium">{ch.charge_type as string}</TableCell>
                      <TableCell className="text-right tabular-nums">
                        {(ch.amount as number)?.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                      </TableCell>
                      <TableCell>{(ch.prepaid_or_collect as string) || "\u2014"}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          </div>
        )}

        <div className="mt-3">
          <TotalRow label="Total Charges" value={data.total_charges as number | null} currency={currency} />
        </div>
      </SectionCard>

      {!!data.handling_info && (
        <SectionCard title="Handling Information" icon={FileText}>
          <p className="text-sm text-muted-foreground">{String(data.handling_info)}</p>
        </SectionCard>
      )}

      <NotesSection notes={data.notes as string | null} />
    </motion.div>
  );
}

// ---------------------------------------------------------------------------
// Debit/Credit Note
// ---------------------------------------------------------------------------

function DebitCreditNoteView({ data }: { data: Record<string, unknown> }) {
  const lineItems = (data.line_items as Array<Record<string, unknown>>) || [];
  const currency = data.currency as string;
  const noteType = data.note_type as string;

  return (
    <motion.div className="space-y-4" variants={container} initial="hidden" animate="show">
      <SectionCard title="Note Details" icon={CreditCard}>
        <motion.div variants={container} initial="hidden" animate="show" className="divide-y">
          <motion.div variants={item} className="flex justify-between gap-4 py-2">
            <span className="text-sm text-muted-foreground">Note Number</span>
            <span className="flex items-center gap-2">
              <Badge variant={noteType === "credit" ? "secondary" : "destructive"} className="text-xs">
                {noteType === "credit" ? "Credit" : "Debit"}
              </Badge>
              <span className="text-sm font-medium font-mono">{data.note_number as string}</span>
            </span>
          </motion.div>
          <FieldRow label="Note Date" value={data.note_date as string} />
          <MonoFieldRow label="Original Invoice #" value={data.original_invoice_number as string} />
          <FieldRow label="Original Invoice Date" value={data.original_invoice_date as string} />
          <FieldRow label="Currency" value={currency} />
        </motion.div>
      </SectionCard>

      <SectionCard title="Parties" icon={User}>
        <PartiesGrid parties={[
          { label: "Issuer", party: data.issuer as PartyInfo | null },
          { label: "Recipient", party: data.recipient as PartyInfo | null },
        ]} />
      </SectionCard>

      {!!data.reason && (
        <SectionCard title="Reason for Adjustment" icon={FileText}>
          <p className="text-sm text-muted-foreground">{String(data.reason)}</p>
        </SectionCard>
      )}

      {lineItems.length > 0 && (
        <SectionCard title="Adjustment Line Items" icon={Package}>
          <div className="rounded-md border overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Description</TableHead>
                  <TableHead className="text-right">Original Amt</TableHead>
                  <TableHead className="text-right">Adjusted Amt</TableHead>
                  <TableHead className="text-right">Difference</TableHead>
                  <TableHead>Reason</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {lineItems.map((li, i) => (
                  <TableRow key={i}>
                    <TableCell className="font-medium">{li.description as string}</TableCell>
                    <TableCell className="text-right tabular-nums">
                      {li.original_amount != null
                        ? (li.original_amount as number).toLocaleString(undefined, { minimumFractionDigits: 2 })
                        : "\u2014"}
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      {(li.adjusted_amount as number)?.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      {li.difference != null
                        ? (li.difference as number).toLocaleString(undefined, { minimumFractionDigits: 2 })
                        : "\u2014"}
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground">{(li.reason as string) || "\u2014"}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </SectionCard>
      )}

      <SectionCard title="Financial Summary" icon={DollarSign}>
        <motion.div variants={container} initial="hidden" animate="show" className="divide-y">
          <AmountRow label="Subtotal" value={data.subtotal as number | null} />
          <AmountRow label="Tax" value={data.tax_amount as number | null} />
          <TotalRow label="Total Amount" value={data.total_amount as number | null} currency={currency} />
        </motion.div>
      </SectionCard>

      <NotesSection notes={data.notes as string | null} />
    </motion.div>
  );
}

// ---------------------------------------------------------------------------
// CBP 7501 Customs Entry
// ---------------------------------------------------------------------------

function CustomsEntryView({ data }: { data: Record<string, unknown> }) {
  const lineItems = (data.line_items as Array<Record<string, unknown>>) || [];

  return (
    <motion.div className="space-y-4" variants={container} initial="hidden" animate="show">
      <SectionCard title="Entry Details" icon={ScrollText}>
        <motion.div variants={container} initial="hidden" animate="show" className="divide-y">
          <MonoFieldRow label="Entry Number" value={data.entry_number as string} />
          <FieldRow label="Entry Type" value={data.entry_type as string} />
          <FieldRow label="Summary Date" value={data.summary_date as string} />
          <FieldRow label="Entry Date" value={data.entry_date as string} />
          <MonoFieldRow label="Port Code" value={data.port_code as string} />
          <MonoFieldRow label="Surety Number" value={data.surety_number as string} />
          <FieldRow label="Bond Type" value={data.bond_type as string} />
        </motion.div>
      </SectionCard>

      <SectionCard title="Import Details" icon={Ship}>
        <motion.div variants={container} initial="hidden" animate="show" className="divide-y">
          <FieldRow label="Importing Carrier" value={data.importing_carrier as string} />
          <FieldRow label="Mode of Transport" value={data.mode_of_transport as string} />
          <FieldRow label="Country of Origin" value={data.country_of_origin as string} />
          <FieldRow label="Exporting Country" value={data.exporting_country as string} />
          <FieldRow label="Import Date" value={data.import_date as string} />
          <MonoFieldRow label="BOL / AWB" value={data.bol_or_awb as string} />
          <MonoFieldRow label="Manufacturer ID" value={data.manufacturer_id as string} />
        </motion.div>
      </SectionCard>

      <SectionCard title="Importer / Consignee" icon={User}>
        <motion.div variants={container} initial="hidden" animate="show" className="divide-y">
          <MonoFieldRow label="Importer Number" value={data.importer_number as string} />
          <FieldRow label="Importer Name" value={data.importer_name as string} />
          <MonoFieldRow label="Consignee Number" value={data.consignee_number as string} />
          <FieldRow label="Consignee Name" value={data.consignee_name as string} />
        </motion.div>
      </SectionCard>

      {lineItems.length > 0 && (
        <SectionCard title="Entry Line Items" icon={Package}>
          <div className="rounded-md border overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Line #</TableHead>
                  <TableHead className="font-mono">HTS #</TableHead>
                  <TableHead>Description</TableHead>
                  <TableHead>Origin</TableHead>
                  <TableHead className="text-right">Qty</TableHead>
                  <TableHead className="text-right">Entered Value</TableHead>
                  <TableHead className="text-right">Duty Rate</TableHead>
                  <TableHead className="text-right">Duty Amt</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {lineItems.map((li, i) => (
                  <TableRow key={i}>
                    <TableCell className="tabular-nums">{(li.line_number as number) ?? "\u2014"}</TableCell>
                    <TableCell className="font-mono text-xs">{li.hts_number as string}</TableCell>
                    <TableCell className="font-medium">{li.description as string}</TableCell>
                    <TableCell>{(li.country_of_origin as string) || "\u2014"}</TableCell>
                    <TableCell className="text-right tabular-nums">
                      {li.quantity != null ? `${li.quantity} ${(li.unit as string) || ""}` : "\u2014"}
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      {(li.entered_value as number)?.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      {li.duty_rate != null ? `${((li.duty_rate as number) * 100).toFixed(2)}%` : "\u2014"}
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      {li.duty_amount != null
                        ? (li.duty_amount as number).toLocaleString(undefined, { minimumFractionDigits: 2 })
                        : "\u2014"}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </SectionCard>
      )}

      <SectionCard title="Financial Summary" icon={DollarSign}>
        <motion.div variants={container} initial="hidden" animate="show" className="divide-y">
          <AmountRow label="Total Entered Value" value={data.total_entered_value as number | null} />
          <AmountRow label="Total Duty" value={data.total_duty as number | null} />
          <AmountRow label="Total Tax" value={data.total_tax as number | null} />
          <AmountRow label="Total Other" value={data.total_other as number | null} />
          <TotalRow label="Total Amount" value={data.total_amount as number | null} />
        </motion.div>
      </SectionCard>

      <NotesSection notes={data.notes as string | null} />
    </motion.div>
  );
}

// ---------------------------------------------------------------------------
// Proof of Delivery
// ---------------------------------------------------------------------------

function ProofOfDeliveryView({ data }: { data: Record<string, unknown> }) {
  const items = (data.items as Array<Record<string, unknown>>) || [];

  return (
    <motion.div className="space-y-4" variants={container} initial="hidden" animate="show">
      <SectionCard title="Delivery Details" icon={ClipboardCheck}>
        <motion.div variants={container} initial="hidden" animate="show" className="divide-y">
          <MonoFieldRow label="POD Number" value={data.pod_number as string} />
          <FieldRow label="Delivery Date" value={data.delivery_date as string} />
          <FieldRow label="Delivery Time" value={data.delivery_time as string} />
          <FieldRow label="Carrier" value={data.carrier_name as string} />
          <FieldRow label="Driver" value={data.driver_name as string} />
        </motion.div>
      </SectionCard>

      <SectionCard title="References" icon={FileText}>
        <motion.div variants={container} initial="hidden" animate="show" className="divide-y">
          <MonoFieldRow label="BOL #" value={data.bol_number as string} />
          <MonoFieldRow label="Order #" value={data.order_number as string} />
          <MonoFieldRow label="Tracking #" value={data.tracking_number as string} />
        </motion.div>
      </SectionCard>

      <SectionCard title="Parties" icon={User}>
        <PartiesGrid parties={[
          { label: "Shipper", party: data.shipper as PartyInfo | null },
          { label: "Consignee", party: data.consignee as PartyInfo | null },
        ]} />
      </SectionCard>

      <SectionCard title="Delivery Confirmation" icon={Truck}>
        <motion.div variants={container} initial="hidden" animate="show" className="divide-y">
          <FieldRow label="Delivery Address" value={data.delivery_address as string} />
          <FieldRow label="Receiver" value={data.receiver_name as string} />
          <motion.div variants={item} className="flex justify-between gap-4 py-2">
            <span className="text-sm text-muted-foreground">Signature</span>
            <Badge variant={data.receiver_signature ? "secondary" : "outline"} className="text-xs">
              {data.receiver_signature ? "Signed" : "Not signed"}
            </Badge>
          </motion.div>
          <FieldRow label="Condition" value={data.condition as string} />
          <FieldRow label="Condition Notes" value={data.condition_notes as string} />
          {!!data.has_photo && (
            <motion.div variants={item} className="flex justify-between gap-4 py-2">
              <span className="text-sm text-muted-foreground">Photo</span>
              <Badge variant="secondary" className="text-xs">Photo attached</Badge>
            </motion.div>
          )}
          <MonoFieldRow label="GPS" value={data.gps_coordinates as string} />
          <FieldRow label="Total Packages" value={data.total_packages as number | null} />
          <FieldRow
            label="Total Weight"
            value={data.total_weight != null ? `${data.total_weight} ${(data.weight_unit as string) || ""}` : null}
          />
        </motion.div>
      </SectionCard>

      {items.length > 0 && (
        <SectionCard title="Delivered Items" icon={Package}>
          <div className="rounded-md border overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Description</TableHead>
                  <TableHead className="text-right">Expected</TableHead>
                  <TableHead className="text-right">Delivered</TableHead>
                  <TableHead>Condition</TableHead>
                  <TableHead>Notes</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {items.map((it, i) => (
                  <TableRow key={i}>
                    <TableCell className="font-medium">{it.description as string}</TableCell>
                    <TableCell className="text-right tabular-nums">{(it.quantity_expected as number) ?? "\u2014"}</TableCell>
                    <TableCell className="text-right tabular-nums">{(it.quantity_delivered as number) ?? "\u2014"}</TableCell>
                    <TableCell>{(it.condition as string) || "\u2014"}</TableCell>
                    <TableCell className="text-xs text-muted-foreground">{(it.notes as string) || "\u2014"}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </SectionCard>
      )}

      <NotesSection notes={data.notes as string | null} />
    </motion.div>
  );
}

// ---------------------------------------------------------------------------
// Certificate of Origin
// ---------------------------------------------------------------------------

function CertificateOfOriginView({ data }: { data: Record<string, unknown> }) {
  const items = (data.items as Array<Record<string, unknown>>) || [];

  return (
    <motion.div className="space-y-4" variants={container} initial="hidden" animate="show">
      <SectionCard title="Certificate Details" icon={ShieldCheck}>
        <motion.div variants={container} initial="hidden" animate="show" className="divide-y">
          <MonoFieldRow label="Certificate Number" value={data.certificate_number as string} />
          {!!data.certificate_type && (
            <motion.div variants={item} className="flex justify-between gap-4 py-2">
              <span className="text-sm text-muted-foreground">Type</span>
              <Badge variant="secondary" className="text-xs">{String(data.certificate_type)}</Badge>
            </motion.div>
          )}
          <FieldRow label="Issue Date" value={data.issue_date as string} />
          <FieldRow label="Origin Criterion" value={data.origin_criterion as string} />
          <MonoFieldRow label="Invoice #" value={data.invoice_number as string} />
        </motion.div>
      </SectionCard>

      <SectionCard title="Parties" icon={User}>
        <PartiesGrid parties={[
          { label: "Exporter", party: data.exporter as PartyInfo | null },
          { label: "Producer", party: data.producer as PartyInfo | null },
          { label: "Importer", party: data.importer as PartyInfo | null },
        ]} />
      </SectionCard>

      <SectionCard title="Origin" icon={Globe}>
        <motion.div variants={container} initial="hidden" animate="show" className="divide-y">
          <FieldRow label="Country of Origin" value={data.country_of_origin as string} />
          <FieldRow label="Country of Destination" value={data.country_of_destination as string} />
          <FieldRow label="Transport Details" value={data.transport_details as string} />
          {!!(data.blanket_period_start || data.blanket_period_end) && (
            <motion.div variants={item} className="flex justify-between gap-4 py-2">
              <span className="text-sm text-muted-foreground">Blanket Period</span>
              <span className="text-sm font-medium">
                {(data.blanket_period_start as string) || "?"} \u2014 {(data.blanket_period_end as string) || "?"}
              </span>
            </motion.div>
          )}
        </motion.div>
      </SectionCard>

      {items.length > 0 && (
        <SectionCard title="Items" icon={Package}>
          <div className="rounded-md border overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Description</TableHead>
                  <TableHead className="font-mono">HS Code</TableHead>
                  <TableHead className="text-right">Qty</TableHead>
                  <TableHead>Unit</TableHead>
                  <TableHead>Origin Criterion</TableHead>
                  <TableHead>Country</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {items.map((it, i) => (
                  <TableRow key={i}>
                    <TableCell className="font-medium">{it.description as string}</TableCell>
                    <TableCell className="font-mono text-xs">{(it.hs_code as string) || "\u2014"}</TableCell>
                    <TableCell className="text-right tabular-nums">{(it.quantity as number) ?? "\u2014"}</TableCell>
                    <TableCell>{(it.unit as string) || "\u2014"}</TableCell>
                    <TableCell>{(it.origin_criterion as string) || "\u2014"}</TableCell>
                    <TableCell>{(it.country_of_origin as string) || "\u2014"}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </SectionCard>
      )}

      <SectionCard title="Certification" icon={FileText}>
        <motion.div variants={container} initial="hidden" animate="show" className="divide-y">
          <FieldRow label="Issuing Authority" value={data.issuing_authority as string} />
          <FieldRow label="Certifier Name" value={data.certifier_name as string} />
          <FieldRow label="Certification Date" value={data.certification_date as string} />
        </motion.div>
      </SectionCard>

      <NotesSection notes={data.notes as string | null} />
    </motion.div>
  );
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatLocationInfo(loc: Record<string, unknown> | null): string {
  if (!loc) return "\u2014";
  const parts = [loc.port, loc.city, loc.state, loc.country].filter(Boolean);
  return parts.join(", ") || "\u2014";
}

// ---------------------------------------------------------------------------
// Raw JSON fallback
// ---------------------------------------------------------------------------

function RawJsonView({ data }: { data: Record<string, unknown> }) {
  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
      <pre className="max-h-[600px] overflow-auto rounded-lg border bg-muted/50 p-4 text-xs font-mono">
        {JSON.stringify(data, null, 2)}
      </pre>
    </motion.div>
  );
}

// ---------------------------------------------------------------------------
// Document type renderer registry
// ---------------------------------------------------------------------------

const DOC_TYPE_RENDERERS: Record<string, (data: Record<string, unknown>) => React.JSX.Element> = {
  freight_invoice: (data) => <FreightInvoiceView data={data} />,
  bill_of_lading: (data) => <BillOfLadingView data={data} />,
  commercial_invoice: (data) => <CommercialInvoiceView data={data} />,
  purchase_order: (data) => <PurchaseOrderView data={data} />,
  packing_list: (data) => <PackingListView data={data} />,
  arrival_notice: (data) => <ArrivalNoticeView data={data} />,
  air_waybill: (data) => <AirWaybillView data={data} />,
  debit_credit_note: (data) => <DebitCreditNoteView data={data} />,
  customs_entry: (data) => <CustomsEntryView data={data} />,
  proof_of_delivery: (data) => <ProofOfDeliveryView data={data} />,
  certificate_of_origin: (data) => <CertificateOfOriginView data={data} />,
};

// ---------------------------------------------------------------------------
// Main export
// ---------------------------------------------------------------------------

export function ExtractionResultView({
  extraction,
}: {
  extraction: ExtractionResponse;
}) {
  const [tab, setTab] = useState<"structured" | "raw">("structured");

  const renderer = DOC_TYPE_RENDERERS[extraction.document_type];

  return (
    <div className="space-y-4">
      {/* Meta badges */}
      <div className="flex flex-wrap gap-2">
        <Badge variant="secondary" className="gap-1">
          <Cpu className="size-3" />
          {extraction.model_used}
        </Badge>
        {extraction.processing_time_ms && (
          <Badge variant="outline" className="gap-1">
            <Clock className="size-3" />
            {(extraction.processing_time_ms / 1000).toFixed(1)}s
          </Badge>
        )}
      </div>

      {/* Tab switcher */}
      <div className="flex gap-1 rounded-lg border bg-muted/50 p-1">
        {(["structured", "raw"] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`relative rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
              tab === t
                ? "text-foreground"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            {tab === t && (
              <motion.div
                layoutId="extraction-tab"
                className="absolute inset-0 rounded-md bg-background shadow-sm"
                transition={{ type: "spring", stiffness: 400, damping: 30 }}
              />
            )}
            <span className="relative z-10">
              {t === "structured" ? "Structured Data" : "Raw JSON"}
            </span>
          </button>
        ))}
      </div>

      <Separator />

      {/* Content */}
      {tab === "structured" ? (
        renderer ? (
          renderer(extraction.extraction)
        ) : (
          <RawJsonView data={extraction.extraction} />
        )
      ) : (
        <RawJsonView data={extraction.extraction} />
      )}
    </div>
  );
}

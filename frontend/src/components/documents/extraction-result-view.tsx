"use client";

import { useState } from "react";
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
import type { ExtractionResponse } from "@/types/extraction";

const container = {
  hidden: {},
  show: { transition: { staggerChildren: 0.06 } },
};
const item = {
  hidden: { opacity: 0, y: 8 },
  show: { opacity: 1, y: 0 },
};

function FieldRow({ label, value }: { label: string; value: string | number | null | undefined }) {
  if (value === null || value === undefined || value === "") return null;
  return (
    <motion.div variants={item} className="flex justify-between gap-4 py-2">
      <span className="text-sm text-muted-foreground shrink-0">{label}</span>
      <span className="text-sm font-medium text-right">{String(value)}</span>
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

function FreightInvoiceView({ data }: { data: Record<string, unknown> }) {
  const lineItems = (data.line_items as Array<Record<string, unknown>>) || [];

  return (
    <motion.div
      className="space-y-4"
      variants={container}
      initial="hidden"
      animate="show"
    >
      <SectionCard title="Invoice Details" icon={FileText}>
        <motion.div variants={container} initial="hidden" animate="show" className="divide-y">
          <FieldRow label="Invoice Number" value={data.invoice_number as string} />
          <FieldRow label="Invoice Date" value={data.invoice_date as string} />
          <FieldRow label="Vendor" value={data.vendor_name as string} />
          <FieldRow label="Currency" value={data.currency as string} />
        </motion.div>
      </SectionCard>

      <SectionCard title="Parties & Route" icon={MapPin}>
        <motion.div variants={container} initial="hidden" animate="show" className="divide-y">
          <FieldRow label="Shipper" value={data.shipper_name as string} />
          <FieldRow label="Consignee" value={data.consignee_name as string} />
          {(data.origin || data.destination) && (
            <motion.div variants={item} className="flex items-center gap-2 py-2 text-sm">
              <span className="text-muted-foreground">{(data.origin as string) || "—"}</span>
              <ArrowRight className="size-3 text-muted-foreground" />
              <span className="font-medium">{(data.destination as string) || "—"}</span>
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
                    <TableCell className="font-medium">
                      {li.description as string}
                    </TableCell>
                    <TableCell className="text-right">{li.quantity as number}</TableCell>
                    <TableCell>{li.unit as string}</TableCell>
                    <TableCell className="text-right">
                      {(li.unit_price as number)?.toLocaleString(undefined, {
                        minimumFractionDigits: 2,
                      })}
                    </TableCell>
                    <TableCell className="text-right font-medium">
                      {(li.total as number)?.toLocaleString(undefined, {
                        minimumFractionDigits: 2,
                      })}
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
          <FieldRow label="Subtotal" value={data.subtotal != null ? Number(data.subtotal).toLocaleString(undefined, { minimumFractionDigits: 2 }) : null} />
          <FieldRow label="Tax" value={data.tax_amount != null ? Number(data.tax_amount).toLocaleString(undefined, { minimumFractionDigits: 2 }) : null} />
          <motion.div variants={item} className="flex justify-between gap-4 py-2">
            <span className="text-sm font-semibold">Total Amount</span>
            <span className="text-sm font-bold text-primary">
              {data.currency as string}{" "}
              {data.total_amount != null
                ? Number(data.total_amount).toLocaleString(undefined, {
                    minimumFractionDigits: 2,
                  })
                : "—"}
            </span>
          </motion.div>
        </motion.div>
      </SectionCard>

      {data.notes && (
        <SectionCard title="Notes" icon={FileText}>
          <p className="text-sm text-muted-foreground">{data.notes as string}</p>
        </SectionCard>
      )}
    </motion.div>
  );
}

function BillOfLadingView({ data }: { data: Record<string, unknown> }) {
  const shipper = data.shipper as Record<string, unknown> | null;
  const consignee = data.consignee as Record<string, unknown> | null;
  const origin = data.origin as Record<string, unknown> | null;
  const destination = data.destination as Record<string, unknown> | null;
  const containers = (data.container_numbers as string[]) || [];

  function formatLocation(loc: Record<string, unknown> | null): string {
    if (!loc) return "—";
    const parts = [loc.port, loc.city, loc.state, loc.country].filter(Boolean);
    return parts.join(", ") || "—";
  }

  return (
    <motion.div
      className="space-y-4"
      variants={container}
      initial="hidden"
      animate="show"
    >
      <SectionCard title="BOL Details" icon={FileText}>
        <motion.div variants={container} initial="hidden" animate="show" className="divide-y">
          <FieldRow label="BOL Number" value={data.bol_number as string} />
          <FieldRow label="Issue Date" value={data.issue_date as string} />
          <FieldRow label="Carrier" value={data.carrier_name as string} />
          <FieldRow label="SCAC" value={data.carrier_scac as string} />
          <FieldRow label="Vessel" value={data.vessel_name as string} />
          <FieldRow label="Voyage" value={data.voyage_number as string} />
        </motion.div>
      </SectionCard>

      <SectionCard title="Parties" icon={User}>
        <div className="grid gap-4 sm:grid-cols-2">
          {shipper && (
            <div className="rounded-lg border p-3">
              <p className="mb-1 text-xs font-medium uppercase text-muted-foreground">
                Shipper
              </p>
              <p className="text-sm font-medium">{shipper.name as string}</p>
              {shipper.address && (
                <p className="mt-0.5 text-xs text-muted-foreground">
                  {shipper.address as string}
                </p>
              )}
            </div>
          )}
          {consignee && (
            <div className="rounded-lg border p-3">
              <p className="mb-1 text-xs font-medium uppercase text-muted-foreground">
                Consignee
              </p>
              <p className="text-sm font-medium">{consignee.name as string}</p>
              {consignee.address && (
                <p className="mt-0.5 text-xs text-muted-foreground">
                  {consignee.address as string}
                </p>
              )}
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
            value={
              data.gross_weight != null
                ? `${data.gross_weight} ${(data.weight_unit as string) || ""}`
                : null
            }
          />
          <FieldRow
            label="Volume"
            value={
              data.volume != null
                ? `${data.volume} ${(data.volume_unit as string) || ""}`
                : null
            }
          />
          {containers.length > 0 && (
            <motion.div variants={item} className="py-2">
              <p className="mb-1.5 text-sm text-muted-foreground">Containers</p>
              <div className="flex flex-wrap gap-1.5">
                {containers.map((c) => (
                  <Badge key={c} variant="secondary" className="font-mono text-xs">
                    {c}
                  </Badge>
                ))}
              </div>
            </motion.div>
          )}
        </motion.div>
      </SectionCard>

      <SectionCard title="Freight" icon={DollarSign}>
        <motion.div variants={container} initial="hidden" animate="show" className="divide-y">
          <FieldRow
            label="Charges"
            value={
              data.freight_charges != null
                ? Number(data.freight_charges).toLocaleString(undefined, {
                    minimumFractionDigits: 2,
                  })
                : null
            }
          />
          <FieldRow label="Payment Type" value={data.freight_payment_type as string} />
        </motion.div>
      </SectionCard>

      {(data.special_instructions || data.notes) && (
        <SectionCard title="Notes" icon={FileText}>
          {data.special_instructions && (
            <p className="text-sm text-muted-foreground">
              {data.special_instructions as string}
            </p>
          )}
          {data.notes && (
            <p className="mt-1 text-sm text-muted-foreground">{data.notes as string}</p>
          )}
        </SectionCard>
      )}
    </motion.div>
  );
}

function RawJsonView({ data }: { data: Record<string, unknown> }) {
  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
      <pre className="max-h-[600px] overflow-auto rounded-lg border bg-muted/50 p-4 text-xs font-mono">
        {JSON.stringify(data, null, 2)}
      </pre>
    </motion.div>
  );
}

export function ExtractionResultView({
  extraction,
}: {
  extraction: ExtractionResponse;
}) {
  const [tab, setTab] = useState<"structured" | "raw">("structured");

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
        extraction.document_type === "freight_invoice" ? (
          <FreightInvoiceView data={extraction.extraction} />
        ) : extraction.document_type === "bill_of_lading" ? (
          <BillOfLadingView data={extraction.extraction} />
        ) : (
          <RawJsonView data={extraction.extraction} />
        )
      ) : (
        <RawJsonView data={extraction.extraction} />
      )}
    </div>
  );
}

"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { Check, Info, Pencil, X } from "lucide-react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ConfidenceBar } from "./confidence-bar";
import { overrideLineItem } from "@/lib/api-client";
import type { AllocationLineItem, LineItemStatus } from "@/types/allocation";

const statusConfig: Record<
  LineItemStatus,
  { variant: "default" | "secondary" | "outline"; label: string }
> = {
  auto_approved: { variant: "default", label: "Auto-Approved" },
  needs_review: { variant: "secondary", label: "Needs Review" },
  manually_overridden: { variant: "outline", label: "Overridden" },
};

const listContainer = { hidden: {}, show: { transition: { staggerChildren: 0.03 } } };
const listItem = { hidden: { opacity: 0, x: -8 }, show: { opacity: 1, x: 0 } };

function formatCurrency(amount: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
  }).format(amount);
}

export function AllocationTable({
  lineItems,
  onItemUpdated,
}: {
  lineItems: AllocationLineItem[];
  onItemUpdated?: (updated: AllocationLineItem) => void;
}) {
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editValues, setEditValues] = useState({
    project_code: "",
    cost_center: "",
    gl_account: "",
  });
  const [saving, setSaving] = useState(false);

  const startEdit = (item: AllocationLineItem) => {
    setEditingId(item.id);
    setEditValues({
      project_code: item.override_project_code || item.project_code || "",
      cost_center: item.override_cost_center || item.cost_center || "",
      gl_account: item.override_gl_account || item.gl_account || "",
    });
  };

  const cancelEdit = () => {
    setEditingId(null);
  };

  const saveEdit = async (itemId: string) => {
    setSaving(true);
    try {
      const updated = await overrideLineItem(itemId, editValues);
      onItemUpdated?.(updated);
      setEditingId(null);
    } catch (err) {
      console.error("Failed to save override:", err);
    } finally {
      setSaving(false);
    }
  };

  return (
    <motion.div variants={listContainer} initial="hidden" animate="show">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-8">#</TableHead>
            <TableHead>Description</TableHead>
            <TableHead className="text-right">Amount</TableHead>
            <TableHead>Project Code</TableHead>
            <TableHead>Cost Center</TableHead>
            <TableHead>GL Account</TableHead>
            <TableHead>Confidence</TableHead>
            <TableHead>Status</TableHead>
            <TableHead className="w-10" />
          </TableRow>
        </TableHeader>
        <TableBody>
          {lineItems.map((item) => {
            const status = statusConfig[item.status];
            const isEditing = editingId === item.id;

            return (
              <motion.tr key={item.id} variants={listItem} className="group">
                <TableCell className="text-muted-foreground font-mono text-xs">
                  {item.line_item_index + 1}
                </TableCell>
                <TableCell>
                  <div className="flex items-center gap-1.5">
                    <span className="font-medium max-w-[200px] truncate">
                      {item.description}
                    </span>
                    {item.reasoning && (
                      <span title={item.reasoning} className="cursor-help">
                        <Info className="size-3.5 text-muted-foreground" />
                      </span>
                    )}
                  </div>
                </TableCell>
                <TableCell className="text-right tabular-nums">
                  {formatCurrency(item.amount)}
                </TableCell>

                {/* Project Code */}
                <TableCell>
                  {isEditing ? (
                    <Input
                      className="h-7 text-xs w-36"
                      value={editValues.project_code}
                      onChange={(e) =>
                        setEditValues((v) => ({ ...v, project_code: e.target.value }))
                      }
                    />
                  ) : (
                    <code className="text-xs bg-muted px-1.5 py-0.5 rounded">
                      {item.override_project_code || item.project_code || "—"}
                    </code>
                  )}
                </TableCell>

                {/* Cost Center */}
                <TableCell>
                  {isEditing ? (
                    <Input
                      className="h-7 text-xs w-32"
                      value={editValues.cost_center}
                      onChange={(e) =>
                        setEditValues((v) => ({ ...v, cost_center: e.target.value }))
                      }
                    />
                  ) : (
                    <code className="text-xs bg-muted px-1.5 py-0.5 rounded">
                      {item.override_cost_center || item.cost_center || "—"}
                    </code>
                  )}
                </TableCell>

                {/* GL Account */}
                <TableCell>
                  {isEditing ? (
                    <Input
                      className="h-7 text-xs w-32"
                      value={editValues.gl_account}
                      onChange={(e) =>
                        setEditValues((v) => ({ ...v, gl_account: e.target.value }))
                      }
                    />
                  ) : (
                    <code className="text-xs bg-muted px-1.5 py-0.5 rounded">
                      {item.override_gl_account || item.gl_account || "—"}
                    </code>
                  )}
                </TableCell>

                <TableCell>
                  {item.confidence != null && (
                    <ConfidenceBar confidence={item.confidence} />
                  )}
                </TableCell>

                <TableCell>
                  <Badge variant={status.variant}>{status.label}</Badge>
                </TableCell>

                <TableCell>
                  {isEditing ? (
                    <div className="flex gap-1">
                      <Button
                        size="icon"
                        variant="ghost"
                        className="size-7"
                        disabled={saving}
                        onClick={() => saveEdit(item.id)}
                      >
                        <Check className="size-3.5" />
                      </Button>
                      <Button
                        size="icon"
                        variant="ghost"
                        className="size-7"
                        onClick={cancelEdit}
                      >
                        <X className="size-3.5" />
                      </Button>
                    </div>
                  ) : (
                    item.status === "needs_review" && (
                      <Button
                        size="icon"
                        variant="ghost"
                        className="size-7 opacity-0 group-hover:opacity-100 transition-opacity"
                        onClick={() => startEdit(item)}
                      >
                        <Pencil className="size-3.5" />
                      </Button>
                    )
                  )}
                </TableCell>
              </motion.tr>
            );
          })}
        </TableBody>
      </Table>
    </motion.div>
  );
}

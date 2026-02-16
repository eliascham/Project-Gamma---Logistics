"use client";

import { useEffect, useState, useCallback } from "react";
import { motion } from "framer-motion";
import {
  Database,
  Ship,
  Warehouse,
  FileText,
  DollarSign,
  Search,
  Loader2,
  Sparkles,
  ChevronLeft,
  ChevronRight,
  Package,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { PageTransition } from "@/components/shared/page-transition";
import { EmptyState } from "@/components/shared/empty-state";
import { TableRowSkeleton } from "@/components/shared/loading-skeleton";
import {
  getMcpStats,
  getMcpRecords,
  getMcpBudgets,
  getMcpStatus,
  seedMcpData,
} from "@/lib/api-client";

// ── Types ──

interface MockRecord {
  id: string;
  data_source: string;
  record_type: string | null;
  reference_number: string | null;
  data: Record<string, unknown> | null;
  created_at: string | null;
}

interface MockRecordList {
  items: MockRecord[];
  total: number;
  page: number;
  per_page: number;
}

interface ProjectBudget {
  id: string;
  project_code: string;
  project_name: string | null;
  budget_amount: number;
  spent_amount: number;
  currency: string;
  fiscal_year: number | null;
  cost_center: string | null;
}

interface McpStats {
  total_records: number;
  by_source: Record<string, number>;
  by_record_type: Record<string, number>;
  total_budgets: number;
}

interface McpStatus {
  status: string;
  tools: string[];
  mock_data_seeded: boolean;
  total_mock_records: number;
  total_budgets: number;
}

// ── Config ──

const tabs = [
  { key: "shipments", label: "Shipments", icon: Ship, source: "tms", recordType: "shipment" },
  { key: "inventory", label: "Inventory", icon: Warehouse, source: "wms", recordType: "inventory" },
  { key: "purchase_orders", label: "Purchase Orders", icon: FileText, source: "erp", recordType: "purchase_order" },
  { key: "gl_entries", label: "GL Entries", icon: DollarSign, source: "erp", recordType: "gl_entry" },
  { key: "budgets", label: "Budgets", icon: Package, source: null, recordType: null },
] as const;

type TabKey = (typeof tabs)[number]["key"];

const sourceColors: Record<string, string> = {
  tms: "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300",
  wms: "bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-300",
  erp: "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300",
};

const listContainer = { hidden: {}, show: { transition: { staggerChildren: 0.02 } } };
const listItem = { hidden: { opacity: 0, y: 4 }, show: { opacity: 1, y: 0 } };

// ── Shipment columns ──

function ShipmentRow({ record }: { record: MockRecord }) {
  const d = record.data || {};
  return (
    <motion.tr variants={listItem} className="transition-colors hover:bg-accent/50">
      <TableCell className="font-mono text-xs">{record.reference_number || "—"}</TableCell>
      <TableCell>{(d.origin as string) || "—"}</TableCell>
      <TableCell>{(d.destination as string) || "—"}</TableCell>
      <TableCell>{(d.carrier as string) || "—"}</TableCell>
      <TableCell>{(d.mode as string) || "—"}</TableCell>
      <TableCell className="tabular-nums text-right">
        {d.total_cost != null ? `$${Number(d.total_cost).toLocaleString("en-US", { minimumFractionDigits: 2 })}` : "—"}
      </TableCell>
      <TableCell>
        <Badge variant="outline" className="text-xs">
          {(d.status as string) || "—"}
        </Badge>
      </TableCell>
    </motion.tr>
  );
}

function ShipmentHeaders() {
  return (
    <TableRow>
      <TableHead>Reference</TableHead>
      <TableHead>Origin</TableHead>
      <TableHead>Destination</TableHead>
      <TableHead>Carrier</TableHead>
      <TableHead>Mode</TableHead>
      <TableHead className="text-right">Cost</TableHead>
      <TableHead>Status</TableHead>
    </TableRow>
  );
}

// ── Inventory columns ──

function InventoryRow({ record }: { record: MockRecord }) {
  const d = record.data || {};
  return (
    <motion.tr variants={listItem} className="transition-colors hover:bg-accent/50">
      <TableCell className="font-mono text-xs">{(d.sku as string) || "—"}</TableCell>
      <TableCell>{(d.product_name as string) || "—"}</TableCell>
      <TableCell>{(d.facility as string) || "—"}</TableCell>
      <TableCell className="tabular-nums text-right">{d.quantity != null ? Number(d.quantity).toLocaleString() : "—"}</TableCell>
      <TableCell className="tabular-nums text-right">
        {d.unit_cost != null ? `$${Number(d.unit_cost).toFixed(2)}` : "—"}
      </TableCell>
      <TableCell className="tabular-nums text-right">
        {d.quantity != null && d.unit_cost != null
          ? `$${(Number(d.quantity) * Number(d.unit_cost)).toLocaleString("en-US", { minimumFractionDigits: 2 })}`
          : "—"}
      </TableCell>
    </motion.tr>
  );
}

function InventoryHeaders() {
  return (
    <TableRow>
      <TableHead>SKU</TableHead>
      <TableHead>Product</TableHead>
      <TableHead>Facility</TableHead>
      <TableHead className="text-right">Quantity</TableHead>
      <TableHead className="text-right">Unit Cost</TableHead>
      <TableHead className="text-right">Total Value</TableHead>
    </TableRow>
  );
}

// ── PO columns ──

function PORow({ record }: { record: MockRecord }) {
  const d = record.data || {};
  return (
    <motion.tr variants={listItem} className="transition-colors hover:bg-accent/50">
      <TableCell className="font-mono text-xs">{record.reference_number || "—"}</TableCell>
      <TableCell>{(d.vendor as string) || "—"}</TableCell>
      <TableCell className="tabular-nums text-right">
        {d.total_amount != null ? `$${Number(d.total_amount).toLocaleString("en-US", { minimumFractionDigits: 2 })}` : "—"}
      </TableCell>
      <TableCell>{(d.order_date as string) || "—"}</TableCell>
      <TableCell>
        <Badge variant="outline" className="text-xs">
          {(d.status as string) || "—"}
        </Badge>
      </TableCell>
      <TableCell className="text-xs text-muted-foreground">{(d.project_code as string) || "—"}</TableCell>
    </motion.tr>
  );
}

function POHeaders() {
  return (
    <TableRow>
      <TableHead>PO Number</TableHead>
      <TableHead>Vendor</TableHead>
      <TableHead className="text-right">Amount</TableHead>
      <TableHead>Order Date</TableHead>
      <TableHead>Status</TableHead>
      <TableHead>Project Code</TableHead>
    </TableRow>
  );
}

// ── GL Entry columns ──

function GLRow({ record }: { record: MockRecord }) {
  const d = record.data || {};
  return (
    <motion.tr variants={listItem} className="transition-colors hover:bg-accent/50">
      <TableCell className="font-mono text-xs">{record.reference_number || "—"}</TableCell>
      <TableCell>{(d.gl_account as string) || "—"}</TableCell>
      <TableCell>{(d.description as string) || "—"}</TableCell>
      <TableCell className="tabular-nums text-right">
        {d.debit != null ? `$${Number(d.debit).toLocaleString("en-US", { minimumFractionDigits: 2 })}` : "—"}
      </TableCell>
      <TableCell className="tabular-nums text-right">
        {d.credit != null ? `$${Number(d.credit).toLocaleString("en-US", { minimumFractionDigits: 2 })}` : "—"}
      </TableCell>
      <TableCell className="text-xs text-muted-foreground">{(d.cost_center as string) || "—"}</TableCell>
    </motion.tr>
  );
}

function GLHeaders() {
  return (
    <TableRow>
      <TableHead>Reference</TableHead>
      <TableHead>GL Account</TableHead>
      <TableHead>Description</TableHead>
      <TableHead className="text-right">Debit</TableHead>
      <TableHead className="text-right">Credit</TableHead>
      <TableHead>Cost Center</TableHead>
    </TableRow>
  );
}

// ── Budget row ──

function BudgetRow({ budget }: { budget: ProjectBudget }) {
  const utilization = budget.budget_amount > 0 ? budget.spent_amount / budget.budget_amount : 0;
  const remaining = budget.budget_amount - budget.spent_amount;
  const utilizationPct = Math.round(utilization * 100);
  const barColor =
    utilization >= 0.9 ? "bg-red-500" : utilization >= 0.7 ? "bg-yellow-500" : "bg-green-500";

  return (
    <motion.tr variants={listItem} className="transition-colors hover:bg-accent/50">
      <TableCell>
        <span className="font-mono text-xs font-medium">{budget.project_code}</span>
      </TableCell>
      <TableCell>{budget.project_name || "—"}</TableCell>
      <TableCell className="tabular-nums text-right">
        ${budget.budget_amount.toLocaleString("en-US", { minimumFractionDigits: 2 })}
      </TableCell>
      <TableCell className="tabular-nums text-right">
        ${budget.spent_amount.toLocaleString("en-US", { minimumFractionDigits: 2 })}
      </TableCell>
      <TableCell className="tabular-nums text-right">
        <span className={remaining < 0 ? "text-red-600 dark:text-red-400 font-medium" : ""}>
          ${remaining.toLocaleString("en-US", { minimumFractionDigits: 2 })}
        </span>
      </TableCell>
      <TableCell>
        <div className="flex items-center gap-2 min-w-[120px]">
          <div className="flex-1 h-2 rounded-full bg-muted overflow-hidden">
            <motion.div
              className={`h-full rounded-full ${barColor}`}
              initial={{ width: 0 }}
              animate={{ width: `${Math.min(utilizationPct, 100)}%` }}
              transition={{ duration: 0.8, ease: "easeOut" }}
            />
          </div>
          <span className="text-xs tabular-nums font-medium w-8 text-right">{utilizationPct}%</span>
        </div>
      </TableCell>
      <TableCell className="text-xs text-muted-foreground">{budget.cost_center || "—"}</TableCell>
    </motion.tr>
  );
}

// ── Main Page ──

export default function DataExplorerPage() {
  const [activeTab, setActiveTab] = useState<TabKey>("shipments");
  const [records, setRecords] = useState<MockRecord[]>([]);
  const [budgets, setBudgets] = useState<ProjectBudget[]>([]);
  const [stats, setStats] = useState<McpStats | null>(null);
  const [status, setStatus] = useState<McpStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [seeding, setSeeding] = useState(false);
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const perPage = 25;

  const activeTabConfig = tabs.find((t) => t.key === activeTab)!;

  const loadStats = useCallback(async () => {
    try {
      const [s, st] = await Promise.all([getMcpStats() as Promise<McpStats>, getMcpStatus() as Promise<McpStatus>]);
      setStats(s);
      setStatus(st);
    } catch {
      // ignore
    }
  }, []);

  const loadRecords = useCallback(async () => {
    setLoading(true);
    try {
      if (activeTab === "budgets") {
        const b = (await getMcpBudgets()) as ProjectBudget[];
        setBudgets(b);
        setTotal(b.length);
      } else {
        const tab = tabs.find((t) => t.key === activeTab)!;
        const data = (await getMcpRecords({
          source: tab.source!,
          record_type: tab.recordType!,
          search: search || undefined,
          page,
          per_page: perPage,
        })) as MockRecordList;
        setRecords(data.items);
        setTotal(data.total);
      }
    } catch {
      setRecords([]);
      setBudgets([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }, [activeTab, page, search]);

  useEffect(() => {
    loadStats();
  }, [loadStats]);

  useEffect(() => {
    loadRecords();
  }, [loadRecords]);

  const handleTabChange = (key: TabKey) => {
    setActiveTab(key);
    setPage(1);
    setSearch("");
  };

  const handleSeed = async () => {
    setSeeding(true);
    try {
      await seedMcpData();
      await loadStats();
      await loadRecords();
    } catch {
      // ignore
    } finally {
      setSeeding(false);
    }
  };

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setPage(1);
    loadRecords();
  };

  const totalPages = Math.ceil(total / perPage);

  return (
    <PageTransition>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-2xl font-bold tracking-tight">Data Explorer</h2>
            <p className="text-muted-foreground">
              Browse mock logistics data — shipments, inventory, POs, GL entries & budgets
            </p>
          </div>
          <div className="flex items-center gap-3">
            {status && (
              <Badge variant={status.mock_data_seeded ? "default" : "outline"} className="gap-1.5">
                <Database className="size-3" />
                {status.mock_data_seeded
                  ? `${status.total_mock_records.toLocaleString()} records`
                  : "No data"}
              </Badge>
            )}
            <motion.div whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }}>
              <Button
                variant="outline"
                className="gap-2"
                onClick={handleSeed}
                disabled={seeding}
              >
                {seeding ? <Loader2 className="size-4 animate-spin" /> : <Sparkles className="size-4" />}
                {seeding ? "Seeding..." : "Seed Mock Data"}
              </Button>
            </motion.div>
          </div>
        </div>

        {/* Stats cards */}
        {stats && (
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            {Object.entries(stats.by_source).map(([source, count]) => (
              <div key={source} className="rounded-lg border p-3">
                <div className="flex items-center justify-between">
                  <Badge className={sourceColors[source] || ""}>{source.toUpperCase()}</Badge>
                  <span className="text-lg font-bold tabular-nums">{count.toLocaleString()}</span>
                </div>
              </div>
            ))}
            <div className="rounded-lg border p-3">
              <div className="flex items-center justify-between">
                <Badge variant="secondary">Budgets</Badge>
                <span className="text-lg font-bold tabular-nums">{stats.total_budgets}</span>
              </div>
            </div>
          </div>
        )}

        {/* Tabs */}
        <div className="flex items-center gap-1 border-b">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.key;
            const count =
              tab.key === "budgets"
                ? stats?.total_budgets
                : tab.recordType
                  ? stats?.by_record_type[tab.recordType]
                  : undefined;

            return (
              <button
                key={tab.key}
                onClick={() => handleTabChange(tab.key)}
                className={`relative flex items-center gap-2 px-4 py-2.5 text-sm font-medium transition-colors ${
                  isActive ? "text-foreground" : "text-muted-foreground hover:text-foreground"
                }`}
              >
                <Icon className="size-4" />
                {tab.label}
                {count != null && (
                  <span className="text-xs text-muted-foreground tabular-nums">({count})</span>
                )}
                {isActive && (
                  <motion.div
                    layoutId="data-tab-indicator"
                    className="absolute inset-x-0 -bottom-px h-0.5 bg-primary"
                    transition={{ type: "spring", stiffness: 350, damping: 30 }}
                  />
                )}
              </button>
            );
          })}
        </div>

        {/* Search (not for budgets) */}
        {activeTab !== "budgets" && (
          <form onSubmit={handleSearch} className="flex gap-2 max-w-md">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-muted-foreground" />
              <Input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search by reference number..."
                className="pl-9"
              />
            </div>
            <Button type="submit" variant="secondary" size="sm">
              Search
            </Button>
          </form>
        )}

        {/* Table */}
        {loading ? (
          <TableRowSkeleton rows={8} />
        ) : activeTab === "budgets" ? (
          budgets.length === 0 ? (
            <EmptyState
              icon={Package}
              title="No project budgets"
              description="Seed mock data to populate project budgets."
            />
          ) : (
            <motion.div variants={listContainer} initial="hidden" animate="show">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Project Code</TableHead>
                    <TableHead>Project Name</TableHead>
                    <TableHead className="text-right">Budget</TableHead>
                    <TableHead className="text-right">Spent</TableHead>
                    <TableHead className="text-right">Remaining</TableHead>
                    <TableHead>Utilization</TableHead>
                    <TableHead>Cost Center</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {budgets.map((b) => (
                    <BudgetRow key={b.id} budget={b} />
                  ))}
                </TableBody>
              </Table>
            </motion.div>
          )
        ) : records.length === 0 ? (
          <EmptyState
            icon={activeTabConfig.icon}
            title={`No ${activeTabConfig.label.toLowerCase()} found`}
            description={search ? "Try a different search term." : "Seed mock data to populate records."}
          />
        ) : (
          <>
            <motion.div variants={listContainer} initial="hidden" animate="show">
              <Table>
                <TableHeader>
                  {activeTab === "shipments" && <ShipmentHeaders />}
                  {activeTab === "inventory" && <InventoryHeaders />}
                  {activeTab === "purchase_orders" && <POHeaders />}
                  {activeTab === "gl_entries" && <GLHeaders />}
                </TableHeader>
                <TableBody>
                  {records.map((r) => (
                    <motion.tbody key={r.id}>
                      {activeTab === "shipments" && <ShipmentRow record={r} />}
                      {activeTab === "inventory" && <InventoryRow record={r} />}
                      {activeTab === "purchase_orders" && <PORow record={r} />}
                      {activeTab === "gl_entries" && <GLRow record={r} />}
                    </motion.tbody>
                  ))}
                </TableBody>
              </Table>
            </motion.div>

            {/* Pagination */}
            {totalPages > 1 && (
              <div className="flex items-center justify-between">
                <span className="text-sm text-muted-foreground">
                  Showing {(page - 1) * perPage + 1}–{Math.min(page * perPage, total)} of{" "}
                  {total.toLocaleString()} records
                </span>
                <div className="flex items-center gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setPage((p) => Math.max(1, p - 1))}
                    disabled={page <= 1}
                  >
                    <ChevronLeft className="size-4" />
                  </Button>
                  <span className="text-sm tabular-nums">
                    Page {page} of {totalPages}
                  </span>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                    disabled={page >= totalPages}
                  >
                    <ChevronRight className="size-4" />
                  </Button>
                </div>
              </div>
            )}
          </>
        )}

        {/* MCP Tools info */}
        {status && (
          <div className="rounded-lg border bg-muted/30 p-4">
            <h3 className="text-sm font-medium mb-2 flex items-center gap-2">
              <Database className="size-4" />
              MCP Server Tools
            </h3>
            <p className="text-xs text-muted-foreground mb-3">
              These tools are available to Claude Desktop when connected via MCP.
              The data above is what Claude can query.
            </p>
            <div className="flex flex-wrap gap-2">
              {status.tools.map((tool) => (
                <Badge key={tool} variant="outline" className="font-mono text-xs">
                  {tool}
                </Badge>
              ))}
            </div>
          </div>
        )}
      </div>
    </PageTransition>
  );
}

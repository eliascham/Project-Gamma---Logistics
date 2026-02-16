"use client";

import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Shield,
  Loader2,
  FileText,
  ChevronDown,
  ChevronUp,
  Search,
  Clock,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { AnimatedCard } from "@/components/shared/animated-card";
import { PageTransition } from "@/components/shared/page-transition";
import { EmptyState } from "@/components/shared/empty-state";
import { TableRowSkeleton } from "@/components/shared/loading-skeleton";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface AuditEvent {
  id: string;
  event_type: string;
  entity_type: string;
  entity_id: string;
  actor: string;
  description: string;
  details: Record<string, unknown>;
  created_at: string;
}

const eventTypeColors: Record<string, string> = {
  create: "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300",
  update: "bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300",
  delete: "bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300",
  approve: "bg-emerald-100 text-emerald-700 dark:bg-emerald-900 dark:text-emerald-300",
  reject: "bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300",
  escalate: "bg-orange-100 text-orange-700 dark:bg-orange-900 dark:text-orange-300",
  resolve: "bg-teal-100 text-teal-700 dark:bg-teal-900 dark:text-teal-300",
  extract: "bg-purple-100 text-purple-700 dark:bg-purple-900 dark:text-purple-300",
  allocate: "bg-indigo-100 text-indigo-700 dark:bg-indigo-900 dark:text-indigo-300",
  scan: "bg-amber-100 text-amber-700 dark:bg-amber-900 dark:text-amber-300",
};

const listContainer = { hidden: {}, show: { transition: { staggerChildren: 0.04 } } };
const listItem = {
  hidden: { opacity: 0, y: 10 },
  show: { opacity: 1, y: 0 },
};

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function formatTime(dateStr: string): string {
  return new Date(dateStr).toLocaleTimeString("en-US", {
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function AuditPage() {
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [entityTypeFilter, setEntityTypeFilter] = useState("");
  const [eventTypeFilter, setEventTypeFilter] = useState("");
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadEvents = async () => {
    try {
      const params = new URLSearchParams();
      if (entityTypeFilter) params.set("entity_type", entityTypeFilter);
      if (eventTypeFilter) params.set("event_type", eventTypeFilter);
      const qs = params.toString();
      const res = await fetch(
        `${API_BASE}/api/v1/audit/events${qs ? `?${qs}` : ""}`
      );
      if (res.ok) {
        const data = await res.json();
        setEvents(data.events || []);
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load audit events");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadEvents();
  }, []);

  const handleFilter = () => {
    setLoading(true);
    loadEvents();
  };

  const handleGenerateReport = async () => {
    setGenerating(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/api/v1/audit/reports`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ include_summary: true }),
      });
      if (!res.ok) {
        const detail = await res.text();
        throw new Error(detail || "Report generation failed");
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `audit-report-${new Date().toISOString().slice(0, 10)}.json`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Report generation failed");
    } finally {
      setGenerating(false);
    }
  };

  const toggleExpanded = (id: string) => {
    setExpandedId(expandedId === id ? null : id);
  };

  // Group events by date for timeline
  const groupedEvents = events.reduce<Record<string, AuditEvent[]>>((acc, event) => {
    const date = new Date(event.created_at).toLocaleDateString("en-US", {
      month: "long",
      day: "numeric",
      year: "numeric",
    });
    if (!acc[date]) acc[date] = [];
    acc[date].push(event);
    return acc;
  }, {});

  return (
    <PageTransition>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-2xl font-bold tracking-tight">Audit Log</h2>
            <p className="text-muted-foreground">
              Complete trail of all system events and actions
            </p>
          </div>
          <motion.div whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }}>
            <Button
              variant="outline"
              className="gap-2"
              onClick={handleGenerateReport}
              disabled={generating}
            >
              {generating ? (
                <Loader2 className="size-4 animate-spin" />
              ) : (
                <FileText className="size-4" />
              )}
              Generate Audit Report
            </Button>
          </motion.div>
        </div>

        {/* Filters */}
        <AnimatedCard delay={0.05}>
          <CardContent className="pt-6">
            <div className="flex items-end gap-3">
              <div className="flex-1 space-y-1.5">
                <label className="text-sm font-medium text-muted-foreground">
                  Entity Type
                </label>
                <Input
                  placeholder="e.g. document, allocation, anomaly..."
                  value={entityTypeFilter}
                  onChange={(e) => setEntityTypeFilter(e.target.value)}
                />
              </div>
              <div className="flex-1 space-y-1.5">
                <label className="text-sm font-medium text-muted-foreground">
                  Event Type
                </label>
                <Input
                  placeholder="e.g. create, approve, extract..."
                  value={eventTypeFilter}
                  onChange={(e) => setEventTypeFilter(e.target.value)}
                />
              </div>
              <motion.div whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }}>
                <Button className="gap-2" onClick={handleFilter}>
                  <Search className="size-4" />
                  Filter
                </Button>
              </motion.div>
            </div>
          </CardContent>
        </AnimatedCard>

        {error && (
          <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive">
            {error}
          </div>
        )}

        {/* Timeline */}
        {loading ? (
          <TableRowSkeleton rows={6} />
        ) : events.length === 0 ? (
          <EmptyState
            icon={Shield}
            title="No audit events"
            description="System events will appear here as actions are performed across the platform."
          />
        ) : (
          <motion.div
            variants={listContainer}
            initial="hidden"
            animate="show"
            className="space-y-8"
          >
            {Object.entries(groupedEvents).map(([date, dateEvents]) => (
              <div key={date}>
                <h3 className="text-sm font-semibold text-muted-foreground mb-4">
                  {date}
                </h3>
                <div className="relative space-y-0">
                  {/* Vertical timeline line */}
                  <div className="absolute left-[15px] top-2 bottom-2 w-px bg-border" />

                  {dateEvents.map((event) => {
                    const colorClass =
                      eventTypeColors[event.event_type] ||
                      "bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300";
                    const isExpanded = expandedId === event.id;
                    const hasDetails =
                      event.details && Object.keys(event.details).length > 0;

                    return (
                      <motion.div
                        key={event.id}
                        variants={listItem}
                        className="relative pl-10 pb-4"
                      >
                        {/* Timeline dot */}
                        <div className="absolute left-[10px] top-2.5 size-[11px] rounded-full border-2 border-background bg-border z-10" />

                        <div
                          className={`rounded-lg border p-4 transition-colors ${
                            hasDetails ? "cursor-pointer hover:bg-accent/50" : ""
                          }`}
                          onClick={() => hasDetails && toggleExpanded(event.id)}
                        >
                          <div className="flex items-start justify-between gap-3">
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center gap-2 flex-wrap">
                                <Badge
                                  variant="secondary"
                                  className={colorClass}
                                >
                                  {event.event_type}
                                </Badge>
                                <span className="text-xs text-muted-foreground font-mono">
                                  {event.entity_type}/{event.entity_id.slice(0, 8)}
                                </span>
                              </div>
                              <p className="mt-1.5 text-sm">
                                {event.description}
                              </p>
                              <div className="mt-1.5 flex items-center gap-3 text-xs text-muted-foreground">
                                <span className="flex items-center gap-1">
                                  <Clock className="size-3" />
                                  {formatTime(event.created_at)}
                                </span>
                                <span>by {event.actor}</span>
                              </div>
                            </div>
                            {hasDetails && (
                              <Button
                                variant="ghost"
                                size="icon"
                                className="size-7 shrink-0"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  toggleExpanded(event.id);
                                }}
                              >
                                {isExpanded ? (
                                  <ChevronUp className="size-4" />
                                ) : (
                                  <ChevronDown className="size-4" />
                                )}
                              </Button>
                            )}
                          </div>

                          {/* Expandable details */}
                          <AnimatePresence>
                            {isExpanded && hasDetails && (
                              <motion.div
                                initial={{ height: 0, opacity: 0 }}
                                animate={{ height: "auto", opacity: 1 }}
                                exit={{ height: 0, opacity: 0 }}
                                transition={{ duration: 0.2 }}
                                className="overflow-hidden"
                              >
                                <pre className="mt-3 rounded-md bg-muted p-3 text-xs font-mono overflow-x-auto">
                                  {JSON.stringify(event.details, null, 2)}
                                </pre>
                              </motion.div>
                            )}
                          </AnimatePresence>
                        </div>
                      </motion.div>
                    );
                  })}
                </div>
              </div>
            ))}
          </motion.div>
        )}
      </div>
    </PageTransition>
  );
}

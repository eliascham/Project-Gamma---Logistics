"use client";

import { useState } from "react";
import { ChevronDown, ChevronRight, FileText } from "lucide-react";
import { cn } from "@/lib/utils";
import type { SourceChunk } from "@/types/rag";

export function SourceCitation({ sources }: { sources: SourceChunk[] }) {
  const [expanded, setExpanded] = useState(false);

  if (sources.length === 0) return null;

  return (
    <div className="mt-2">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
      >
        {expanded ? (
          <ChevronDown className="size-3" />
        ) : (
          <ChevronRight className="size-3" />
        )}
        {sources.length} source{sources.length > 1 ? "s" : ""}
      </button>

      {expanded && (
        <div className="mt-2 space-y-2">
          {sources.map((source, idx) => (
            <div
              key={idx}
              className="rounded-md border bg-muted/50 p-3 text-xs"
            >
              <div className="flex items-center justify-between mb-1.5">
                <div className="flex items-center gap-1.5 font-medium">
                  <FileText className="size-3" />
                  Source {idx + 1}
                  {source.document_id && (
                    <span className="text-muted-foreground font-normal">
                      {source.document_id.slice(0, 8)}...
                    </span>
                  )}
                </div>
                <span
                  className={cn(
                    "tabular-nums font-medium",
                    source.similarity >= 0.85
                      ? "text-emerald-600 dark:text-emerald-400"
                      : source.similarity >= 0.7
                        ? "text-amber-600 dark:text-amber-400"
                        : "text-muted-foreground"
                  )}
                >
                  {Math.round(source.similarity * 100)}% match
                </span>
              </div>
              <p className="text-muted-foreground leading-relaxed whitespace-pre-wrap">
                {source.content}
              </p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

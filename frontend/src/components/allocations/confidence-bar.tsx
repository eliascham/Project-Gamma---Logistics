"use client";

import { cn } from "@/lib/utils";

/**
 * Visual confidence indicator for cost allocation line items.
 * Green (≥85%): auto-approved, high confidence
 * Amber (70-84%): needs review, medium confidence
 * Red (<70%): low confidence, likely incorrect
 */
export function ConfidenceBar({
  confidence,
  className,
}: {
  confidence: number;
  className?: string;
}) {
  const percent = Math.round(confidence * 100);

  const color =
    percent >= 85
      ? "bg-emerald-500"
      : percent >= 70
        ? "bg-amber-500"
        : "bg-red-500";

  const textColor =
    percent >= 85
      ? "text-emerald-600 dark:text-emerald-400"
      : percent >= 70
        ? "text-amber-600 dark:text-amber-400"
        : "text-red-600 dark:text-red-400";

  return (
    <div className={cn("flex items-center gap-2", className)}>
      <div className="h-2 w-16 rounded-full bg-muted overflow-hidden">
        <div
          className={cn("h-full rounded-full transition-all", color)}
          style={{ width: `${percent}%` }}
        />
      </div>
      <span className={cn("text-xs font-medium tabular-nums", textColor)}>
        {percent}%
      </span>
    </div>
  );
}

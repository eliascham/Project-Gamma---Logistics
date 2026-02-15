"use client";

import { motion } from "framer-motion";
import { CheckCircle2, XCircle, Loader2, Circle } from "lucide-react";

const statusSteps = [
  { key: "pending", label: "Uploaded", description: "Document received" },
  { key: "processing", label: "Processing", description: "Extraction in progress" },
  { key: "extracted", label: "Extracted", description: "Data extracted successfully" },
];

export function StatusTimeline({ status }: { status: string }) {
  const currentIndex = statusSteps.findIndex((s) => s.key === status);
  const isFailed = status === "failed";

  return (
    <div className="space-y-0">
      {statusSteps.map((step, i) => {
        const isComplete =
          i < currentIndex || (status === "extracted" && i <= currentIndex);
        const isCurrent = i === currentIndex;

        return (
          <div key={step.key} className="flex gap-3">
            <div className="flex flex-col items-center">
              <motion.div
                initial={{ scale: 0 }}
                animate={{ scale: 1 }}
                transition={{ delay: i * 0.15, type: "spring" }}
              >
                {isComplete ? (
                  <CheckCircle2 className="size-5 text-green-500" />
                ) : isFailed && isCurrent ? (
                  <XCircle className="size-5 text-destructive" />
                ) : isCurrent ? (
                  <Loader2 className="size-5 animate-spin text-primary" />
                ) : (
                  <Circle className="size-5 text-muted-foreground/30" />
                )}
              </motion.div>
              {i < statusSteps.length - 1 && (
                <div
                  className={`h-8 w-px ${isComplete ? "bg-green-500" : "bg-muted"}`}
                />
              )}
            </div>
            <div className="pb-6">
              <p
                className={`text-sm font-medium ${
                  isComplete || isCurrent
                    ? "text-foreground"
                    : "text-muted-foreground"
                }`}
              >
                {step.label}
              </p>
              <p className="text-xs text-muted-foreground">
                {isFailed && isCurrent ? "Extraction failed" : step.description}
              </p>
            </div>
          </div>
        );
      })}
    </div>
  );
}

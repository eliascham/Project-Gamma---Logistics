"use client";

import { motion } from "framer-motion";
import { CheckCircle, Loader2 } from "lucide-react";

type Stage = "uploading" | "extracting" | "complete" | "error";

const stages = [
  { label: "Upload", key: "upload" },
  { label: "Parse", key: "parse" },
  { label: "Classify", key: "classify" },
  { label: "Extract", key: "extract" },
  { label: "Review", key: "review" },
];

function getActiveIndex(stage: Stage): number {
  switch (stage) {
    case "uploading":
      return 0;
    case "extracting":
      return 2;
    case "complete":
      return 5;
    case "error":
      return -1;
  }
}

export function PipelineProgress({
  stage,
  progress,
}: {
  stage: Stage;
  progress: number;
}) {
  const activeIndex = getActiveIndex(stage);

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="rounded-xl border bg-card p-6"
    >
      <div className="mb-3 flex items-center justify-between">
        <span className="text-sm font-medium">Pipeline Progress</span>
        {stage === "uploading" && (
          <span className="text-xs text-muted-foreground">{progress}%</span>
        )}
        {stage === "complete" && (
          <span className="text-xs text-green-500">Complete</span>
        )}
      </div>

      <div className="flex items-center justify-between">
        {stages.map((s, i) => {
          const isComplete = i < activeIndex;
          const isCurrent = i === activeIndex;

          return (
            <div key={s.key} className="flex items-center">
              <div className="flex flex-col items-center gap-1.5">
                <motion.div
                  className={`flex size-9 items-center justify-center rounded-full border-2 text-xs font-medium ${
                    isComplete
                      ? "border-green-500 bg-green-500/10 text-green-500"
                      : isCurrent
                        ? "border-primary bg-primary/10 text-primary"
                        : "border-muted bg-muted/50 text-muted-foreground"
                  }`}
                  animate={
                    isCurrent
                      ? { scale: [1, 1.08, 1] }
                      : isComplete
                        ? { scale: 1 }
                        : {}
                  }
                  transition={
                    isCurrent
                      ? { repeat: Infinity, duration: 1.5, ease: "easeInOut" }
                      : {}
                  }
                >
                  {isComplete ? (
                    <CheckCircle className="size-4" />
                  ) : isCurrent ? (
                    <Loader2 className="size-4 animate-spin" />
                  ) : (
                    i + 1
                  )}
                </motion.div>
                <span className="text-[10px] text-muted-foreground">
                  {s.label}
                </span>
              </div>
              {i < stages.length - 1 && (
                <div
                  className={`mx-1 h-0.5 w-6 sm:w-10 ${
                    isComplete ? "bg-green-500" : "bg-muted"
                  }`}
                />
              )}
            </div>
          );
        })}
      </div>
    </motion.div>
  );
}

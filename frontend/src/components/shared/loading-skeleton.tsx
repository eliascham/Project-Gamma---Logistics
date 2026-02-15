"use client";

import { motion } from "framer-motion";
import { Skeleton } from "@/components/ui/skeleton";

export function StatCardSkeleton() {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="space-y-3 rounded-xl border p-6"
    >
      <Skeleton className="h-4 w-24" />
      <Skeleton className="h-8 w-16" />
    </motion.div>
  );
}

export function TableRowSkeleton({ rows = 5 }: { rows?: number }) {
  return (
    <div className="space-y-2">
      {Array.from({ length: rows }).map((_, i) => (
        <motion.div
          key={i}
          initial={{ opacity: 0, x: -10 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: i * 0.05 }}
        >
          <Skeleton className="h-14 w-full rounded-lg" />
        </motion.div>
      ))}
    </div>
  );
}

export function DocumentDetailSkeleton() {
  return (
    <div className="grid gap-6 lg:grid-cols-3">
      <Skeleton className="h-80 rounded-xl" />
      <Skeleton className="h-80 rounded-xl lg:col-span-2" />
    </div>
  );
}

"use client";

import { motion } from "framer-motion";
import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";

export function AnimatedCard({
  className,
  children,
  delay = 0,
  ...props
}: React.ComponentProps<typeof Card> & { delay?: number }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ type: "spring", damping: 20, delay }}
    >
      <Card
        className={cn(className)}
        {...props}
      >
        {children}
      </Card>
    </motion.div>
  );
}

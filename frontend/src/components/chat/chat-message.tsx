"use client";

import { motion } from "framer-motion";
import { Bot, User } from "lucide-react";
import { cn } from "@/lib/utils";
import { SourceCitation } from "./source-citation";
import type { ChatMessage as ChatMessageType } from "@/types/rag";

export function ChatMessage({ message }: { message: ChatMessageType }) {
  const isUser = message.role === "user";

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className={cn("flex gap-3", isUser ? "justify-end" : "justify-start")}
    >
      {!isUser && (
        <div className="flex size-8 shrink-0 items-center justify-center rounded-full bg-primary/10">
          <Bot className="size-4 text-primary" />
        </div>
      )}

      <div
        className={cn(
          "max-w-[80%] rounded-2xl px-4 py-2.5",
          isUser
            ? "bg-primary text-primary-foreground"
            : "bg-muted"
        )}
      >
        <p className="text-sm leading-relaxed whitespace-pre-wrap">
          {message.content}
        </p>

        {!isUser && message.sources && (
          <SourceCitation sources={message.sources} />
        )}
      </div>

      {isUser && (
        <div className="flex size-8 shrink-0 items-center justify-center rounded-full bg-muted">
          <User className="size-4 text-muted-foreground" />
        </div>
      )}
    </motion.div>
  );
}

"use client";

import { useRef, useState } from "react";
import { motion } from "framer-motion";
import { Database, Loader2, MessageSquare, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { PageTransition } from "@/components/shared/page-transition";
import { ChatMessage } from "@/components/chat/chat-message";
import { ChatInput } from "@/components/chat/chat-input";
import { askQuestion, seedRAGData, getRAGStats } from "@/lib/api-client";
import type { ChatMessage as ChatMessageType, RagStats } from "@/types/rag";

const EXAMPLE_QUESTIONS = [
  "What GL account is used for ocean freight?",
  "What are the cost center guidelines for customs brokerage?",
  "How should warehouse storage charges be allocated?",
  "What's the process for handling freight invoices?",
];

export default function ChatPage() {
  const [messages, setMessages] = useState<ChatMessageType[]>([]);
  const [loading, setLoading] = useState(false);
  const [seeding, setSeeding] = useState(false);
  const [stats, setStats] = useState<RagStats | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    setTimeout(() => {
      scrollRef.current?.scrollTo({
        top: scrollRef.current.scrollHeight,
        behavior: "smooth",
      });
    }, 100);
  };

  const handleSend = async (question: string) => {
    // Add user message
    const userMsg: ChatMessageType = {
      role: "user",
      content: question,
      timestamp: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, userMsg]);
    setLoading(true);
    scrollToBottom();

    try {
      const response = await askQuestion(question);

      const assistantMsg: ChatMessageType = {
        role: "assistant",
        content: response.answer,
        sources: response.sources,
        timestamp: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, assistantMsg]);
    } catch (err: unknown) {
      const errorMsg: ChatMessageType = {
        role: "assistant",
        content: `Sorry, something went wrong: ${err instanceof Error ? err.message : "Unknown error"}`,
        timestamp: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setLoading(false);
      scrollToBottom();
    }
  };

  const handleSeedData = async () => {
    setSeeding(true);
    try {
      await seedRAGData();
      const s = await getRAGStats();
      setStats(s);
    } catch (err) {
      console.error("Failed to seed RAG data:", err);
    } finally {
      setSeeding(false);
    }
  };

  const handleLoadStats = async () => {
    try {
      const s = await getRAGStats();
      setStats(s);
    } catch {
      // stats not critical
    }
  };

  // Load stats on first render
  useState(() => {
    handleLoadStats();
  });

  return (
    <PageTransition>
      <div className="flex h-[calc(100vh-8rem)] flex-col">
        {/* Header */}
        <div className="flex items-center justify-between pb-4">
          <div>
            <h2 className="text-2xl font-bold tracking-tight">
              Document Q&A
            </h2>
            <p className="text-muted-foreground">
              Ask questions about your logistics documents
            </p>
          </div>
          <div className="flex items-center gap-3">
            {stats && (
              <div className="flex gap-2">
                <Badge variant="outline" className="gap-1">
                  <Database className="size-3" />
                  {stats.total_embeddings} chunks
                </Badge>
                <Badge variant="outline">
                  {stats.total_documents_ingested} docs
                </Badge>
              </div>
            )}
            <motion.div whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }}>
              <Button
                variant="outline"
                className="gap-2"
                onClick={handleSeedData}
                disabled={seeding}
              >
                {seeding ? (
                  <Loader2 className="size-4 animate-spin" />
                ) : (
                  <Sparkles className="size-4" />
                )}
                Seed Demo Data
              </Button>
            </motion.div>
          </div>
        </div>

        {/* Messages area */}
        <div
          ref={scrollRef}
          className="flex-1 overflow-y-auto rounded-lg border bg-background/50 p-4 space-y-4"
        >
          {messages.length === 0 && !loading && (
            <div className="flex flex-col items-center justify-center h-full text-center">
              <motion.div
                animate={{ y: [0, -6, 0] }}
                transition={{
                  repeat: Infinity,
                  duration: 3,
                  ease: "easeInOut",
                }}
              >
                <MessageSquare className="size-12 text-muted-foreground/40" />
              </motion.div>
              <h3 className="mt-4 text-lg font-semibold">
                Ask anything about your documents
              </h3>
              <p className="mt-1 max-w-sm text-sm text-muted-foreground">
                The AI will search through your uploaded documents and SOPs to
                find relevant answers.
              </p>

              {/* Example question chips */}
              <div className="mt-6 flex flex-wrap justify-center gap-2 max-w-lg">
                {EXAMPLE_QUESTIONS.map((q) => (
                  <motion.button
                    key={q}
                    whileHover={{ scale: 1.02 }}
                    whileTap={{ scale: 0.98 }}
                    onClick={() => handleSend(q)}
                    className="rounded-full border bg-background px-3 py-1.5 text-xs text-muted-foreground hover:text-foreground hover:border-foreground/20 transition-colors"
                  >
                    {q}
                  </motion.button>
                ))}
              </div>
            </div>
          )}

          {messages.map((msg, idx) => (
            <ChatMessage key={idx} message={msg} />
          ))}

          {loading && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="flex items-center gap-2 text-sm text-muted-foreground"
            >
              <Loader2 className="size-4 animate-spin" />
              Searching documents and generating answer...
            </motion.div>
          )}
        </div>

        {/* Input */}
        <div className="pt-4">
          <ChatInput onSend={handleSend} disabled={loading} />
        </div>
      </div>
    </PageTransition>
  );
}

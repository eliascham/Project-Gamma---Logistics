"use client";

import { useState, useRef, type FormEvent } from "react";
import { Send } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export function ChatInput({
  onSend,
  disabled,
}: {
  onSend: (message: string) => void;
  disabled?: boolean;
}) {
  const [value, setValue] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    const trimmed = value.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setValue("");
    inputRef.current?.focus();
  };

  return (
    <form onSubmit={handleSubmit} className="flex gap-2">
      <Input
        ref={inputRef}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder="Ask a question about your documents..."
        disabled={disabled}
        className="flex-1"
      />
      <Button
        type="submit"
        size="icon"
        disabled={disabled || !value.trim()}
      >
        <Send className="size-4" />
      </Button>
    </form>
  );
}

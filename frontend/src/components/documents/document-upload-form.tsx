"use client";

import { useState, useCallback, useRef } from "react";
import { useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import {
  Upload,
  FileText,
  Image,
  FileSpreadsheet,
  X,
  ArrowRight,
} from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { PipelineProgress } from "@/components/documents/pipeline-progress";
import { uploadDocumentWithProgress, triggerExtraction } from "@/lib/api-client";

const ACCEPTED_TYPES = ".pdf,.png,.jpg,.jpeg,.tiff,.tif,.csv";

type UploadStage = "idle" | "uploading" | "extracting" | "complete" | "error";

function getFileIcon(filename: string) {
  const ext = filename.split(".").pop()?.toLowerCase();
  if (ext === "csv") return FileSpreadsheet;
  if (["png", "jpg", "jpeg", "tiff", "tif"].includes(ext || "")) return Image;
  return FileText;
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function DocumentUploadForm() {
  const [file, setFile] = useState<File | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [stage, setStage] = useState<UploadStage>("idle");
  const [uploadProgress, setUploadProgress] = useState(0);
  const [resultId, setResultId] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const router = useRouter();

  const handleDragEnter = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  }, []);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
    const droppedFile = e.dataTransfer.files[0];
    if (droppedFile) setFile(droppedFile);
  }, []);

  const handleFileChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const selected = e.target.files?.[0];
      if (selected) setFile(selected);
    },
    []
  );

  const removeFile = useCallback(() => {
    setFile(null);
    if (inputRef.current) inputRef.current.value = "";
  }, []);

  async function handleUpload() {
    if (!file) return;

    setStage("uploading");
    setUploadProgress(0);

    try {
      const result = await uploadDocumentWithProgress(file, setUploadProgress);
      setResultId(result.id);
      setStage("extracting");
      toast.info("Upload complete. Starting extraction...");

      await triggerExtraction(result.id);
      setStage("complete");
      toast.success("Document extracted successfully!");
    } catch (err) {
      setStage("error");
      toast.error(err instanceof Error ? err.message : "Upload failed");
    }
  }

  function reset() {
    setFile(null);
    setStage("idle");
    setUploadProgress(0);
    setResultId(null);
    if (inputRef.current) inputRef.current.value = "";
  }

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      {/* Drop Zone */}
      {stage === "idle" && (
        <motion.div
          onDragEnter={handleDragEnter}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          onClick={() => !file && inputRef.current?.click()}
          className={`relative flex cursor-pointer flex-col items-center gap-4 rounded-xl border-2 border-dashed p-12 transition-colors ${
            isDragging
              ? "border-primary bg-primary/5"
              : "border-muted-foreground/25 hover:border-primary/50 hover:bg-accent/30"
          }`}
        >
          <motion.div
            animate={isDragging ? { y: -8, scale: 1.1 } : { y: 0, scale: 1 }}
            transition={{ type: "spring", stiffness: 300, damping: 20 }}
          >
            <Upload
              className={`size-10 ${isDragging ? "text-primary" : "text-muted-foreground"}`}
            />
          </motion.div>
          <div className="text-center">
            <p className="text-sm font-medium">
              {isDragging ? "Drop your file here" : "Drag & drop your document here"}
            </p>
            <p className="mt-1 text-xs text-muted-foreground">
              PDF, PNG, JPG, TIFF, CSV up to 50MB
            </p>
          </div>
          {!file && (
            <Button
              variant="outline"
              size="sm"
              onClick={(e) => {
                e.stopPropagation();
                inputRef.current?.click();
              }}
            >
              Browse Files
            </Button>
          )}
          <input
            ref={inputRef}
            type="file"
            className="hidden"
            accept={ACCEPTED_TYPES}
            onChange={handleFileChange}
          />
        </motion.div>
      )}

      {/* File Preview */}
      <AnimatePresence>
        {file && stage === "idle" && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
          >
            <Card>
              <CardContent className="flex items-center justify-between p-4">
                <div className="flex items-center gap-3">
                  {(() => {
                    const Icon = getFileIcon(file.name);
                    return <Icon className="size-8 text-muted-foreground" />;
                  })()}
                  <div>
                    <p className="text-sm font-medium">{file.name}</p>
                    <p className="text-xs text-muted-foreground">
                      {formatFileSize(file.size)}
                    </p>
                  </div>
                </div>
                <Button variant="ghost" size="icon" onClick={removeFile}>
                  <X className="size-4" />
                </Button>
              </CardContent>
            </Card>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Pipeline Progress */}
      <AnimatePresence>
        {stage !== "idle" && (
          <PipelineProgress
            stage={stage as "uploading" | "extracting" | "complete" | "error"}
            progress={uploadProgress}
          />
        )}
      </AnimatePresence>

      {/* Actions */}
      <div className="flex gap-3">
        {stage === "idle" && file && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            whileHover={{ scale: 1.01 }}
            whileTap={{ scale: 0.99 }}
          >
            <Button onClick={handleUpload} className="gap-2">
              <Upload className="size-4" /> Upload & Extract
            </Button>
          </motion.div>
        )}

        {stage === "complete" && resultId && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className="flex gap-3"
          >
            <Button onClick={() => router.push(`/documents/${resultId}`)} className="gap-2">
              View Results <ArrowRight className="size-4" />
            </Button>
            <Button variant="outline" onClick={reset}>
              Upload Another
            </Button>
          </motion.div>
        )}

        {stage === "error" && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
            <Button variant="outline" onClick={reset}>
              Try Again
            </Button>
          </motion.div>
        )}
      </div>
    </div>
  );
}

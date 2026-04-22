"use client";

import { useCallback, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import type { ProcessingStatus } from "@/types/edital";

interface Props {
  status: ProcessingStatus;
  currentFile: string | null;
  onUpload: (file: File) => void;
}

const STATUS_CONFIG = {
  idle:       { label: "Aguardando edital",  color: "text-zinc-500",  dot: "bg-zinc-600"   },
  processing: { label: "Processando...",      color: "text-yellow-400", dot: "bg-yellow-400 animate-pulse" },
  done:       { label: "Extração concluída",  color: "text-green-400",  dot: "bg-green-400"  },
  error:      { label: "Erro na extração",    color: "text-red-400",    dot: "bg-red-500"    },
} as const;

export default function UploadPanel({ status, currentFile, onUpload }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);

  const handleFile = useCallback(
    (file: File | null | undefined) => {
      if (!file || !file.name.toLowerCase().endsWith(".pdf")) return;
      onUpload(file);
    },
    [onUpload]
  );

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragging(false);
      handleFile(e.dataTransfer.files[0]);
    },
    [handleFile]
  );

  const isProcessing = status === "processing";

  return (
    <div className="p-4 border-b border-zinc-800 shrink-0 space-y-3">
      <p className="text-xs font-semibold text-zinc-500 uppercase tracking-widest">
        Upload
      </p>

      {/* Drop zone */}
      <motion.div
        onClick={() => !isProcessing && inputRef.current?.click()}
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        animate={{
          borderColor: dragging
            ? "rgba(74,222,128,0.6)"
            : isProcessing
            ? "rgba(234,179,8,0.4)"
            : "rgba(63,63,70,0.8)",
          boxShadow: dragging
            ? "0 0 20px rgba(74,222,128,0.15)"
            : "none",
        }}
        transition={{ duration: 0.2 }}
        className={`relative flex flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed p-6 cursor-pointer select-none
          ${isProcessing ? "cursor-not-allowed opacity-70" : "hover:border-zinc-500 hover:bg-zinc-900/50"}
        `}
      >
        <AnimatePresence mode="wait">
          {isProcessing ? (
            <motion.div
              key="spinner"
              initial={{ opacity: 0, scale: 0.8 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.8 }}
              className="flex flex-col items-center gap-2"
            >
              <svg
                className="h-7 w-7 text-yellow-400 animate-spin"
                viewBox="0 0 24 24"
                fill="none"
              >
                <circle
                  cx="12" cy="12" r="10"
                  stroke="currentColor" strokeWidth="2"
                  strokeDasharray="32" strokeDashoffset="12"
                />
              </svg>
              <span className="text-xs text-yellow-400 font-mono">Processando...</span>
            </motion.div>
          ) : (
            <motion.div
              key="upload-icon"
              initial={{ opacity: 0, scale: 0.8 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.8 }}
              className="flex flex-col items-center gap-2"
            >
              <svg
                className={`h-7 w-7 transition-colors ${dragging ? "text-green-400" : "text-zinc-500"}`}
                fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}
              >
                <path strokeLinecap="round" strokeLinejoin="round"
                  d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5"
                />
              </svg>
              <span className={`text-xs font-mono transition-colors ${dragging ? "text-green-400" : "text-zinc-500"}`}>
                {dragging ? "Solte aqui" : "Drop PDF ou clique"}
              </span>
            </motion.div>
          )}
        </AnimatePresence>

        <input
          ref={inputRef}
          type="file"
          accept=".pdf"
          className="hidden"
          onChange={(e) => handleFile(e.target.files?.[0])}
        />
      </motion.div>

      {/* Status row */}
      <div className="flex items-center gap-2 px-1">
        <span
          className={`h-1.5 w-1.5 rounded-full shrink-0 ${STATUS_CONFIG[status].dot}`}
        />
        <span className={`text-xs font-mono ${STATUS_CONFIG[status].color}`}>
          {currentFile
            ? `${currentFile} — ${STATUS_CONFIG[status].label}`
            : STATUS_CONFIG[status].label}
        </span>
      </div>
    </div>
  );
}

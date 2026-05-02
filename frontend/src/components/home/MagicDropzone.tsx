"use client";

import { useState } from "react";
import { Upload, Loader2 } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

export default function MagicDropzone() {
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  const handleDrop = async (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    
    const files = Array.from(e.dataTransfer.files);
    const pdf = files.find(f => f.type === "application/pdf");

    if (pdf) {
      simulateUpload();
    }
  };

  const simulateUpload = () => {
    setIsUploading(true);
    // Simulating "Moenda" processing
    setTimeout(() => {
      setIsUploading(false);
    }, 4000);
  };

  return (
    <div
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
      className={`relative overflow-hidden transition-all duration-300 rounded-xl border-2 border-dashed flex flex-col items-center justify-center p-8 text-center cursor-pointer
        ${isDragging 
          ? "border-[var(--primary-teal)] bg-[var(--primary-teal)]/10 scale-[1.02]" 
          : "border-[var(--glass-border-color)] glass hover:border-[var(--primary-teal)]/40 hover:bg-[var(--primary-teal)]/5"
        }`}
    >
      <AnimatePresence mode="wait">
        {isUploading ? (
          <motion.div
            key="uploading"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            className="flex flex-col items-center gap-3"
          >
            <div className="relative">
              <Loader2 className="w-10 h-10 text-[var(--primary-teal)] animate-spin" />
              <motion.div
                animate={{ rotate: 360 }}
                transition={{ duration: 2, repeat: Infinity, ease: "linear" }}
                className="absolute inset-0 rounded-full border-2 border-[var(--primary-teal)] border-t-transparent opacity-30"
              />
            </div>
            <p className="text-sm font-medium text-[var(--primary-teal)] animate-pulse">
              A Moenda está triturando seu edital...
            </p>
            <p className="text-[10px] text-[var(--text-offwhite)]/40">
              O Arquiteto está extraindo o DNA Industrial.
            </p>
          </motion.div>
        ) : (
          <motion.div
            key="idle"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="flex flex-col items-center gap-4"
          >
            <div className={`p-4 rounded-full bg-[var(--primary-teal)]/10 text-[var(--primary-teal)] transition-transform duration-500 ${isDragging ? 'scale-125 rotate-12' : ''}`}>
              <Upload size={32} strokeWidth={1.5} />
            </div>
            <div>
              <p className="text-sm font-semibold text-[var(--text-offwhite)]">
                Não achou seu edital?
              </p>
              <p className="text-xs text-[var(--text-offwhite)]/60 mt-1">
                Solte o PDF aqui e deixe o <span className="text-[var(--primary-teal)] font-bold">Arquiteto</span> fazer a mágica!
              </p>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Industrial aesthetic details */}
      <div className="absolute top-0 right-0 p-2 opacity-10">
        <div className="w-4 h-4 border-t-2 border-r-2 border-[var(--text-offwhite)]" />
      </div>
      <div className="absolute bottom-0 left-0 p-2 opacity-10">
        <div className="w-4 h-4 border-b-2 border-l-2 border-[var(--text-offwhite)]" />
      </div>
    </div>
  );
}

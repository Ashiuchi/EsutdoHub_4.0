'use client';

import React, { useState } from 'react';
import { FileUp, Loader2, CheckCircle2 } from 'lucide-react';

export default function MagicDropzone() {
  const [isUploading, setIsUploading] = useState(false);
  const [isDone, setIsDone] = useState(false);

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsUploading(true);
    // Simulação da Moenda trabalhando
    setTimeout(() => {
      setIsUploading(false);
      setIsDone(true);
      setTimeout(() => setIsDone(false), 3000);
    }, 4000);
  };

  return (
    <div 
      onDragOver={(e) => e.preventDefault()}
      onDrop={handleDrop}
      className="glass rounded-2xl p-8 mb-6 border-2 border-dashed border-[var(--primary-teal)]/30 hover:border-[var(--primary-teal)]/60 transition-all cursor-pointer group relative overflow-hidden"
    >
      <div className="flex flex-col items-center text-center space-y-4">
        {!isUploading && !isDone && (
          <>
            <div className="p-4 bg-[var(--primary-teal)]/10 rounded-full group-hover:scale-110 transition-transform">
              <FileUp size={32} className="text-[var(--primary-teal)]" />
            </div>
            <div>
              <h3 className="text-lg font-semibold text-[var(--text-offwhite)]">A Caixa Mágica do EstudoHub</h3>
              <p className="text-sm text-[var(--text-offwhite)]/60 max-w-xs mx-auto">
                Não achou seu concurso? Solte o PDF aqui e deixe o <strong>Arquiteto</strong> extrair tudo em segundos!
              </p>
            </div>
          </>
        )}

        {isUploading && (
          <div className="flex flex-col items-center space-y-4 py-4">
            <Loader2 size={40} className="text-[var(--primary-teal)] animate-spin" />
            <p className="text-sm font-medium text-[var(--primary-teal)] animate-pulse">
              A Moenda está processando seu edital...
            </p>
          </div>
        )}

        {isDone && (
          <div className="flex flex-col items-center space-y-4 py-4 animate-in zoom-in duration-300">
            <CheckCircle2 size={40} className="text-green-400" />
            <p className="text-sm font-medium text-green-400">
              Edital processado com sucesso! Veja no seu feed.
            </p>
          </div>
        )}
      </div>
      
      {/* Efeito de brilho ao passar o mouse */}
      <div className="absolute inset-0 bg-gradient-to-r from-transparent via-[var(--primary-teal)]/5 to-transparent -translate-x-full group-hover:translate-x-full transition-transform duration-1000" />
    </div>
  );
}

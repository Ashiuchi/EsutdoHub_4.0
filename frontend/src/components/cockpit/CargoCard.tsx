"use client";

import { motion } from "framer-motion";
import type { Cargo } from "@/types/edital";

interface Props {
  cargo: Cargo;
  onClick: (cargo: Cargo) => void;
  fingerprint?: string;
}

export default function CargoCard({ cargo, onClick, fingerprint }: Props) {
  const totalMaterias = cargo.materias?.length || 0;
  const totalTopicos = cargo.materias?.reduce((a, m) => a + (m.topicos?.length || 0), 0) || 0;

  // DNA Progress calculation (Simplified for 26 fields concept)
  const dnaFields = [
    cargo.salario, cargo.vagas_ac, cargo.vagas_cr, cargo.vagas_total,
    cargo.escolaridade, cargo.area, cargo.jornada, cargo.lotation_cities,
    cargo.atribuicoes, cargo.requisitos, totalMaterias
  ];
  const filledFields = dnaFields.filter(f => f !== 0 && f !== "Pendente" && f !== null).length;
  const dnaProgress = (filledFields / dnaFields.length) * 100;

  return (
    <motion.button
      layout
      initial={{ opacity: 0, y: 16, scale: 0.97 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, scale: 0.95 }}
      transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
      whileHover={{ scale: 1.015, transition: { duration: 0.15 } }}
      whileTap={{ scale: 0.985 }}
      onClick={() => onClick(cargo)}
      className="relative w-full text-left rounded-lg border border-[var(--glass-border-color)] bg-[var(--glass-bg)] backdrop-blur-md p-4 overflow-hidden hover:bg-[var(--nav-hover-bg)] hover:border-[var(--primary-teal)]/40 transition-all focus:outline-none focus:ring-1 focus:ring-[var(--primary-teal)]/50 group"
    >
      {/* DNA Progress: 3px gradient line */}
      <div className="absolute top-0 left-0 right-0 h-[3px] bg-[var(--nav-border)]">
        <motion.div 
          initial={{ width: 0 }}
          animate={{ width: `${dnaProgress}%` }}
          className="h-full bg-gradient-to-r from-[var(--primary-teal)]/40 to-[var(--primary-teal)]"
        />
      </div>

      {/* Status Badge: Absolute Position Tag */}
      <div className="absolute top-4 right-4 flex flex-col items-end gap-1.5">
        <span
          className={`shrink-0 px-2 py-0.5 rounded-full text-[9px] font-bold uppercase tracking-wider border leading-none transition-shadow
            ${cargo.status === "vitaminado"
              ? "text-[var(--primary-teal)] bg-[var(--primary-teal)]/10 border-[var(--primary-teal)]/30 group-hover:shadow-[0_0_12px_rgba(0,127,142,0.2)]"
              : cargo.status === "identificado"
              ? "text-yellow-400 bg-yellow-400/10 border-yellow-400/30"
              : "text-[var(--text-offwhite)]/40 bg-[var(--bg-graphite)] border-[var(--nav-border)]"
            }`}
        >
          {cargo.status}
        </span>
        {cargo.status === "vitaminado" && (
          <div className="flex gap-0.5 pr-1">
             <div className="w-1 h-1 rounded-full bg-[var(--primary-teal)] animate-pulse" />
             <div className="w-1 h-1 rounded-full bg-[var(--primary-teal)]/60" />
             <div className="w-1 h-1 rounded-full bg-[var(--primary-teal)]/30" />
          </div>
        )}
      </div>

      <div className="pr-20 pt-1 mb-4">
        <h3 className="text-sm font-bold text-[var(--text-offwhite)] leading-snug line-clamp-2">
          {cargo.titulo}
        </h3>
        {fingerprint && (
          <span className="text-[9px] font-mono text-[var(--primary-teal)]/40 tracking-tight mt-1 block">
            #{fingerprint.slice(0, 8)}
          </span>
        )}
      </div>

      <div className="flex items-end justify-between">
        <div className="space-y-1.5">
          <p className="text-lg font-mono font-bold text-[var(--primary-teal)] leading-none tracking-tight">
            {cargo.salario.toLocaleString("pt-BR", {
              style: "currency",
              currency: "BRL",
              minimumFractionDigits: 0,
            })}
          </p>
          <div className="flex items-center gap-2">
            <p className="text-[10px] text-[var(--text-offwhite)]/50 font-medium">
              <span className="text-[var(--text-offwhite)]/80 font-semibold">{totalMaterias}</span> matérias · <span className="text-[var(--text-offwhite)]/80 font-semibold">{totalTopicos}</span> tópicos
            </p>
            {cargo.status === "vitaminado" && (
              <span className="text-[10px] text-[var(--text-offwhite)]/20">| {cargo.vagas_ac} AC + {cargo.vagas_cr} CR</span>
            )}
          </div>
        </div>

        <div className="text-right space-y-1">
          {cargo.price > 0 ? (
            <p className="text-xs font-mono font-medium text-[var(--text-offwhite)]/50">
              R$ {cargo.price.toFixed(2)}
            </p>
          ) : (
            <p className="text-[10px] font-mono text-[var(--text-offwhite)]/20 italic">gratuito</p>
          )}
          <p className="text-[10px] text-[var(--text-offwhite)] font-mono font-black uppercase tracking-tighter bg-[var(--text-offwhite)]/5 px-1.5 py-0.5 rounded">
            {cargo.vagas_total} vagas
          </p>
        </div>
      </div>
    </motion.button>
  );
}

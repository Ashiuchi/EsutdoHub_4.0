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
      className="relative w-full text-left rounded-lg border border-zinc-800 bg-zinc-900/80 p-3 overflow-hidden card-shimmer hover:border-zinc-700 transition-colors focus:outline-none focus:ring-1 focus:ring-green-500/50"
    >
      {/* Subtle top accent or DNA progress bar */}
      <div className="absolute top-0 left-0 right-0 h-[2px] bg-zinc-800">
        <motion.div 
          initial={{ width: 0 }}
          animate={{ width: `${dnaProgress}%` }}
          className="h-full bg-green-500 shadow-[0_0_8px_rgba(34,197,94,0.4)]"
        />
      </div>

      <div className="flex items-start justify-between gap-2 mb-2 pt-1">
        <h3 className="text-xs font-semibold text-zinc-200 leading-tight line-clamp-2">
          {cargo.titulo}
        </h3>
        <div className="flex flex-col items-end gap-1">
          <span
            className={`shrink-0 px-1.5 py-0.5 rounded text-[10px] font-mono border leading-none
              ${cargo.status === "vitaminado"
                ? "text-green-400 bg-green-400/10 border-green-400/20 shadow-[0_0_8px_rgba(74,222,128,0.1)]"
                : cargo.status === "identificado"
                ? "text-yellow-400 bg-yellow-400/10 border-yellow-400/20"
                : "text-zinc-400 bg-zinc-800 border-zinc-700"
              }`}
          >
            {cargo.status}
          </span>
          {cargo.status === "vitaminado" && (
            <div className="flex gap-0.5">
               <div className="w-1 h-1 rounded-full bg-green-500 animate-pulse" />
               <div className="w-1 h-1 rounded-full bg-green-500/60" />
               <div className="w-1 h-1 rounded-full bg-green-500/30" />
            </div>
          )}
          {fingerprint && (
            <span className="text-[9px] font-mono text-green-500/40 tracking-tight">
              #{fingerprint.slice(0, 8)}
            </span>
          )}
        </div>
      </div>

      <div className="flex items-end justify-between">
        <div className="space-y-0.5">
          <p className="text-sm font-mono font-semibold text-green-400 leading-none">
            {cargo.salario.toLocaleString("pt-BR", {
              style: "currency",
              currency: "BRL",
              minimumFractionDigits: 0,
            })}
          </p>
          <div className="flex items-center gap-1.5">
            <p className="text-[10px] text-zinc-600 font-mono">
              {totalMaterias} mat. · {totalTopicos} tóp.
            </p>
            {cargo.status === "vitaminado" && (
              <span className="text-[10px] text-zinc-700">| {cargo.vagas_ac} AC + {cargo.vagas_cr} CR</span>
            )}
          </div>
        </div>

        <div className="text-right space-y-0.5">
          {cargo.price > 0 ? (
            <p className="text-xs font-mono text-zinc-400">
              R$ {cargo.price.toFixed(2)}
            </p>
          ) : (
            <p className="text-[10px] font-mono text-zinc-700">gratuito</p>
          )}
          <p className="text-[10px] text-zinc-200 font-mono font-bold">
            {cargo.vagas_total} vagas
          </p>
        </div>
      </div>
    </motion.button>
  );
}

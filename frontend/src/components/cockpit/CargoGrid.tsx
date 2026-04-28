"use client";

import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import type { Cargo } from "@/types/edital";
import CargoCard from "./CargoCard";
import CargoModal from "./CargoModal";

interface Props {
  cargos: Cargo[];
  onCargoClick?: (cargo: Cargo) => void;
  fingerprint?: string;
}

export default function CargoGrid({ cargos, onCargoClick, fingerprint }: Props) {
  const [selectedCargo, setSelectedCargo] = useState<Cargo | null>(null);

  const handleCardClick = (cargo: Cargo) => {
    setSelectedCargo(cargo);
    if (onCargoClick) onCargoClick(cargo);
  };

  return (
    <>
      <div className="flex flex-col flex-1 overflow-hidden">
        {/* Section header */}
        <div className="flex items-center justify-between px-4 py-2.5 border-b border-zinc-800 shrink-0">
          <p className="text-xs font-semibold text-zinc-500 uppercase tracking-widest">
            Cargos Extraídos
          </p>
          <AnimatePresence>
            {cargos.length > 0 && (
              <motion.span
                key="count"
                initial={{ opacity: 0, scale: 0.7 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.7 }}
                className="text-xs font-mono text-green-400 bg-green-400/10 border border-green-400/20 px-2 py-0.5 rounded-full"
              >
                {cargos.length}
              </motion.span>
            )}
          </AnimatePresence>
        </div>

        {/* Cards area */}
        <div className="flex-1 overflow-y-auto p-3 grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-2 content-start">
          <AnimatePresence mode="popLayout">
            {cargos.length === 0 ? (
              <motion.div
                key="empty"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="flex flex-col items-center justify-center h-32 gap-2 text-center"
              >
                <svg
                  className="h-8 w-8 text-zinc-800"
                  fill="none" viewBox="0 0 24 24" stroke="currentColor"
                >
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1}
                    d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                  />
                </svg>
                <p className="text-xs text-zinc-700 font-mono">
                  Nenhum cargo extraído ainda
                </p>
              </motion.div>
            ) : (
              cargos.map((cargo, idx) => (
                <CargoCard
                  key={`${cargo.titulo}-${idx}`}
                  cargo={cargo}
                  onClick={handleCardClick}
                  fingerprint={fingerprint}
                />
              ))
            )}
          </AnimatePresence>
        </div>
      </div>

      {/* Detail modal */}
      <CargoModal
        cargo={selectedCargo}
        onClose={() => setSelectedCargo(null)}
      />
    </>
  );
}

"use client";

import { useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import type { Cargo } from "@/types/edital";

interface Props {
  cargo: Cargo | null;
  onClose: () => void;
}

export default function CargoModal({ cargo, onClose }: Props) {
  // Close on Escape
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onClose]);

  return (
    <AnimatePresence>
      {cargo && (
        <>
          {/* Backdrop */}
          <motion.div
            key="backdrop"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            onClick={onClose}
            className="fixed inset-0 bg-black/70 backdrop-blur-sm z-40"
          />

          {/* Modal */}
          <motion.div
            key="modal"
            initial={{ opacity: 0, y: 40, scale: 0.96 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 40, scale: 0.96 }}
            transition={{ duration: 0.25, ease: [0.16, 1, 0.3, 1] }}
            className="fixed inset-x-4 top-1/2 -translate-y-1/2 z-50 max-w-2xl mx-auto max-h-[80vh] flex flex-col rounded-xl border border-zinc-700 bg-zinc-900 shadow-2xl overflow-hidden"
          >
            {/* Modal header */}
            <div className="flex items-start justify-between gap-4 p-5 border-b border-zinc-800 shrink-0">
              <div>
                <h2 className="font-semibold text-zinc-100 text-base leading-tight">
                  {cargo.titulo}
                </h2>
                <div className="flex items-center gap-3 mt-1.5">
                  <span className="text-xs font-mono text-green-400">
                    R$ {(cargo.salario || 0).toLocaleString("pt-BR", { minimumFractionDigits: 2 })}
                  </span>
                  <StatusBadge status={cargo.status} />
                  {(cargo.price || 0) > 0 && (
                    <span className="text-xs text-zinc-400 font-mono">
                      Acesso: R$ {cargo.price.toFixed(2)}
                    </span>
                  )}
                </div>
              </div>
              <button
                onClick={onClose}
                className="text-zinc-500 hover:text-zinc-300 transition-colors shrink-0 p-1"
                aria-label="Fechar"
              >
                <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            <div className="flex-1 overflow-y-auto px-5 py-4 space-y-6">
              {/* Vagas e Cotas */}
              <section>
                <p className="text-xs font-semibold text-zinc-500 uppercase tracking-widest mb-3">
                  Vagas e Cotas
                </p>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                  <InfoBlock label="Ampla" value={cargo.vagas_ac || 0} />
                  <InfoBlock label="CR" value={cargo.vagas_cr || 0} />
                  <InfoBlock label="PcD" value={cargo.vagas_pcd || 0} />
                  <InfoBlock label="Negros" value={cargo.vagas_negros || 0} />
                  <InfoBlock label="Indígenas" value={cargo.vagas_indigenas || 0} />
                  <InfoBlock label="Trans" value={cargo.vagas_trans || 0} />
                  <InfoBlock label="Total" value={cargo.vagas_total || 0} isHighlight />
                </div>
              </section>

              {/* Localidades e Jornada */}
              <section className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <p className="text-xs font-semibold text-zinc-500 uppercase tracking-widest mb-1.5">
                    Escolaridade e Área
                  </p>
                  <p className="text-sm text-zinc-300">
                    {cargo.escolaridade || "Pendente"} {(cargo.area && cargo.area !== "Pendente") ? `— ${cargo.area}` : ""}
                  </p>
                </div>
                <div>
                  <p className="text-xs font-semibold text-zinc-500 uppercase tracking-widest mb-1.5">
                    Localização e Jornada
                  </p>
                  <p className="text-sm text-zinc-300">
                    {cargo.lotation_cities || "Pendente"} {(cargo.jornada && cargo.jornada !== "Pendente") ? `— ${cargo.jornada}` : ""}
                  </p>
                </div>
              </section>

              {/* Atribuições */}
              {cargo.atribuicoes && cargo.atribuicoes !== "Pendente" && (
                <section>
                  <p className="text-xs font-semibold text-zinc-500 uppercase tracking-widest mb-1.5">
                    Atribuições
                  </p>
                  <p className="text-sm text-zinc-400 leading-relaxed italic">
                    "{cargo.atribuicoes}"
                  </p>
                </section>
              )}

              {/* Requisitos */}
              {cargo.requisitos && (
                <section>
                  <p className="text-xs font-semibold text-zinc-500 uppercase tracking-widest mb-1.5">
                    Requisitos
                  </p>
                  <p className="text-sm text-zinc-400 leading-relaxed">{cargo.requisitos}</p>
                </section>
              )}

              {/* Matérias & Tópicos */}
              <section className="space-y-4">
                <p className="text-xs font-semibold text-zinc-500 uppercase tracking-widest">
                  Conteúdo Programático ({cargo.materias?.length || 0})
                </p>
                {cargo.materias?.map((mat, mi) => (
                  <div key={mi} className="space-y-1.5">
                    <div className="flex items-center gap-2">
                      <span className="h-1 w-1 rounded-full bg-green-400 shrink-0" />
                      <span className="text-sm font-medium text-zinc-200">{mat.nome}</span>
                      {mat.peso && mat.peso !== 1 && (
                        <span className="ml-auto text-xs font-mono text-zinc-600">
                          peso {mat.peso}
                        </span>
                      )}
                    </div>
                    {mat.topicos?.length > 0 && (
                      <ul className="ml-3 space-y-0.5">
                        {mat.topicos.map((top, ti) => (
                          <li
                            key={ti}
                            className="text-xs text-zinc-500 leading-5 flex gap-2"
                          >
                            <span className="text-zinc-700 shrink-0">–</span>
                            <span>{top}</span>
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                ))}
              </section>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}

function StatusBadge({ status }: { status: string }) {
  const color =
    status === "vitaminado"
      ? "text-green-400 bg-green-400/10 border-green-400/20 shadow-[0_0_8px_rgba(74,222,128,0.1)]"
      : status === "identificado"
      ? "text-yellow-400 bg-yellow-400/10 border-yellow-400/20"
      : status === "extraido"
      ? "text-blue-400 bg-blue-400/10 border-blue-400/20"
      : "text-zinc-400 bg-zinc-400/10 border-zinc-400/20";

  return (
    <span className={`px-1.5 py-0.5 rounded text-[10px] font-mono border leading-none ${color}`}>
      {status}
    </span>
  );
}

function InfoBlock({ label, value, isHighlight = false }: { label: string, value: string | number, isHighlight?: boolean }) {
  return (
    <div className={`p-2 rounded border ${isHighlight ? 'bg-green-500/5 border-green-500/20' : 'bg-zinc-800/50 border-zinc-800'}`}>
      <p className="text-[10px] text-zinc-500 uppercase tracking-tighter mb-0.5">{label}</p>
      <p className={`text-sm font-mono ${isHighlight ? 'text-green-400 font-bold' : 'text-zinc-200'}`}>
        {value}
      </p>
    </div>
  );
}

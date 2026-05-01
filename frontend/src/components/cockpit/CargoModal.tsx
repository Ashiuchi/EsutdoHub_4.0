"use client";

import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import type { Cargo } from "@/types/edital";

interface Props {
  cargo: Cargo | null;
  onClose: () => void;
  onAction?: (id: string, action: "vitaminar" | "delete") => void;
}

export default function CargoModal({ cargo, onClose, onAction }: Props) {
  const [deleteArmed, setDeleteArmed] = useState(false);

  // Reset armed state whenever the modal opens on a different cargo
  useEffect(() => {
    setDeleteArmed(false);
  }, [cargo?.id]);

  // Close on Escape; disarm delete on Escape if armed
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        if (deleteArmed) {
          setDeleteArmed(false);
        } else {
          onClose();
        }
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onClose, deleteArmed]);

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
            className="fixed inset-x-4 top-1/2 -translate-y-1/2 z-50 max-w-2xl mx-auto max-h-[80vh] flex flex-col rounded-xl border border-[var(--glass-border-color)] bg-[var(--bg-graphite)] shadow-2xl overflow-hidden backdrop-blur-md"
          >
            {/* Modal header */}
            <div className="flex items-start justify-between gap-4 p-5 border-b border-[var(--nav-border)] shrink-0">
              <div>
                <h2 className="font-semibold text-[var(--text-offwhite)] text-base leading-tight">
                  {cargo.titulo}
                </h2>
                <div className="flex items-center gap-3 mt-1.5">
                  <span className="text-xs font-mono text-[var(--primary-teal)]">
                    R$ {(cargo.salario || 0).toLocaleString("pt-BR", { minimumFractionDigits: 2 })}
                  </span>
                  <StatusBadge status={cargo.status} />
                  {(cargo.price || 0) > 0 && (
                    <span className="text-xs text-[var(--text-offwhite)]/40 font-mono">
                      Acesso: R$ {cargo.price.toFixed(2)}
                    </span>
                  )}
                </div>
              </div>
              {/* Action buttons — only shown when cargo has an id and a handler */}
              {cargo.id && onAction && (
                <div className="flex items-center gap-1 shrink-0">
                  {/* Vitaminar */}
                  <button
                    onClick={() => onAction(cargo.id!, "vitaminar")}
                    className="flex items-center gap-1 px-2 py-1 rounded text-xs font-mono border border-[var(--primary-teal)]/30 text-[var(--primary-teal)]/70 hover:text-[var(--primary-teal)] hover:bg-[var(--primary-teal)]/10 hover:border-[var(--primary-teal)]/60 transition-all"
                    aria-label="Vitaminar cargo"
                    title="Marcar como vitaminado"
                  >
                    <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
                    </svg>
                    <span>Vitaminar</span>
                  </button>

                  {/* Excluir — 2-click armed confirmation */}
                  {deleteArmed ? (
                    <button
                      onClick={() => {
                        setDeleteArmed(false);
                        onAction(cargo.id!, "delete");
                      }}
                      className="flex items-center gap-1 px-2 py-1 rounded text-xs font-mono border border-red-500 text-red-400 bg-red-500/15 shadow-[0_0_8px_rgba(239,68,68,0.3)] animate-pulse transition-all"
                      aria-label="Confirmar exclusão"
                      title="Clique novamente para confirmar a exclusão"
                    >
                      <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
                      </svg>
                      <span>Confirmar?</span>
                    </button>
                  ) : (
                    <button
                      onClick={() => setDeleteArmed(true)}
                      className="flex items-center gap-1 px-2 py-1 rounded text-xs font-mono border border-[var(--nav-border)] text-[var(--text-offwhite)]/40 hover:text-red-400 hover:bg-red-500/10 hover:border-red-500/40 transition-all"
                      aria-label="Excluir cargo"
                      title="Excluir cargo (requer confirmação)"
                    >
                      <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                      </svg>
                      <span>Excluir</span>
                    </button>
                  )}
                </div>
              )}

              <button
                onClick={onClose}
                className="text-[var(--text-offwhite)]/40 hover:text-[var(--primary-teal)] transition-colors shrink-0 p-1"
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
                <p className="text-xs font-semibold text-[var(--text-offwhite)]/40 uppercase tracking-widest mb-3">
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
                  <p className="text-xs font-semibold text-[var(--text-offwhite)]/40 uppercase tracking-widest mb-1.5">
                    Escolaridade e Área
                  </p>
                  <p className="text-sm text-[var(--text-offwhite)]/80">
                    {cargo.escolaridade || "Pendente"} {(cargo.area && cargo.area !== "Pendente") ? `— ${cargo.area}` : ""}
                  </p>
                </div>
                <div>
                  <p className="text-xs font-semibold text-[var(--text-offwhite)]/40 uppercase tracking-widest mb-1.5">
                    Localização e Jornada
                  </p>
                  <p className="text-sm text-[var(--text-offwhite)]/80">
                    {cargo.lotation_cities || "Pendente"} {(cargo.jornada && cargo.jornada !== "Pendente") ? `— ${cargo.jornada}` : ""}
                  </p>
                </div>
              </section>

              {/* Atribuições */}
              {cargo.atribuicoes && cargo.atribuicoes !== "Pendente" && (
                <section>
                  <p className="text-xs font-semibold text-[var(--text-offwhite)]/40 uppercase tracking-widest mb-1.5">
                    Atribuições
                  </p>
                  <p className="text-sm text-[var(--text-offwhite)]/60 leading-relaxed italic">
                    "{cargo.atribuicoes}"
                  </p>
                </section>
              )}

              {/* Requisitos */}
              {cargo.requisitos && (
                <section>
                  <p className="text-xs font-semibold text-[var(--text-offwhite)]/40 uppercase tracking-widest mb-1.5">
                    Requisitos
                  </p>
                  <p className="text-sm text-[var(--text-offwhite)]/60 leading-relaxed">{cargo.requisitos}</p>
                </section>
              )}

              {/* Matérias & Tópicos */}
              <section className="space-y-4">
                <p className="text-xs font-semibold text-[var(--text-offwhite)]/40 uppercase tracking-widest">
                  Conteúdo Programático ({cargo.materias?.length || 0})
                </p>
                {cargo.materias?.map((mat, mi) => (
                  <div key={mi} className="space-y-1.5">
                    <div className="flex items-center gap-2">
                      <span className="h-1 w-1 rounded-full bg-[var(--primary-teal)] shrink-0" />
                      <span className="text-sm font-medium text-[var(--text-offwhite)]/80">{mat.nome}</span>
                      {mat.peso && mat.peso !== 1 && (
                        <span className="ml-auto text-xs font-mono text-[var(--text-offwhite)]/20">
                          peso {mat.peso}
                        </span>
                      )}
                    </div>
                    {mat.topicos?.length > 0 && (
                      <ul className="ml-3 space-y-0.5">
                        {mat.topicos.map((top, ti) => (
                          <li
                            key={ti}
                            className="text-xs text-[var(--text-offwhite)]/40 leading-5 flex gap-2"
                          >
                            <span className="text-[var(--text-offwhite)]/20 shrink-0">–</span>
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
      ? "text-[var(--primary-teal)] bg-[var(--primary-teal)]/10 border-[var(--primary-teal)]/20 shadow-[0_0_8px_rgba(0,127,142,0.1)]"
      : status === "identificado"
        ? "text-yellow-400 bg-yellow-400/10 border-yellow-400/20"
        : status === "extraido"
          ? "text-blue-400 bg-blue-400/10 border-blue-400/20"
          : "text-[var(--text-offwhite)]/40 bg-[var(--text-offwhite)]/5 border-[var(--nav-border)]";

  return (
    <span className={`px-1.5 py-0.5 rounded text-[10px] font-mono border leading-none ${color}`}>
      {status}
    </span>
  );
}

function InfoBlock({ label, value, isHighlight = false }: { label: string, value: string | number, isHighlight?: boolean }) {
  return (
    <div className={`p-2 rounded border ${isHighlight ? 'bg-[var(--primary-teal)]/5 border-[var(--primary-teal)]/20' : 'bg-[var(--bg-graphite)]/50 border-[var(--nav-border)]'}`}>
      <p className="text-[10px] text-[var(--text-offwhite)]/40 uppercase tracking-tighter mb-0.5">{label}</p>
      <p className={`text-sm font-mono ${isHighlight ? 'text-[var(--primary-teal)] font-bold' : 'text-[var(--text-offwhite)]'}`}>
        {value}
      </p>
    </div>
  );
}

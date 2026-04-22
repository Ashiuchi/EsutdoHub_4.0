"use client";

import React from "react";
import type { Cargo, Edital } from "@/types/edital";
import { motion } from "framer-motion";

interface Props {
  cargo: Cargo;
  edital: Partial<Edital>;
}

export default function CargoDNAGrid({ cargo, edital }: Props) {
  const fields = [
    // Financeiro
    { label: "Salário", value: cargo.salario > 0 ? `R$ ${cargo.salario.toLocaleString("pt-BR")}` : null, cat: "Fin" },
    { label: "Taxa Inscr.", value: edital.fee && edital.fee > 0 ? `R$ ${edital.fee.toFixed(2)}` : null, cat: "Fin" },
    { label: "Preço Hub", value: cargo.price > 0 ? `R$ ${cargo.price.toFixed(2)}` : "Grátis", cat: "Fin" },
    
    // Vagas
    { label: "Vagas AC", value: cargo.vagas_ac || null, cat: "Vagas" },
    { label: "Vagas CR", value: cargo.vagas_cr || null, cat: "Vagas" },
    { label: "Vagas PcD", value: cargo.vagas_pcd || null, cat: "Vagas" },
    { label: "Vagas Negro", value: cargo.vagas_negros || null, cat: "Vagas" },
    { label: "Vagas Indíg.", value: cargo.vagas_indigenas || null, cat: "Vagas" },
    { label: "Vagas Trans", value: cargo.vagas_trans || null, cat: "Vagas" },
    { label: "Total Vagas", value: cargo.vagas_total || null, cat: "Vagas", highlight: true },

    // Prazos
    { label: "Início Inscr.", value: (edital.inscription_start && edital.inscription_start !== "Pendente") ? edital.inscription_start : null, cat: "Prazos" },
    { label: "Fim Inscr.", value: (edital.inscription_end && edital.inscription_end !== "Pendente") ? edital.inscription_end : null, cat: "Prazos" },
    { label: "Pagamento", value: (edital.payment_deadline && edital.payment_deadline !== "Pendente") ? edital.payment_deadline : null, cat: "Prazos" },
    { label: "Data Prova", value: (edital.data_prova && edital.data_prova !== "Pendente") ? edital.data_prova : null, cat: "Prazos", highlight: true },

    // Regras / Atributos
    { label: "Escolaridade", value: (cargo.escolaridade && cargo.escolaridade !== "Pendente") ? cargo.escolaridade : null, cat: "Regras" },
    { label: "Área", value: (cargo.area && cargo.area !== "Pendente") ? cargo.area : null, cat: "Regras" },
    { label: "Jornada", value: (cargo.jornada && cargo.jornada !== "Pendente") ? cargo.jornada : null, cat: "Regras" },
    { label: "Cidades Lota.", value: (cargo.lotation_cities && cargo.lotation_cities !== "Pendente") ? cargo.lotation_cities : null, cat: "Regras" },
    { label: "Cidades Prova", value: (edital.exam_cities && edital.exam_cities !== "Pendente") ? edital.exam_cities : null, cat: "Regras" },
    
    // Metadados
    { label: "Órgão", value: (edital.orgao && edital.orgao !== "Aguardando...") ? edital.orgao : null, cat: "Meta" },
    { label: "Banca", value: (edital.banca && edital.banca !== "Detectando...") ? edital.banca : null, cat: "Meta" },
    { label: "Cód. Edital", value: cargo.codigo_edital || null, cat: "Meta" },
    { label: "Status", value: cargo.status, cat: "Meta" },
    { label: "Matérias", value: cargo.materias?.length ? cargo.materias.length : null, cat: "Conteúdo" },
    { label: "Tópicos", value: (cargo.materias || []).reduce((a, m) => a + (m.topicos?.length || 0), 0) || null, cat: "Conteúdo" },
  ];

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-1 p-1 bg-zinc-900/50 rounded-lg border border-zinc-800">
      {fields.map((f, i) => (
        <motion.div
          key={i}
          layout
          className={`p-1.5 rounded flex flex-col gap-0.5 border ${
            f.value 
              ? "bg-green-500/5 border-green-500/20" 
              : "bg-zinc-800/20 border-zinc-800/50 opacity-40"
          }`}
        >
          <div className="flex items-center justify-between gap-1">
            <span className="text-[9px] font-mono text-zinc-500 uppercase truncate">
              {f.label}
            </span>
            {f.value && (
              <span className="w-1.5 h-1.5 rounded-full bg-green-500 shadow-[0_0_4px_rgba(34,197,94,0.6)]" />
            )}
          </div>
          <span className={`text-[10px] font-mono truncate ${
            f.value ? (f.highlight ? "text-green-400 font-bold" : "text-zinc-200") : "text-zinc-600"
          }`}>
            {f.value || "---"}
          </span>
        </motion.div>
      ))}
    </div>
  );
}

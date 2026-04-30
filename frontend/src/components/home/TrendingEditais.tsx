"use client";

import { useEffect, useState } from "react";
import { TrendingUp } from "lucide-react";

interface Edital {
  id: string;
  title: string;
  banca: string;
  orgao: string;
  cargos: Array<{
    titulo: string;
    vagas_total?: number;
  }>;
}

export default function TrendingEditais() {
  const [editais, setEditais] = useState<Edital[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchEditais() {
      try {
        // Using localhost:8000 for browser-side fetching
        const res = await fetch("http://127.0.0.1:8000/api/v1/");
        if (res.ok) {
          const data = await res.json();
          setEditais(data.slice(0, 5)); // Show up to 5 editais
        }
      } catch (error) {
        console.error("Failed to fetch editais:", error);
      } finally {
        setLoading(false);
      }
    }
    fetchEditais();
  }, []);

  if (loading) {
    return (
      <div className="glass rounded-xl p-4 space-y-4 animate-pulse">
        <div className="h-3 w-24 bg-white/10 rounded" />
        <div className="space-y-4">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="space-y-2">
              <div className="h-3 w-full bg-white/10 rounded" />
              <div className="h-2 w-1/2 bg-white/5 rounded" />
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (editais.length === 0) return null;

  return (
    <div className="glass rounded-xl p-4 space-y-4">
      <h2
        className="text-[10px] font-semibold uppercase tracking-widest flex items-center gap-2"
        style={{ color: "var(--text-offwhite)", opacity: 0.5 }}
      >
        <TrendingUp size={13} strokeWidth={2} />
        Editais em Alta
      </h2>
      <ul className="space-y-4">
        {editais.map((e) => {
          const totalVagas = e.cargos.reduce((acc, c) => acc + (c.vagas_total || 0), 0);
          return (
            <li key={e.id} className="group cursor-pointer">
              <p className="text-sm font-medium text-[var(--text-offwhite)] leading-tight group-hover:text-[var(--primary-teal)] transition-colors line-clamp-2">
                {e.title || e.orgao}
              </p>
              <div className="flex items-center gap-2 mt-1.5">
                <span className="text-[10px] px-1.5 py-0.5 rounded bg-[var(--primary-teal)]/15 text-[var(--primary-teal)] font-medium">
                  {e.banca}
                </span>
                <span className="text-[10px] text-[var(--text-offwhite)]/40">
                  {totalVagas > 0 ? `${totalVagas} vagas` : "Vagas a definir"}
                </span>
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

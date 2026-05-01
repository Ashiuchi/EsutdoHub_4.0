"use client";

import { useEffect, useState, useMemo } from "react";
import { Search } from "lucide-react";

interface EditalListItem {
  id: string;
  orgao: string;
  created_at: string | null;
  has_quarantine: boolean;
}

interface EditalSelectorProps {
  onSelect: (id: string) => void;
  activeId: string | null;
}

type FilterType = 'todos' | 'quarentena' | 'concluidos';

export default function EditalSelector({ onSelect, activeId }: EditalSelectorProps) {
  const [items, setItems] = useState<EditalListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState<FilterType>("todos");

  useEffect(() => {
    async function loadList() {
      try {
        const res = await fetch("http://localhost:8000/api/v1/editais/list");
        if (res.ok) {
          const data = await res.json();
          setItems(data);
        }
      } catch (err) {
        console.error("Erro ao carregar lista de editais:", err);
      } finally {
        setLoading(false);
      }
    }
    loadList();
  }, []);

  const filteredItems = useMemo(() => {
    return items.filter((item) => {
      const matchesSearch = item.orgao.toLowerCase().includes(search.toLowerCase());
      const matchesFilter = 
        filter === 'todos' ? true :
        filter === 'quarentena' ? item.has_quarantine :
        !item.has_quarantine; // filter === 'concluidos'
      
      return matchesSearch && matchesFilter;
    });
  }, [items, search, filter]);

  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return "---";
    try {
      const date = new Date(dateStr);
      return date.toLocaleDateString("pt-BR", {
        day: "2-digit",
        month: "short",
        year: "numeric",
      });
    } catch {
      return "---";
    }
  };

  return (
    <div className="w-64 shrink-0 flex flex-col bg-[var(--bg-graphite)]/20 border-r border-[var(--nav-border)] overflow-hidden">
      <div className="p-4 border-b border-[var(--nav-border)] bg-[var(--bg-graphite)]/40">
        <h3 className="text-[10px] font-mono text-[var(--text-offwhite)]/40 uppercase tracking-widest">
          Biblioteca de Editais
        </h3>
      </div>

      {/* Busca e Filtro */}
      <div className="p-3 space-y-3 border-b border-[var(--nav-border)]/30 bg-[var(--bg-graphite)]/10">
        <div className="relative group">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-[var(--text-offwhite)]/20 group-focus-within:text-[var(--primary-teal)] transition-colors" />
          <input
            type="text"
            placeholder="Buscar por órgão..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full bg-[var(--bg-graphite)]/40 border border-[var(--nav-border)]/30 rounded-md py-1.5 pl-8 pr-3 text-[11px] text-[var(--text-offwhite)] placeholder:text-[var(--text-offwhite)]/20 focus:outline-none focus:border-[var(--primary-teal)]/50 focus:ring-1 focus:ring-[var(--primary-teal)]/20 transition-all font-mono"
          />
        </div>

        <div className="flex gap-1">
          <button
            onClick={() => setFilter('todos')}
            className={`flex-1 py-1 px-2 rounded-sm text-[9px] font-mono uppercase tracking-tighter transition-all border ${
              filter === 'todos' 
                ? 'bg-[var(--text-offwhite)]/10 border-[var(--text-offwhite)]/30 text-[var(--text-offwhite)]' 
                : 'bg-transparent border-transparent text-[var(--text-offwhite)]/30 hover:bg-[var(--text-offwhite)]/5'
            }`}
          >
            Todos
          </button>
          <button
            onClick={() => setFilter('quarentena')}
            className={`flex-1 py-1 px-2 rounded-sm text-[9px] font-mono uppercase tracking-tighter transition-all border ${
              filter === 'quarentena' 
                ? 'bg-amber-500/20 border-amber-500/40 text-amber-500' 
                : 'bg-transparent border-transparent text-[var(--text-offwhite)]/30 hover:bg-amber-500/10'
            }`}
          >
            Quarentena
          </button>
          <button
            onClick={() => setFilter('concluidos')}
            className={`flex-1 py-1 px-2 rounded-sm text-[9px] font-mono uppercase tracking-tighter transition-all border ${
              filter === 'concluidos' 
                ? 'bg-[var(--primary-teal)]/20 border-[var(--primary-teal)]/40 text-[var(--primary-teal)]' 
                : 'bg-transparent border-transparent text-[var(--text-offwhite)]/30 hover:bg-[var(--primary-teal)]/10'
            }`}
          >
            OK
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto scrollbar-hide py-2">
        {loading ? (
          <div className="p-4 text-center">
            <div className="inline-block h-4 w-4 border-2 border-[var(--primary-teal)]/30 border-t-[var(--primary-teal)] rounded-full animate-spin" />
          </div>
        ) : filteredItems.length === 0 ? (
          <p className="p-4 text-[10px] text-[var(--text-offwhite)]/20 font-mono italic text-center">
            {search || filter !== 'todos' ? "Nenhum edital encontrado." : "Nenhum edital processado."}
          </p>
        ) : (
          filteredItems.map((item) => (
            <button
              key={item.id}
              onClick={() => onSelect(item.id)}
              className={`w-full text-left px-4 py-3 border-b border-[var(--nav-border)]/50 transition-colors relative group ${activeId === item.id
                  ? "bg-[var(--primary-teal)]/10 border-l-2 border-l-[var(--primary-teal)]"
                  : "hover:bg-[var(--text-offwhite)]/5 border-l-2 border-l-transparent"
                }`}
            >
              <div className="flex items-center justify-between gap-2 mb-1">
                <span className={`text-xs font-semibold truncate ${activeId === item.id ? "text-[var(--primary-teal)]" : "text-[var(--text-offwhite)]/80"
                  }`}>
                  {item.orgao}
                </span>
                {item.has_quarantine && (
                  <span className="shrink-0 h-1.5 w-1.5 rounded-full bg-amber-500 shadow-[0_0_4px_#f59e0b]" title="Contém cargos em quarentena" />
                )}
              </div>

              <div className="flex items-center justify-between">
                <span className="text-[9px] font-mono text-[var(--text-offwhite)]/30 uppercase">
                  {formatDate(item.created_at)}
                </span>
                {activeId === item.id && (
                  <span className="text-[10px] text-[var(--primary-teal)] font-mono animate-pulse">SELECTED</span>
                )}
              </div>
            </button>
          ))
        )}
      </div>
    </div>
  );
}

"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type {
  Cargo,
  ConnectionStatus,
  ProcessingStatus,
  SSELogEvent,
  Edital,
} from "@/types/edital";
import HackerTerminal from "./HackerTerminal";
import UploadPanel from "./UploadPanel";
import CargoGrid from "./CargoGrid";
import CargoDNAGrid from "./CargoDNAGrid";
import EditalSelector from "./EditalSelector";

export interface LogLine {
  id: number;
  message: string;
  level: SSELogEvent["level"];
  ts: string;
}

let _logSeq = 0;

function makeLog(message: string, level: SSELogEvent["level"] = "INFO"): LogLine {
  return {
    id: ++_logSeq,
    message,
    level,
    ts: new Date().toLocaleTimeString("pt-BR", { hour12: false }),
  };
}

const MAX_LOGS = 300;

export default function CockpitDashboard() {
  const [logs, setLogs] = useState<LogLine[]>([]);

  useEffect(() => {
    setLogs([
      makeLog("EstudoHub Pro 4.0 — Cockpit inicializado.", "INFO"),
      makeLog("Aguardando conexão SSE...", "INFO"),
    ]);
  }, []);

  const [cargos, setCargos] = useState<Cargo[]>([]);
  const [selectedCargo, setSelectedCargo] = useState<Cargo | null>(null);
  const [edital, setEdital] = useState<Partial<Edital>>({
    orgao: "Aguardando...",
    banca: "Detectando...",
    status: "idle",
  });
  const [activeEditalId, setActiveEditalId] = useState<string | null>(null);
  const [connStatus, setConnStatus] = useState<ConnectionStatus>("connecting");
  const [procStatus, setProcStatus] = useState<ProcessingStatus>("idle");
  const [currentFile, setCurrentFile] = useState<string | null>(null);

  const pushLog = useCallback((message: string, level: SSELogEvent["level"] = "INFO") => {
    setLogs((prev) => {
      const next = [...prev, makeLog(message, level)];
      return next.length > MAX_LOGS ? next.slice(next.length - MAX_LOGS) : next;
    });
  }, []);

  const loadEditalData = useCallback(async (id: string) => {
    try {
      pushLog(`Carregando edital ${id.slice(0, 8)}...`, "INFO");
      const res = await fetch(`http://localhost:8000/api/v1/editais/${id}`);
      if (res.ok) {
        const data = await res.json();
        setEdital(data);
        if (data.cargos) {
          setCargos(data.cargos);
          if (data.cargos.length > 0) {
            setSelectedCargo(data.cargos[0]);
          }
        }
        pushLog(`Edital ${data.orgao} carregado com sucesso.`, "SUCCESS");
      } else {
        pushLog(`Erro ao carregar edital: ${res.status}`, "ERROR");
      }
    } catch (err) {
      console.error("Erro ao carregar edital:", err);
      pushLog("Erro de conexão ao carregar edital.", "ERROR");
    }
  }, [pushLog]);

  // ── History loading ──────────────────────────────────────────────────
  useEffect(() => {
    async function loadInitial() {
      try {
        const res = await fetch("http://localhost:8000/api/v1/editais/list");
        if (res.ok) {
          const data = await res.json();
          if (Array.isArray(data) && data.length > 0) {
            const latest = data[0];
            setActiveEditalId(latest.id);
            loadEditalData(latest.id);
          }
        }
      } catch (err) {
        console.error("Erro no carregamento inicial:", err);
      }
    }
    loadInitial();
  }, [loadEditalData]);

  // ── SSE connection ──────────────────────────────────────────────────
  const esRef = useRef<EventSource | null>(null);

  useEffect(() => {
    function connect() {
      const es = new EventSource("http://localhost:8000/api/v1/cockpit/stream");
      esRef.current = es;

      es.addEventListener("open", () => {
        setConnStatus("connected");
        pushLog("Stream SSE conectado.", "INFO");
      });

      es.addEventListener("log", (e: MessageEvent) => {
        try {
          const data = JSON.parse(e.data) as { message: string; level: SSELogEvent["level"] };
          pushLog(data.message, data.level);
        } catch {
          pushLog(e.data, "INFO");
        }
      });

      es.addEventListener("data", (e: MessageEvent) => {
        try {
          const event = JSON.parse(e.data);
          
          if (event.type === "data") {
            // Se o evento confirma que o edital foi processado
            if (event.status === "processado") {
              setProcStatus("done");
              pushLog("Processamento finalizado via SSE.", "SUCCESS");
              
              if (event.edital) setEdital(event.edital);
              if (event.cargos) {
                setCargos(event.cargos);
                if (event.cargos.length > 0) setSelectedCargo(event.cargos[0]);
              }
            } else if (event.payload) {
              // Atualização de cargo individual (opcional se o backend enviar)
              const newCargo = event.payload as Cargo;
              setCargos((prev) => {
                const index = prev.findIndex((c) => c.titulo === newCargo.titulo);
                if (index >= 0) {
                  const updated = [...prev];
                  updated[index] = { ...updated[index], ...newCargo };
                  return updated;
                }
                return [...prev, newCargo];
              });
            }
          }
        } catch (err) {
          console.error("Erro no SSE data:", err);
          pushLog("Erro ao parsear evento de dados.", "ERROR");
        }
      });

      es.addEventListener("ping", () => {});
      
      es.onerror = () => {
        setConnStatus("error");
        pushLog("Conexão SSE perdida. Reconectando em 5s...", "WARNING");
        es.close();
        setTimeout(connect, 5000);
      };
    }

    connect();

    return () => {
      esRef.current?.close();
    };
  }, [pushLog]);

  useEffect(() => {
    if (!selectedCargo && cargos.length > 0) {
      setSelectedCargo(cargos[0]);
    }
  }, [cargos, selectedCargo]);

  // ── Upload handler ──────────────────────────────────────────────────
  const handleUpload = useCallback(
    async (file: File) => {
      setCurrentFile(file.name);
      setProcStatus("processing");
      setCargos([]);
      setEdital({ orgao: "Detectando...", banca: "Detectando...", status: "processing" });
      pushLog(`Enviando arquivo: ${file.name}`, "INFO");

      const form = new FormData();
      form.append("file", file);

      try {
        const res = await fetch("http://localhost:8000/api/v1/upload", {
          method: "POST",
          body: form,
        });

        if (!res.ok) {
          const text = await res.text();
          let detail = `HTTP ${res.status}`;
          try {
            const err = JSON.parse(text);
            detail = err.detail || detail;
          } catch {
            detail = text || detail;
          }
          throw new Error(detail);
        }

        const result = await res.json();
        // ATENÇÃO: Não mudamos para 'done' aqui. Esperamos o evento 'data' via SSE.
        pushLog(`Upload aceito. Aguardando processamento via IA...`, "INFO");
        
        if (result.status === "processado") {
           // Se já existia no banco, retorna imediatamente
           setProcStatus("done");
           if (result.edital) setEdital(result.edital);
           if (result.cargos) setCargos(result.cargos);
        }
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : "Falha no upload";
        pushLog(`Erro: ${msg}`, "ERROR");
        setProcStatus("error");
      }
    },
    [pushLog]
  );

  const handleCargoAction = useCallback(
    async (id: string, action: "vitaminar" | "delete") => {
      const target = cargos.find((c) => c.id === id);
      const label = target?.titulo ?? id;

      if (action === "vitaminar") {
        try {
          const res = await fetch(`http://localhost:8000/api/v1/cargos/${id}`, {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ status: "vitaminado" }),
          });
          if (!res.ok) throw new Error(`HTTP ${res.status}`);
          setCargos((prev) =>
            prev.map((c) => (c.id === id ? { ...c, status: "vitaminado" } : c))
          );
          setSelectedCargo((prev) =>
            prev?.id === id ? { ...prev, status: "vitaminado" } : prev
          );
          pushLog(`[AUDITORIA] Cargo '${label}' movido para GOLD.`, "SUCCESS");
        } catch (err) {
          pushLog(`[AUDITORIA] Erro ao vitaminar '${label}': ${err}`, "ERROR");
        }
      } else {
        try {
          const res = await fetch(`http://localhost:8000/api/v1/cargos/${id}`, {
            method: "DELETE",
          });
          if (!res.ok) throw new Error(`HTTP ${res.status}`);
          setCargos((prev) => prev.filter((c) => c.id !== id));
          setSelectedCargo((prev) => (prev?.id === id ? null : prev));
          pushLog(`[EXPURGO] Cargo '${label}' removido.`, "WARNING");
        } catch (err) {
          pushLog(`[EXPURGO] Erro ao remover '${label}': ${err}`, "ERROR");
        }
      }
    },
    [cargos, pushLog]
  );

  const handleSelectEdital = (id: string) => {
    setActiveEditalId(id);
    loadEditalData(id);
  };

  return (
    <div className="flex flex-col h-screen bg-transparent text-[var(--text-offwhite)] overflow-hidden">
      {/* ── Header ─────────────────────────────────────────────────── */}
      <header className="flex items-center justify-between px-6 py-3 bg-[var(--background)]/50 backdrop-blur-sm shrink-0 border-seamless-b">
        <div className="flex items-center gap-3">
          <span className="text-[var(--primary-teal)] font-mono text-sm terminal-glow">▶</span>
          <h1 className="font-semibold text-[var(--text-offwhite)] tracking-tight">
            EstudoHub Pro{" "}
            <span className="text-[var(--text-offwhite)]/40 font-normal">4.0</span>
            <span className="ml-2 text-[var(--text-offwhite)]/20 font-normal">/ Inteligência de Editais</span>
          </h1>
        </div>

        <div className="flex items-center gap-2">
          <span
            className={`h-2 w-2 rounded-full ${
              connStatus === "connected"
                ? "bg-[var(--primary-teal)] shadow-[0_0_6px_var(--primary-teal)]"
                : connStatus === "connecting"
                ? "bg-yellow-400 animate-pulse"
                : "bg-red-500"
            }`}
          />
          <span className="text-xs text-[var(--text-offwhite)]/40 font-mono">
            {connStatus === "connected"
              ? "SSE LIVE"
              : connStatus === "connecting"
              ? "CONECTANDO"
              : "OFFLINE"}
          </span>
        </div>
      </header>

      {/* ── Body grid ──────────────────────────────────────────────── */}
      <div className="flex flex-1 overflow-hidden">
        {/* New Selector Panel */}
        <EditalSelector onSelect={handleSelectEdital} activeId={activeEditalId} />

        {/* Left panel — Grid */}
        <aside className="flex flex-col flex-1 overflow-hidden glass border-seamless-r">
          <UploadPanel
            status={procStatus}
            currentFile={currentFile}
            onUpload={handleUpload}
          />
          
          <div className="px-6 py-4 bg-[var(--bg-graphite)]/30 flex items-center justify-between border-seamless-b">
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <span className="text-[10px] font-mono text-[var(--text-offwhite)]/40 uppercase tracking-widest">Órgão</span>
                <span className="text-sm font-semibold text-[var(--text-offwhite)]/80">{edital.orgao}</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-[10px] font-mono text-[var(--text-offwhite)]/40 uppercase tracking-widest">Banca</span>
                <span className="text-sm text-[var(--text-offwhite)]/60">{edital.banca}</span>
              </div>
            </div>
            
            <div className="text-right space-y-1">
              <div className="flex items-center justify-end gap-2">
                <span className="text-[10px] font-mono text-[var(--text-offwhite)]/40 uppercase tracking-widest">Prova</span>
                <span className="text-sm font-mono text-[var(--primary-teal)]">{edital.data_prova || "Pendente"}</span>
              </div>
              <div className="flex items-center justify-end gap-2">
                <span className="text-[10px] font-mono text-[var(--text-offwhite)]/40 uppercase tracking-widest">Inscrições</span>
                <span className="text-xs text-[var(--text-offwhite)]/40">
                  {edital.inscription_start} — {edital.inscription_end}
                </span>
              </div>
            </div>
          </div>

          <CargoGrid cargos={cargos} onCargoClick={setSelectedCargo} onAction={handleCargoAction} fingerprint={edital.fingerprint} />
        </aside>

        {/* Right panel — Terminal */}
        <main className="flex flex-col w-[380px] shrink-0 overflow-hidden glass">
          <div className="p-4 bg-[var(--bg-graphite)]/50 shrink-0 border-seamless-b">
             <div className="flex items-center justify-between mb-3">
               <h3 className="text-[10px] font-mono text-[var(--text-offwhite)]/40 uppercase tracking-widest flex items-center gap-2">
                  <span className="text-[var(--primary-teal)] animate-pulse">🧬</span> DNA 26 Monitor
               </h3>
               {selectedCargo && (
                 <span className="text-[10px] font-mono text-[var(--primary-teal)]/70 truncate max-w-[180px]">
                   {selectedCargo.titulo}
                 </span>
               )}
             </div>
             
             {selectedCargo ? (
               <CargoDNAGrid cargo={selectedCargo} edital={edital} />
             ) : (
               <div className="h-24 flex items-center justify-center border border-dashed border-seamless-b rounded-lg">
                 <p className="text-[10px] text-[var(--text-offwhite)]/20 font-mono italic text-center px-4">
                   Selecione um cargo para monitorar o DNA
                 </p>
               </div>
             )}
          </div>

          <div className="p-3 bg-[var(--primary-teal)]/5 border-seamless-b">
             <h3 className="text-[10px] font-mono text-[var(--primary-teal)]/70 uppercase tracking-widest mb-2 flex items-center gap-2">
                <span className="relative flex h-2 w-2">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[var(--primary-teal)] opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-[var(--primary-teal)]"></span>
                </span>
                Discovery Monitor
             </h3>
             <div className="space-y-1 max-h-24 overflow-y-auto scrollbar-hide">
                {logs.filter(l => l.message.includes("📌") || l.message.includes("✅") || l.message.includes("SUCCESS")).slice(-3).reverse().map(log => (
                  <div key={log.id} className="text-[10px] font-mono text-[var(--text-offwhite)]/40 border-l border-[var(--primary-teal)]/30 pl-2">
                    {log.message}
                  </div>
                ))}
             </div>
          </div>
          <HackerTerminal logs={logs} connStatus={connStatus} />
        </main>
      </div>
    </div>
  );
}

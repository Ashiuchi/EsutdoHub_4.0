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
  const [connStatus, setConnStatus] = useState<ConnectionStatus>("connecting");
  const [procStatus, setProcStatus] = useState<ProcessingStatus>("idle");
  const [currentFile, setCurrentFile] = useState<string | null>(null);

  const pushLog = useCallback((message: string, level: SSELogEvent["level"] = "INFO") => {
    setLogs((prev) => {
      const next = [...prev, makeLog(message, level)];
      return next.length > MAX_LOGS ? next.slice(next.length - MAX_LOGS) : next;
    });
  }, []);

  // ── SSE connection ──────────────────────────────────────────────────
  const esRef = useRef<EventSource | null>(null);

  useEffect(() => {
    function connect() {
      const es = new EventSource("/api/v1/cockpit/stream");
      esRef.current = es;

      es.addEventListener("open", () => {
        setConnStatus("connected");
        pushLog("Stream SSE conectado.", "INFO");
      });

      es.addEventListener("log", (e: MessageEvent) => {
        try {
          const data = JSON.parse(e.data) as { message: string; level: SSELogEvent["level"] };
          pushLog(data.message, data.level);
          
          // Heurística simples para atualizar metadados do edital via logs se necessário
          if (data.message.includes("📌 Legenda descoberta")) {
            // Pode disparar animações ou efeitos no futuro
          }
        } catch {
          pushLog(e.data, "INFO");
        }
      });

      es.addEventListener("data", (e: MessageEvent) => {
        try {
          const event = JSON.parse(e.data);
          
          if (event.type === "data" && event.payload) {
            const newCargo = event.payload as Cargo;
            setCargos((prev) => {
              const index = prev.findIndex((c) => c.titulo === newCargo.titulo);
              if (index >= 0) {
                const updated = [...prev];
                // Merge properties, keeping old ones if new ones are empty/zero (optional, but let's overwrite for status)
                updated[index] = { ...updated[index], ...newCargo };

                // Update selected cargo if it's the one being updated
                setSelectedCargo(current => 
                  current?.titulo === newCargo.titulo ? updated[index] : current
                );

                return updated;
              }
              return [...prev, newCargo];
            });

            // Auto-select first cargo if nothing is selected
            setSelectedCargo(current => current || newCargo);
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

  // Auto-selecionar primeiro cargo se nenhum estiver selecionado
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
        const res = await fetch("/api/v1/upload", {
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
        if (result.edital) {
          setEdital(result.edital);
        }
        if (result.cargos && result.cargos.length > 0) {
          setCargos(result.cargos);
        }

        pushLog(`Extração concluída com sucesso!`, "INFO");
        setProcStatus("done");
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : "Falha no upload";
        pushLog(`Erro: ${msg}`, "ERROR");
        setProcStatus("error");
      }
    },
    [pushLog]
  );

  return (
    <div className="flex flex-col h-screen bg-zinc-950 text-zinc-100 overflow-hidden">
      {/* ── Header ─────────────────────────────────────────────────── */}
      <header className="flex items-center justify-between px-6 py-3 border-b border-zinc-800 shrink-0">
        <div className="flex items-center gap-3">
          <span className="text-green-400 font-mono text-sm terminal-glow">▶</span>
          <h1 className="font-semibold text-zinc-100 tracking-tight">
            EstudoHub Pro{" "}
            <span className="text-zinc-500 font-normal">4.0</span>
            <span className="ml-2 text-zinc-400 font-normal">/ Cockpit</span>
          </h1>
        </div>

        <div className="flex items-center gap-2">
          <span
            className={`h-2 w-2 rounded-full ${
              connStatus === "connected"
                ? "bg-green-400 shadow-[0_0_6px_rgba(74,222,128,0.8)]"
                : connStatus === "connecting"
                ? "bg-yellow-400 animate-pulse"
                : "bg-red-500"
            }`}
          />
          <span className="text-xs text-zinc-500 font-mono">
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
        {/* Left panel — Grid (larger, grows) */}
        <aside className="flex flex-col flex-1 border-r border-zinc-800 overflow-hidden">
          <UploadPanel
            status={procStatus}
            currentFile={currentFile}
            onUpload={handleUpload}
          />
          
          {/* Metadata Header (DNA 26) */}
          <div className="px-6 py-4 bg-zinc-900/30 border-b border-zinc-800 flex items-center justify-between">
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <span className="text-[10px] font-mono text-zinc-500 uppercase tracking-widest">Órgão</span>
                <span className="text-sm font-semibold text-zinc-200">{edital.orgao}</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-[10px] font-mono text-zinc-500 uppercase tracking-widest">Banca</span>
                <span className="text-sm text-zinc-400">{edital.banca}</span>
              </div>
            </div>
            
            <div className="text-right space-y-1">
              <div className="flex items-center justify-end gap-2">
                <span className="text-[10px] font-mono text-zinc-500 uppercase tracking-widest">Prova</span>
                <span className="text-sm font-mono text-green-400">{edital.data_prova || "Pendente"}</span>
              </div>
              <div className="flex items-center justify-end gap-2">
                <span className="text-[10px] font-mono text-zinc-500 uppercase tracking-widest">Inscrições</span>
                <span className="text-xs text-zinc-500">
                  {edital.inscription_start} — {edital.inscription_end}
                </span>
              </div>
            </div>
          </div>

          <CargoGrid cargos={cargos} onCargoClick={setSelectedCargo} />
        </aside>

        {/* Right panel — Terminal (fixed width) */}
        <main className="flex flex-col w-[380px] shrink-0 border-l border-zinc-800 overflow-hidden">
          {/* DNA Monitor (DNA 26 Live) */}
          <div className="p-4 bg-zinc-900 border-b border-zinc-800 shrink-0">
             <div className="flex items-center justify-between mb-3">
               <h3 className="text-[10px] font-mono text-zinc-400 uppercase tracking-widest flex items-center gap-2">
                  <span className="text-green-500 animate-pulse">🧬</span> DNA 26 Monitor
               </h3>
               {selectedCargo && (
                 <span className="text-[10px] font-mono text-green-500/70 truncate max-w-[180px]">
                   {selectedCargo.titulo}
                 </span>
               )}
             </div>
             
             {selectedCargo ? (
               <CargoDNAGrid cargo={selectedCargo} edital={edital} />
             ) : (
               <div className="h-24 flex items-center justify-center border border-dashed border-zinc-800 rounded-lg">
                 <p className="text-[10px] text-zinc-600 font-mono italic text-center px-4">
                   Selecione um cargo para monitorar o DNA
                 </p>
               </div>
             )}
          </div>

          {/* Discovery Monitor Overlay (Minimalist) */}
          <div className="p-3 bg-green-500/5 border-b border-zinc-800">
             <h3 className="text-[10px] font-mono text-green-500/70 uppercase tracking-widest mb-2 flex items-center gap-2">
                <span className="relative flex h-2 w-2">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-green-500"></span>
                </span>
                Discovery Monitor
             </h3>
             <div className="space-y-1 max-h-24 overflow-y-auto scrollbar-hide">
                {logs.filter(l => l.message.includes("📌") || l.message.includes("✅")).slice(-3).reverse().map(log => (
                  <div key={log.id} className="text-[10px] font-mono text-zinc-400 border-l border-green-500/30 pl-2 animate-in fade-in slide-in-from-left-1">
                    {log.message}
                  </div>
                ))}
                {logs.filter(l => l.message.includes("📌") || l.message.includes("✅")).length === 0 && (
                  <div className="text-[10px] font-mono text-zinc-600 italic">
                    Aguardando descobertas da IA...
                  </div>
                )}
             </div>
          </div>
          <HackerTerminal logs={logs} connStatus={connStatus} />
        </main>
      </div>
    </div>
  );
}

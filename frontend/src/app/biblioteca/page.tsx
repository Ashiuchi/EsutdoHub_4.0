"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Library, Upload, FileText, Brain, Sparkles, CheckCircle2,
  Loader2, ChevronRight, BookOpen, BrainCircuit, X, History,
  Lock, Crown, Zap, AlertCircle,
} from "lucide-react";
import { useAuth, useUser } from "@clerk/nextjs";

/* ── Types ─────────────────────────────────────────────────────────── */
interface Documento {
  id: string;
  filename: string;
  status: string;
  created_at: string;
}

interface TopicoAtomico {
  id: string;
  materia: string;
  topico: string;
  ai_summary: string;
  flashcards: string; // JSON string
}

interface LogLine {
  id: number;
  ts: string;
  level: string;
  message: string;
}

type UserTier = "FREE" | "PREMIUM" | "PLATINUM";

/* ── Constants ──────────────────────────────────────────────────────── */
const API_BASE = "http://localhost:8000/api/v1/biblioteca";
const SSE_URL  = "http://localhost:8000/api/v1/cockpit/stream";

const TIER_CONFIG: Record<UserTier, { label: string; color: string; bg: string; border: string; canProcess: boolean }> = {
  FREE:     { label: "Free",     color: "text-zinc-400",   bg: "bg-zinc-500/10",    border: "border-zinc-500/20",    canProcess: false },
  PREMIUM:  { label: "Premium",  color: "text-amber-400",  bg: "bg-amber-500/10",   border: "border-amber-500/20",   canProcess: true  },
  PLATINUM: { label: "Platinum", color: "text-[#007F8E]",  bg: "bg-[#007F8E]/10",  border: "border-[#007F8E]/25",   canProcess: true  },
};

const LEVEL_COLOR: Record<string, string> = {
  INFO:    "text-green-400",
  WARNING: "text-yellow-400",
  ERROR:   "text-red-400",
  SUCCESS: "text-[#007F8E]",
};

/* ── Helpers ────────────────────────────────────────────────────────── */
function getUserTier(user: ReturnType<typeof useUser>["user"]): UserTier {
  const t = (user?.publicMetadata?.tier as string | undefined)?.toUpperCase();
  if (t === "PLATINUM") return "PLATINUM";
  if (t === "PREMIUM")  return "PREMIUM";
  return "FREE";
}

/* ── Component ──────────────────────────────────────────────────────── */
export default function BibliotecaPage() {
  const { getToken }   = useAuth();
  const { user }       = useUser();
  const tier           = getUserTier(user);
  const tc             = TIER_CONFIG[tier];

  const [docs,           setDocs]           = useState<Documento[]>([]);
  const [loading,        setLoading]        = useState(true);
  const [uploading,      setUploading]      = useState(false);
  const [dragging,       setDragging]       = useState(false);
  const [selectedDoc,    setSelectedDoc]    = useState<Documento | null>(null);
  const [atomos,         setAtomos]         = useState<TopicoAtomico[]>([]);
  const [loadingAtomos,  setLoadingAtomos]  = useState(false);
  const [logs,           setLogs]           = useState<LogLine[]>([]);
  const [sseConnected,   setSseConnected]   = useState(false);

  const logIdRef    = useRef(0);
  const inputRef    = useRef<HTMLInputElement>(null);
  const logsEndRef  = useRef<HTMLDivElement>(null);
  const pollingRef  = useRef<ReturnType<typeof setInterval> | null>(null);

  /* ── SSE — live log stream ────────────────────────────────────────── */
  useEffect(() => {
    let es: EventSource;
    try {
      es = new EventSource(SSE_URL);
      es.onopen    = () => setSseConnected(true);
      es.onerror   = () => setSseConnected(false);
      es.onmessage = (e) => {
        try {
          const data = JSON.parse(e.data);
          if (data.type === "log" && data.message) {
            const id = ++logIdRef.current;
            const ts = new Date().toLocaleTimeString("pt-BR", { hour12: false });
            setLogs(prev => [...prev.slice(-79), { id, ts, level: data.level ?? "INFO", message: data.message }]);
          }
        } catch { /* skip malformed frames */ }
      };
    } catch { /* SSE not available — page still works */ }
    return () => es?.close();
  }, []);

  /* ── Autoscroll logs ─────────────────────────────────────────────── */
  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs]);

  /* ── Fetch docs ──────────────────────────────────────────────────── */
  const fetchDocs = useCallback(async () => {
    try {
      const token = await getToken();
      const res   = await fetch(`${API_BASE}/`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      const data  = await res.json();
      setDocs(Array.isArray(data) ? data : []);
    } catch (err) {
      console.error("Erro ao buscar biblioteca:", err);
    } finally {
      setLoading(false);
    }
  }, [getToken]);

  useEffect(() => { fetchDocs(); }, [fetchDocs]);

  /* ── Poll while any doc is processing ───────────────────────────── */
  useEffect(() => {
    const hasProcessing = docs.some(d => d.status === "processando");
    if (hasProcessing && !pollingRef.current) {
      pollingRef.current = setInterval(fetchDocs, 3000);
    } else if (!hasProcessing && pollingRef.current) {
      clearInterval(pollingRef.current);
      pollingRef.current = null;
    }
    return () => {
      if (pollingRef.current) { clearInterval(pollingRef.current); pollingRef.current = null; }
    };
  }, [docs, fetchDocs]);

  /* ── Upload ──────────────────────────────────────────────────────── */
  const handleFile = useCallback(async (file: File | null | undefined) => {
    if (!file || !file.name.toLowerCase().endsWith(".pdf")) return;
    setUploading(true);
    const fd = new FormData();
    fd.append("file", file);
    try {
      const token = await getToken();
      await fetch(`${API_BASE}/upload`, {
        method:  "POST",
        headers: { Authorization: `Bearer ${token}` },
        body:    fd,
      });
      await fetchDocs();
    } catch (err) {
      console.error("Erro no upload:", err);
    } finally {
      setUploading(false);
    }
  }, [getToken, fetchDocs]);

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    handleFile(e.dataTransfer.files[0]);
  }, [handleFile]);

  /* ── Fetch atomos ────────────────────────────────────────────────── */
  const fetchAtomos = async (doc: Documento) => {
    setSelectedDoc(doc);
    setAtomos([]);
    setLoadingAtomos(true);
    try {
      const token = await getToken();
      const res   = await fetch(`${API_BASE}/${doc.id}/atomos`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      const data  = await res.json();
      setAtomos(Array.isArray(data) ? data : []);
    } catch (err) {
      console.error("Erro ao buscar átomos:", err);
    } finally {
      setLoadingAtomos(false);
    }
  };

  /* ── Derived ─────────────────────────────────────────────────────── */
  const hasProcessing = docs.some(d => d.status === "processando");

  /* ── Render ──────────────────────────────────────────────────────── */
  return (
    <div className="min-h-screen bg-transparent p-6 md:p-10">

      {/* ── Header ───────────────────────────────────────────────────── */}
      <header className="flex flex-col sm:flex-row sm:items-end justify-between gap-4 mb-10">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-[#007F8E]/15 border border-[#007F8E]/20">
            <Library className="text-[#007F8E]" size={26} />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-[var(--text-offwhite)]">Biblioteca Estratégica</h1>
            <p className="text-[var(--text-offwhite)]/40 text-xs mt-0.5">
              Materiais transformados em átomos de conhecimento
            </p>
          </div>
        </div>

        {/* Tier badge */}
        <div className={`flex items-center gap-2 px-3 py-1.5 rounded-full border ${tc.bg} ${tc.border} self-start sm:self-auto`}>
          {tier === "FREE"
            ? <Lock size={11} className={tc.color} />
            : <Crown size={11} className={tc.color} />}
          <span className={`text-[10px] font-black uppercase tracking-widest ${tc.color}`}>{tc.label}</span>
        </div>
      </header>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">

        {/* ── LEFT col: drop zone + doc grid ────────────────────────── */}
        <div className="lg:col-span-2 space-y-6">

          {/* Drag-and-Drop Zone */}
          <motion.div
            onClick={() => !uploading && inputRef.current?.click()}
            onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
            onDragLeave={() => setDragging(false)}
            onDrop={onDrop}
            animate={{
              borderColor: dragging
                ? "#007F8E"
                : uploading
                ? "rgba(234,179,8,0.5)"
                : "var(--glass-border-color)",
              boxShadow: dragging ? "0 0 40px rgba(0,127,142,0.18)" : "none",
            }}
            transition={{ duration: 0.18 }}
            className={[
              "relative glass rounded-3xl border-2 border-dashed p-10",
              "flex flex-col items-center justify-center gap-4",
              "overflow-hidden transition-colors",
              uploading ? "cursor-not-allowed opacity-70" : "cursor-pointer hover:border-[#007F8E]/40",
            ].join(" ")}
          >
            {/* teal glow when dragging */}
            <AnimatePresence>
              {dragging && (
                <motion.div
                  initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
                  className="absolute inset-0 bg-[#007F8E]/5 pointer-events-none"
                />
              )}
            </AnimatePresence>

            <AnimatePresence mode="wait">
              {uploading ? (
                <motion.div key="uploading"
                  initial={{ opacity: 0, scale: 0.9 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0 }}
                  className="flex flex-col items-center gap-3"
                >
                  <div className="w-14 h-14 rounded-2xl bg-amber-500/10 border border-amber-500/20 flex items-center justify-center">
                    <Loader2 size={28} className="text-amber-400 animate-spin" />
                  </div>
                  <p className="text-sm font-semibold text-amber-400">Enviando documento...</p>
                  <p className="text-xs text-white/30 font-mono">Aguarde o processamento</p>
                </motion.div>
              ) : dragging ? (
                <motion.div key="dragging"
                  initial={{ opacity: 0, scale: 0.9 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0 }}
                  className="flex flex-col items-center gap-3"
                >
                  <div className="w-14 h-14 rounded-2xl bg-[#007F8E]/20 border border-[#007F8E]/30 flex items-center justify-center">
                    <Upload size={28} className="text-[#007F8E]" />
                  </div>
                  <p className="text-base font-bold text-[#007F8E]">Solte para adicionar</p>
                </motion.div>
              ) : (
                <motion.div key="idle"
                  initial={{ opacity: 0, scale: 0.9 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0 }}
                  className="flex flex-col items-center gap-4 text-center"
                >
                  <div className="w-14 h-14 rounded-2xl bg-white/[0.04] border border-white/10 flex items-center justify-center">
                    <Upload size={28} className="text-white/20" />
                  </div>
                  <div>
                    <p className="text-sm font-semibold text-white/55">
                      Arraste um PDF ou clique para selecionar
                    </p>
                    <p className="text-xs text-white/20 mt-1 font-mono">
                      Apostilas, editais, provas anteriores — qualquer PDF
                    </p>
                  </div>
                  <div className="flex items-center gap-2 px-5 py-2 rounded-xl bg-[#007F8E] text-white text-xs font-bold uppercase tracking-wider shadow-lg shadow-[#007F8E]/20">
                    <Upload size={12} />
                    Selecionar PDF
                  </div>
                </motion.div>
              )}
            </AnimatePresence>

            <input
              ref={inputRef}
              type="file"
              accept=".pdf"
              className="hidden"
              onChange={e => handleFile(e.target.files?.[0])}
              disabled={uploading}
            />
          </motion.div>

          {/* Document list */}
          {loading ? (
            <div className="flex items-center justify-center py-16 gap-3 text-white/20">
              <Loader2 size={22} className="animate-spin text-[#007F8E]" />
              <span className="text-sm font-mono">Carregando biblioteca...</span>
            </div>
          ) : docs.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-16 gap-3 text-white/20 text-center">
              <Library size={40} />
              <p className="text-sm font-medium">Biblioteca vazia</p>
              <p className="text-xs font-mono">Adicione seu primeiro PDF acima</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <AnimatePresence>
                {docs.map((doc, idx) => (
                  <DocumentCard
                    key={doc.id}
                    doc={doc}
                    idx={idx}
                    canProcess={tc.canProcess}
                    onView={() => fetchAtomos(doc)}
                  />
                ))}
              </AnimatePresence>
            </div>
          )}
        </div>

        {/* ── RIGHT col: live terminal + stats ─────────────────────── */}
        <div className="space-y-4">

          {/* Live Terminal */}
          <div className="glass rounded-2xl overflow-hidden h-[400px] flex flex-col">
            <div className="flex items-center gap-2 px-4 py-2.5 border-b border-white/5 bg-white/[0.02] shrink-0">
              <span className="h-2.5 w-2.5 rounded-full bg-red-500/70" />
              <span className="h-2.5 w-2.5 rounded-full bg-yellow-500/70" />
              <span className="h-2.5 w-2.5 rounded-full bg-green-500/70" />
              <span className="ml-2 text-[10px] text-white/30 font-mono">
                biblioteca@estudohub
              </span>
              <span className="ml-auto text-[10px] font-mono flex items-center gap-1.5">
                {sseConnected || hasProcessing ? (
                  <>
                    <span className="h-1.5 w-1.5 rounded-full bg-amber-400 animate-pulse" />
                    <span className="text-amber-400">LIVE</span>
                  </>
                ) : (
                  <>
                    <span className="h-1.5 w-1.5 rounded-full bg-white/15" />
                    <span className="text-white/20">OFFLINE</span>
                  </>
                )}
              </span>
            </div>

            <div className="flex-1 overflow-y-auto p-4 font-mono text-[11px] space-y-0.5 terminal-scanline terminal-crt">
              {logs.length === 0 ? (
                <div className="flex items-center gap-2 text-white/15 leading-5">
                  <span className="text-white/10">
                    {new Date().toLocaleTimeString("pt-BR", { hour12: false })}
                  </span>
                  <span className="text-green-400 animate-pulse">█</span>
                  <span>Aguardando atividade...</span>
                </div>
              ) : (
                logs.map(log => (
                  <div key={log.id} className="flex gap-2 leading-5">
                    <span className="text-white/20 shrink-0 select-none">{log.ts}</span>
                    <span className={`shrink-0 font-semibold select-none ${LEVEL_COLOR[log.level] ?? "text-green-400"}`}>
                      {log.level === "ERROR" ? "[ERR]" : log.level === "WARNING" ? "[WRN]" : "[INF]"}
                    </span>
                    <span className={`break-all ${
                      log.level === "ERROR"   ? "text-red-300"    :
                      log.level === "WARNING" ? "text-yellow-300" : "text-green-300"
                    }`}>
                      {log.message}
                    </span>
                  </div>
                ))
              )}
              <div ref={logsEndRef} />
            </div>
          </div>

          {/* Stats */}
          <div className="glass rounded-2xl p-5">
            <h3 className="text-[10px] font-black uppercase tracking-widest text-white/25 mb-4">
              Resumo da Biblioteca
            </h3>
            <div className="grid grid-cols-2 gap-3">
              <div className="bg-white/[0.04] rounded-xl p-3 text-center">
                <p className="text-2xl font-black text-[#007F8E]">{docs.length}</p>
                <p className="text-[10px] text-white/30 font-mono mt-1">Documentos</p>
              </div>
              <div className="bg-white/[0.04] rounded-xl p-3 text-center">
                <p className="text-2xl font-black text-emerald-400">
                  {docs.filter(d => d.status === "concluido").length}
                </p>
                <p className="text-[10px] text-white/30 font-mono mt-1">Processados</p>
              </div>
            </div>

            {/* Free tier upsell */}
            {!tc.canProcess && (
              <div className="mt-4 p-3 rounded-xl bg-amber-500/5 border border-amber-500/15 text-center">
                <Crown size={16} className="text-amber-400 mx-auto mb-2" />
                <p className="text-[10px] text-amber-400 font-bold leading-relaxed">
                  Faça upgrade para Premium e processe seus PDFs com IA
                </p>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* ── Atomic Viewer Drawer ────────────────────────────────────── */}
      <AnimatePresence>
        {selectedDoc && (
          <div className="fixed inset-0 z-50 flex items-stretch justify-end">
            {/* Backdrop */}
            <motion.div
              initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
              onClick={() => setSelectedDoc(null)}
              className="absolute inset-0 bg-black/80 backdrop-blur-sm"
            />

            {/* Drawer */}
            <motion.div
              initial={{ x: "100%" }}
              animate={{ x: 0 }}
              exit={{ x: "100%" }}
              transition={{ type: "spring", damping: 28, stiffness: 220 }}
              className="relative w-full max-w-2xl glass flex flex-col shadow-2xl border-l border-white/10"
            >
              {/* Drawer header */}
              <header className="p-6 border-b border-white/5 flex items-center justify-between bg-white/[0.02] shrink-0">
                <div className="flex items-center gap-3 min-w-0">
                  <div className="p-2.5 rounded-xl bg-[#007F8E]/15 border border-[#007F8E]/20 shrink-0">
                    <BrainCircuit size={20} className="text-[#007F8E]" />
                  </div>
                  <div className="min-w-0">
                    <h2 className="text-base font-bold text-white truncate max-w-[280px]">
                      {selectedDoc.filename}
                    </h2>
                    <p className="text-[10px] text-[#007F8E] font-bold uppercase tracking-widest mt-0.5">
                      Inteligência Extraída
                    </p>
                  </div>
                </div>
                <button
                  onClick={() => setSelectedDoc(null)}
                  className="p-2 text-white/30 hover:text-white rounded-lg hover:bg-white/5 transition-all shrink-0"
                >
                  <X size={20} />
                </button>
              </header>

              {/* Atom count strip */}
              {!loadingAtomos && atomos.length > 0 && (
                <div className="px-6 py-2.5 border-b border-white/5 bg-[#007F8E]/5 flex items-center gap-2 shrink-0">
                  <Brain size={13} className="text-[#007F8E]" />
                  <span className="text-xs text-white/50">
                    <span className="text-[#007F8E] font-bold">{atomos.length}</span> átomos extraídos
                  </span>
                </div>
              )}

              {/* Scrollable content */}
              <div className="flex-1 overflow-y-auto p-6 space-y-10">
                {loadingAtomos ? (
                  <div className="flex flex-col items-center justify-center h-full gap-4 text-white/20">
                    <Loader2 size={40} className="animate-spin text-[#007F8E]" />
                    <p className="text-sm font-medium animate-pulse">Recuperando átomos do banco...</p>
                  </div>
                ) : atomos.length === 0 ? (
                  <div className="flex flex-col items-center justify-center h-full gap-4 text-white/20">
                    <Brain size={40} />
                    <p className="text-sm">Nenhum átomo encontrado</p>
                  </div>
                ) : (
                  atomos.map((atomo, idx) => (
                    <AtomoCard key={atomo.id} atomo={atomo} idx={idx} />
                  ))
                )}
              </div>

              {/* Footer */}
              <footer className="p-4 border-t border-white/5 bg-black/10 text-center shrink-0">
                <p className="text-[9px] text-white/15 font-mono">
                  Processado via IA · EstudoHub Pro 4.0
                </p>
              </footer>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </div>
  );
}

/* ── DocumentCard ───────────────────────────────────────────────────── */
function DocumentCard({
  doc, idx, canProcess, onView,
}: {
  doc: Documento;
  idx: number;
  canProcess: boolean;
  onView: () => void;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, scale: 0.95 }}
      transition={{ delay: idx * 0.04 }}
      className="glass p-5 rounded-2xl group hover:border-[#007F8E]/30 transition-all flex flex-col"
    >
      {/* Top row */}
      <div className="flex items-start justify-between mb-4">
        <div className="p-2.5 rounded-xl bg-white/[0.05] text-[#007F8E]">
          <FileText size={20} />
        </div>
        <StatusBadge status={doc.status} />
      </div>

      <h3 className="text-sm text-white font-semibold truncate mb-1" title={doc.filename}>
        {doc.filename}
      </h3>
      <p className="text-white/25 text-[10px] uppercase font-mono mb-4 flex items-center gap-1.5">
        <History size={9} />
        {new Date(doc.created_at).toLocaleDateString("pt-BR")}
      </p>

      {/* Actions */}
      <div className="mt-auto flex flex-col gap-2">
        {doc.status === "concluido" && (
          <button
            onClick={onView}
            className="w-full flex items-center justify-center gap-2 py-2.5 rounded-xl bg-white/[0.05] hover:bg-[#007F8E]/10 border border-white/5 hover:border-[#007F8E]/25 text-xs font-bold text-white transition-all group/btn"
          >
            <Sparkles size={13} className="text-[#007F8E] group-hover/btn:scale-110 transition-transform" />
            Ver Resumo IA
            <ChevronRight size={13} className="opacity-0 group-hover/btn:opacity-100 group-hover/btn:translate-x-0.5 transition-all" />
          </button>
        )}

        {/* Processar com IA — tier gated */}
        {canProcess ? (
          <button className="w-full flex items-center justify-center gap-2 py-2.5 rounded-xl bg-[#007F8E]/10 hover:bg-[#007F8E]/20 border border-[#007F8E]/20 hover:border-[#007F8E]/40 text-xs font-bold text-[#007F8E] transition-all">
            <Zap size={13} />
            Processar com IA
          </button>
        ) : (
          <button
            disabled
            title="Disponível apenas para usuários Premium/Platinum"
            className="w-full flex items-center justify-center gap-2 py-2.5 rounded-xl bg-zinc-500/5 border border-zinc-500/15 text-xs font-bold text-zinc-500 cursor-not-allowed"
          >
            <Lock size={12} />
            Processar com IA
            <span className="ml-auto text-[9px] font-black bg-amber-500/15 text-amber-400 px-1.5 py-0.5 rounded-full border border-amber-500/20">
              PREMIUM
            </span>
          </button>
        )}
      </div>
    </motion.div>
  );
}

/* ── StatusBadge ────────────────────────────────────────────────────── */
function StatusBadge({ status }: { status: string }) {
  if (status === "concluido") return (
    <span className="flex items-center gap-1.5 text-emerald-400 bg-emerald-500/10 px-2.5 py-1 rounded-full text-[10px] font-bold uppercase border border-emerald-500/15">
      <CheckCircle2 size={10} /> Pronto
    </span>
  );
  if (status === "erro") return (
    <span className="flex items-center gap-1.5 text-red-400 bg-red-500/10 px-2.5 py-1 rounded-full text-[10px] font-bold uppercase border border-red-500/15">
      <AlertCircle size={10} /> Erro
    </span>
  );
  return (
    <span className="flex items-center gap-1.5 text-amber-400 bg-amber-500/10 px-2.5 py-1 rounded-full text-[10px] font-bold uppercase border border-amber-500/15">
      <Loader2 size={10} className="animate-spin" /> Processando
    </span>
  );
}

/* ── AtomoCard ──────────────────────────────────────────────────────── */
function AtomoCard({ atomo, idx }: { atomo: TopicoAtomico; idx: number }) {
  let flashcards: { pergunta: string; resposta: string }[] = [];
  try { flashcards = JSON.parse(atomo.flashcards); } catch { /* skip */ }

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: idx * 0.05 }}
      className="space-y-4"
    >
      {/* Header */}
      <div className="flex items-center gap-3">
        <span className="text-[9px] font-black text-[#007F8E] bg-[#007F8E]/10 px-2 py-1 rounded border border-[#007F8E]/20">
          ÁTOMO {idx + 1}
        </span>
        <div className="h-px flex-1 bg-white/5" />
        <span className="text-[9px] font-bold text-amber-400 uppercase tracking-widest bg-amber-500/10 px-2 py-1 rounded">
          {atomo.materia}
        </span>
      </div>

      {/* Topic */}
      <h4 className="text-base font-bold text-white flex items-center gap-2">
        <BookOpen size={16} className="text-[#007F8E] shrink-0" />
        {atomo.topico}
      </h4>

      {/* Summary */}
      <p className="text-sm text-white/55 leading-relaxed bg-white/[0.03] p-4 rounded-xl border border-white/5">
        {atomo.ai_summary}
      </p>

      {/* Flashcards */}
      {flashcards.length > 0 && (
        <div className="space-y-2">
          <h5 className="text-[9px] font-bold uppercase tracking-widest text-[#007F8E] flex items-center gap-1.5">
            <Sparkles size={10} />
            Flashcards de Memorização
          </h5>
          <div className="space-y-2">
            {flashcards.map((f, fIdx) => (
              <div
                key={fIdx}
                className="p-3.5 rounded-xl bg-black/20 border border-white/5 hover:border-emerald-500/25 transition-colors"
              >
                <p className="text-xs font-semibold text-white/80 mb-2">Q: {f.pergunta}</p>
                <p className="text-xs text-emerald-400 italic">A: {f.resposta}</p>
              </div>
            ))}
          </div>
        </div>
      )}
    </motion.div>
  );
}

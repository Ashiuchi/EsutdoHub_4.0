"use client";

import type { CSSProperties } from "react";
import { useState, useEffect, useMemo, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Mail, ShieldCheck, Camera, Check, Loader2, Target, Clock, Star, LogOut, ChevronRight, Search, Upload, X, Lock, FileText } from "lucide-react";
import { useUser, SignInButton, useClerk, UserProfile } from "@clerk/nextjs";
import { useTheme } from "next-themes";
import { dark } from "@clerk/themes";
import ThemeBackground from "@/components/ThemeBackground";

// ── Types ─────────────────────────────────────────────────────────────────────

interface Edital {
  id: string;
  title: string;
  orgao: string;
  banca: string;
  cargos: Cargo[];
}

interface Cargo {
  titulo: string;
  salario: number;
  escolaridade: string;
  materias: Materia[];
}

interface Materia {
  nome: string;
  topicos: string[];
  peso?: number; // proportion 0-1; falls back to equal distribution if absent
}

// ── Presets ───────────────────────────────────────────────────────────────────

const BANNER_PRESETS = [
  { id: "grafite", label: "Grafite", value: "linear-gradient(to right, #18181b, rgba(0,127,142,0.20))" },
  { id: "teal-pulse", label: "Teal Pulse", value: "linear-gradient(135deg, #030712 0%, rgba(0,127,142,0.45) 50%, #030712 100%)" },
  { id: "industrial", label: "Industrial", value: "linear-gradient(to bottom right, #0c1820, #007F8E)" },
] as const;

const AVATAR_PRESETS = [
  { id: "avataaars",  name: "Humanos",      url: "https://api.dicebear.com/7.x/avataaars/svg?seed=" },
  { id: "pixel-art",  name: "Pixel Art",    url: "https://api.dicebear.com/7.x/pixel-art/svg?seed=" },
  { id: "bottts",     name: "Robôs",        url: "https://api.dicebear.com/7.x/bottts/svg?seed=" },
  { id: "big-smile",  name: "Pets/Bichos",  url: "https://api.dicebear.com/7.x/big-smile/svg?seed=" },
  { id: "adventurer", name: "Aventureiros", url: "https://api.dicebear.com/7.x/adventurer/svg?seed=" },
] as const;

function isImageUrl(value: string) {
  return /^https?:\/\//.test(value) || value.startsWith("/");
}

function resolveBannerStyle(bannerUrl?: string): CSSProperties {
  if (!bannerUrl) return {};
  if (isImageUrl(bannerUrl)) {
    return { backgroundImage: `url(${bannerUrl})`, backgroundSize: "cover", backgroundPosition: "center" };
  }
  return { background: bannerUrl };
}

// ── Lock Overlay ──────────────────────────────────────────────────────────────

function LockOverlay({ message, ctaLabel }: { message: string; ctaLabel: string }) {
  return (
    <div className="absolute inset-0 z-10 flex flex-col items-center justify-center gap-5 rounded-[inherit] bg-black/25 backdrop-blur-md">
      <div className="w-12 h-12 rounded-2xl bg-[#007F8E]/15 border border-[#007F8E]/35 flex items-center justify-center shadow-lg shadow-[#007F8E]/10">
        <Lock size={20} className="text-[#007F8E]" />
      </div>
      <div className="text-center px-8 max-w-[240px] space-y-1">
        <p className="text-sm font-bold text-white/80">{message}</p>
      </div>
      <button className="px-6 py-2.5 bg-[#007F8E] hover:bg-[#007F8E]/80 text-white text-xs font-bold rounded-xl transition-all shadow-lg shadow-[#007F8E]/20 hover:shadow-[#007F8E]/40 hover:scale-105">
        {ctaLabel}
      </button>
    </div>
  );
}

// ── Adaptive Cycle Engine ─────────────────────────────────────────────────────

const AFFINITY_MULTIPLIER: Record<number, number> = {
  1: 1.40,
  2: 1.20,
  3: 1.00,
  4: 0.85,
  5: 0.70,
};

interface CycleEntry {
  nome: string;
  horasSemana: number;
  proporcao: number;
  status: 'reforco' | 'neutro' | 'reducao';
}

function computeAdaptiveCycle(
  materias: Materia[],
  affinities: Record<string, number>,
  totalHoras: number,
  adaptive: boolean,
): CycleEntry[] {
  if (!materias.length || totalHoras <= 0) return [];

  const n = materias.length;
  const raw = materias.map(m => m.peso ?? 1 / n);
  const sumRaw = raw.reduce((a, b) => a + b, 0);
  const base = raw.map(w => w / sumRaw);

  const adjusted = base.map((w, i) => {
    if (!adaptive) return w;
    const aff = affinities[materias[i].nome] || 3;
    return w * (AFFINITY_MULTIPLIER[aff] ?? 1.0);
  });

  const sumAdj = adjusted.reduce((a, b) => a + b, 0);
  const final = adjusted.map(w => w / sumAdj);

  return materias.map((m, i) => {
    const aff = affinities[m.nome] || 3;
    let status: CycleEntry['status'] = 'neutro';
    if (adaptive) {
      if (aff <= 2) status = 'reforco';
      else if (aff >= 4) status = 'reducao';
    }
    return {
      nome: m.nome,
      horasSemana: Math.round(final[i] * totalHoras * 10) / 10,
      proporcao: final[i],
      status,
    };
  });
}

// ── Tier System ────────────────────────────────────────────────────────────────

type Tier = 'Free' | 'Premium' | 'Platinum';

const TIER_CONFIG: Record<Tier, { label: string; pill: string; glow: string }> = {
  Free:     {
    label: 'RECRUTA',
    pill:  'text-slate-400 bg-slate-700/30 border border-slate-600/30',
    glow:  '',
  },
  Premium:  {
    label: 'GUERREIRO',
    pill:  'text-[#007F8E] bg-[#007F8E]/15 border border-[#007F8E]/40',
    glow:  'shadow-sm shadow-[#007F8E]/20',
  },
  Platinum: {
    label: 'LENDA',
    pill:  'text-amber-300 bg-amber-500/15 border border-amber-400/40',
    glow:  'shadow-sm shadow-amber-400/20',
  },
};

function TierBadge({ tier }: { tier: Tier }) {
  const cfg = TIER_CONFIG[tier];
  return (
    <span className={`inline-flex items-center px-3 py-1 rounded-lg text-[10px] font-black tracking-[0.15em] ${cfg.pill} ${cfg.glow}`}>
      {cfg.label}
    </span>
  );
}

function RadarChart({ materias, affinities }: { materias: string[]; affinities: Record<string, number> }) {
  const cx = 100, cy = 100, r = 72;
  const n = materias.length;
  if (n < 3) return (
    <div className="h-32 flex items-center justify-center">
      <p className="text-xs text-white/20 italic text-center">Selecione um cargo com 3+ matérias para ver o diagnóstico</p>
    </div>
  );

  const pts = materias.map((name, i) => {
    const angle = (2 * Math.PI * i) / n - Math.PI / 2;
    const v = (affinities[name] || 1) / 5;
    return {
      x: cx + v * r * Math.cos(angle),
      y: cy + v * r * Math.sin(angle),
      ax: cx + r * Math.cos(angle),
      ay: cy + r * Math.sin(angle),
      lx: cx + (r + 14) * Math.cos(angle),
      ly: cy + (r + 14) * Math.sin(angle),
      name: name.length > 7 ? name.substring(0, 7) + '…' : name,
    };
  });

  return (
    <svg viewBox="0 0 200 200" className="w-full max-w-[200px] mx-auto">
      {[0.25, 0.5, 0.75, 1].map(ratio => (
        <circle key={ratio} cx={cx} cy={cy} r={r * ratio} fill="none" stroke="rgba(255,255,255,0.05)" strokeWidth="1" />
      ))}
      {pts.map((p, i) => (
        <line key={i} x1={cx} y1={cy} x2={p.ax} y2={p.ay} stroke="rgba(255,255,255,0.08)" strokeWidth="1" />
      ))}
      <polygon
        points={pts.map(p => `${p.x},${p.y}`).join(' ')}
        fill="rgba(245,158,11,0.15)"
        stroke="rgb(245,158,11)"
        strokeWidth="1.5"
        strokeLinejoin="round"
      />
      {pts.map((p, i) => (
        <circle key={i} cx={p.x} cy={p.y} r={2.5} fill="rgb(245,158,11)" />
      ))}
      {pts.map((p, i) => (
        <text key={i} x={p.lx} y={p.ly} textAnchor="middle" dominantBaseline="middle" fontSize="6.5" fill="rgba(255,255,255,0.4)">
          {p.name}
        </text>
      ))}
    </svg>
  );
}

// ── Component ─────────────────────────────────────────────────────────────────

export default function PerfilDashboard() {
  const { isLoaded, isSignedIn, user } = useUser();
  const { signOut } = useClerk();
  const { resolvedTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  // States for Backend Data
  const [editais, setEditais] = useState<Edital[]>([]);
  const [loadingEditais, setLoadingEditais] = useState(true);

  // States for Selection
  const [selectedEditalId, setSelectedEditalId] = useState<string>("");
  const [selectedCargoTitle, setSelectedCargoTitle] = useState<string>("");
  const [affinities, setAffinities] = useState<Record<string, number>>({});
  const [studyHours, setStudyHours] = useState(4);
  const [studyDays, setStudyDays] = useState(6);

  // UI States
  const [editingBanner, setEditingBanner] = useState(false);
  const [showAvatarModal, setShowAvatarModal] = useState(false);
  const [urlInput, setUrlInput] = useState("");
  const [saving, setSaving] = useState(false);
  const [uploadingAvatar, setUploadingAvatar] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [saveError, setSaveError] = useState<string | null>(null);

  useEffect(() => {
    setMounted(true);
    fetchEditais();
  }, []);

  // Initialize from Metadata
  useEffect(() => {
    if (user?.unsafeMetadata) {
      const meta = user.unsafeMetadata as any;
      if (meta.targetEditalId) setSelectedEditalId(meta.targetEditalId);
      if (meta.targetCargoTitle) setSelectedCargoTitle(meta.targetCargoTitle);
      if (meta.affinities) setAffinities(meta.affinities);
      if (meta.studyHours) setStudyHours(meta.studyHours);
      if (meta.studyDays) setStudyDays(meta.studyDays);
    }
  }, [user]);

  const fetchEditais = async () => {
    try {
      const res = await fetch("http://localhost:8000/api/v1/");
      const data = await res.json();
      setEditais(data);
    } catch (err) {
      console.error("Erro ao buscar editais:", err);
    } finally {
      setLoadingEditais(false);
    }
  };

  const isLight = mounted && resolvedTheme === "light";

  // ── Clerk appearance — theme-aware ────────────────────────────────────────
  const clerkAppearance = {
    ...(!isLight && { baseTheme: dark }),
    variables: {
      colorBackground: isLight ? "#f8fafc" : "#030712",
      colorInputBackground: isLight ? "#f1f5f9" : "#18181b",
      colorText: isLight ? "#0f172a" : "#e4e4e7",
      colorTextSecondary: isLight ? "#475569" : "#a1a1aa",
      colorPrimary: "#007F8E",
      fontFamily: "var(--font-geist-sans)",
    },
    elements: {
      rootBox: "w-full",
      card: "bg-transparent shadow-none rounded-none border-0",
      navbar: isLight
        ? "bg-slate-100/80 border-r border-slate-200"
        : "bg-zinc-900/60 border-r border-zinc-800",
      navbarButton: isLight
        ? "text-slate-700 hover:text-slate-900 hover:bg-slate-200"
        : "text-zinc-300 hover:text-zinc-100 hover:bg-zinc-800",
      navbarButtonIcon: "text-[#007F8E]",
      pageScrollBox: isLight ? "bg-[#f8fafc]" : "bg-[#030712]",
      formFieldInput: isLight
        ? "bg-slate-100 border-slate-300 text-slate-900"
        : "bg-zinc-900 border-zinc-800 text-zinc-100",
      formButtonPrimary: "bg-[#007F8E] hover:bg-[#007F8E]/80 shadow-none",
      headerTitle: isLight ? "text-slate-900" : "text-zinc-100",
      headerSubtitle: isLight ? "text-slate-500" : "text-zinc-400",
      dividerLine: isLight ? "bg-slate-200" : "bg-zinc-800",
      profileSection: isLight ? "border-slate-200" : "border-zinc-800",
      profileSectionTitle: isLight ? "text-slate-500" : "text-zinc-400",
    },
  };

  // ── Handlers ──────────────────────────────────────────────────────────────
  const updateMetadata = async (newData: any) => {
    setSaving(true);
    try {
      await user?.update({
        unsafeMetadata: { ...user.unsafeMetadata, ...newData },
      });
    } catch (err) {
      console.error("Erro ao salvar preferências:", err);
    } finally {
      setSaving(false);
    }
  };

  const saveBanner = async (value: string) => {
    setSaving(true);
    setSaveError(null);
    try {
      await user?.update({
        unsafeMetadata: { ...user.unsafeMetadata, bannerUrl: value },
      });
      setEditingBanner(false);
      setUrlInput("");
    } catch {
      setSaveError("Erro ao salvar. Tente novamente.");
    } finally {
      setSaving(false);
    }
  };

  const handleAvatarUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploadingAvatar(true);
    try {
      await user?.setProfileImage({ file });
      setShowAvatarModal(false);
    } catch (err) {
      console.error("Erro no upload do avatar:", err);
    } finally {
      setUploadingAvatar(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const handlePresetAvatar = async (baseUrl: string) => {
    setUploadingAvatar(true);
    try {
      const seed = Math.random().toString(36).substring(7);
      const imageUrl = `${baseUrl}${seed}`;
      const response = await fetch(imageUrl);
      const blob = await response.blob();
      const file = new File([blob], "avatar.svg", { type: "image/svg+xml" });
      
      await user?.setProfileImage({ file });
      setShowAvatarModal(false);
    } catch (err) {
      console.error("Erro ao aplicar preset:", err);
    } finally {
      setUploadingAvatar(false);
    }
  };

  // ── Derived ───────────────────────────────────────────────────────────────
  const selectedEdital = editais.find(e => e.id === selectedEditalId);
  const availableCargos = selectedEdital?.cargos || [];
  const selectedCargo = availableCargos.find(c => c.titulo === selectedCargoTitle);

  const userTier = ((user?.unsafeMetadata as any)?.tier as Tier) || 'Free';
  const isAdaptive = userTier === 'Platinum';
  const totalHorasSemanais = studyHours * studyDays;

  const cycleData = useMemo(() => computeAdaptiveCycle(
    selectedCargo?.materias ?? [],
    affinities,
    totalHorasSemanais,
    isAdaptive,
  ), [selectedCargo, affinities, totalHorasSemanais, isAdaptive]);

  // ── Render ────────────────────────────────────────────────────────────────

  if (!isLoaded) return <div className="min-h-screen bg-transparent animate-pulse" />;

  if (!isSignedIn) {
    return (
      <div className="min-h-screen bg-transparent flex flex-col items-center justify-center gap-5 text-center px-6">
        <ThemeBackground />
        <div className="w-20 h-20 rounded-full border flex items-center justify-center glass">
          <ShieldCheck className="w-9 h-9 text-zinc-600" />
        </div>
        <div>
          <p className="text-[var(--text-offwhite)] text-xl font-semibold">Acesso restrito</p>
          <p className="text-[var(--text-offwhite)]/50 text-sm mt-1">Faça login para configurar seu plano.</p>
        </div>
        <SignInButton mode="modal">
          <button className="px-6 py-2.5 bg-[#007F8E] hover:bg-[#007F8E]/80 text-white text-sm font-medium rounded-lg transition-colors">
            Entrar
          </button>
        </SignInButton>
      </div>
    );
  }

  const displayName = user.fullName || user.username || "Recruta";
  const bannerUrl = user.unsafeMetadata?.bannerUrl as string;
  const bannerStyle = resolveBannerStyle(bannerUrl);

  return (
    <div className="min-h-screen relative bg-transparent pb-20">
      <ThemeBackground />
      
      {/* ── Header / Banner ──────────────────────────────────────────────── */}
      <div className={`h-[180px] relative overflow-hidden ${!bannerUrl ? (isLight ? "bg-zinc-200" : "bg-zinc-900") : ""}`} style={bannerStyle}>
        {!bannerUrl && <div className="absolute inset-0 opacity-10" style={{ backgroundImage: "radial-gradient(circle, #007F8E 1px, transparent 1px)", backgroundSize: "20px 20px" }} />}
        <motion.button
          whileHover={{ scale: 1.05 }}
          onClick={() => setEditingBanner(!editingBanner)}
          className="absolute bottom-4 right-6 p-2 rounded-full bg-black/40 backdrop-blur-md border border-white/10 text-white/70 hover:text-white"
        >
          <Camera size={16} />
        </motion.button>
      </div>

      {/* ── Avatar Overlap ──────────────────────────────────────────────── */}
      <div className="px-6 md:px-12 -mt-12 flex flex-col md:flex-row md:items-end gap-6 relative z-10">
        <div className="relative group cursor-pointer" onClick={() => setShowAvatarModal(true)}>
          <div className="w-32 h-32 rounded-2xl overflow-hidden border-4 border-[var(--background)] shadow-xl relative z-10 bg-zinc-800">
            <img src={user.imageUrl} alt={displayName} className="w-full h-full object-cover" />
            <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center text-white/90">
              <Camera size={28} />
            </div>
          </div>
          <div className="absolute -inset-1 bg-gradient-to-tr from-[#007F8E] to-transparent rounded-2xl blur-sm opacity-50 group-hover:opacity-100 transition-opacity" />
        </div>
        <div className="mb-2">
          <div className="flex items-center gap-3 flex-wrap">
            <h1 className="text-3xl font-bold tracking-tight text-[var(--text-offwhite)]">{displayName}</h1>
            <TierBadge tier={userTier} />
          </div>
          <p className="text-sm font-medium text-[#007F8E] flex items-center gap-2">
            <Target size={14} /> 
            {selectedCargoTitle || "Nenhum objetivo definido"}
          </p>
        </div>
      </div>

      {/* ── Grid de Seções ──────────────────────────────────────────────── */}
      <div className="px-6 md:px-12 mt-12 grid grid-cols-1 lg:grid-cols-3 gap-8 relative z-10">
        
        {/* COLUNA 1 & 2: MISSÃO E DIAGNÓSTICO */}
        <div className="lg:col-span-2 space-y-8">
          
          <section className="glass p-8 rounded-3xl relative overflow-hidden">
            <div className="flex items-center gap-4 mb-8">
              <div className="w-10 h-10 rounded-xl bg-[#007F8E]/20 flex items-center justify-center text-[#007F8E]">
                <Target size={20} />
              </div>
              <div>
                <h2 className="text-lg font-bold text-[var(--text-offwhite)]">Objetivo de Campanha</h2>
                <p className="text-xs text-[var(--text-offwhite)]/40">Selecione o edital e cargo que deseja conquistar</p>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="space-y-2">
                <label className="text-[10px] font-bold uppercase tracking-widest text-[#007F8E]">Edital Ativo</label>
                <select 
                  value={selectedEditalId}
                  onChange={(e) => {
                    const id = e.target.value;
                    setSelectedEditalId(id);
                    setSelectedCargoTitle("");
                    updateMetadata({ targetEditalId: id, targetCargoTitle: "" });
                  }}
                  className="w-full bg-black/20 border border-white/10 rounded-xl px-4 py-3 text-sm text-[var(--text-offwhite)] focus:outline-none focus:border-[#007F8E] appearance-none cursor-pointer"
                >
                  <option value="">Selecione um Edital...</option>
                  {editais.map(e => (
                    <option key={e.id} value={e.id}>{e.orgao} ({e.banca})</option>
                  ))}
                </select>
              </div>

              <div className="space-y-2">
                <label className="text-[10px] font-bold uppercase tracking-widest text-[#007F8E]">Cargo Alvo</label>
                <select 
                  disabled={!selectedEditalId}
                  value={selectedCargoTitle}
                  onChange={(e) => {
                    const title = e.target.value;
                    setSelectedCargoTitle(title);
                    updateMetadata({ targetCargoTitle: title });
                  }}
                  className="w-full bg-black/20 border border-white/10 rounded-xl px-4 py-3 text-sm text-[var(--text-offwhite)] focus:outline-none focus:border-[#007F8E] appearance-none disabled:opacity-30 cursor-pointer"
                >
                  <option value="">Selecione o Cargo...</option>
                  {availableCargos.map(c => (
                    <option key={c.titulo} value={c.titulo}>{c.titulo}</option>
                  ))}
                </select>
              </div>
            </div>
          </section>

          <section className="glass p-8 rounded-3xl relative overflow-hidden">
            <div className="flex items-center justify-between mb-6">
              <div className="flex items-center gap-4">
                <div className="w-10 h-10 rounded-xl bg-[#007F8E]/20 flex items-center justify-center text-[#007F8E]">
                  <FileText size={20} />
                </div>
                <div>
                  <h2 className="text-lg font-bold text-[var(--text-offwhite)]">Edital Verticalizado</h2>
                  <p className="text-xs text-[var(--text-offwhite)]/40">Matérias do cargo alvo</p>
                </div>
              </div>
              <span className="text-[10px] font-mono text-[#007F8E] bg-[#007F8E]/10 px-2 py-1 rounded border border-[#007F8E]/20">GRATUITO</span>
            </div>

            {!selectedCargo ? (
              <div className="h-32 flex flex-col items-center justify-center border border-dashed border-white/10 rounded-2xl bg-white/[0.02]">
                <Search size={20} className="text-white/10 mb-2" />
                <p className="text-xs text-white/20 italic">Selecione um edital e cargo para ver as matérias</p>
              </div>
            ) : (
              <div className="space-y-2">
                {selectedCargo.materias.map((m, i) => (
                  <div key={m.nome} className="flex items-center justify-between p-3 rounded-xl bg-white/[0.03] border border-white/5">
                    <div className="flex items-center gap-3">
                      <span className="text-[10px] font-black text-[#007F8E]/50 w-5 flex-shrink-0">{i + 1}</span>
                      <span className="text-sm font-medium text-white/75">{m.nome}</span>
                    </div>
                    <span className="text-[10px] text-white/25 flex-shrink-0">{m.topicos.length} tópicos</span>
                  </div>
                ))}
              </div>
            )}
          </section>

          <section className="glass p-8 rounded-3xl relative overflow-hidden">
            <div className={userTier === 'Free' ? 'pointer-events-none select-none' : ''}>
              <div className="flex items-center justify-between mb-8">
                <div className="flex items-center gap-4">
                  <div className="w-10 h-10 rounded-xl bg-amber-500/20 flex items-center justify-center text-amber-500">
                    <Star size={20} />
                  </div>
                  <div>
                    <h2 className="text-lg font-bold text-[var(--text-offwhite)]">Mapa de Afinidade</h2>
                    <p className="text-xs text-[var(--text-offwhite)]/40">Sua base de conhecimento por matéria</p>
                  </div>
                </div>
                <span className="text-[10px] font-mono text-amber-500 bg-amber-500/10 px-2 py-1 rounded">MENSURAÇÃO IA</span>
              </div>

              {!selectedCargo ? (
                <div className="h-40 flex flex-col items-center justify-center border border-dashed border-white/10 rounded-2xl bg-white/[0.02]">
                  <Search size={24} className="text-white/10 mb-2" />
                  <p className="text-xs text-white/20 italic">Selecione um cargo para mapear as matérias</p>
                </div>
              ) : (
                <div className="space-y-4">
                  {selectedCargo.materias.map((m) => (
                    <div key={m.nome} className="flex items-center justify-between p-4 rounded-2xl bg-white/[0.03] border border-white/5 hover:border-amber-500/30 transition-colors">
                      <span className="text-sm font-medium text-white/80">{m.nome}</span>
                      <div className="flex gap-1.5">
                        {[1, 2, 3, 4, 5].map((level) => (
                          <button
                            key={level}
                            onClick={() => {
                              const newAff = { ...affinities, [m.nome]: level };
                              setAffinities(newAff);
                              updateMetadata({ affinities: newAff });
                            }}
                            className={`w-8 h-8 rounded-lg flex items-center justify-center text-xs transition-all ${
                              (affinities[m.nome] || 0) >= level
                                ? "bg-amber-500 text-black font-bold scale-110 shadow-lg shadow-amber-500/20"
                                : "bg-white/5 text-white/20 hover:bg-white/10"
                            }`}
                          >
                            {level}
                          </button>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {userTier === 'Free' && (
              <LockOverlay
                message="Acesse seu Ciclo Pro no Plano Premium"
                ctaLabel="Conhecer Planos Pro"
              />
            )}
          </section>
        </div>

        {/* COLUNA 3: RITMO E CONTA */}
        <div className="space-y-8 relative z-10">
          
          <section className="glass p-8 rounded-3xl bg-gradient-to-b from-white/[0.05] to-transparent relative overflow-hidden">
            <div className={userTier === 'Free' ? 'pointer-events-none select-none' : ''}>
              <div className="flex items-center justify-between mb-8">
                <div className="flex items-center gap-4">
                  <div className="w-10 h-10 rounded-xl bg-emerald-500/20 flex items-center justify-center text-emerald-500">
                    <Clock size={20} />
                  </div>
                  <h2 className="text-lg font-bold text-[var(--text-offwhite)]">Ritmo de Estudos</h2>
                </div>
                {isAdaptive ? (
                  <div className="flex items-center gap-1.5 px-2 py-1 rounded-lg bg-teal-500/10 border border-teal-500/20 flex-shrink-0">
                    <div className="w-1.5 h-1.5 rounded-full bg-teal-400 animate-pulse" />
                    <span className="text-[8px] font-black text-teal-400 uppercase tracking-widest whitespace-nowrap">Ciclo Adaptativo</span>
                  </div>
                ) : (
                  <span className="text-[8px] font-black text-zinc-500 uppercase tracking-widest px-2 py-1 rounded-lg bg-zinc-500/10 border border-zinc-500/20 flex-shrink-0">Ciclo Básico</span>
                )}
              </div>

              <div className="space-y-8">
                <div className="space-y-4">
                  <div className="flex justify-between text-[10px] font-bold uppercase tracking-widest">
                    <span className="text-emerald-500">Carga Diária</span>
                    <span className="text-white">{studyHours}h</span>
                  </div>
                  <input
                    type="range" min="1" max="12" value={studyHours}
                    onChange={(e) => setStudyHours(parseInt(e.target.value))}
                    onMouseUp={() => updateMetadata({ studyHours })}
                    className="w-full h-1.5 bg-white/10 rounded-lg appearance-none cursor-pointer accent-emerald-500"
                  />
                </div>

                <div className="space-y-4">
                  <div className="flex justify-between text-[10px] font-bold uppercase tracking-widest">
                    <span className="text-emerald-500">Frequência Semanal</span>
                    <span className="text-white">{studyDays} Dias</span>
                  </div>
                  <div className="flex justify-between gap-1">
                    {[1,2,3,4,5,6,7].map(d => (
                      <button
                        key={d}
                        onClick={() => { setStudyDays(d); updateMetadata({ studyDays: d }); }}
                        className={`flex-1 h-10 rounded-lg text-xs font-bold transition-all ${studyDays >= d ? "bg-emerald-500 text-black" : "bg-white/5 text-white/20"}`}
                      >
                        {d}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Distribuição por Matéria */}
                {cycleData.length > 0 && (
                  <div className="space-y-3 pt-4 border-t border-white/5">
                    {cycleData.map(entry => (
                      <div key={entry.nome} className="space-y-1">
                        <div className="flex items-center justify-between gap-2">
                          <span className="text-[10px] font-medium text-white/55 truncate flex-1">{entry.nome}</span>
                          <span className="text-[10px] font-bold text-white">{entry.horasSemana}h</span>
                        </div>
                        <div className="h-1 bg-white/5 rounded-full overflow-hidden">
                          <motion.div
                            className={`h-full rounded-full ${entry.status === 'reforco' ? 'bg-orange-500' : entry.status === 'reducao' ? 'bg-teal-400' : 'bg-emerald-500'}`}
                            initial={{ width: 0 }} animate={{ width: `${entry.proporcao * 100}%` }}
                          />
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>

            {userTier === 'Free' && (
              <LockOverlay message="Acesse seu Ciclo Pro no Plano Premium" ctaLabel="Conhecer Planos Pro" />
            )}
          </section>

          <section className="glass p-8 rounded-3xl relative overflow-hidden">
            <div className="flex items-center justify-between mb-6">
              <div className="flex items-center gap-4">
                <div className="w-10 h-10 rounded-xl bg-amber-500/20 flex items-center justify-center text-amber-500">
                  <Star size={20} />
                </div>
                <h2 className="text-lg font-bold text-[var(--text-offwhite)]">Diagnóstico Elite</h2>
              </div>
            </div>

            {userTier === 'Platinum' ? (
              <RadarChart materias={selectedCargo?.materias.map(m => m.nome) || []} affinities={affinities} />
            ) : (
              <div className="relative">
                <div className="blur-sm opacity-40 h-32 flex items-center justify-center">
                  <Star size={40} className="text-white/10" />
                </div>
                <LockOverlay message="Exclusivo para Membros Platinum" ctaLabel="Upgrade para Platinum" />
              </div>
            )}
          </section>

          <section className="glass p-8 rounded-3xl relative overflow-hidden">
            <div className="flex items-center gap-4 mb-8">
              <div className="w-10 h-10 rounded-xl bg-zinc-500/20 flex items-center justify-center text-zinc-400">
                <ShieldCheck size={20} />
              </div>
              <h2 className="text-lg font-bold text-[var(--text-offwhite)]">Conta</h2>
            </div>

            <div className="space-y-4">
              <div className="rounded-xl overflow-hidden border border-white/5 bg-[var(--background)]">
                <UserProfile path="/perfil" routing="path" appearance={clerkAppearance} />
              </div>
              <button 
                onClick={() => signOut()}
                className="w-full flex items-center justify-between p-4 rounded-2xl bg-red-500/5 border border-red-500/10 text-red-400 hover:bg-red-500/10 transition-colors"
              >
                <div className="flex items-center gap-3">
                  <LogOut size={16} />
                  <span className="text-xs font-bold uppercase tracking-wider">Sair</span>
                </div>
                <ChevronRight size={14} />
              </button>
            </div>
          </section>
        </div>
      </div>

      <AnimatePresence>
        {showAvatarModal && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => !uploadingAvatar && setShowAvatarModal(false)}
              className="absolute inset-0 bg-black/60 backdrop-blur-sm"
            />
            <motion.div
              initial={{ scale: 0.9, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.9, opacity: 0 }}
              className="relative w-full max-w-md glass p-8 rounded-3xl max-h-[90vh] flex flex-col"
            >
              {/* Header */}
              <div className="flex items-center justify-between mb-6">
                <h3 className="text-xl font-bold text-white">Personalizar Perfil</h3>
                <button
                  type="button"
                  onClick={() => !uploadingAvatar && setShowAvatarModal(false)}
                  className="p-1.5 rounded-lg text-white/40 hover:text-white hover:bg-white/10 transition-colors"
                  aria-label="Fechar"
                >
                  <X size={18} />
                </button>
              </div>

              {/* Hidden file input */}
              <input
                ref={fileInputRef}
                type="file"
                accept="image/*"
                className="hidden"
                onChange={handleAvatarUpload}
              />

              {/* Hero Upload Zone */}
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                disabled={uploadingAvatar}
                className="w-full p-5 rounded-2xl bg-white/5 border border-white/10 hover:border-[#007F8E]/60 hover:bg-[#007F8E]/5 transition-all group disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <div className="flex flex-col items-center gap-2">
                  {uploadingAvatar ? (
                    <Loader2 size={28} className="text-[#007F8E] animate-spin" />
                  ) : (
                    <Upload size={28} className="text-[#007F8E] group-hover:scale-110 transition-transform" />
                  )}
                  <span className="text-sm font-bold text-white/80">
                    {uploadingAvatar ? "Enviando..." : "Enviar Foto"}
                  </span>
                  <span className="text-[10px] text-white/30">Clique para selecionar um arquivo</span>
                </div>
              </button>

              {/* Divider */}
              <div className="flex items-center gap-3 my-6">
                <div className="flex-1 h-px bg-white/10" />
                <span className="text-[10px] text-white/30 uppercase tracking-widest whitespace-nowrap">
                  ou escolha um preset
                </span>
                <div className="flex-1 h-px bg-white/10" />
              </div>

              {/* Presets Grid — scrollable */}
              <div className="flex-1 min-h-0 overflow-y-auto pr-1">
                <div className="grid grid-cols-2 gap-3">
                  {AVATAR_PRESETS.map((preset) => (
                    <button
                      key={preset.id}
                      type="button"
                      onClick={() => handlePresetAvatar(preset.url)}
                      disabled={uploadingAvatar}
                      className="flex items-center gap-3 p-3 rounded-2xl bg-white/5 border border-white/5 hover:border-[#007F8E]/50 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      <img
                        src={`${preset.url}${preset.id}`}
                        alt={preset.name}
                        className="w-10 h-10 rounded-lg bg-zinc-800 flex-shrink-0"
                      />
                      <span className="text-xs font-bold text-white/70">{preset.name}</span>
                    </button>
                  ))}
                </div>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </div>
  );
}

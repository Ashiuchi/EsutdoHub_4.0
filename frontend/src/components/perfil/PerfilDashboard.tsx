"use client";

import type { CSSProperties } from "react";
import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Mail, ShieldCheck, Camera, Check, Loader2 } from "lucide-react";
import { useUser, UserProfile, SignInButton } from "@clerk/nextjs";
import { useTheme } from "next-themes";
import { dark } from "@clerk/themes";
import ThemeBackground from "@/components/ThemeBackground";

// ── Banner presets ────────────────────────────────────────────────────────────

const BANNER_PRESETS = [
  {
    id: "grafite",
    label: "Grafite",
    value: "linear-gradient(to right, #18181b, rgba(0,127,142,0.20))",
  },
  {
    id: "teal-pulse",
    label: "Teal Pulse",
    value: "linear-gradient(135deg, #030712 0%, rgba(0,127,142,0.45) 50%, #030712 100%)",
  },
  {
    id: "industrial",
    label: "Industrial",
    value: "linear-gradient(to bottom right, #0c1820, #007F8E)",
  },
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

// ── Component ─────────────────────────────────────────────────────────────────

export default function PerfilDashboard() {
  const { isLoaded, isSignedIn, user } = useUser();
  const { resolvedTheme } = useTheme();
  const isLight = resolvedTheme === "light";

  const [editingBanner, setEditingBanner] = useState(false);
  const [urlInput, setUrlInput] = useState("");
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  // ── Loading skeleton ──────────────────────────────────────────────────────
  if (!isLoaded) {
    return (
      <div className="min-h-screen bg-[var(--background)] animate-pulse">
        <div className="h-[160px] bg-zinc-900/60" />
        <div className="px-6 md:px-10 -mt-14">
          <div className="w-28 h-28 rounded-full bg-zinc-800 ring-4 ring-zinc-700 ring-offset-4 ring-offset-[var(--background)]" />
          <div className="mt-6 space-y-3">
            <div className="h-7 w-52 bg-zinc-800 rounded-md" />
            <div className="h-4 w-64 bg-zinc-800 rounded-md" />
          </div>
        </div>
      </div>
    );
  }

  // ── Not signed in ─────────────────────────────────────────────────────────
  if (!isSignedIn) {
    return (
      <div className="min-h-screen bg-[var(--background)] flex flex-col items-center justify-center gap-5 text-center px-6">
        <div className="w-20 h-20 rounded-full border flex items-center justify-center"
          style={{ background: "var(--glass-bg)", borderColor: "var(--glass-border-color)" }}>
          <ShieldCheck className="w-9 h-9 text-zinc-600" />
        </div>
        <div>
          <p className="text-[var(--text-offwhite)] text-xl font-semibold">Acesso restrito</p>
          <p className="text-[var(--text-offwhite)]/50 text-sm mt-1">
            Faça login para ver e gerenciar seu perfil.
          </p>
        </div>
        <SignInButton mode="modal">
          <button className="px-6 py-2.5 bg-[#007F8E] hover:bg-[#007F8E]/80 text-white text-sm font-medium rounded-lg transition-colors">
            Entrar
          </button>
        </SignInButton>
      </div>
    );
  }

  // ── Derived values ────────────────────────────────────────────────────────
  const displayName = user.fullName || user.username || "Usuário";
  const email = user.primaryEmailAddress?.emailAddress;
  const bannerUrl = user.unsafeMetadata?.bannerUrl;
  const bannerStyle = resolveBannerStyle(bannerUrl);
  const usingImage = Boolean(bannerUrl && isImageUrl(bannerUrl));

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
  const saveBanner = async (value: string) => {
    setSaving(true);
    setSaveError(null);
    try {
      await user.update({
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

  const handleUrlSave = () => {
    const trimmed = urlInput.trim();
    if (trimmed) saveBanner(trimmed);
  };

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <div className="min-h-screen relative">
      {/* Theme-aware page background */}
      <ThemeBackground />

      {/* All content floats above the background */}
      <div className="relative z-0">

        {/* ── Banner ──────────────────────────────────────────────────── */}
        <div
          className={`h-[160px] relative overflow-hidden${!bannerUrl ? " bg-gradient-to-r from-zinc-900 to-[#007F8E]/20" : ""}`}
          style={bannerStyle}
        >
          {!bannerUrl && (
            <div
              className="absolute inset-0 opacity-[0.07]"
              style={{
                backgroundImage:
                  "linear-gradient(rgba(0,127,142,1) 1px, transparent 1px), linear-gradient(90deg, rgba(0,127,142,1) 1px, transparent 1px)",
                backgroundSize: "40px 40px",
              }}
            />
          )}
          {usingImage && <div className="absolute inset-0 bg-[#030712]/40" />}

          <motion.button
            whileHover={{ scale: 1.04 }}
            whileTap={{ scale: 0.96 }}
            onClick={() => { setEditingBanner((v) => !v); setSaveError(null); }}
            className="absolute bottom-3 right-4 flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium text-zinc-300 bg-black/40 hover:bg-black/60 backdrop-blur-sm border border-white/10 transition-colors"
          >
            <Camera size={13} strokeWidth={1.75} />
            {editingBanner ? "Fechar" : "Editar banner"}
          </motion.button>
        </div>

        {/* ── Avatar — overlaps banner ─────────────────────────────── */}
        <div className="px-6 md:px-10 -mt-14">
          <motion.div
            initial={{ scale: 0.85, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            transition={{ type: "spring", stiffness: 260, damping: 22 }}
            className="relative inline-block"
          >
            <div
              className="rounded-full p-[3px]"
              style={{ background: "linear-gradient(135deg, #007F8E, rgba(0,127,142,0.35))" }}
            >
              <div className="rounded-full p-[3px] bg-[var(--background)]">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={user.imageUrl}
                  alt={displayName}
                  className="w-24 h-24 rounded-full object-cover block"
                />
              </div>
            </div>
            {/* Reactive: useUser() reflects UserProfile photo changes instantly */}
            <span className="absolute bottom-2 right-2 w-4 h-4 rounded-full bg-emerald-500 ring-2 ring-[var(--background)]" />
          </motion.div>
        </div>

        {/* ── Name & email ─────────────────────────────────────────── */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.15, duration: 0.3 }}
          className="px-6 md:px-10 mt-4"
        >
          <h1 className="text-[var(--text-offwhite)] text-2xl font-bold tracking-tight">{displayName}</h1>
          {email && (
            <div className="flex items-center gap-2 mt-1.5">
              <Mail className="w-4 h-4 shrink-0" style={{ color: "var(--primary-teal)" }} />
              <span className="text-sm font-medium" style={{ color: "var(--primary-teal)" }}>{email}</span>
            </div>
          )}
        </motion.div>

        {/* ── Banner editor (below name to preserve -mt-14 avatar) ── */}
        <AnimatePresence>
          {editingBanner && (
            <motion.div
              key="banner-editor"
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
              transition={{ duration: 0.22, ease: "easeInOut" }}
              className="overflow-hidden"
            >
              <div
                className="mx-6 md:mx-10 mt-5 rounded-xl border p-5 space-y-5"
                style={{ background: "var(--glass-bg)", borderColor: "var(--nav-border)" }}
              >
                <div>
                  <p className="text-[10px] font-semibold uppercase tracking-[0.15em] mb-3"
                    style={{ color: "var(--text-offwhite)", opacity: 0.5 }}>
                    Padrões industriais
                  </p>
                  <div className="flex flex-wrap gap-3">
                    {BANNER_PRESETS.map((preset) => (
                      <button
                        key={preset.id}
                        disabled={saving}
                        onClick={() => saveBanner(preset.value)}
                        title={preset.label}
                        className="relative h-14 w-28 rounded-lg overflow-hidden border border-zinc-700 hover:border-[#007F8E] disabled:opacity-50 transition-colors"
                        style={{ background: preset.value }}
                      >
                        {bannerUrl === preset.value && (
                          <span className="absolute inset-0 flex items-center justify-center bg-black/20">
                            <Check size={15} className="text-[#007F8E] drop-shadow" />
                          </span>
                        )}
                        <span className="absolute bottom-1 inset-x-0 text-center text-[9px] text-white/70">
                          {preset.label}
                        </span>
                      </button>
                    ))}
                  </div>
                </div>

                <div>
                  <p className="text-[10px] font-semibold uppercase tracking-[0.15em] mb-2"
                    style={{ color: "var(--text-offwhite)", opacity: 0.5 }}>
                    Imagem personalizada (URL)
                  </p>
                  <div className="flex gap-2">
                    <input
                      type="url"
                      value={urlInput}
                      onChange={(e) => setUrlInput(e.target.value)}
                      onKeyDown={(e) => e.key === "Enter" && handleUrlSave()}
                      placeholder="https://..."
                      disabled={saving}
                      className="flex-1 min-w-0 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-[#007F8E] transition-colors disabled:opacity-50"
                      style={{
                        background: "var(--clerk-input-bg)",
                        border: "1px solid var(--nav-border)",
                        color: "var(--text-offwhite)",
                      }}
                    />
                    <button
                      onClick={handleUrlSave}
                      disabled={saving || !urlInput.trim()}
                      className="px-4 py-2 bg-[#007F8E] hover:bg-[#007F8E]/80 disabled:opacity-40 text-white text-sm font-medium rounded-lg transition-colors flex items-center gap-2 shrink-0"
                    >
                      {saving ? <Loader2 size={14} className="animate-spin" /> : <Check size={14} />}
                      Salvar
                    </button>
                  </div>
                  {saveError && <p className="mt-2 text-xs text-red-400">{saveError}</p>}
                </div>

                {/* LGPD notice */}
                <p className="text-[10px] leading-relaxed" style={{ color: "var(--text-offwhite)", opacity: 0.35 }}>
                  Ao fazer upload, você confirma possuir os direitos de uso da imagem conforme a LGPD.
                </p>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        <div className="mx-6 md:mx-10 mt-8" style={{ borderTop: "1px solid var(--nav-border)" }} />

        {/* ── Segurança e Dados ────────────────────────────────────── */}
        <motion.section
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.25, duration: 0.35 }}
          className="px-6 md:px-10 mt-8 pb-16"
        >
          <div className="flex items-center gap-2.5 mb-6">
            <span className="w-1 h-5 rounded-full bg-[#007F8E]" />
            <h2 className="text-xs font-semibold uppercase tracking-[0.15em]"
              style={{ color: "var(--text-offwhite)", opacity: 0.5 }}>
              Segurança e Dados
            </h2>
          </div>

          {/* Opaque container so Clerk always has a solid background */}
          <div
            className="rounded-xl overflow-hidden"
            style={{ border: "1px solid var(--nav-border)", background: "var(--background)" }}
          >
            <UserProfile
              path="/perfil"
              routing="path"
              appearance={clerkAppearance}
            />
          </div>

          <footer className="mt-12 text-center">
            <p className="text-[10px] font-mono leading-relaxed" style={{ color: "var(--text-offwhite)", opacity: 0.25 }}>
              EstudoHub Pro 4.0 — LGPD Compliance: As imagens e dados de perfil são processados de acordo com a nossa Política de Privacidade.
              <br />
              O usuário é o único responsável pelos direitos autorais das imagens de banner e avatar utilizadas.
            </p>
          </footer>
        </motion.section>

      </div>
    </div>
  );
}

import { Users, TrendingUp } from "lucide-react";
import SocialFeed from "@/components/social/SocialFeed";

const GRUPOS = [
  { name: "Concursos Federais", members: "2,4k membros" },
  { name: "ENEM 2025", members: "5,1k membros" },
  { name: "OAB Preparatório", members: "1,8k membros" },
  { name: "Residência Médica", members: "3,2k membros" },
];

const EDITAIS = [
  { title: "TCU 2025 – Auditor Federal", tag: "Federal", vagas: 40 },
  { title: "TJSP – Escrevente Técnico", tag: "Estadual", vagas: 200 },
  { title: "Correios – Carteiro", tag: "Federal", vagas: 150 },
  { title: "INSS – Perito Médico", tag: "Federal", vagas: 900 },
];

export default function Home() {
  return (
    <div className="relative min-h-screen">
      {/* Fixed background image */}
      <div
        className="fixed inset-0 -z-20 bg-cover bg-center bg-no-repeat"
        style={{ backgroundImage: "url('/static/images/Background06.jpg')" }}
      />
      {/* Hero gradient: dark-to-transparent from the top */}
      <div className="fixed inset-0 -z-10 hero-gradient" />
      {/* Uniform dark veil for readability */}
      <div className="fixed inset-0 -z-10 bg-[#030712]/65" />

      {/* Page layout */}
      <div className="flex gap-6 p-6 max-w-[1100px] mx-auto">
        {/* ── Feed ──────────────────────────────────────────────────── */}
        <div className="flex-1 min-w-0">
          <SocialFeed />
        </div>

        {/* ── Right panel (desktop only) ────────────────────────────── */}
        <aside className="hidden xl:flex flex-col gap-4 w-[272px] shrink-0">
          {/* Sugestões de Grupos */}
          <div className="glass rounded-xl p-4 space-y-4">
            <h2
              className="text-[10px] font-semibold uppercase tracking-widest flex items-center gap-2"
              style={{ color: "var(--text-offwhite)", opacity: 0.5 }}
            >
              <Users size={13} strokeWidth={2} />
              Sugestões de Grupos
            </h2>
            <ul className="space-y-3">
              {GRUPOS.map((g) => (
                <li key={g.name} className="flex items-center justify-between gap-3">
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-[var(--text-offwhite)] leading-tight truncate">
                      {g.name}
                    </p>
                    <p className="text-[10px] text-[var(--text-offwhite)]/40">
                      {g.members}
                    </p>
                  </div>
                  <button className="shrink-0 text-[10px] font-semibold px-2.5 py-1 rounded-md transition-colors bg-[var(--primary-teal)]/20 text-[var(--primary-teal)] hover:bg-[var(--primary-teal)]/40">
                    Entrar
                  </button>
                </li>
              ))}
            </ul>
          </div>

          {/* Editais em Alta */}
          <div className="glass rounded-xl p-4 space-y-4">
            <h2
              className="text-[10px] font-semibold uppercase tracking-widest flex items-center gap-2"
              style={{ color: "var(--text-offwhite)", opacity: 0.5 }}
            >
              <TrendingUp size={13} strokeWidth={2} />
              Editais em Alta
            </h2>
            <ul className="space-y-3">
              {EDITAIS.map((e) => (
                <li key={e.title} className="space-y-1.5">
                  <p className="text-sm font-medium text-[var(--text-offwhite)] leading-tight">
                    {e.title}
                  </p>
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-[var(--primary-teal)]/15 text-[var(--primary-teal)] font-medium">
                      {e.tag}
                    </span>
                    <span className="text-[10px] text-[var(--text-offwhite)]/40">
                      {e.vagas} vagas
                    </span>
                  </div>
                </li>
              ))}
            </ul>
          </div>
        </aside>
      </div>
    </div>
  );
}

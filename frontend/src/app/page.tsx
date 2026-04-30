import { Users } from "lucide-react";
import SocialFeed from "@/components/social/SocialFeed";
import ThemeBackground from "@/components/ThemeBackground";
import TrendingEditais from "@/components/home/TrendingEditais";

const GRUPOS = [
  { name: "Concursos Federais", members: "2,4k membros" },
  { name: "ENEM 2025", members: "5,1k membros" },
  { name: "OAB Preparatório", members: "1,8k membros" },
  { name: "Residência Médica", members: "3,2k membros" },
];

export default function Home() {
  return (
    <div className="relative min-h-screen">
      {/* Theme-aware background: dark → Background01.jpg / light → Background08.jpg */}
      <ThemeBackground />

      {/* Page layout */}
      <div className="flex gap-6 p-6 max-w-[1100px] mx-auto relative z-10">
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

          <TrendingEditais />
        </aside>
      </div>
    </div>
  );
}

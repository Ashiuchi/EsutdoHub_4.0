"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Home, LayoutDashboard, BookOpen, User } from "lucide-react";
import { useState } from "react";

const NAV_ITEMS = [
  { href: "/", label: "Home", icon: Home },
  { href: "/cockpit", label: "Cockpit", icon: LayoutDashboard },
  { href: "/biblioteca", label: "Biblioteca", icon: BookOpen },
  { href: "/perfil", label: "Perfil", icon: User },
];

function Logo() {
  const [imgError, setImgError] = useState(false);

  if (imgError) {
    return (
      <span className="text-[var(--text-offwhite)] font-semibold text-lg tracking-tight">
        EstudoHub <span className="text-[var(--primary-teal)]">Pro</span>
      </span>
    );
  }

  return (
    <div className="flex justify-center w-full">
      <Image
        src="/static/logo_nav.svg"
        alt="EstudoHub Pro"
        width={180}
        height={40}
        priority
        onError={() => setImgError(true)}
      />
    </div>
  );
}

export default function Sidebar() {
  const pathname = usePathname();

  return (
    <>
      {/* ── Desktop sidebar (≥ md) ─────────────────────────────────── */}
      <aside
        className="hidden md:flex fixed inset-y-0 left-0 w-[280px] flex-col z-40 glass"
        style={{ borderRight: "1px solid var(--nav-border)" }}
      >
        {/* Logo */}
        <div
          className="flex items-center px-4 py-8"
          style={{ borderBottom: "1px solid var(--nav-border)" }}
        >
          <Logo />
        </div>

        {/* Navigation */}
        <nav className="flex-1 px-3 py-6 space-y-1 overflow-y-auto">
          {NAV_ITEMS.map(({ href, label, icon: Icon }) => {
            const active =
              pathname === href || (href !== "/" && pathname.startsWith(href));
            return (
              <Link
                key={href}
                href={href}
                className={[
                  "flex items-center gap-3 px-4 py-3 rounded-lg text-sm font-medium transition-colors",
                  active
                    ? "bg-[var(--primary-teal)] text-white"
                    : "text-[var(--text-offwhite)] hover:bg-[var(--nav-hover-bg)]",
                ].join(" ")}
              >
                <Icon size={18} strokeWidth={1.75} />
                {label}
              </Link>
            );
          })}
        </nav>

        {/* Clean Footer */}
        <div className="px-6 py-8">
          <p className="text-[10px] text-[var(--text-offwhite)]/20 uppercase tracking-widest font-bold text-center">
            EstudoHub 4.0 Industrial
          </p>
        </div>
      </aside>

      {/* ── Mobile bottom nav (< md) ───────────────────────────────── */}
      <nav
        className="md:hidden fixed bottom-0 inset-x-0 z-40 glass flex"
        style={{ borderTop: "1px solid var(--nav-border)" }}
      >
        {NAV_ITEMS.map(({ href, label, icon: Icon }) => {
          const active =
            pathname === href || (href !== "/" && pathname.startsWith(href));

          return (
            <Link
              key={href}
              href={href}
              className={[
                "flex flex-1 flex-col items-center justify-center gap-1 py-3 text-[10px] font-medium transition-colors",
                active
                  ? "text-[var(--primary-teal)]"
                  : "text-[var(--text-offwhite)]/60 hover:text-[var(--text-offwhite)]",
              ].join(" ")}
            >
              <Icon size={20} strokeWidth={1.75} />
              {label}
            </Link>
          );
        })}
      </nav>
    </>
  );
}

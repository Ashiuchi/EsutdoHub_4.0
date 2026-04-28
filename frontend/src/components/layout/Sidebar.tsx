"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Home, LayoutDashboard, BookOpen, User, LogIn, LogOut } from "lucide-react";
import { useState } from "react";

const MOCK_USER = {
  name: "Alessandro Morais",
  handle: "amorais",
  avatarUrl:
    "https://ui-avatars.com/api/?name=Alessandro+Morais&background=007F8E&color=fff&size=80",
};

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
    <Image
      src="/static/logo_nav.svg"
      alt="EstudoHub Pro"
      width={160}
      height={40}
      priority
      onError={() => setImgError(true)}
    />
  );
}

export default function Sidebar() {
  const pathname = usePathname();
  const [isLoggedIn, setIsLoggedIn] = useState(false);

  return (
    <>
      {/* ── Desktop sidebar (≥ md) ─────────────────────────────────── */}
      <aside
        className="hidden md:flex fixed inset-y-0 left-0 w-[280px] flex-col z-40 glass"
        style={{ borderRight: "1px solid rgba(224,224,224,0.06)" }}
      >
        {/* Logo */}
        <div
          className="flex items-center px-6 py-5"
          style={{ borderBottom: "1px solid rgba(224,224,224,0.06)" }}
        >
          <Logo />
        </div>

        {/* Navigation */}
        <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
          {NAV_ITEMS.map(({ href, label, icon: Icon }) => {
            const active =
              pathname === href ||
              (href !== "/" && pathname.startsWith(href));
            return (
              <Link
                key={href}
                href={href}
                className={[
                  "flex items-center gap-3 px-4 py-3 rounded-lg text-sm font-medium transition-colors",
                  active
                    ? "bg-[var(--primary-teal)] text-white"
                    : "text-[var(--text-offwhite)] hover:bg-white/[0.06]",
                ].join(" ")}
              >
                <Icon size={18} strokeWidth={1.75} />
                {label}
              </Link>
            );
          })}
        </nav>

        {/* Auth footer */}
        <div
          className="px-3 py-4"
          style={{ borderTop: "1px solid rgba(224,224,224,0.06)" }}
        >
          {isLoggedIn ? (
            <div
              className="flex items-center gap-3 px-3 py-3 rounded-xl"
              style={{
                background: "rgba(0,127,142,0.10)",
                border: "1px solid rgba(0,127,142,0.25)",
              }}
            >
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={MOCK_USER.avatarUrl}
                alt={MOCK_USER.name}
                width={36}
                height={36}
                className="w-9 h-9 rounded-full shrink-0"
                style={{ boxShadow: "0 0 0 2px var(--primary-teal)" }}
              />
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-[var(--text-offwhite)] leading-tight truncate">
                  {MOCK_USER.name}
                </p>
                <p className="text-[10px] font-medium" style={{ color: "var(--primary-teal)" }}>
                  Online
                </p>
              </div>
              <button
                onClick={() => setIsLoggedIn(false)}
                title="Sair"
                className="shrink-0 text-[var(--text-offwhite)]/40 hover:text-red-400 transition-colors"
              >
                <LogOut size={16} strokeWidth={1.75} />
              </button>
            </div>
          ) : (
            <button
              onClick={() => setIsLoggedIn(true)}
              className="flex w-full items-center gap-3 px-4 py-3 rounded-lg text-sm font-medium text-[var(--text-offwhite)] hover:bg-white/[0.06] transition-colors"
            >
              <LogIn size={18} strokeWidth={1.75} />
              Login
            </button>
          )}
        </div>
      </aside>

      {/* ── Mobile bottom nav (< md) ───────────────────────────────── */}
      <nav
        className="md:hidden fixed bottom-0 inset-x-0 z-40 glass flex"
        style={{ borderTop: "1px solid rgba(224,224,224,0.06)" }}
      >
        {NAV_ITEMS.map(({ href, label, icon: Icon }) => {
          const active =
            pathname === href ||
            (href !== "/" && pathname.startsWith(href));
          const isProfileItem = href === "/perfil";

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
              {isProfileItem && isLoggedIn ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={MOCK_USER.avatarUrl}
                  alt={MOCK_USER.name}
                  className="w-5 h-5 rounded-full"
                  style={{ boxShadow: "0 0 0 1.5px var(--primary-teal)" }}
                />
              ) : (
                <Icon size={20} strokeWidth={1.75} />
              )}
              {label}
            </Link>
          );
        })}
      </nav>
    </>
  );
}

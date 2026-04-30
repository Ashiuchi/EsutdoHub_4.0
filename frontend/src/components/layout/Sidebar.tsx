"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Home, LayoutDashboard, BookOpen, User } from "lucide-react";
import { useState } from "react";
import { useUser } from "@clerk/nextjs";

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
      <h1 className="text-[var(--text-offwhite)] font-semibold text-lg tracking-tight px-4">
        EstudoHub Pro <span className="text-[var(--text-offwhite)]/40 font-normal">4.0</span>
        <span className="ml-2 text-[var(--text-offwhite)]/20 font-normal">/ Centro de Estudos</span>
      </h1>
    );
  }

  return (
    <div className="relative p-3 rounded-xl transition-all [html.light_&]:bg-gradient-to-r [html.light_&]:from-zinc-900/90 [html.light_&]:via-zinc-900/40 [html.light_&]:to-transparent">
      <Image
        src="/static/logo_nav.svg"
        alt="EstudoHub Pro"
        width={250}
        height={55}
        priority
        onError={() => setImgError(true)}
      />
    </div>
  );
}

export default function Sidebar() {
  const pathname = usePathname();
  const { isSignedIn, user, isLoaded } = useUser();

  return (
    <>
      {/* ── Desktop sidebar (≥ md) ─────────────────────────────────── */}
      <aside
        className="hidden md:flex fixed inset-y-0 left-0 w-[280px] flex-col z-40 glass border-none shadow-2xl shadow-black/20"
      >
        {/* Logo */}
        <div
          className="flex items-center px-2 py-5"
        >
          <Logo />
        </div>

        {/* Navigation */}
        <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
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
      </aside>

      {/* ── Mobile bottom nav (< md) ───────────────────────────────── */}
      <nav
        className="md:hidden fixed bottom-0 inset-x-0 z-40 glass flex shadow-[0_-8px_30px_rgb(0,0,0,0.12)] border-none"
      >
        {NAV_ITEMS.map(({ href, label, icon: Icon }) => {
          const active =
            pathname === href || (href !== "/" && pathname.startsWith(href));
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
              {isProfileItem && isLoaded && isSignedIn && user.imageUrl ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={user.imageUrl}
                  alt={user.fullName ?? "Perfil"}
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

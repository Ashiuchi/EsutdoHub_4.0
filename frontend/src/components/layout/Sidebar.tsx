"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Home, LayoutDashboard, BookOpen, User, LogIn, LogOut, Sun, Moon } from "lucide-react";
import { useState, useEffect } from "react";
import { useUser, useClerk, SignInButton } from "@clerk/nextjs";
import { useTheme } from "next-themes";
import { motion } from "framer-motion";

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
      width={250}
      height={55}
      priority
      onError={() => setImgError(true)}
    />
  );
}

function ThemeToggle() {
  const { resolvedTheme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  useEffect(() => setMounted(true), []);

  // Before mount, assume dark to match server render
  const isLight = mounted && resolvedTheme === "light";

  return (
    <motion.button
      whileHover={{ scale: 1.02 }}
      whileTap={{ scale: 0.97 }}
      onClick={() => setTheme(isLight ? "dark" : "light")}
      className="flex w-full items-center gap-3 px-4 py-3 rounded-lg text-sm font-medium transition-colors"
      style={{ color: "var(--text-offwhite)", opacity: 0.8 }}
      onMouseEnter={(e) => (e.currentTarget.style.opacity = "1")}
      onMouseLeave={(e) => (e.currentTarget.style.opacity = "0.8")}
    >
      <span
        className="transition-colors"
        style={{ color: "var(--primary-teal)" }}
      >
        {isLight ? <Moon size={18} strokeWidth={1.75} /> : <Sun size={18} strokeWidth={1.75} />}
      </span>
      {isLight ? "Modo Escuro" : "Modo Claro"}
    </motion.button>
  );
}

function AuthFooter() {
  const { isSignedIn, user, isLoaded } = useUser();
  const { signOut } = useClerk();

  if (!isLoaded) {
    return (
      <div
        className="h-[60px] rounded-xl animate-pulse"
        style={{ background: "rgba(255,255,255,0.04)" }}
      />
    );
  }

  if (isSignedIn) {
    return (
      <motion.div
        initial={{ opacity: 0, y: 6 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.25 }}
        className="flex items-center gap-3 px-3 py-3 rounded-xl"
        style={{
          background: "rgba(0,127,142,0.10)",
          border: "1px solid rgba(0,127,142,0.25)",
        }}
      >
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={user.imageUrl}
          alt={user.fullName ?? "Perfil"}
          width={36}
          height={36}
          className="w-9 h-9 rounded-full shrink-0"
          style={{ boxShadow: "0 0 0 2px var(--primary-teal)" }}
        />
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium leading-tight truncate" style={{ color: "var(--text-offwhite)" }}>
            {user.firstName ?? user.username ?? "Usuário"}
          </p>
          <p className="text-[10px] font-medium" style={{ color: "var(--primary-teal)" }}>
            Online
          </p>
        </div>
        <motion.button
          whileHover={{ scale: 1.15 }}
          whileTap={{ scale: 0.9 }}
          onClick={() => signOut()}
          title="Sair"
          className="shrink-0 transition-colors"
          style={{ color: "var(--text-offwhite)", opacity: 0.4 }}
          onMouseEnter={(e) => {
            e.currentTarget.style.color = "#f87171";
            e.currentTarget.style.opacity = "1";
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.color = "var(--text-offwhite)";
            e.currentTarget.style.opacity = "0.4";
          }}
        >
          <LogOut size={16} strokeWidth={1.75} />
        </motion.button>
      </motion.div>
    );
  }

  return (
    <SignInButton mode="modal">
      <motion.button
        whileHover={{
          scale: 1.02,
          boxShadow: "0 0 18px rgba(0,127,142,0.30)",
        }}
        whileTap={{ scale: 0.97 }}
        transition={{ type: "spring", stiffness: 320, damping: 22 }}
        className="flex w-full items-center gap-3 px-4 py-3 rounded-lg text-sm font-medium transition-colors"
        style={{
          color: "var(--text-offwhite)",
          border: "1px solid rgba(0,127,142,0.25)",
        }}
      >
        <motion.span
          whileHover={{ x: 3 }}
          transition={{ type: "spring", stiffness: 400, damping: 20 }}
        >
          <LogIn size={18} strokeWidth={1.75} />
        </motion.span>
        Entrar
      </motion.button>
    </SignInButton>
  );
}

export default function Sidebar() {
  const pathname = usePathname();
  const { isSignedIn, user, isLoaded } = useUser();

  return (
    <>
      {/* ── Desktop sidebar (≥ md) ─────────────────────────────────── */}
      <aside
        className="hidden md:flex fixed inset-y-0 left-0 w-[280px] flex-col z-40 glass"
        style={{ borderRight: "1px solid var(--nav-border)" }}
      >
        {/* Logo */}
        <div
          className="flex items-center px-2 py-5"
          style={{ borderBottom: "1px solid var(--nav-border)" }}
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

        {/* Theme toggle */}
        <div
          className="px-3 pb-1"
          style={{ borderTop: "1px solid var(--nav-border)" }}
        >
          <ThemeToggle />
        </div>

        {/* Auth footer */}
        <div className="px-3 pb-4">
          <AuthFooter />
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

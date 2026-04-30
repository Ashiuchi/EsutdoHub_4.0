"use client";

import { Sun, Moon, LogIn, LogOut } from "lucide-react";
import { useState, useEffect } from "react";
import { useUser, useClerk, SignInButton } from "@clerk/nextjs";
import { useTheme } from "next-themes";
import { motion } from "framer-motion";

function ThemeToggle() {
  const { resolvedTheme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  useEffect(() => setMounted(true), []);

  const isLight = mounted && resolvedTheme === "light";

  return (
    <motion.button
      whileHover={{ scale: 1.08 }}
      whileTap={{ scale: 0.92 }}
      onClick={() => setTheme(isLight ? "dark" : "light")}
      title={isLight ? "Modo Escuro" : "Modo Claro"}
      className="flex items-center justify-center w-9 h-9 rounded-lg transition-colors"
      style={{
        color: "var(--primary-teal)",
        background: "rgba(0,127,142,0.08)",
        border: "1px solid rgba(0,127,142,0.18)",
      }}
    >
      {isLight ? <Moon size={17} strokeWidth={1.75} /> : <Sun size={17} strokeWidth={1.75} />}
    </motion.button>
  );
}

function AuthSection() {
  const { isSignedIn, user, isLoaded } = useUser();
  const { signOut } = useClerk();

  if (!isLoaded) {
    return (
      <div
        className="w-9 h-9 rounded-full animate-pulse"
        style={{ background: "rgba(255,255,255,0.06)" }}
      />
    );
  }

  if (isSignedIn) {
    return (
      <motion.div
        initial={{ opacity: 0, x: 8 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ duration: 0.2 }}
        className="flex items-center gap-2"
      >
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={user.imageUrl}
          alt={user.fullName ?? "Perfil"}
          className="w-8 h-8 rounded-full shrink-0"
          style={{ boxShadow: "0 0 0 2px var(--primary-teal)" }}
        />
        <span
          className="hidden lg:block text-sm font-medium truncate max-w-[120px]"
          style={{ color: "var(--text-offwhite)" }}
        >
          {user.firstName ?? user.username ?? "Usuário"}
        </span>
        <motion.button
          whileHover={{ scale: 1.12 }}
          whileTap={{ scale: 0.9 }}
          onClick={() => signOut()}
          title="Sair"
          className="flex items-center justify-center w-8 h-8 rounded-lg transition-colors"
          style={{ color: "var(--text-offwhite)", opacity: 0.45 }}
          onMouseEnter={(e) => {
            e.currentTarget.style.color = "#f87171";
            e.currentTarget.style.opacity = "1";
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.color = "var(--text-offwhite)";
            e.currentTarget.style.opacity = "0.45";
          }}
        >
          <LogOut size={15} strokeWidth={1.75} />
        </motion.button>
      </motion.div>
    );
  }

  return (
    <SignInButton mode="modal">
      <motion.button
        whileHover={{ scale: 1.03, boxShadow: "0 0 14px rgba(0,127,142,0.28)" }}
        whileTap={{ scale: 0.97 }}
        transition={{ type: "spring", stiffness: 320, damping: 22 }}
        className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium"
        style={{
          color: "var(--text-offwhite)",
          border: "1px solid rgba(0,127,142,0.25)",
        }}
      >
        <LogIn size={16} strokeWidth={1.75} />
        <span className="hidden sm:inline">Entrar</span>
      </motion.button>
    </SignInButton>
  );
}

export default function TopNavbar() {
  return (
    <header
      className="fixed top-0 right-0 left-0 md:left-[280px] h-16 z-50 glass border-none flex items-center justify-end px-4 gap-3 shadow-sm"
    >
      <ThemeToggle />
      <AuthSection />
    </header>
  );
}

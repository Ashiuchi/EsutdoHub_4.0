"use client";

import { Sun, Moon, LogOut, User as UserIcon } from "lucide-react";
import { useState, useEffect } from "react";
import { useUser, useClerk, SignInButton, UserButton } from "@clerk/nextjs";
import { useTheme } from "next-themes";
import { motion } from "framer-motion";

function ThemeToggle() {
  const { resolvedTheme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  useEffect(() => setMounted(true), []);

  const isLight = mounted && resolvedTheme === "light";

  return (
    <motion.button
      whileHover={{ scale: 1.05 }}
      whileTap={{ scale: 0.95 }}
      onClick={() => setTheme(isLight ? "dark" : "light")}
      className="flex items-center justify-center w-8 h-8 rounded-full transition-all"
      style={{
        color: "var(--primary-teal)",
        background: "var(--nav-hover-bg)",
        border: "1px solid var(--nav-border)",
      }}
    >
      {isLight ? <Moon size={14} strokeWidth={2} /> : <Sun size={14} strokeWidth={2} />}
    </motion.button>
  );
}

function AuthSection() {
  const { isSignedIn, isLoaded } = useUser();

  if (!isLoaded) return <div className="w-8 h-8 rounded-full bg-white/5 animate-pulse" />;

  if (isSignedIn) {
    return (
      <div className="flex items-center gap-2">
        <UserButton 
          afterSignOutUrl="/"
          appearance={{
            elements: {
              userButtonAvatarBox: "w-8 h-8 border border-[var(--primary-teal)]/30",
              userButtonTrigger: "focus:shadow-none focus:outline-none"
            }
          }}
        />
      </div>
    );
  }

  return (
    <SignInButton mode="modal">
      <button className="text-xs font-semibold px-4 py-1.5 rounded-full bg-[var(--primary-teal)] text-white hover:brightness-110 transition-all">
        Entrar
      </button>
    </SignInButton>
  );
}

export default function TopNavbar() {
  return (
    <header
      className="fixed top-0 right-0 left-0 md:left-[280px] h-14 z-50 flex items-center justify-end px-6 gap-4"
    >
      <div className="flex items-center gap-4 py-2 px-4 rounded-full glass border-seamless-b">
        <ThemeToggle />
        <div className="w-[1px] h-4 bg-[var(--nav-border)]" />
        <AuthSection />
      </div>
    </header>
  );
}

"use client";

import { useTheme } from "next-themes";
import { useState, useEffect } from "react";

/**
 * Fixed full-page background that swaps image based on active theme.
 * dark  → Background01.jpg
 * light → Background08.jpg
 */
export default function ThemeBackground() {
  const { resolvedTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  useEffect(() => setMounted(true), []);

  const isLight = mounted && resolvedTheme === "light";

  return (
    <>
      {/* Background image layer */}
      <div
        suppressHydrationWarning
        className="fixed inset-0 -z-20 bg-cover bg-center bg-no-repeat transition-opacity duration-700"
        style={{
          opacity: mounted ? 1 : 0,
          backgroundImage: mounted
            ? `url('/static/images/${isLight ? "Background08" : "Background01"}.jpg')`
            : undefined,
        }}
      />
      {/* Gradient veil — auto-tinted via CSS variable */}
      <div className="fixed inset-0 -z-10 hero-gradient" />
      {/* Uniform dark/light veil for readability */}
      <div
        suppressHydrationWarning
        className="fixed inset-0 -z-10"
        style={{
          background: mounted
            ? (isLight ? "rgba(248,250,252,0.72)" : "rgba(3,7,18,0.65)")
            : undefined,
        }}
      />
    </>
  );
}

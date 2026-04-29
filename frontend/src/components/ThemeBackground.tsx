"use client";

import { useTheme } from "next-themes";

/**
 * Fixed full-page background that swaps image based on active theme.
 * dark  → Background01.jpg
 * light → Background08.jpg
 *
 * Render this as the first child of any page wrapper that needs the
 * themed background. The page content must sit on top (z-index ≥ 0).
 */
export default function ThemeBackground() {
  const { resolvedTheme } = useTheme();
  const isLight = resolvedTheme === "light";

  return (
    <>
      {/* Background image layer */}
      <div
        className="fixed inset-0 -z-20 bg-cover bg-center bg-no-repeat"
        style={{
          backgroundImage: `url('/static/images/${isLight ? "Background08" : "Background01"}.jpg')`,
        }}
      />
      {/* Gradient veil — auto-tinted via CSS variable */}
      <div className="fixed inset-0 -z-10 hero-gradient" />
      {/* Uniform dark/light veil for readability */}
      <div
        className="fixed inset-0 -z-10"
        style={{
          background: isLight ? "rgba(248,250,252,0.72)" : "rgba(3,7,18,0.65)",
        }}
      />
    </>
  );
}

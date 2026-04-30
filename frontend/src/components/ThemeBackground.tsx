"use client";

import { useTheme } from "next-themes";
import { useState, useEffect } from "react";

export default function ThemeBackground() {
  const { resolvedTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  useEffect(() => setMounted(true), []);

  // Render placeholder divs on server/before-mount to avoid hydration mismatch.
  // suppressHydrationWarning lets React silently patch style differences on mount.
  const isLight = mounted && resolvedTheme === "light";

  return (
    <>
      <div
        suppressHydrationWarning
        style={{
          position: "fixed",
          inset: 0,
          zIndex: -1,
          backgroundImage: mounted
            ? `url('/static/images/${isLight ? "Background08" : "Background01"}.jpg')`
            : undefined,
          backgroundSize: "cover",
          backgroundPosition: "center",
          backgroundRepeat: "no-repeat",
        }}
      />
      <div
        suppressHydrationWarning
        style={{
          position: "fixed",
          inset: 0,
          zIndex: -1,
          background: mounted
            ? isLight ? "rgba(248,250,252,0.40)" : "rgba(3,7,18,0.30)"
            : undefined,
        }}
      />
    </>
  );
}

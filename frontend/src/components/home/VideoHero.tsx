"use client";

import { motion } from "framer-motion";

export default function VideoHero() {
  return (
    <div className="mb-12 group mx-auto max-w-[800px]">
      <motion.div 
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="relative aspect-video rounded-2xl overflow-hidden border-2 border-[var(--primary-teal)]/30 shadow-[0_0_50px_-12px_rgba(0,127,142,0.3)] group-hover:shadow-[0_0_60px_-12px_rgba(0,127,142,0.5)] transition-all duration-500"
      >
        {/* Shiny Frame Effect */}
        <div className="absolute inset-0 pointer-events-none z-10 border border-white/10 rounded-2xl" />
        <div className="absolute -inset-[100%] group-hover:inset-0 bg-gradient-to-tr from-transparent via-white/5 to-transparent transition-all duration-1000 pointer-events-none z-10" />
        
        {/* Youtube Iframe */}
        <iframe
          width="100%"
          height="100%"
          src="https://www.youtube.com/embed/-Be0qYh0WNI?autoplay=0&controls=1&rel=0"
          title="EstudoHub Pro 4.0 - DNA Industrial"
          frameBorder="0"
          allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
          allowFullScreen
          className="relative z-0"
        />

        {/* Industrial scanline overlay for that tech look */}
        <div className="absolute inset-0 pointer-events-none z-10 terminal-scanline opacity-30" />
      </motion.div>
      
      <div className="mt-4 flex items-center justify-center text-center">
        <div>
          <h2 className="text-lg font-bold text-[var(--text-offwhite)] flex items-center gap-2 justify-center">
            <span className="w-2 h-2 rounded-full bg-[var(--primary-teal)] animate-pulse" />
            DNA Industrial: O Arquiteto de Editais
          </h2>
          <p className="text-xs text-[var(--text-offwhite)]/40 uppercase tracking-widest font-medium">
            Tecnologia & Inovação para sua Aprovação
          </p>
        </div>
      </div>
    </div>
  );
}

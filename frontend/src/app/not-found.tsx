"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import Image from "next/image";

export default function NotFound() {
  return (
    <div className="min-h-screen bg-[var(--background)] flex flex-col items-center justify-center p-6 text-center">
      <motion.div
        initial={{ opacity: 0, scale: 0.9 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
        className="max-w-md w-full space-y-8"
      >
        {/* Logo Section */}
        <div className="flex justify-center mb-12">
           <Image
             src="/static/logo_nav.svg"
             alt="EstudoHub Pro"
             width={280}
             height={60}
             priority
           />
        </div>

        {/* 404 Visual */}
        <div className="relative">
          <h1 className="text-[120px] font-bold text-[var(--text-offwhite)]/5 leading-none select-none">
            404
          </h1>
          <div className="absolute inset-0 flex items-center justify-center">
            <motion.div 
              animate={{ 
                rotate: [0, 5, -5, 0],
                y: [0, -5, 0]
              }}
              transition={{ duration: 4, repeat: Infinity, ease: "easeInOut" }}
              className="text-[var(--primary-teal)] text-xl font-mono tracking-widest terminal-glow"
            >
              NAV_ERROR: LOST_IN_SPACE
            </motion.div>
          </div>
        </div>

        {/* Text Content */}
        <div className="space-y-3">
          <h2 className="text-2xl font-semibold text-[var(--text-offwhite)]">
            Módulo Não Encontrado
          </h2>
          <p className="text-[var(--text-offwhite)]/40 text-sm max-w-xs mx-auto leading-relaxed">
            As coordenadas solicitadas não correspondem a nenhum setor ativo do EstudoHub Pro 4.0.
          </p>
        </div>

        {/* Action Button */}
        <div className="pt-8">
          <Link href="/">
            <motion.button
              whileHover={{ scale: 1.05, boxShadow: "0 0 20px rgba(0,127,142,0.2)" }}
              whileTap={{ scale: 0.95 }}
              className="px-8 py-3 bg-[var(--primary-teal)] text-white rounded-full font-medium transition-all hover:bg-[var(--primary-teal)]/90 flex items-center gap-2 mx-auto"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
              </svg>
              Retornar à Base
            </motion.button>
          </Link>
        </div>
      </motion.div>

      {/* Background Decor */}
      <div className="fixed inset-0 pointer-events-none overflow-hidden z-[-1] opacity-20">
        <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-[var(--primary-teal)]/10 rounded-full blur-[120px]" />
        <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-blue-500/5 rounded-full blur-[120px]" />
      </div>
    </div>
  );
}

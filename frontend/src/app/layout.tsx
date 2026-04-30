import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import Sidebar from "@/components/layout/Sidebar";
import TopNavbar from "@/components/layout/TopNavbar";
import ThemeProvider from "@/components/providers/ThemeProvider";
import ThemeBackground from "@/components/ThemeBackground";
import { ClerkProvider } from "@clerk/nextjs";
import { ptBR } from "@clerk/localizations";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "EstudoHub Pro",
  description: "Plataforma inteligente de editais",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <ClerkProvider localization={ptBR}>
      <html
        lang="pt-BR"
        className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
        suppressHydrationWarning={true}
      >
        <body className="min-h-full text-[var(--text-offwhite)]" suppressHydrationWarning={true}>
          <ThemeProvider>
            <ThemeBackground />
            <Sidebar />
            <TopNavbar />
            {/* pb-16 reserves space for the mobile bottom nav; removed on md+ */}
            <main className="md:ml-[280px] pt-16 min-h-screen pb-16 md:pb-0 bg-transparent">
              {children}
            </main>
          </ThemeProvider>
        </body>
      </html>
    </ClerkProvider>
  );
}

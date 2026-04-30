import type { Metadata } from "next";
import PerfilDashboard from "@/components/perfil/PerfilDashboard";

export const metadata: Metadata = {
  title: "Perfil — EstudoHub Pro 4.0",
  description: "Gerencie seu perfil e configurações de segurança",
};

export default function PerfilPage() {
  return <PerfilDashboard />;
}

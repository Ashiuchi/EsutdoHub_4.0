/** 
 * Cockpit — EstudoHub Pro 4.0
 * Resilient Route for real-time edital extraction dashboard
 */
// DNA 26 Stabilized
import type { Metadata } from "next";
import CockpitDashboard from "@/components/cockpit/CockpitDashboard";

export const metadata: Metadata = {
  title: "Cockpit — EstudoHub Pro 4.0",
  description: "Real-time edital extraction dashboard",
};

export default function CockpitPage() {
  return <CockpitDashboard />;
}

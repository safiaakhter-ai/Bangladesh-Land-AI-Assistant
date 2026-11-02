import "./globals.css";
import "leaflet/dist/leaflet.css";

export const metadata = {
  title: "ভূমি সহায় | Bangladesh Land AI Assistant",
  description: "Bangladesh land-record research workspace: khatian lookup, Bengali knowledge assistant, and digital mouza map.",
  applicationName: "Bangladesh Land AI Assistant",
};

export const viewport = { width: "device-width", initialScale: 1 };

export default function RootLayout({ children }) {
  return (
    <html lang="bn" className="h-full dark">
      <body className="min-h-full h-full bg-slate-950 text-slate-100 font-sans selection:bg-emerald-500/30">
        {children}
      </body>
    </html>
  );
}

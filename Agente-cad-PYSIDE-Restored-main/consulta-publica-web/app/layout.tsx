import type { Metadata, Viewport } from "next";
import { ThemeProvider } from "@/lib/theme/ThemeProvider";
import { RegisterServiceWorker } from "@/lib/pwa/registerServiceWorker";
import "./globals.css";

// Dado é privado-por-código — nunca indexável (AC1). Redundante com o
// header X-Robots-Tag (next.config.js + middleware.ts) de propósito: meta
// tag cobre crawlers que ignoram headers HTTP, header cobre os que ignoram
// HTML.
export const metadata: Metadata = {
  title: "Consulta de Fôrma",
  description: "Consulta pública de especificação de itens de fôrma por código.",
  robots: { index: false, follow: false },
  manifest: "/manifest.json",
  icons: {
    icon: "/icons/icon.svg",
    apple: "/icons/icon.svg",
  },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#0b4da2",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pt-BR">
      <body>
        <ThemeProvider>{children}</ThemeProvider>
        <RegisterServiceWorker />
      </body>
    </html>
  );
}

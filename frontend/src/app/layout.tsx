import type { Metadata, Viewport } from "next";
import { EB_Garamond, DM_Sans } from "next/font/google";
import "./globals.css";
import { AppShell } from "@/components/AppShell";

const garamond = EB_Garamond({
  subsets: ["latin"],
  variable: "--font-eb-garamond",
});
const dmSans = DM_Sans({
  subsets: ["latin"],
  variable: "--font-dm-sans",
});

export const metadata: Metadata = {
  title: "BROT — La Panadería",
  description: "Sistema de gestión del obrador",
  manifest: "/manifest.json",
  appleWebApp: { capable: true, statusBarStyle: "black-translucent" },
};

export const viewport: Viewport = {
  themeColor: "#004225",
  viewportFit: "cover",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="es" className={`${garamond.variable} ${dmSans.variable}`}>
      <body className="antialiased">
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
